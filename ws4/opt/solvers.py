"""Metaheuristic solvers over the operator registry.

Each solver takes a :class:`~ws4.opt.core.Problem`, a random source, and a budget, and
returns the best schedule it found and its objective. All solvers are seeded and
reproducible, and each reports its objective trajectory through an optional ``on_step``
callback.
"""

from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Callable

from .core import Problem
from .incremental import IncrementalObjective
from .operators import Candidates, Chain, OperatorRegistry, Schedule

StepCallback = Callable[[int, float], None]


def _changed_blocks(before: Schedule, after: Schedule) -> list[int]:
    """Return the blocks whose assignment differs between two schedules."""
    changed = [block for block, value in after.items() if before.get(block) != value]
    changed.extend(block for block in before if block not in after)
    return changed


def _signature(before: Schedule, after: Schedule) -> frozenset[tuple[int, Chain | None]]:
    """Return the set of blocks a move changed, with their new assignment."""
    blocks = set(before) | set(after)
    return frozenset(
        (block, after.get(block)) for block in blocks if before.get(block) != after.get(block)
    )


def _report(on_step: StepCallback | None, iteration: int, objective: float) -> None:
    """Report an iteration's objective when a callback is given."""
    if on_step is not None:
        on_step(iteration, objective)


def solve_sa(
    problem: Problem,
    rng: random.Random,
    *,
    iterations: int,
    temperature: float,
    cooling: float,
    on_step: StepCallback | None = None,
    initial: Schedule | None = None,
) -> tuple[Schedule, float]:
    """Run simulated annealing.

    Parameters
    ----------
    problem : Problem
        The problem adapter.
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    temperature : float
        The initial temperature.
    cooling : float
        The geometric cooling factor.
    on_step : callable or None, optional
        Called with ``(iteration, best_objective)`` each iteration.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current: Schedule = dict(initial) if initial is not None else {}
    current_obj = problem.evaluate(current)
    best, best_obj = dict(current), current_obj
    temp = temperature
    for iteration in range(iterations):
        move = problem.registry.pick(rng).apply(current, rng, problem.candidates)
        if move is not None:
            move_obj = problem.evaluate(move)
            if move_obj <= current_obj or rng.random() < math.exp(
                (current_obj - move_obj) / max(temp, 1e-9)
            ):
                current, current_obj = move, move_obj
                if move_obj < best_obj:
                    best, best_obj = dict(move), move_obj
        temp *= cooling
        _report(on_step, iteration, best_obj)
    return best, best_obj


def solve_sa_delta(
    evaluator: IncrementalObjective,
    rng: random.Random,
    *,
    iterations: int,
    temperature: float,
    cooling: float,
    candidates: Candidates,
    registry: OperatorRegistry,
    initial: Schedule | None = None,
    on_step: StepCallback | None = None,
) -> tuple[Schedule, float]:
    """Run simulated annealing priced by per-move objective deltas.

    The acceptance rule is identical to :func:`solve_sa`, but the objective is updated by
    the move's exact delta instead of recomputing the whole schedule, so a move costs
    O(cells the block touches) rather than O(schedule).

    Parameters
    ----------
    evaluator : IncrementalObjective
        The move-based evaluator (it also holds the running state).
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    temperature : float
        The initial temperature.
    cooling : float
        The geometric cooling factor.
    candidates : dict of int to list of tuple of (str, int)
        The per-block options.
    registry : OperatorRegistry
        The move operators.
    initial : dict or None, optional
        A starting schedule.
    on_step : callable or None, optional
        Called with ``(iteration, best_objective)`` each iteration.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current: Schedule = dict(initial) if initial is not None else {}
    evaluator.reset(current)
    current_obj = evaluator.objective
    best, best_obj = dict(current), current_obj
    temp = temperature
    for iteration in range(iterations):
        proposal = registry.pick(rng).propose(current, rng, candidates)
        if proposal is not None:
            move, changed = proposal
            move_obj = current_obj + evaluator.delta(changed, move)
            if move_obj <= current_obj or rng.random() < math.exp(
                (current_obj - move_obj) / max(temp, 1e-9)
            ):
                evaluator.apply(changed, move)
                current, current_obj = move, move_obj
                if move_obj < best_obj:
                    best, best_obj = dict(move), move_obj
        temp *= cooling
        _report(on_step, iteration, best_obj)
    return best, best_obj


def solve_tabu(
    problem: Problem,
    rng: random.Random,
    *,
    iterations: int,
    tenure: int,
    samples: int = 8,
    on_step: StepCallback | None = None,
    initial: Schedule | None = None,
) -> tuple[Schedule, float]:
    """Run tabu search: pick the best non-tabu move each iteration.

    Parameters
    ----------
    problem : Problem
        The problem adapter.
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    tenure : int
        The tabu list length.
    samples : int
        The number of candidate moves sampled per iteration.
    on_step : callable or None, optional
        Called with ``(iteration, best_objective)`` each iteration.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current: Schedule = dict(initial) if initial is not None else {}
    current_obj = problem.evaluate(current)
    best, best_obj = dict(current), current_obj
    tabu: deque[frozenset[tuple[int, Chain | None]]] = deque(maxlen=tenure)
    for iteration in range(iterations):
        chosen: Schedule | None = None
        chosen_obj = math.inf
        for _ in range(samples):
            move = problem.registry.pick(rng).apply(current, rng, problem.candidates)
            if move is None:
                continue
            signature = _signature(current, move)
            move_obj = problem.evaluate(move)
            if signature in tabu and move_obj >= best_obj:
                continue
            if move_obj < chosen_obj:
                chosen, chosen_obj = move, move_obj
        if chosen is not None:
            tabu.append(_signature(current, chosen))
            current, current_obj = chosen, chosen_obj
            if current_obj < best_obj:
                best, best_obj = dict(current), current_obj
        _report(on_step, iteration, best_obj)
    return best, best_obj


def solve_ils(
    problem: Problem,
    rng: random.Random,
    *,
    iterations: int,
    perturbation: int,
    on_step: StepCallback | None = None,
    initial: Schedule | None = None,
) -> tuple[Schedule, float]:
    """Run iterated local search: perturb, then accept an improvement.

    Parameters
    ----------
    problem : Problem
        The problem adapter.
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    perturbation : int
        The number of random moves applied to perturb the incumbent.
    on_step : callable or None, optional
        Called with ``(iteration, best_objective)`` each iteration.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current: Schedule = dict(initial) if initial is not None else {}
    current_obj = problem.evaluate(current)
    best, best_obj = dict(current), current_obj
    for iteration in range(iterations):
        candidate = dict(current)
        for _ in range(perturbation):
            move = problem.registry.pick(rng).apply(candidate, rng, problem.candidates)
            if move is not None:
                candidate = move
        candidate_obj = problem.evaluate(candidate)
        if candidate_obj < current_obj:
            current, current_obj = candidate, candidate_obj
            if candidate_obj < best_obj:
                best, best_obj = dict(candidate), candidate_obj
        _report(on_step, iteration, best_obj)
    return best, best_obj
