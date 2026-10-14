"""Metaheuristic solvers over the operator registry.

Each solver takes an initial schedule, an objective evaluator, the operator registry,
and the candidate moves, and returns the best schedule it found and its objective.
All solvers are seeded and reproducible.
"""

from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Callable

from .operators import Candidates, OperatorRegistry, Schedule

Evaluate = Callable[[Schedule], float]


def _signature(before: Schedule, after: Schedule) -> frozenset[tuple[int, tuple[str, int] | None]]:
    """Return the set of blocks a move changed, with their new assignment."""
    blocks = set(before) | set(after)
    return frozenset(
        (block, after.get(block)) for block in blocks if before.get(block) != after.get(block)
    )


def solve_sa(
    initial: Schedule,
    evaluate: Evaluate,
    registry: OperatorRegistry,
    candidates: Candidates,
    rng: random.Random,
    *,
    iterations: int,
    temperature: float,
    cooling: float,
) -> tuple[Schedule, float]:
    """Run simulated annealing.

    Parameters
    ----------
    initial : Schedule
        The starting schedule.
    evaluate : callable
        The objective evaluator (lower is better).
    registry : OperatorRegistry
        The neighbourhood operators.
    candidates : Candidates
        The candidate moves per block.
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    temperature : float
        The initial temperature.
    cooling : float
        The geometric cooling factor.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current = dict(initial)
    current_obj = evaluate(current)
    best, best_obj = dict(current), current_obj
    temp = temperature
    for _ in range(iterations):
        move = registry.pick(rng).apply(current, rng, candidates)
        if move is None:
            continue
        move_obj = evaluate(move)
        if move_obj <= current_obj or rng.random() < math.exp(
            (current_obj - move_obj) / max(temp, 1e-9)
        ):
            current, current_obj = move, move_obj
            if move_obj < best_obj:
                best, best_obj = dict(move), move_obj
        temp *= cooling
    return best, best_obj


def solve_tabu(
    initial: Schedule,
    evaluate: Evaluate,
    registry: OperatorRegistry,
    candidates: Candidates,
    rng: random.Random,
    *,
    iterations: int,
    tenure: int,
    samples: int = 8,
) -> tuple[Schedule, float]:
    """Run tabu search: pick the best non-tabu move each iteration.

    Parameters
    ----------
    initial : Schedule
        The starting schedule.
    evaluate : callable
        The objective evaluator.
    registry : OperatorRegistry
        The neighbourhood operators.
    candidates : Candidates
        The candidate moves per block.
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    tenure : int
        The tabu list length.
    samples : int
        The number of candidate moves sampled per iteration.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current = dict(initial)
    current_obj = evaluate(current)
    best, best_obj = dict(current), current_obj
    tabu: deque[frozenset[tuple[int, tuple[str, int] | None]]] = deque(maxlen=tenure)
    for _ in range(iterations):
        chosen: Schedule | None = None
        chosen_obj = math.inf
        for _ in range(samples):
            move = registry.pick(rng).apply(current, rng, candidates)
            if move is None:
                continue
            signature = _signature(current, move)
            move_obj = evaluate(move)
            if signature in tabu and move_obj >= best_obj:
                continue
            if move_obj < chosen_obj:
                chosen, chosen_obj = move, move_obj
        if chosen is None:
            continue
        tabu.append(_signature(current, chosen))
        current, current_obj = chosen, chosen_obj
        if current_obj < best_obj:
            best, best_obj = dict(current), current_obj
    return best, best_obj


def solve_ils(
    initial: Schedule,
    evaluate: Evaluate,
    registry: OperatorRegistry,
    candidates: Candidates,
    rng: random.Random,
    *,
    iterations: int,
    perturbation: int,
) -> tuple[Schedule, float]:
    """Run iterated local search: perturb, then accept an improvement.

    Parameters
    ----------
    initial : Schedule
        The starting schedule.
    evaluate : callable
        The objective evaluator.
    registry : OperatorRegistry
        The neighbourhood operators.
    candidates : Candidates
        The candidate moves per block.
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    perturbation : int
        The number of random moves applied to perturb the incumbent.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current = dict(initial)
    current_obj = evaluate(current)
    best, best_obj = dict(current), current_obj
    for _ in range(iterations):
        candidate = dict(current)
        for _ in range(perturbation):
            move = registry.pick(rng).apply(candidate, rng, candidates)
            if move is not None:
                candidate = move
        candidate_obj = evaluate(candidate)
        if candidate_obj < current_obj:
            current, current_obj = candidate, candidate_obj
            if candidate_obj < best_obj:
                best, best_obj = dict(candidate), candidate_obj
    return best, best_obj
