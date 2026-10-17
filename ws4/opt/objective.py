"""Weighted-goal objective over account values.

Each target names an account and a year with a minimum, a maximum, or both. The
penalty is the weighted shortfall below the minimum plus the weighted excess above
the maximum; the objective is the total penalty (lower is better).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd
import yaml


@dataclass(frozen=True)
class Target:
    """One goal-programming target.

    A target is **periodic**: it applies to the account summed over ``period_width`` years
    starting at ``year`` (a single year when ``period_width`` is 1). Treatments are still
    scheduled by year; only the accounting is aggregated.

    Attributes
    ----------
    account : str
        The account label the target applies to.
    year : int
        The first year of the period the target applies to.
    minimum : float or None
        The lower bound; a value below it is penalized.
    maximum : float or None
        The upper bound; a value above it is penalized.
    min_weight : float
        The weight on the shortfall below the minimum.
    max_weight : float
        The weight on the excess above the maximum.
    period_width : int
        The account time step, in whole years: the number of years the account is summed over for
        this target. One year is the simulation step; five or ten are the planning convention.
    shape : str
        The penalty shape: ``"linear"`` adds the weighted deviation, ``"non_linear"`` adds the
        weighted squared deviation (the weight is applied after squaring, matching the default
        non-premultiplied scaling).
    flow : str
        A flow term: ``""`` for an ordinary level target, ``"even"`` for even flow, or ``"ndy"`` for
        non-declining yield. A flow target's value is an aggregate over the periods of its window,
        not a period's account value, and it is normally targeted at ``0`` with a weight.
    flow_start : int
        The first year of a flow term's window.
    flow_end : int or None
        The year the flow window ends (exclusive), or None for the end of the horizon.
    flow_reference : int or None
        The first year of the flow term's reference period, or None for the final period of the
        window. Every other period is measured as a percent difference from it.
    """

    account: str
    year: int
    minimum: float | None = None
    maximum: float | None = None
    min_weight: float = 1.0
    max_weight: float = 1.0
    period_width: int = 1
    shape: str = "linear"
    flow: str = ""
    flow_start: int = 0
    flow_end: int | None = None
    flow_reference: int | None = None

    def __post_init__(self) -> None:
        """Reject an unknown penalty shape, flow type, or a period shorter than a year."""
        if self.shape not in {"linear", "non_linear"}:
            raise ValueError(f"unknown penalty shape: {self.shape!r}")
        if self.period_width < 1:
            raise ValueError("period_width must be at least one year")
        if self.flow not in {"", "even", "ndy"}:
            raise ValueError(f"unknown flow type: {self.flow!r}")
        if self.flow_end is not None and self.flow_end <= self.flow_start:
            raise ValueError("flow_end must be after flow_start")

    def cell_years(self) -> range:
        """Return the years the target sums the account over.

        Returns
        -------
        range
            The years of the target's period.
        """
        return range(self.year, self.year + max(1, self.period_width))


def penalty(value: float, target: Target) -> float:
    """Return the penalty for one account value against one target.

    Parameters
    ----------
    value : float
        The account value.
    target : Target
        The target.

    Returns
    -------
    float
        The weighted shortfall plus the weighted excess (zero when in range).
    """
    total = 0.0
    if target.minimum is not None and value < target.minimum:
        deviation = target.minimum - value
        if target.shape == "non_linear":
            deviation *= deviation
        total += target.min_weight * deviation
    if target.maximum is not None and value > target.maximum:
        deviation = value - target.maximum
        if target.shape == "non_linear":
            deviation *= deviation
        total += target.max_weight * deviation
    return total


def flow_values(
    index: Mapping[tuple[int, str], float],
    target: Target,
    years: int,
    pending: Mapping[tuple[int, str], float] | None = None,
) -> list[float]:
    """Return a flow target's percent value for each period it compares.

    A flow target constrains the **shape** of the account's profile over the periods, not its level;
    the level comes from a separate target on the same account, and the flow target itself is
    normally a narrow band around zero. The two kinds differ in what they compare, and both give one
    value per period, so the target's minimum, maximum, weights and shape apply period by period:

    * ``even`` is the **percent difference of each period from a reference period**:
      ``100 * (x_p - x_ref) / x_ref``. The reference is the **final period of the window** by
      default, or ``flow_reference`` (the first year of the period to use), and it contributes no
      value of its own.
    * ``ndy`` (non-declining yield) is the **percent change between consecutive periods**:
      ``100 * (x_p - x_{p-1}) / x_{p-1}``, starting from the second period of the window.

    Both divide by a balance that can be zero, in which case every period that depends on it is
    infinite. A run primes that balance first, for example with a linear volume target above the
    sustainable level so that every period has wood, and only then switches the flow account on.
    This is the definitional behaviour, not a defect.

    Parameters
    ----------
    index : mapping of (int, str) to float
        The account values by ``(year, account)``.
    target : Target
        A target whose ``flow`` is ``"even"`` or ``"ndy"``.
    years : int
        The horizon, in years; the window's end when ``flow_end`` is not set.
    pending : mapping of (int, str) to float, optional
        A move's change per cell, added to ``index`` without copying it.

    Returns
    -------
    list of float
        One percent value per compared period; empty when the window holds fewer than two periods.
    """
    width = max(1, target.period_width)
    stop = target.flow_end if target.flow_end is not None else years
    account = target.account
    periods: list[float] = []
    starts: list[int] = []
    for begin in range(target.flow_start, stop, width):
        total = 0.0
        for year in range(begin, min(begin + width, stop)):
            cell = (year, account)
            total += index.get(cell, 0.0)
            if pending is not None:
                total += pending.get(cell, 0.0)
        periods.append(total)
        starts.append(begin)
    if len(periods) < 2:
        return []
    if target.flow == "ndy":
        values: list[float] = []
        for position in range(1, len(periods)):
            previous = periods[position - 1]
            values.append(
                math.inf if previous <= 0.0 else 100.0 * (periods[position] - previous) / previous
            )
        return values
    reference = len(periods) - 1
    if target.flow_reference is not None:
        # the period containing that year, clamped to the window
        reference = 0
        for position, begin in enumerate(starts):
            if begin <= target.flow_reference:
                reference = position
    balance = periods[reference]
    if balance <= 0.0:
        # every non-reference period differs from nothing: the whole band is infinite
        return [math.inf] * (len(periods) - 1)
    return [
        100.0 * (value - balance) / balance
        for position, value in enumerate(periods)
        if position != reference
    ]


def flow_penalty(
    index: Mapping[tuple[int, str], float],
    target: Target,
    years: int,
    pending: Mapping[tuple[int, str], float] | None = None,
) -> float:
    """Return a flow target's penalty: each period's percent value, priced by the target.

    The target's minimum, maximum, weights and shape are applied **per period**, so a band of
    ``minimum: -1`` and ``maximum: 1`` gives every period a one-percent-either-way safe range and
    charges only what falls outside it.

    Parameters
    ----------
    index : mapping of (int, str) to float
        The account values by ``(year, account)``.
    target : Target
        A target whose ``flow`` is ``"even"`` or ``"ndy"``.
    years : int
        The horizon, in years; the window's end when ``flow_end`` is not set.
    pending : mapping of (int, str) to float, optional
        A move's change per cell, added to ``index`` without copying it.

    Returns
    -------
    float
        The summed per-period penalty.
    """
    return sum(penalty(value, target) for value in flow_values(index, target, years, pending))


def objective(values: pd.DataFrame, targets: Sequence[Target]) -> float:
    """Return the total weighted penalty over a set of targets.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values, with ``year``, ``account``, and ``value`` columns.
    targets : sequence of Target
        The targets.

    Returns
    -------
    float
        The total penalty.
    """
    index = _value_index(values)
    horizon = max((year for year, _ in index), default=-1) + 1
    total = 0.0
    for target in targets:
        if target.flow:
            total += flow_penalty(index, target, horizon)
            continue
        value = sum(index.get((year, target.account), 0.0) for year in target.cell_years())
        total += penalty(value, target)
    return total


def _value_index(values: pd.DataFrame) -> dict[tuple[int, str], float]:
    """Index an account-values frame by ``(year, account)``."""
    return {
        (int(float(str(row.year))), str(row.account)): float(str(row.value))
        for row in values.itertuples(index=False)
    }


def objective_terms(
    values: pd.DataFrame,
    targets: Sequence[Target],
    point_in_time: Callable[[str], bool] | None = None,
) -> list[float]:
    """Return the penalty of each target, in order.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values, with ``year``, ``account``, and ``value`` columns.
    targets : sequence of Target
        The targets.
    point_in_time : callable or None, optional
        Returns True for an account that is a snapshot rather than an additive quantity (a patch
        account); such a target is read at the first year of its period only. Defaults to None
        (every account is additive).

    Returns
    -------
    list of float
        One penalty per target.
    """
    index = _value_index(values)
    horizon = max((year for year, _ in index), default=-1) + 1
    penalties: list[float] = []
    for target in targets:
        if target.flow:
            penalties.append(flow_penalty(index, target, horizon))
            continue
        years = list(target.cell_years())
        if point_in_time is not None and point_in_time(target.account):
            years = years[:1]
        value = sum(index.get((year, target.account), 0.0) for year in years)
        penalties.append(penalty(value, target))
    return penalties


def balance_targets(targets: Sequence[Target], peaks: Sequence[float]) -> list[Target]:
    """Rescale the targets so no single penalty term dominates the objective.

    ``peaks[i]`` is the largest penalty target ``i`` reached in a pilot run. Every target that
    fired is rescaled so its peak matches the mean peak of the firing targets; a target that
    never fired keeps its own weights. This automates the first pass of the manual rescaling
    Lockwood and Moore (1993) used to make the terms decrease at similar rates.

    Parameters
    ----------
    targets : sequence of Target
        The targets.
    peaks : sequence of float
        The peak penalty per target, in the same order.

    Returns
    -------
    list of Target
        The rescaled targets.

    Raises
    ------
    ValueError
        If ``peaks`` and ``targets`` differ in length.
    """
    if len(peaks) != len(targets):
        raise ValueError("peaks and targets must have the same length")
    active = [peak for peak in peaks if peak > 0.0]
    if not active:
        return list(targets)
    mean_peak = sum(active) / len(active)
    scaled: list[Target] = []
    for target, peak in zip(targets, peaks, strict=True):
        if peak <= 0.0:
            scaled.append(target)
            continue
        factor = mean_peak / peak
        scaled.append(
            replace(
                target,
                min_weight=target.min_weight * factor
                if target.minimum is not None
                else target.min_weight,
                max_weight=target.max_weight * factor
                if target.maximum is not None
                else target.max_weight,
            )
        )
    return scaled


def load_targets(path: Path) -> list[Target]:
    """Load targets from a YAML file.

    The file is a mapping with a ``targets`` list; each entry has ``account``,
    ``year``, and any of ``minimum``, ``maximum``, ``min_weight``, ``max_weight``,
    ``period_width`` (years per period; the account is summed over them), ``shape``
    (``linear`` or ``non_linear``), and the flow keys ``flow`` (``even`` or ``ndy``),
    ``flow_start`` and ``flow_end`` (the flow window, in years).

    Parameters
    ----------
    path : Path
        The targets file.

    Returns
    -------
    list of Target
        The parsed targets.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    entries = raw.get("targets", []) if isinstance(raw, dict) else []
    return [
        Target(
            account=str(entry["account"]),
            year=int(entry["year"]),
            minimum=entry.get("minimum"),
            maximum=entry.get("maximum"),
            min_weight=float(entry.get("min_weight", 1.0)),
            max_weight=float(entry.get("max_weight", 1.0)),
            period_width=int(entry.get("period_width", 1)),
            shape=str(entry.get("shape", "linear")),
            flow=str(entry.get("flow", "")),
            flow_start=int(entry.get("flow_start", 0)),
            flow_end=(int(entry["flow_end"]) if entry.get("flow_end") is not None else None),
            flow_reference=(
                int(entry["flow_reference"]) if entry.get("flow_reference") is not None else None
            ),
        )
        for entry in entries
    ]
