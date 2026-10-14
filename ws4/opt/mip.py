"""A mixed-integer bound for the schedule problem.

The problem is: choose, for each block, one of its treatment options (or none), to
minimize the weighted-goal penalty. Each option contributes a known amount to each
target's account value (computed by simulating the block alone with that option), so
the choice is a set of binary variables and the penalty is linearized with slacks. The
result is a valid lower bound on the penalty, used for gap tracking.

This is a bounded implementation: it enumerates options per block and solves with
HiGHS through ``scipy.optimize.milp``. It is intended for a subset of blocks (a
subproblem), not a full landscape.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .objective import Target
from .operators import Candidates, Schedule


@dataclass(frozen=True)
class MipResult:
    """The result of the bound solve.

    Attributes
    ----------
    objective : float
        The optimal penalty of the relaxation (a lower bound on the true penalty).
    schedule : Schedule
        The option chosen for each block in the solved subset.
    status : str
        The solver status.
    variables : int
        The number of binary variables.
    """

    objective: float
    schedule: Schedule
    status: str
    variables: int


def _simulate_index(
    simulator_factory: Callable[[], object], schedule: pd.DataFrame, years: int, block: int
) -> dict[tuple[str, int], float]:
    """Simulate a schedule with one block's fragments isolated.

    The simulator reads every fragment, so the fragments are filtered to the block to
    measure that block's own contribution.
    """
    simulator = simulator_factory()
    fragments = simulator.fragments  # type: ignore[attr-defined]
    simulator.fragments = fragments[fragments["block_id"] == block].copy()  # type: ignore[attr-defined]
    simulator.fragments["offset"] = simulator.fragments["age"].astype(int)  # type: ignore[attr-defined]
    values = simulator.simulate(schedule, years)  # type: ignore[attr-defined]
    return {
        (str(row.account), int(float(str(row.year)))): float(str(row.value))
        for row in values.itertuples(index=False)
    }


def option_contributions(
    simulator_factory: Callable[[], object],
    candidates: Candidates,
    targets: Sequence[Target],
    years: int,
) -> tuple[
    dict[int, dict[tuple[str, int], float]],
    dict[tuple[int, tuple[str, int]], dict[tuple[str, int], float]],
    list[tuple[str, int]],
]:
    """Compute each block's base value and each option's delta.

    The base is the block's account values with no treatment; an option's delta is its
    value minus the base. The full value is the sum of the bases plus the chosen deltas.

    Parameters
    ----------
    simulator_factory : callable
        Returns a fresh simulator (its ``simulate`` method is used).
    candidates : Candidates
        The candidate options per block.
    targets : sequence of Target
        The targets, whose ``(account, year)`` pairs are the accounted values.
    years : int
        The simulation horizon.

    Returns
    -------
    tuple of (dict, dict, list)
        The base values per block, the deltas per block-option, and the accounted keys.
    """
    accounted = sorted({(target.account, target.year) for target in targets})
    empty = pd.DataFrame([], columns=["block_id", "treatment", "period"])
    base: dict[int, dict[tuple[str, int], float]] = {}
    deltas: dict[tuple[int, tuple[str, int]], dict[tuple[str, int], float]] = {}
    for block, options in candidates.items():
        base_index = _simulate_index(simulator_factory, empty, years, block)
        base[block] = {key: base_index.get(key, 0.0) for key in accounted}
        for option in options:
            schedule = pd.DataFrame(
                [{"block_id": block, "treatment": option[0], "period": option[1]}]
            )
            option_index = _simulate_index(simulator_factory, schedule, years, block)
            deltas[(block, option)] = {
                key: option_index.get(key, 0.0) - base[block][key] for key in accounted
            }
    return base, deltas, accounted


def solve_mip(
    base: dict[int, dict[tuple[str, int], float]],
    deltas: dict[tuple[int, tuple[str, int]], dict[tuple[str, int], float]],
    accounted: Sequence[tuple[str, int]],
    targets: Sequence[Target],
) -> MipResult:
    """Solve the option-selection MILP and return the bound.

    Parameters
    ----------
    base : dict
        The no-treatment values per block, from :func:`option_contributions`.
    deltas : dict
        The per-block-option deltas, from :func:`option_contributions`.
    accounted : sequence of (str, int)
        The accounted ``(account, year)`` pairs.
    targets : sequence of Target
        The targets.

    Returns
    -------
    MipResult
        The bound, the chosen schedule, and the solver status.

    Raises
    ------
    RuntimeError
        When the optional ``scipy`` dependency is not installed.
    """
    try:
        from scipy.optimize import Bounds, LinearConstraint, milp
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "the mixed-integer bound needs scipy; install the 'opt' extra (pip install 'ws4[opt]')"
        ) from exc

    variables = list(deltas)
    index = {key: position for position, key in enumerate(variables)}
    blocks = sorted(base)
    n_x = len(variables)
    n_targets = len(targets)
    n_vars = n_x + 2 * n_targets

    # The value is the summed base plus the chosen deltas.
    offset = {key: sum(base[block].get(key, 0.0) for block in blocks) for key in accounted}

    objective = np.zeros(n_vars)
    for target_index, target in enumerate(targets):
        objective[n_x + target_index] = target.min_weight
        objective[n_x + n_targets + target_index] = target.max_weight

    rows: list[np.ndarray] = []
    lower: list[float] = []
    upper: list[float] = []

    # At most one option per block.
    for block in blocks:
        row = np.zeros(n_vars)
        for option in (key for key in variables if key[0] == block):
            row[index[option]] = 1.0
        rows.append(row)
        lower.append(-np.inf)
        upper.append(1.0)

    # value + shortfall >= minimum ; -value + excess >= -maximum.
    for target_index, target in enumerate(targets):
        accounted_index = accounted.index((target.account, target.year))
        key_pair = accounted[accounted_index]
        delta_row = np.zeros(n_vars)
        for key, delta in deltas.items():
            delta_row[index[key]] = delta[key_pair]
        if target.minimum is not None:
            row = delta_row.copy()
            row[n_x + target_index] = 1.0
            rows.append(row)
            lower.append(target.minimum - offset[key_pair])
            upper.append(np.inf)
        if target.maximum is not None:
            row = -delta_row
            row[n_x + n_targets + target_index] = 1.0
            rows.append(row)
            lower.append(-target.maximum + offset[key_pair])
            upper.append(np.inf)

    if not rows:
        return MipResult(0.0, {}, "no-targets", n_x)

    matrix = np.vstack(rows)
    constraint = LinearConstraint(matrix, np.array(lower), np.array(upper))
    bounds = Bounds(np.zeros(n_vars), np.full(n_vars, np.inf))
    integrality = np.ones(n_vars)
    result = milp(objective, constraints=[constraint], bounds=bounds, integrality=integrality)

    schedule: Schedule = {}
    if result.x is not None:
        for key, position in index.items():
            if result.x[position] > 0.5:
                schedule[key[0]] = key[1]
    status = "optimal" if result.success else "not-solved"
    return MipResult(
        objective=float(result.fun) if result.fun is not None else float("inf"),
        schedule=schedule,
        status=status,
        variables=n_x,
    )


def bound_for(
    dataset_dir: Path, targets: Sequence[Target], candidates: Candidates, years: int
) -> MipResult:
    """Compute a penalty lower bound for a dataset and a target set.

    Parameters
    ----------
    dataset_dir : Path
        The compiled dataset.
    targets : sequence of Target
        The targets.
    candidates : Candidates
        The candidate options per block.
    years : int
        The simulation horizon.

    Returns
    -------
    MipResult
        The bound and the chosen schedule.
    """
    from ..sim.engine import Simulator  # local import to avoid a cycle

    def factory() -> Simulator:
        return Simulator.from_dataset(dataset_dir)

    base, deltas, accounted = option_contributions(factory, candidates, targets, years)
    return solve_mip(base, deltas, accounted, targets)
