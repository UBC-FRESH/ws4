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

    A target is **periodic**: it applies to one accounting period of ``period_width`` years.
    Period 1 is the first accounting period (years 1 to ``period_width``), period 2 the next,
    and period 0 is the initial snapshot at year 0. Treatments are still scheduled by year;
    only the accounting is aggregated.

    Attributes
    ----------
    account : str
        The account label the target applies to.
    year : int
        The end year of the period, derived from ``period`` and ``period_width``. Kept because
        account values are stored by year; prefer ``period`` in the target file.
    period : int or None
        The period index. Period 0 is the initial snapshot; periods 1 to N are the accounting
        periods. When given, ``year`` is derived as ``period * period_width``.
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
    flow_start_period : int or None
        The first period of a flow term's window, inclusive. When given, ``flow_start`` is derived.
    flow_end_period : int or None
        The last period of a flow term's window, inclusive. When given, ``flow_end`` is derived.
    flow_reference_period : int or None
        The reference period for an even-flow comparison. When given, ``flow_reference`` is derived.
    active : bool
        Whether the search prices this target. An inactive target stays in the file and is
        reported, but its penalty is not part of the objective.
    """

    account: str
    year: int = 0
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
    period: int | None = None
    flow_start_period: int | None = None
    flow_end_period: int | None = None
    flow_reference_period: int | None = None
    active: bool = True

    def __post_init__(self) -> None:
        """Reject an unknown penalty shape, flow type, or a period shorter than a year."""
        if self.shape not in {"linear", "non_linear"}:
            raise ValueError(f"unknown penalty shape: {self.shape!r}")
        if self.period_width < 1:
            raise ValueError("period_width must be at least one year")
        if self.flow not in {"", "even", "ndy"}:
            raise ValueError(f"unknown flow type: {self.flow!r}")
        if self.period is not None:
            if self.period < 0:
                raise ValueError("period must be zero (initial snapshot) or positive")
            # ``year`` is the display label: the 1-based year the period ends on.
            object.__setattr__(self, "year", self.period * self.period_width)
        if self.flow_start_period is not None:
            if self.flow_start_period < 0:
                raise ValueError("flow_start_period must not be negative")
            # Flow windows are offset ranges: period p starts at offset (p-1)*width.
            object.__setattr__(
                self,
                "flow_start",
                (self.flow_start_period - 1) * self.period_width,
            )
        if self.flow_end_period is not None:
            if self.flow_end_period < 0:
                raise ValueError("flow_end_period must not be negative")
            # Exclusive offset end: period p covers offsets up to p*width - 1.
            object.__setattr__(
                self,
                "flow_end",
                self.flow_end_period * self.period_width,
            )
        if self.flow_reference_period is not None:
            if self.flow_reference_period < 0:
                raise ValueError("flow_reference_period must not be negative")
            object.__setattr__(
                self,
                "flow_reference",
                (self.flow_reference_period - 1) * self.period_width,
            )
        if self.flow_end is not None and self.flow_end <= self.flow_start:
            raise ValueError("flow_end must be after flow_start")

    def cell_offsets(self) -> tuple[int, ...]:
        """Return the simulation offsets of the target's period.

        Period 0 is the snapshot at offset -1. Period ``p >= 1`` covers offsets
        ``(p - 1) * width`` through ``p * width - 1``. ``year`` remains a display
        label only: the 1-based year the period ends on.

        Returns
        -------
        tuple of int
            The offsets of the target's period.
        """
        width = max(1, self.period_width)
        if self.period is not None:
            if self.period == 0:
                return (-1,)
            return tuple(range((self.period - 1) * width, self.period * width))
        # Legacy ``year`` is a 1-based end year; year 0 is the snapshot.
        if self.year == 0:
            return (-1,)
        return tuple(range(self.year - width, self.year))

    def end_offset(self) -> int:
        """Return the offset the period is read at for a level account.

        Returns
        -------
        int
            The last offset of the period, or -1 for the snapshot.
        """
        offsets = self.cell_offsets()
        return offsets[-1] if offsets else -1


#: The prefix of an account that accumulates over a period rather than being read at its end.
ACCUMULATING_PREFIX = "product."


def accumulates(account: str) -> bool:
    """Return whether an account accumulates over a target's period.

    A ``product.`` account is something produced during the period, so a period's value is the
    sum of its years. Everything else — the ``feature.`` accounts, the patch accounts, a size
    class's share — is a level: a state of the map at a point in time, read at the period's end.
    That is the reference's own convention, and its report writers say the same in their own
    definitions.

    Parameters
    ----------
    account : str
        The account name.

    Returns
    -------
    bool
        True when the period's value is the sum of its years.
    """
    return account.startswith(ACCUMULATING_PREFIX)


def period_value(index: Mapping[tuple[int, str], float], target: Target) -> float:
    """Return a target's value over its period.

    Parameters
    ----------
    index : mapping of (int, str) to float
        The account values by ``(year, account)``.
    target : Target
        The target.

    Returns
    -------
    float
        The sum of the account over the target's period when it accumulates, and its value at the
        period's end year when it does not.
    """
    if accumulates(target.account):
        return sum(index.get((offset, target.account), 0.0) for offset in target.cell_offsets())
    return index.get((target.end_offset(), target.account), 0.0)


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


def flow_period_ends(target: Target, years: int) -> list[int]:
    """Return the year each of a flow target's periods ends on.

    A flow target constrains the shape of an account's profile, one value per period and in the
    order :func:`flow_values` returns them. The periods are the ones whose **end** year falls in the
    target's window, which is the reference implementation's convention and the same one
    :meth:`Target.cell_years` uses.

    Parameters
    ----------
    target : Target
        A target whose ``flow`` is ``"even"`` or ``"ndy"``.
    years : int
        The horizon, in years; the window's end when ``flow_end`` is not set.

    Returns
    -------
    list of int
        The end year of each period of the window, ascending.
    """
    width = max(1, target.period_width)
    stop = target.flow_end if target.flow_end is not None else years
    # Periods end on offsets width-1, 2*width-1, ...; the window is half-open.
    return [end for end in range(width - 1, stop, width) if end >= target.flow_start]


def flow_reference_end(target: Target, years: int) -> int:
    """Return the period an even-flow comparison is made against.

    It is the last period of the window by default, or the period whose window contains
    ``flow_reference``. That period contributes no value of its own — the reference's own report
    carries a zero in its row — which is why a series and a period list are not always the same
    length.

    Parameters
    ----------
    target : Target
        A target whose ``flow`` is ``"even"``.
    years : int
        The horizon, in years; the window's end when ``flow_end`` is not set.

    Returns
    -------
    int
        The end year of the reference period, or 0 when the window holds none.
    """
    ends = flow_period_ends(target, years)
    if not ends:
        return 0
    if target.flow_reference is None:
        return ends[-1]
    width = max(1, target.period_width)
    for end in ends:
        if end - width + 1 <= target.flow_reference <= end:
            return end
    return ends[0]


def flow_series(
    index: Mapping[tuple[int, str], float],
    target: Target,
    years: int,
    pending: Mapping[tuple[int, str], float] | None = None,
) -> dict[int, float]:
    """Return a flow target's value per period, keyed by the year each period ends on.

    This is what a report needs and what a comparison against a reference report needs: one
    value per period of the window, with the period an even-flow comparison is made against
    carrying zero, which is how the reference's own report has it. :func:`flow_values` gives the
    same values without the periods attached, which is what the objective prices.

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
    dict of int to float
        The percent value per period end year.
    """

    def reported(value: float) -> float:
        """Report a value: a period with nothing to compare against is satisfied.

        Returns
        -------
        float
            The value, or 0.0 where it is not finite.
        """
        # The reference's own report holds a zero where the balance it divides by is empty —
        # measured on the 2026 sample's no-treatment scenario, where every period reports 0.0 —
        # so a report and a comparison carry a zero. The objective still prices such a period as
        # infinite (`flow_penalty`), which is its documented behaviour and a separate question.
        return 0.0 if not math.isfinite(value) else value

    ends = flow_period_ends(target, years)
    values = [reported(value) for value in flow_values(index, target, years, pending)]
    if target.flow == "ndy":
        return dict(zip(ends, values, strict=False))
    reference = flow_reference_end(target, years)
    others = [end for end in ends if end != reference]
    return {**dict(zip(others, values, strict=False)), reference: 0.0}


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
      ``100 * (x_p - x_{p-1}) / x_{p-1}``. Every period in the window is compared, the first of
      them with the period immediately before the window when one exists.

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
    account = target.account
    # The period grid is anchored at zero and each period **ends** at a multiple of its width, which
    # is the reference's convention (see `Target.cell_years`): the C5 model's period 1 ends at year
    # 10 and covers years 1-10, so a window from year 101 to 200 holds the periods ending at 110
    # through 200. A window that reaches back past year 0 contributes nothing, which is how the
    # reference's initial snapshot period is expressed.
    ends = flow_period_ends(target, years)
    if target.flow == "ndy" and ends and ends[0] - width >= 0:
        # A non-declining window includes its first period, which compares with the period before
        # the window, so the series starts one period earlier than the window does.
        ends = [ends[0] - width, *ends]
    periods: list[float] = []
    accumulating = accumulates(account)
    for end in ends:
        # a period's value follows the same rule as a level target's: an accumulating account sums
        # its years, and a level — which is what a flow on a growing stock constrains — is read at
        # the period's end. Summing a level over ten years would make the flow ten times its size.
        if not accumulating:
            cell = (end, account)
            total = index.get(cell, 0.0)
            if pending is not None:
                total += pending.get(cell, 0.0)
            periods.append(total)
            continue
        total = 0.0
        for year in range(max(0, end - width + 1), end + 1):
            cell = (year, account)
            total += index.get(cell, 0.0)
            if pending is not None:
                total += pending.get(cell, 0.0)
        periods.append(total)
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
        reference_end = flow_reference_end(target, years)
        reference = ends.index(reference_end) if reference_end in ends else 0
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
    ``minimum: -1`` and ``maximum: 1`` is a one-percent-either-way safe range: around the reference
    period for ``even``, and around the previous period for ``ndy``, where a minimum of ``-1``
    tolerates a one-percent decline and a maximum of ``1`` tolerates a one-percent rise. Either side
    may be left out; with only a minimum, growth is free.

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
    horizon = max((offset for offset, _ in index), default=-1) + 1
    total = 0.0
    for target in targets:
        if not target.active:
            continue
        if target.flow:
            total += flow_penalty(index, target, horizon)
            continue
        total += penalty(period_value(index, target), target)
    return total


def _value_index(values: pd.DataFrame) -> dict[tuple[int, str], float]:
    """Index an account-values frame by ``(offset, account)``."""
    return {
        (int(float(str(row.offset))), str(row.account)): float(str(row.value))
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
        account); such a target is read at its period's end year. Defaults to None, which applies
        :func:`accumulates`: a ``product.`` account sums its period, everything else is a level.

    Returns
    -------
    list of float
        One penalty per target.
    """
    index = _value_index(values)
    horizon = max((offset for offset, _ in index), default=-1) + 1
    penalties: list[float] = []
    for target in targets:
        if not target.active:
            penalties.append(0.0)
            continue
        if target.flow:
            penalties.append(flow_penalty(index, target, horizon))
            continue
        if point_in_time is not None and point_in_time(target.account):
            # a caller that knows an account is a level, whatever its name says
            value = index.get((target.end_offset(), target.account), 0.0)
        else:
            value = period_value(index, target)
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


