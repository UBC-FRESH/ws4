"""Weighted-goal objective over account values.

Each target names an account and a year with a minimum, a maximum, or both. The
penalty is the weighted shortfall below the minimum plus the weighted excess above
the maximum; the objective is the total penalty (lower is better).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml


@dataclass(frozen=True)
class Target:
    """One goal-programming target.

    Attributes
    ----------
    account : str
        The account label the target applies to.
    year : int
        The year the target applies to.
    minimum : float or None
        The lower bound; a value below it is penalized.
    maximum : float or None
        The upper bound; a value above it is penalized.
    min_weight : float
        The weight on the shortfall below the minimum.
    max_weight : float
        The weight on the excess above the maximum.
    """

    account: str
    year: int
    minimum: float | None = None
    maximum: float | None = None
    min_weight: float = 1.0
    max_weight: float = 1.0


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
        total += target.min_weight * (target.minimum - value)
    if target.maximum is not None and value > target.maximum:
        total += target.max_weight * (value - target.maximum)
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
    index: Mapping[tuple[int, str], float] = {
        (int(float(str(row.year))), str(row.account)): float(str(row.value))
        for row in values.itertuples(index=False)
    }
    return sum(penalty(index.get((target.year, target.account), 0.0), target) for target in targets)


def load_targets(path: Path) -> list[Target]:
    """Load targets from a YAML file.

    The file is a mapping with a ``targets`` list; each entry has ``account``,
    ``year``, and any of ``minimum``, ``maximum``, ``min_weight``, and ``max_weight``.

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
        )
        for entry in entries
    ]
