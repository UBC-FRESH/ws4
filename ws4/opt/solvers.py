"""Metaheuristic solvers over the operator registry.

Each solver takes a :class:`~ws4.opt.core.Problem`, a random source, and a budget, and
returns the best schedule it found and its objective. All solvers are seeded and
reproducible, and each reports its objective trajectory through an optional ``on_step``
callback.
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence

from .control import RunControl
from .cooling import TemperatureSchedule
from .core import Problem
from .incremental import IncrementalObjective
from .operators import Candidates, Chain, OperatorRegistry, Schedule, restore

StepCallback = Callable[[int, float], None]

#: Called with (iteration, incumbent objective, current objective, accepted moves).
TraceCallback = Callable[[int, float, float, int], None]

#: Called with (iteration, realized cells) on a snapshot interval.
SnapshotCallback = Callable[
    [int, Mapping[tuple[int, str], float], Mapping[int, Sequence[tuple[str, int]]]], None
]


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


def _stopped(control: RunControl | None, iteration: int) -> bool:
    """Return whether the control file asks the search to stop, waiting while it is paused.

    The file is polled every sixty-fourth iteration, which is often enough for a person to see and
    cheap enough not to dominate a move; a missing or invalid file means "run".

    Parameters
    ----------
    control : RunControl or None
        The run's control file, or None when it has none.
    iteration : int
        The current iteration index.

    Returns
    -------
    bool
        True when the search should stop.
    """
    if control is None or iteration % 64:
        return False
    action = control.action()
    while action == "pause":
        time.sleep(0.2)
        action = control.action()
    return action == "stop"


def _report(on_step: StepCallback | None, iteration: int, objective: float) -> None:
    """Report an iteration's incumbent objective when a callback is given."""
    if on_step is not None:
        on_step(iteration, objective)


def _trace(
    on_trace: TraceCallback | None,
    iteration: int,
    best: float,
    current: float,
    accepted: int,
) -> None:
    """Report the current solution alongside the incumbent when a callback is given."""
    if on_trace is not None:
        on_trace(iteration, best, current, accepted)


def _emit_snapshot(
    on_snapshot: SnapshotCallback | None,
    problem: Problem,
    iteration: int,
    iterations: int,
    best: Schedule,
) -> None:
    """Emit a realized-cell snapshot on the shared twentieth-iteration cadence."""
    if on_snapshot is None or not (iteration % 20 == 0 or iteration == iterations - 1):
        return
    totals = problem.snapshot(best) if problem.snapshot is not None else {}
    on_snapshot(iteration, totals, best)


def parse_time_limit(text: str) -> float | None:
    """Return a time limit in seconds, or None when the text states no limit.

    Parameters
    ----------
    text : str
        The limit as ``HH:MM:SS``, or an empty string for none.

    Returns
    -------
    float or None
        The limit in seconds, or None when the text is empty.

    Raises
    ------
    ValueError
        When the text is not ``HH:MM:SS``, or states a limit of zero or less — which would stop a
        run before it started rather than bound it.
    """
    if not text.strip():
        return None
    parts = text.strip().split(":")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"a time limit is HH:MM:SS, and {text!r} is not")
    hours, minutes, seconds = (int(part) for part in parts)
    if minutes > 59 or seconds > 59:
        raise ValueError(f"a time limit is HH:MM:SS, and {text!r} has no such minutes or seconds")
    total = float(hours * 3600 + minutes * 60 + seconds)
    if total <= 0.0:
        raise ValueError(f"a time limit of {text!r} would stop a run before it started")
    return total


def expired(deadline: float | None) -> bool:
    """Return whether a deadline has passed.

    Parameters
    ----------
    deadline : float or None
        A :func:`time.monotonic` value, or None for no deadline.

    Returns
    -------
    bool
        True when the deadline is set and has been reached.
    """
    return deadline is not None and time.monotonic() >= deadline