def _optional_int(entry: Mapping[str, object], key: str) -> int | None:
    """Return an optional integer field from a YAML target entry."""
    value = entry.get(key)
    return None if value is None else int(float(str(value)))


def load_targets(path: Path) -> list[Target]:
    """Load targets from a YAML file.

    The file is a mapping with a ``targets`` list. Each entry names one accounting period
    with ``period`` (period 1 is the first accounting period and period 0 the initial
    snapshot) and any of ``minimum``, ``maximum``, ``min_weight``, ``max_weight``,
    ``period_width`` (years per period), ``shape`` (``linear`` or ``non_linear``), the flow
    keys ``flow`` (``even`` or ``ndy``), ``flow_start_period`` and ``flow_end_period``
    (inclusive period window), ``flow_reference_period``, and ``active``.

    ``year`` and the year-based flow keys are still accepted for older files; a period key
    takes precedence when both are present.

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
    targets: list[Target] = []
    for entry in entries:
        period = _optional_int(entry, "period")
        year = _optional_int(entry, "year")
        if period is None and year is None:
            raise ValueError(f"target {entry.get('account')!r} needs 'period' (or a legacy 'year')")
        targets.append(
            Target(
                account=str(entry["account"]),
                year=year or 0,
                period=period,
                minimum=entry.get("minimum"),
                maximum=entry.get("maximum"),
                min_weight=float(entry.get("min_weight", 1.0)),
                max_weight=float(entry.get("max_weight", 1.0)),
                period_width=int(entry.get("period_width", 1)),
                shape=str(entry.get("shape", "linear")),
                flow=str(entry.get("flow", "")),
                flow_start=int(entry.get("flow_start", 0)),
                flow_end=_optional_int(entry, "flow_end"),
                flow_reference=_optional_int(entry, "flow_reference"),
                flow_start_period=_optional_int(entry, "flow_start_period"),
                flow_end_period=_optional_int(entry, "flow_end_period"),
                flow_reference_period=_optional_int(entry, "flow_reference_period"),
                active=bool(entry.get("active", True)),
            )
        )
    return targets
