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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ..patch.accounts import load_patch_edges_detailed
from .objective import Target
from .operators import Candidates, Chain, Schedule


@dataclass(frozen=True)
class MipResult:
    """The result of the bound solve.

    Attributes
    ----------
    objective : float
        The penalty optimum of the option-selection model: exact for additive accounts,
        a lower bound when interactions (adjacency, edge contrast) are ignored, and
        accurate to the mixed-integer solver's tolerance (a relative ~1e-6).
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
    dict[tuple[int, Chain], dict[tuple[str, int], float]],
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
    accounted = sorted(
        {(target.account, year) for target in targets for year in target.cell_years()}
    )
    empty = pd.DataFrame([], columns=["block_id", "treatment", "period"])
    base: dict[int, dict[tuple[str, int], float]] = {}
    deltas: dict[tuple[int, Chain], dict[tuple[str, int], float]] = {}
    for block, options in candidates.items():
        base_index = _simulate_index(simulator_factory, empty, years, block)
        base[block] = {key: base_index.get(key, 0.0) for key in accounted}
        for option in options:
            schedule = pd.DataFrame(
                [
                    {"block_id": block, "treatment": treatment, "period": year}
                    for treatment, year in option
                ]
            )
            option_index = _simulate_index(simulator_factory, schedule, years, block)
            deltas[(block, option)] = {
                key: option_index.get(key, 0.0) - base[block][key] for key in accounted
            }
    return base, deltas, accounted


def _opening_rows(
    variables: list[tuple[int, Chain]],
    index: dict[tuple[int, Chain], int],
    n_vars: int,
    years: int,
    adjacency: Mapping[int, Sequence[int]],
    block_area: Mapping[int, float],
    max_opening_ha: float,
) -> tuple[list[np.ndarray], list[float], list[float]]:
    """Return the stand-centred adjacency rows (Gunn and Richards 2005, eq. 6).

    For each stand ``k`` and year ``t``::

        sum_{i in A_k} a_i x_it + A'_k x_kt <= sum_{i in A_k} a_i

    where ``A_k`` is the stands adjacent to ``k``, ``a_i`` the stand area, and
    ``A'_k = sum_{i in A_k} a_i - (A_max - a_k)``. One linear row per stand and period
    expresses the opening-size adjacency limit without enumerating covers.
    """
    treated: dict[tuple[int, Chain], set[int]] = {
        key: {year for _, year in key[1]} for key in variables
    }
    by_block: dict[int, list[tuple[int, Chain]]] = {}
    for key in variables:
        by_block.setdefault(key[0], []).append(key)
    rows: list[np.ndarray] = []
    lower: list[float] = []
    upper: list[float] = []
    for block, neighbours in adjacency.items():
        area_k = block_area.get(block, 0.0)
        plus = max_opening_ha - area_k
        neighbour_area = sum(block_area.get(other, 0.0) for other in neighbours)
        if plus < 0.0:
            # the stand alone exceeds the opening cap, so it cannot be harvested at all
            for year in range(years):
                row = np.zeros(n_vars)
                touched = False
                for key in by_block.get(block, ()):
                    if year in treated[key]:
                        row[index[key]] = 1.0
                        touched = True
                if touched:
                    rows.append(row)
                    lower.append(-np.inf)
                    upper.append(0.0)
            continue
        aprime = neighbour_area - plus
        for year in range(years):
            row = np.zeros(n_vars)
            touched = False
            for other in neighbours:
                other_area = block_area.get(other, 0.0)
                for key in by_block.get(other, ()):
                    if year in treated[key]:
                        row[index[key]] += other_area
                        touched = True
            if aprime != 0.0:
                for key in by_block.get(block, ()):
                    if year in treated[key]:
                        row[index[key]] += aprime
                        touched = True
            if not touched:
                continue
            rows.append(row)
            lower.append(-np.inf)
            upper.append(neighbour_area)
    return rows, lower, upper


def solve_mip(
    base: dict[int, dict[tuple[str, int], float]],
    deltas: dict[tuple[int, Chain], dict[tuple[str, int], float]],
    accounted: Sequence[tuple[str, int]],
    targets: Sequence[Target],
    opening: tuple[Mapping[int, Sequence[int]], Mapping[int, float], float] | None = None,
    years: int = 0,
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
    opening : tuple or None, optional
        The stand-centred opening constraints, as ``(neighbours, areas, cap)``: the adjacency
        per block, the block areas in hectares, and the maximum opening size. None omits them.
    years : int, optional
        The horizon in years, used to index the option variables per year. Defaults to 0.

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
        target_years = list(target.cell_years())
        delta_row = np.zeros(n_vars)
        for key, delta in deltas.items():
            total = sum(delta.get((target.account, year), 0.0) for year in target_years)
            if total:
                delta_row[index[key]] = total
        offset_value = sum(offset.get((target.account, year), 0.0) for year in target_years)
        if target.minimum is not None:
            row = delta_row.copy()
            row[n_x + target_index] = 1.0
            rows.append(row)
            lower.append(target.minimum - offset_value)
            upper.append(np.inf)
        if target.maximum is not None:
            row = -delta_row
            row[n_x + n_targets + target_index] = 1.0
            rows.append(row)
            lower.append(-target.maximum + offset_value)
            upper.append(np.inf)

    if opening is not None and years:
        adjacency, block_area, max_opening_ha = opening
        opening_rows, opening_lower, opening_upper = _opening_rows(
            variables, index, n_vars, years, adjacency, block_area, max_opening_ha
        )
        rows.extend(opening_rows)
        lower.extend(opening_lower)
        upper.extend(opening_upper)

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
    dataset_dir: Path,
    targets: Sequence[Target],
    candidates: Candidates,
    years: int,
    topology_path: Path | None = None,
    max_opening_ha: float | None = None,
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
    topology_path : Path or None, optional
        The block topology. When given with ``max_opening_ha``, the stand-centred opening
        constraints (Gunn and Richards 2005, eq. 6) tighten the bound.
    max_opening_ha : float or None, optional
        The maximum opening (harvest block) area the stand-centred constraints enforce.

    Returns
    -------
    MipResult
        The bound and the chosen schedule.
    """
    from ..sim.engine import Simulator  # local import to avoid a cycle

    def factory() -> Simulator:
        return Simulator.from_dataset(dataset_dir)

    base, deltas, accounted = option_contributions(factory, candidates, targets, years)
    opening: tuple[Mapping[int, Sequence[int]], Mapping[int, float], float] | None = None
    if topology_path is not None and max_opening_ha is not None:
        adjacency: dict[int, list[int]] = {}
        for source, target, _length, _distance in load_patch_edges_detailed(topology_path):
            adjacency.setdefault(source, []).append(target)
            adjacency.setdefault(target, []).append(source)
        block_area = factory().fragments.groupby("block_id")["area_ha"].sum().to_dict()
        opening = (
            {block: tuple(items) for block, items in adjacency.items()},
            {int(float(str(k))): float(v) for k, v in block_area.items()},
            float(max_opening_ha),
        )
    return solve_mip(base, deltas, accounted, targets, opening=opening, years=years)