def patience_reached(iteration: int, last_improvement: int, patience: int) -> bool:
    """Return whether a search has gone ``patience`` iterations without an improvement.

    Parameters
    ----------
    iteration : int
        The next iteration the search would run.
    last_improvement : int
        The iteration of the last incumbent improvement.
    patience : int
        The allowed run of unimproved iterations; 0 disables the criterion.

    Returns
    -------
    bool
        True when the criterion is enabled and its run is exhausted.
    """
    return patience > 0 and iteration - last_improvement >= patience


def reversion_due(accepted: int, reversion: int) -> bool:
    """Return whether a reversion is due after an accepted move.

    Parameters
    ----------
    accepted : int
        The number of accepted moves so far.
    reversion : int
        The reversion interval; 0 disables it.

    Returns
    -------
    bool
        True when ``reversion`` is positive and ``accepted`` is a positive multiple of it.
    """
    return reversion > 0 and accepted > 0 and accepted % reversion == 0


def solve_sa(
    problem: Problem,
    rng: random.Random,
    *,
    iterations: int,
    temperature: float,
    cooling: float,
    on_step: StepCallback | None = None,
    on_trace: TraceCallback | None = None,
    control: RunControl | None = None,
    on_snapshot: SnapshotCallback | None = None,
    initial: Schedule | None = None,
    adaptive: bool = False,
    cooling_window: int = 64,
    deadline: float | None = None,
    patience: int = 0,
    reversion: int = 0,
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
    deadline : float or None, optional
        A :func:`time.monotonic` value to stop at, or None to run the budget out. A run stopped by
        the clock is not reproducible from its seed, which is why the budget is the default bound.
    temperature : float
        The initial temperature.
    cooling : float
        The geometric cooling factor.
    on_step : callable or None, optional
        Called with ``(iteration, best_objective)`` each iteration.
    on_trace : callable or None, optional
        Called with ``(iteration, best_objective, current_objective, accepted_moves)`` each
        iteration, for a live view of the search while the incumbent is flat.
    on_snapshot : callable or None, optional
        Called with ``(iteration, realized cells, incumbent schedule)`` every twentieth iteration
        and on the last one, for a live target view and an animated map.
    control : RunControl or None, optional
        A polled control file; the search holds while it says ``pause`` and returns its best
        schedule when it says ``stop``.
    initial : dict or None, optional
        A starting schedule.
    adaptive : bool, optional
        Use the adaptive Aarts-Van Laarhoven schedule instead of the geometric one.
    cooling_window : int, optional
        The iterations per temperature when ``adaptive`` is set, capped at half the budget.
    patience : int, optional
        Stop after this many iterations without an incumbent improvement; 0 disables it.
    reversion : int, optional
        Reset the current solution to the incumbent every ``reversion`` accepted moves;
        0 disables it.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current: Schedule = dict(initial) if initial is not None else {}
    current_obj = problem.evaluate(current)
    best, best_obj = dict(current), current_obj
    accepted = 0
    schedule = TemperatureSchedule(
        initial=temperature,
        cooling=cooling,
        adaptive=adaptive,
        window=TemperatureSchedule.effective_window(iterations, cooling_window),
    )
    last_improvement = 0
    for iteration in range(iterations):
        if patience_reached(iteration, last_improvement, patience):
            break
        if expired(deadline) or _stopped(control, iteration):
            break
        increase = 0.0
        move = problem.registry.pick(rng).apply(current, rng, problem.candidates)
        if move is not None:
            move_obj = problem.evaluate(move)
            increase = move_obj - current_obj
            if move_obj <= current_obj or rng.random() < math.exp(
                (current_obj - move_obj) / max(schedule.temperature, 1e-9)
            ):
                current, current_obj = move, move_obj
                accepted += 1
                if move_obj < best_obj:
                    best, best_obj = dict(move), move_obj
                    last_improvement = iteration
                if reversion_due(accepted, reversion):
                    current, current_obj = dict(best), best_obj
                    accepted = 0
        schedule.observe(increase, current_obj)
        _report(on_step, iteration, best_obj)
        _trace(on_trace, iteration, best_obj, current_obj, accepted)
        _emit_snapshot(on_snapshot, problem, iteration, iterations, best)
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
    on_trace: TraceCallback | None = None,
    control: RunControl | None = None,
    on_snapshot: SnapshotCallback | None = None,
    adaptive: bool = False,
    cooling_window: int = 64,
    deadline: float | None = None,
    patience: int = 0,
    reversion: int = 0,
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
    deadline : float or None, optional
        A :func:`time.monotonic` value to stop at, or None to run the budget out. A run stopped by
        the clock is not reproducible from its seed, which is why the budget is the default bound.
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
    on_trace : callable or None, optional
        Called with ``(iteration, best_objective, current_objective, accepted_moves)`` each
        iteration, for a live view of the search while the incumbent is flat.
    control : RunControl or None, optional
        A polled control file; the search holds while it says ``pause`` and returns its best
        schedule when it says ``stop``.
    on_snapshot : callable or None, optional
        Called with ``(iteration, realized cells, incumbent schedule)`` every twentieth iteration
        and on the last one, which is what a live target view and an animated map read.
    adaptive : bool, optional
        Use the adaptive Aarts-Van Laarhoven schedule instead of the geometric one.
    cooling_window : int, optional
        The iterations per temperature when ``adaptive`` is set, capped at half the budget.
    patience : int, optional
        Stop after this many iterations without an incumbent improvement; 0 disables it.
    reversion : int, optional
        Reset the current solution to the incumbent every ``reversion`` accepted moves;
        0 disables it.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current: Schedule = dict(initial) if initial is not None else {}
    evaluator.reset(current)
    current_obj = evaluator.objective
    best, best_obj = dict(current), current_obj
    schedule = TemperatureSchedule(
        initial=temperature,
        cooling=cooling,
        adaptive=adaptive,
        window=TemperatureSchedule.effective_window(iterations, cooling_window),
    )
    last_improvement = 0
    accepted = 0
    for iteration in range(iterations):
        if patience_reached(iteration, last_improvement, patience):
            break
        if expired(deadline) or _stopped(control, iteration):
            break
        increase = 0.0
        operator = registry.pick(rng)
        undo = operator.propose_inplace(current, rng, candidates)
        if undo is not None:
            changed = list(undo)
            move_obj = current_obj + evaluator.delta(changed, current)
            increase = move_obj - current_obj
            if move_obj <= current_obj or rng.random() < math.exp(
                (current_obj - move_obj) / max(schedule.temperature, 1e-9)
            ):
                evaluator.apply(changed, current)
                current_obj = move_obj
                accepted += 1
                if move_obj < best_obj:
                    best, best_obj = dict(current), move_obj
                    last_improvement = iteration
                if reversion_due(accepted, reversion):
                    current = dict(best)
                    evaluator.reset(current)
                    current_obj = best_obj
                    accepted = 0
            else:
                restore(current, undo)
                evaluator.revert()
        schedule.observe(increase, current_obj)
        _report(on_step, iteration, best_obj)
        _trace(on_trace, iteration, best_obj, current_obj, accepted)
        if on_snapshot is not None and (iteration % 20 == 0 or iteration == iterations - 1):
            on_snapshot(iteration, evaluator.totals, evaluator.assignments)
    return best, best_obj


def solve_threshold(
    problem: Problem,
    rng: random.Random,
    *,
    iterations: int,
    threshold: float,
    cooling: float,
    on_step: StepCallback | None = None,
    on_trace: TraceCallback | None = None,
    control: RunControl | None = None,
    on_snapshot: SnapshotCallback | None = None,
    initial: Schedule | None = None,
    deadline: float | None = None,
    patience: int = 0,
    reversion: int = 0,
) -> tuple[Schedule, float]:
    """Run threshold accepting: accept a feasible move within the current threshold.

    A move that improves the objective is always accepted. A move that worsens it is
    accepted while the increase is no larger than the current threshold. The threshold
    is multiplied by ``cooling`` each iteration, so the search diversifies early and
    intensifies as the threshold approaches zero.

    Parameters
    ----------
    problem : Problem
        The problem adapter.
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    threshold : float
        The initial threshold, in objective units.
    cooling : float
        The factor applied to the threshold each iteration; it must be in ``(0, 1]``.
    on_step : callable or None, optional
        Called with ``(iteration, best_objective)`` each iteration.
    on_trace : callable or None, optional
        Called with ``(iteration, best_objective, current_objective, accepted_moves)`` each
        iteration, for a live view of the search while the incumbent is flat.
    on_snapshot : callable or None, optional
        Called with ``(iteration, realized cells, incumbent schedule)`` every twentieth iteration
        and on the last one, for a live target view and an animated map.
    control : RunControl or None, optional
        A polled control file; the search holds while it says ``pause`` and returns its best
        schedule when it says ``stop``.
    initial : dict or None, optional
        A starting schedule. Defaults to the empty schedule.
    deadline : float or None, optional
        A :func:`time.monotonic` value to stop at, or None to run the budget out.
    patience : int, optional
        Stop after this many iterations without an incumbent improvement; 0 disables it.
    reversion : int, optional
        Reset the current solution to the incumbent every ``reversion`` accepted moves;
        0 disables it.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.

    Raises
    ------
    ValueError
        When ``threshold`` is negative or ``cooling`` is outside ``(0, 1]``.
    """
    if threshold < 0.0:
        raise ValueError("threshold must be zero or positive")
    if not 0.0 < cooling <= 1.0:
        raise ValueError("cooling must be in (0, 1]")
    current: Schedule = dict(initial) if initial is not None else {}
    current_obj = problem.evaluate(current)
    best, best_obj = dict(current), current_obj
    accepted = 0
    last_improvement = 0
    current_threshold = threshold
    for iteration in range(iterations):
        if patience_reached(iteration, last_improvement, patience):
            break
        if expired(deadline) or _stopped(control, iteration):
            break
        move = problem.registry.pick(rng).apply(current, rng, problem.candidates)
        if move is not None:
            move_obj = problem.evaluate(move)
            if move_obj <= current_obj or (move_obj - current_obj) <= current_threshold:
                current, current_obj = move, move_obj
                accepted += 1
                if move_obj < best_obj:
                    best, best_obj = dict(move), move_obj
                    last_improvement = iteration
                if reversion_due(accepted, reversion):
                    current, current_obj = dict(best), best_obj
                    accepted = 0
        current_threshold *= cooling
        _report(on_step, iteration, best_obj)
        _trace(on_trace, iteration, best_obj, current_obj, accepted)
        _emit_snapshot(on_snapshot, problem, iteration, iterations, best)
        if current_threshold <= 1e-12:
            break
    return best, best_obj


def solve_tabu(
    problem: Problem,
    rng: random.Random,
    *,
    iterations: int,
    tenure: int,
    samples: int = 8,
    on_step: StepCallback | None = None,
    on_trace: TraceCallback | None = None,
    control: RunControl | None = None,
    on_snapshot: SnapshotCallback | None = None,
    initial: Schedule | None = None,
    deadline: float | None = None,
    patience: int = 0,
    reversion: int = 0,
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
    deadline : float or None, optional
        A :func:`time.monotonic` value to stop at, or None to run the budget out. A run stopped by
        the clock is not reproducible from its seed, which is why the budget is the default bound.
    tenure : int
        The tabu list length.
    samples : int
        The number of candidate moves sampled per iteration.
    on_step : callable or None, optional
        Called with ``(iteration, best_objective)`` each iteration.
    on_trace : callable or None, optional
        Called with ``(iteration, best_objective, current_objective, accepted_moves)`` each
        iteration, for a live view of the search while the incumbent is flat.
    on_snapshot : callable or None, optional
        Called with ``(iteration, realized cells, incumbent schedule)`` every twentieth iteration
        and on the last one, for a live target view and an animated map.
    control : RunControl or None, optional
        A polled control file; the search holds while it says ``pause`` and returns its best
        schedule when it says ``stop``.
    initial : dict or None, optional
        A starting schedule. Defaults to the empty schedule.
    patience : int, optional
        Stop after this many iterations without an incumbent improvement; 0 disables it.
    reversion : int, optional
        Reset the current solution to the incumbent every ``reversion`` accepted moves;
        0 disables it.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current: Schedule = dict(initial) if initial is not None else {}
    current_obj = problem.evaluate(current)
    best, best_obj = dict(current), current_obj
    accepted = 0
    tabu: deque[frozenset[tuple[int, Chain | None]]] = deque(maxlen=tenure)
    last_improvement = 0
    for iteration in range(iterations):
        if patience_reached(iteration, last_improvement, patience):
            break
        if expired(deadline) or _stopped(control, iteration):
            break
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
            accepted += 1
            if current_obj < best_obj:
                best, best_obj = dict(current), current_obj
                last_improvement = iteration
            if reversion_due(accepted, reversion):
                current, current_obj = dict(best), best_obj
                accepted = 0
        _report(on_step, iteration, best_obj)
        _trace(on_trace, iteration, best_obj, current_obj, accepted)
        _emit_snapshot(on_snapshot, problem, iteration, iterations, best)
    return best, best_obj


def solve_ils(
    problem: Problem,
    rng: random.Random,
    *,
    iterations: int,
    perturbation: int,
    on_step: StepCallback | None = None,
    on_trace: TraceCallback | None = None,
    control: RunControl | None = None,
    on_snapshot: SnapshotCallback | None = None,
    initial: Schedule | None = None,
    deadline: float | None = None,
    patience: int = 0,
    reversion: int = 0,
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
    deadline : float or None, optional
        A :func:`time.monotonic` value to stop at, or None to run the budget out. A run stopped by
        the clock is not reproducible from its seed, which is why the budget is the default bound.
    perturbation : int
        The number of random moves applied to perturb the incumbent.
    on_step : callable or None, optional
        Called with ``(iteration, best_objective)`` each iteration.
    on_trace : callable or None, optional
        Called with ``(iteration, best_objective, current_objective, accepted_moves)`` each
        iteration, for a live view of the search while the incumbent is flat.
    on_snapshot : callable or None, optional
        Called with ``(iteration, realized cells, incumbent schedule)`` every twentieth iteration
        and on the last one, for a live target view and an animated map.
    control : RunControl or None, optional
        A polled control file; the search holds while it says ``pause`` and returns its best
        schedule when it says ``stop``.
    initial : dict or None, optional
        A starting schedule. Defaults to the empty schedule.
    patience : int, optional
        Stop after this many iterations without an incumbent improvement; 0 disables it.
    reversion : int, optional
        Reset the current solution to the incumbent every ``reversion`` accepted moves;
        0 disables it.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    current: Schedule = dict(initial) if initial is not None else {}
    current_obj = problem.evaluate(current)
    best, best_obj = dict(current), current_obj
    last_improvement = 0
    accepted = 0
    for iteration in range(iterations):
        if patience_reached(iteration, last_improvement, patience):
            break
        if expired(deadline) or _stopped(control, iteration):
            break
        candidate = dict(current)
        for _ in range(perturbation):
            move = problem.registry.pick(rng).apply(candidate, rng, problem.candidates)
            if move is not None:
                candidate = move
        candidate_obj = problem.evaluate(candidate)
        if candidate_obj < current_obj:
            current, current_obj = candidate, candidate_obj
            accepted += 1
            if candidate_obj < best_obj:
                best, best_obj = dict(candidate), candidate_obj
                last_improvement = iteration
            if reversion_due(accepted, reversion):
                current, current_obj = dict(best), best_obj
                accepted = 0
        _report(on_step, iteration, best_obj)
        _trace(on_trace, iteration, best_obj, current_obj, accepted)
        _emit_snapshot(on_snapshot, problem, iteration, iterations, best)
    return best, best_obj
