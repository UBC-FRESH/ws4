"""Cheap candidate screening for a feature reduction goal.

The exact seed prices every candidate chain through the simulator, which is correct but expensive
on a large instance. A feature goal has a direct curve representation: the block's current feature
value and the treated track's value are in the compiled tables. This module ranks blocks by that
direct cost per unit of feature reduction, so the exact seed can score a shortlist of blocks. It is
a screening heuristic, not the schedule: the exact seed still verifies every chosen chain.

Only a ``feature.`` goal with product cost ceilings is screened. Anything else returns ``None`` and
the caller uses the full candidate set.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd

from .objective import Target


def _curve_values(curves: pd.DataFrame) -> dict[tuple[int, float], float]:
    """Return the curve table keyed by ``(curve_id, x)``."""
    return {
        (int(curve), float(x)): float(y)
        for curve, x, y in zip(curves["curve_id"], curves["x"], curves["y"], strict=True)
    }


def _value_at(
    table: Mapping[tuple[int, float], float],
    by_track: Mapping[int, int],
    track: int,
    age: float,
) -> float | None:
    """Return a track's feature value at an age, using x=0 when the age is absent."""
    curve = by_track.get(track)
    if curve is None:
        return None
    value = table.get((curve, float(age)))
    if value is None:
        value = table.get((curve, 0.0))
    return value


def feature_goal_blocks(
    dataset: Path,
    goal_account: str,
    targets: Sequence[Target],
    year: int,
    limit: int = 40_000,
) -> set[int] | None:
    """Return the blocks with the cheapest direct reduction per unit of cost.

    Parameters
    ----------
    dataset : Path
        The compiled dataset directory.
    goal_account : str
        The feature account to reduce, for example ``feature.FuelHazard``.
    targets : sequence of Target
        The active targets; their product maxima are the cost accounts.
    year : int
        The year the feature goal reads.
    limit : int, optional
        The most blocks to keep, by ascending cost per feature unit.

    Returns
    -------
    set of int or None
        The shortlisted block ids, or None when the goal is not a feature, the tables are
        missing, or no cost account maps to a treatment.
    """
    if not goal_account.startswith("feature.") or limit < 1:
        return None
    root = Path(dataset)
    required = (
        "blocks.parquet",
        "treatments.parquet",
        "features.parquet",
        "curves.parquet",
        "products.parquet",
    )
    if not all((root / name).is_file() for name in required):
        return None
    blocks = pd.read_parquet(root / "blocks.parquet")
    treatments = pd.read_parquet(root / "treatments.parquet")
    features = pd.read_parquet(root / "features.parquet")
    curves = pd.read_parquet(root / "curves.parquet")
    products = pd.read_parquet(root / "products.parquet")
    table = _curve_values(curves)
    goal_rows = features[features["label"] == goal_account]
    if goal_rows.empty:
        return None
    by_track = {
        int(track): int(curve)
        for track, curve in zip(goal_rows["track_id"], goal_rows["curve_id"], strict=True)
    }
    cost_curves: dict[str, int] = {}
    for target in targets:
        if not target.account.startswith("product.") or target.maximum is None:
            continue
        rows = products[products["label"] == target.account]
        for treatment, curve in zip(rows["treatment"], rows["curve_id"], strict=True):
            cost_curves.setdefault(str(treatment), int(curve))
    if not cost_curves:
        return None
    treatment_windows: dict[tuple[int, str], tuple[float, float, int]] = {}
    for row in treatments.itertuples(index=False):
        treatment_windows.setdefault(
            (int(str(row.track_id)), str(row.treatment)),
            (float(str(row.begin)), float(str(row.end)), int(str(row.new_track))),
        )
    ranked: list[tuple[float, int]] = []
    for row in blocks.itertuples(index=False):
        block = int(str(row.block_id))
        track = int(str(row.track_id))
        offset = float(str(row.offset))
        area = float(str(row.area_ha))
        before = _value_at(table, by_track, track, offset)
        if before is None:
            continue
        for treatment, cost_curve in cost_curves.items():
            window = treatment_windows.get((track, treatment))
            if window is None:
                continue
            begin, end, new_track = window
            if not begin <= offset <= end:
                continue
            after = _value_at(table, by_track, new_track, float(year))
            if after is None:
                continue
            reduction = max(before - after, 0.0) * area
            if reduction <= 0.0:
                continue
            cost = table.get((cost_curve, 0.0), 0.0) * area
            if cost <= 0.0:
                continue
            ranked.append((cost / reduction, block))
    if not ranked:
        return None
    ranked.sort()
    return {block for _, block in ranked[:limit]}
