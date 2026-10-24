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

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ..patch.accounts import load_patch_edges_detailed
from .objective import Target, accumulates, normalization_scale
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


@dataclass(frozen=True)
class TargetDual:
    """One LP target row's dual price and slack.

    Attributes
    ----------
    account : str
        The target account.
    period : int or None
        The target period, when the target is periodic.
    year : int
        The display year.
    bound : str
        ``"minimum"`` or ``"maximum"``.
    dual : float
        The objective reduction from relaxing the bound by one unit: lowering a minimum or
        raising a maximum. A non-binding row has zero.
    slack : float
        The distance to the binding side: above the floor or below the ceiling. Zero means
        binding.
    binding : bool
        Whether the row is at its bound within the solver tolerance.
    """

    account: str
    period: int | None
    year: int
    bound: str
    dual: float
    slack: float
    binding: bool

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready record.

        Returns
        -------
        dict of str to object
            The account, period, year, bound, dual, slack, and binding flag.
        """
        return {
            "account": self.account,
            "period": self.period,
            "year": self.year,
            "bound": self.bound,
            "dual": round(self.dual, 8),
            "slack": round(self.slack, 8),
            "binding": self.binding,
        }


@dataclass(frozen=True)
class OptionReducedCost:
    """One option variable's LP value and reduced cost.

    Attributes
    ----------
    block : int
        The block identifier.
    treatments : tuple of (str, int)
        The option's treatment chain.
    value : float
        The LP value, between 0 and 1.
    reduced_cost : float
        The objective change per unit of the variable at its bound; zero for a basic or
        fractional variable.
    """

    block: int
    treatments: tuple[tuple[str, int], ...]
    value: float
    reduced_cost: float

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready record.

        Returns
        -------
        dict of str to object
            The block, treatments, value, and reduced cost.
        """
        return {
            "block": self.block,
            "treatments": [[treatment, offset] for treatment, offset in self.treatments],
            "value": round(self.value, 8),
            "reduced_cost": round(self.reduced_cost, 8),
        }


