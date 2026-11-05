"""Metaheuristic solvers over the operator registry.

The solvers are re-exported from the shared kernel in ``fresh-solutions``. WS4 keeps this
module as its stable import surface and supplies the schedule-specific pieces (the state
clone, the tabu signature, and the delta evaluator).
"""

from __future__ import annotations

import random

from fresh_solutions.kernel import (
    DeltaEvaluator,
    RunControl,
    SnapshotCallback,
    StepCallback,
    TraceCallback,
    solve_ils,
    solve_sa,
    solve_tabu,
    solve_threshold,
)
from fresh_solutions.kernel.solvers import solve_sa_delta as _solve_sa_delta
from fresh_solutions.kernel.stopping import (
    expired,
    parse_time_limit,
    patience_reached,
    reversion_due,
)
from fresh_solutions.kernel.stopping import stopped as _stopped  # compatibility re-export

__all__ = [
    "_stopped",
    "expired",
    "parse_time_limit",
    "patience_reached",
    "reversion_due",
    "solve_ils",
    "solve_sa",
    "solve_sa_delta",
    "solve_tabu",
    "solve_threshold",
]

from .operators import Candidates, OperatorRegistry, Schedule


def _changed_blocks(before: Schedule, after: Schedule) -> list[int]:
    """Return the blocks whose assignment differs between two schedules.

    Parameters
    ----------
    before : Schedule
        The schedule before a move.
    after : Schedule
        The schedule after a move.

    Returns
    -------
    list of int
        The changed block identifiers.
    """
    changed = [block for block, value in after.items() if before.get(block) != value]
    changed.extend(block for block in before if block not in after)
    return changed


def solve_sa_delta(
    evaluator: DeltaEvaluator[Schedule],
    rng: random.Random,
    *,
    iterations: int,
    temperature: float,
    cooling: float,
    candidates: Candidates,
    registry: OperatorRegistry[Schedule, Candidates],
    initial: Schedule | None = None,
    on_step: StepCallback | None = None,
    on_trace: TraceCallback | None = None,
    on_snapshot: SnapshotCallback[Schedule] | None = None,
    adaptive: bool = False,
    cooling_window: int = 64,
    control: RunControl | None = None,
    deadline: float | None = None,
    patience: int = 0,
    reversion: int = 0,
) -> tuple[Schedule, float]:
    """Run simulated annealing priced by exact per-move deltas.

    This wrapper preserves WS4's ``None``-means-empty starting state; the kernel itself
    requires an explicit state.

    Parameters
    ----------
    evaluator : DeltaEvaluator
        The move-based evaluator.
    rng : random.Random
        The random source.
    iterations : int
        The iteration budget.
    temperature : float
        The initial temperature.
    cooling : float
        The geometric cooling factor.
    candidates : Candidates
        The candidate chains per block.
    registry : OperatorRegistry
        The move operators.
    initial : Schedule or None, optional
        A starting schedule. ``None`` starts from the empty schedule.
    on_step, on_trace, on_snapshot : callable or None, optional
        Progress callbacks, as in :func:`solve_sa`.
    adaptive : bool, optional
        Use the adaptive Aarts--Van Laarhoven schedule.
    cooling_window : int, optional
        The iterations per temperature in adaptive mode.
    control : RunControl or None, optional
        A polled control file.
    deadline : float or None, optional
        A :func:`time.monotonic` deadline, or ``None``.
    patience : int, optional
        Stop after this many iterations without improvement; ``0`` disables it.
    reversion : int, optional
        Revert to the incumbent every this many accepted moves; ``0`` disables it.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective.
    """
    return _solve_sa_delta(
        evaluator,
        rng,
        iterations=iterations,
        temperature=temperature,
        cooling=cooling,
        candidates=candidates,
        registry=registry,
        initial={} if initial is None else initial,
        on_step=on_step,
        on_trace=on_trace,
        on_snapshot=on_snapshot,
        adaptive=adaptive,
        cooling_window=cooling_window,
        control=control,
        deadline=deadline,
        patience=patience,
        reversion=reversion,
    )
