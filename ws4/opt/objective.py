"""Weighted-goal objective over account values.

Each target names an account and a year with a minimum, a maximum, or both. The
penalty is the weighted shortfall below the minimum plus the weighted excess above
the maximum; the objective is the total penalty (lower is better).
"""

from __future__ import annotations

from collections.abc import Sequence
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
        The number of years the account is summed over for this target.
    shape : str
        The penalty shape: ``"linear"`` adds the weighted deviation, ``"non_linear"`` adds the
        weighted squared deviation (the weight is applied after squaring, matching the default
        non-premultiplied scaling).
    """

    account: str
    year: int
    minimum: float | None = None
    maximum: float | None = None
    min_weight: float = 1.0
    max_weight: float = 1.0
    period_width: int = 1
    shape: str = "linear"

    def __post_init__(self) -> None:
        """Reject an unknown penalty shape."""
        if self.shape not in {"linear", "non_linear"}:
            raise ValueError(f"unknown penalty shape: {self.shape!r}")

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
    total = 0.0
    for target in targets:
        value = sum(index.get((year, target.account), 0.0) for year in target.cell_years())
        total += penalty(value, target)
    return total


def _value_index(values: pd.DataFrame) -> dict[tuple[int, str], float]:
    """Index an account-values frame by ``(year, account)``."""
    return {
        (int(float(str(row.year))), str(row.account)): float(str(row.value))
        for row in values.itertuples(index=False)
    }


def objective_terms(values: pd.DataFrame, targets: Sequence[Target]) -> list[float]:
    """Return the penalty of each target, in order.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values, with ``year``, ``account``, and ``value`` columns.
    targets : sequence of Target
        The targets.

    Returns
    -------
    list of float
        One penalty per target.
    """
    index = _value_index(values)
    return [
        penalty(sum(index.get((year, target.account), 0.0) for year in target.cell_years()), target)
        for target in targets
    ]


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
    ``period_width`` (years per period; the account is summed over them), and ``shape``
    (``linear`` or ``non_linear``).

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
        )
        for entry in entries
    ]