@dataclass(frozen=True)
class LpResult:
    """The LP relaxation's bound, target duals, and option reduced costs.

    Attributes
    ----------
    objective : float
        The LP relaxation objective: a lower bound on the mixed-integer penalty.
    status : str
        The solver status.
    variables : int
        The number of option variables.
    duals : tuple of TargetDual
        One record per target bound.
    reduced_costs : tuple of OptionReducedCost
        One record per option variable.
    message : str
        The solver message.
    """

    objective: float
    status: str
    variables: int
    duals: tuple[TargetDual, ...]
    reduced_costs: tuple[OptionReducedCost, ...]
    message: str = ""

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready record.

        Returns
        -------
        dict of str to object
            The objective, status, variables, duals, reduced costs, and message.
        """
        return {
            "objective": None if math.isinf(self.objective) else self.objective,
            "status": self.status,
            "variables": self.variables,
            "duals": [dual.as_dict() for dual in self.duals],
            "reduced_costs": [cost.as_dict() for cost in self.reduced_costs],
            "message": self.message,
        }


@dataclass(frozen=True)
class _Program:
    """The shared option-selection program for the MIP and the LP."""

    variables: tuple[tuple[int, Chain], ...]
    index: Mapping[tuple[int, Chain], int]
    blocks: tuple[int, ...]
    n_x: int
    n_targets: int
    n_vars: int
    objective: np.ndarray
    rows: tuple[np.ndarray, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    target_rows: tuple[dict[str, object], ...]


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
        (str(row.account), int(float(str(row.offset)))): float(str(row.value))
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
        {(target.account, year) for target in targets for year in _target_years(target)}
    )
    empty = pd.DataFrame([], columns=["block_id", "treatment", "offset"])
    base: dict[int, dict[tuple[str, int], float]] = {}
    deltas: dict[tuple[int, Chain], dict[tuple[str, int], float]] = {}
    for block, options in candidates.items():
        base_index = _simulate_index(simulator_factory, empty, years, block)
        base[block] = {key: base_index.get(key, 0.0) for key in accounted}
        for option in options:
            schedule = pd.DataFrame(
                [
                    {"block_id": block, "treatment": treatment, "offset": year}
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


def _build_program(
    base: dict[int, dict[tuple[str, int], float]],
    deltas: dict[tuple[int, Chain], dict[tuple[str, int], float]],
    accounted: Sequence[tuple[str, int]],
    targets: Sequence[Target],
    opening: tuple[Mapping[int, Sequence[int]], Mapping[int, float], float] | None = None,
    years: int = 0,
) -> _Program | None:
    """Build the shared option-selection program, or None when it has no target rows.

    Parameters
    ----------
    base : dict
        The no-treatment values per block.
    deltas : dict
        The per-block-option deltas.
    accounted : sequence of (str, int)
        The accounted ``(account, year)`` pairs.
    targets : sequence of Target
        The targets.
    opening : tuple or None, optional
        The stand-centred opening constraints, as ``(neighbours, areas, cap)``.
    years : int, optional
        The horizon used to index the opening rows.

    Returns
    -------
    _Program or None
        The shared program, or None when no target or opening row exists.
    """
    variables = list(deltas)
    index = {key: position for position, key in enumerate(variables)}
    blocks = sorted(base)
    n_x = len(variables)
    n_targets = len(targets)
    n_vars = n_x + 2 * n_targets
    offset = {key: sum(base[block].get(key, 0.0) for block in blocks) for key in accounted}
    objective = np.zeros(n_vars)
    for target_index, target in enumerate(targets):
        scale = normalization_scale(target)
        objective[n_x + target_index] = target.min_weight / scale
        objective[n_x + n_targets + target_index] = target.max_weight / scale
    rows: list[np.ndarray] = []
    lower: list[float] = []
    upper: list[float] = []
    target_rows: list[dict[str, object]] = []
    for block in blocks:
        row = np.zeros(n_vars)
        for option in (key for key in variables if key[0] == block):
            row[index[option]] = 1.0
        rows.append(row)
        lower.append(-np.inf)
        upper.append(1.0)
    for target_index, target in enumerate(targets):
        target_years = _target_years(target)
        delta_row = np.zeros(n_vars)
        for key, delta in deltas.items():
            total = sum(delta.get((target.account, year), 0.0) for year in target_years)
            if total:
                delta_row[index[key]] = total
        offset_value = sum(offset.get((target.account, year), 0.0) for year in target_years)
        if target.minimum is not None:
            row = delta_row.copy()
            row[n_x + target_index] = 1.0
            target_rows.append(
                {
                    "row": len(rows),
                    "account": target.account,
                    "period": target.period,
                    "year": target.year,
                    "bound": "minimum",
                }
            )
            rows.append(row)
            lower.append(target.minimum - offset_value)
            upper.append(np.inf)
        if target.maximum is not None:
            row = -delta_row
            row[n_x + n_targets + target_index] = 1.0
            target_rows.append(
                {
                    "row": len(rows),
                    "account": target.account,
                    "period": target.period,
                    "year": target.year,
                    "bound": "maximum",
                }
            )
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
        return None
    return _Program(
        variables=tuple(variables),
        index=index,
        blocks=tuple(blocks),
        n_x=n_x,
        n_targets=n_targets,
        n_vars=n_vars,
        objective=objective,
        rows=tuple(rows),
        lower=tuple(lower),
        upper=tuple(upper),
        target_rows=tuple(target_rows),
    )


def _upper_form(program: _Program) -> tuple[np.ndarray, np.ndarray, dict[int, int]]:
    """Convert the mixed lower/upper rows to ``A_ub x <= b_ub``.

    Parameters
    ----------
    program : _Program
        The shared program.

    Returns
    -------
    tuple of (ndarray, ndarray, dict)
        The matrix, the right-hand side, and the map from the original row to the upper-form
        row used for duals.
    """
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    row_map: dict[int, int] = {}
    for index, row in enumerate(program.rows):
        low = program.lower[index]
        high = program.upper[index]
        if np.isfinite(high):
            row_map[index] = len(rows)
            rows.append(row)
            rhs.append(high)
        if np.isfinite(low):
            row_map[index] = len(rows)
            rows.append(-row)
            rhs.append(-low)
    return np.vstack(rows), np.array(rhs), row_map


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

    program = _build_program(base, deltas, accounted, targets, opening, years)
    if program is None:
        return MipResult(0.0, {}, "no-targets", 0)
    matrix = np.vstack(program.rows)
    constraint = LinearConstraint(matrix, np.array(program.lower), np.array(program.upper))
    bounds = Bounds(np.zeros(program.n_vars), np.full(program.n_vars, np.inf))
    integrality = np.ones(program.n_vars)
    result = milp(
        program.objective,
        constraints=[constraint],
        bounds=bounds,
        integrality=integrality,
    )
    schedule: Schedule = {}
    if result.x is not None:
        for key, position in program.index.items():
            if result.x[position] > 0.5:
                schedule[key[0]] = key[1]
    status = "optimal" if result.success else "not-solved"
    return MipResult(
        objective=float(result.fun) if result.fun is not None else float("inf"),
        schedule=schedule,
        status=status,
        variables=program.n_x,
    )


def solve_lp(
    base: dict[int, dict[tuple[str, int], float]],
    deltas: dict[tuple[int, Chain], dict[tuple[str, int], float]],
    accounted: Sequence[tuple[str, int]],
    targets: Sequence[Target],
    opening: tuple[Mapping[int, Sequence[int]], Mapping[int, float], float] | None = None,
    years: int = 0,
) -> LpResult:
    """Solve the continuous relaxation and return target duals and reduced costs.

    The option variables are relaxed from binary to ``[0, 1]``. The objective is a lower bound
    on the mixed-integer penalty, and the target duals are the objective reduction from
    relaxing one bound by one unit. The report is advisory: it prices a relaxation, not a
    schedule.

    Parameters
    ----------
    base : dict
        The no-treatment values per block.
    deltas : dict
        The per-block-option deltas.
    accounted : sequence of (str, int)
        The accounted ``(account, year)`` pairs.
    targets : sequence of Target
        The targets.
    opening : tuple or None, optional
        The stand-centred opening constraints.
    years : int, optional
        The horizon used to index the opening rows.

    Returns
    -------
    LpResult
        The bound, duals, reduced costs, and solver status.

    Raises
    ------
    RuntimeError
        When the optional ``scipy`` dependency is not installed.
    """
    try:
        from scipy.optimize import linprog
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "the LP relaxation needs scipy; install the 'opt' extra (pip install 'ws4[opt]')"
        ) from exc

    program = _build_program(base, deltas, accounted, targets, opening, years)
    if program is None:
        return LpResult(0.0, "no-targets", 0, (), (), "")
    matrix, rhs, row_map = _upper_form(program)
    bounds = [(0.0, 1.0)] * program.n_x + [(0.0, None)] * (2 * program.n_targets)
    result = linprog(
        program.objective,
        A_ub=matrix,
        b_ub=rhs,
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        return LpResult(
            float("inf"),
            "not-solved",
            program.n_x,
            (),
            (),
            str(result.message),
        )
    marginals = result.ineqlin.marginals
    residuals = result.ineqlin.residual
    duals: list[TargetDual] = []
    for meta in program.target_rows:
        row = int(str(meta["row"]))
        position = row_map[row]
        marginal = float(marginals[position])
        slack = max(0.0, float(residuals[position]))
        dual = -marginal
        if abs(dual) < 1e-9:
            dual = 0.0
        duals.append(
            TargetDual(
                account=str(meta["account"]),
                period=meta["period"] if isinstance(meta["period"], int) else None,
                year=int(str(meta["year"])),
                bound=str(meta["bound"]),
                dual=dual,
                slack=slack,
                binding=slack <= 1e-7,
            )
        )
    lower_marginals = result.lower.marginals if result.lower is not None else np.zeros(program.n_x)
    upper_marginals = result.upper.marginals if result.upper is not None else np.zeros(program.n_x)
    reduced: list[OptionReducedCost] = []
    for position, (block, chain) in enumerate(program.variables):
        value = float(result.x[position])
        if value <= 1e-9:
            reduced_cost = float(lower_marginals[position])
        elif value >= 1.0 - 1e-9:
            reduced_cost = float(upper_marginals[position])
        else:
            reduced_cost = 0.0
        reduced.append(
            OptionReducedCost(
                block=block,
                treatments=tuple(chain),
                value=value,
                reduced_cost=reduced_cost,
            )
        )
    return LpResult(
        objective=float(result.fun),
        status="optimal",
        variables=program.n_x,
        duals=tuple(duals),
        reduced_costs=tuple(reduced),
        message=str(result.message),
    )


def _target_years(target: Target) -> list[int]:
    """Return the years a target's value is read from.

    An accumulating account sums its whole period; a level is read at the period's end year, which
    is the reference implementation's convention (see :func:`ws4.opt.objective.accumulates`).

    Parameters
    ----------
    target : Target
        The target.

    Returns
    -------
    list of int
        The years the target's value comes from.
    """
    return list(target.cell_offsets()) if accumulates(target.account) else [target.end_offset()]


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
    opening = _opening_for(factory, topology_path, max_opening_ha)
    return solve_mip(base, deltas, accounted, targets, opening=opening, years=years)


def relaxation_for(
    dataset_dir: Path,
    targets: Sequence[Target],
    candidates: Candidates,
    years: int,
    topology_path: Path | None = None,
    max_opening_ha: float | None = None,
) -> LpResult:
    """Compute the LP relaxation and its target duals for a dataset and target set.

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
        The block topology, used with ``max_opening_ha`` for the opening constraints.
    max_opening_ha : float or None, optional
        The maximum opening area.

    Returns
    -------
    LpResult
        The LP bound, duals, and reduced costs.
    """
    from ..sim.engine import Simulator  # local import to avoid a cycle

    def factory() -> Simulator:
        return Simulator.from_dataset(dataset_dir)

    base, deltas, accounted = option_contributions(factory, candidates, targets, years)
    opening = _opening_for(factory, topology_path, max_opening_ha)
    return solve_lp(base, deltas, accounted, targets, opening=opening, years=years)


def _opening_for(
    factory: Callable[[], object],
    topology_path: Path | None,
    max_opening_ha: float | None,
) -> tuple[Mapping[int, Sequence[int]], Mapping[int, float], float] | None:
    """Build the stand-centred opening constraints for the shared program.

    Parameters
    ----------
    factory : callable
        Returns a fresh simulator; its fragments supply the block areas.
    topology_path : Path or None
        The block topology.
    max_opening_ha : float or None
        The maximum opening area.

    Returns
    -------
    tuple or None
        ``(neighbours, areas, cap)``, or None when either input is missing.
    """
    if topology_path is None or max_opening_ha is None:
        return None
    adjacency: dict[int, list[int]] = {}
    for source, target, _length, _distance in load_patch_edges_detailed(topology_path):
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, []).append(source)
    simulator = factory()
    fragments = simulator.fragments  # type: ignore[attr-defined]
    block_area = fragments.groupby("block_id")["area_ha"].sum().to_dict()
    return (
        {block: tuple(items) for block, items in adjacency.items()},
        {int(float(str(k))): float(v) for k, v in block_area.items()},
        float(max_opening_ha),
    )
