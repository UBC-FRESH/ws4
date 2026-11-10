"""Sample a P156 growth field at synthetic tree positions.

The scene package normally animates whole fragments because the P144 event log is
fragment-level. A growth run has cell-level arrival times, so this module turns that field
into a per-tree ignition schedule. The result is a continuous front inside each stand while
the event log remains the fragment-level audit record.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
import pandas as pd

from ws4.fire.growth import GrowthResult, directional_ros

from .trees import TreeInventory


class IgnitionSamplingError(ValueError):
    """Raised when a growth field cannot be sampled at the tree positions."""


TreeFireOutcome = Literal["unburned", "scorched", "torched", "consumed"]


def classify_tree_fire_outcome(
    *,
    flame_length_m: float,
    height_m: float,
    crown_ratio: float,
    burned: bool,
) -> TreeFireOutcome:
    """Classify a tree's visual post-fire outcome.

    Parameters
    ----------
    flame_length_m : float
        Local flame length in metres.
    height_m : float
        Tree height in metres.
    crown_ratio : float
        Live crown length divided by height, in [0, 1].
    burned : bool
        Whether the tree was reached by the fire.

    Returns
    -------
    str
        ``unburned``, ``scorched``, ``torched``, or ``consumed``.

    Raises
    ------
    IgnitionSamplingError
        If an input is invalid.

    Notes
    -----
    This is a visual class, not a validated tree-mortality model. Scorching is assigned when
    the flame stays below the crown base; torching when it reaches the crown but not the top;
    consumption when it reaches the tree top.
    """
    if not isinstance(burned, bool):
        raise IgnitionSamplingError("burned must be a boolean")
    flame = _non_negative(flame_length_m, "flame_length_m")
    height = _positive(height_m, "height_m")
    crown = _fraction(crown_ratio, "crown_ratio")
    if not burned:
        return "unburned"
    crown_base = height * (1.0 - crown)
    if flame >= height:
        return "consumed"
    if flame >= crown_base:
        return "torched"
    return "scorched"


def sample_tree_ignition(
    trees: TreeInventory,
    growth: GrowthResult,
    *,
    cell_size_m: float,
    margin_m: float = 30.0,
    origin_xy: tuple[float, float] | None = None,
    flame_length_m: float = 0.0,
    smoke_strength: float = 0.0,
    burn_duration: float = 2.0,
) -> pd.DataFrame:
    """Sample a growth field at every tree position.

    Parameters
    ----------
    trees : TreeInventory
        The synthetic tree inventory.
    growth : GrowthResult
        A completed P156 growth run.
    cell_size_m : float
        Growth-grid cell size in metres.
    margin_m : float, optional
        Margin around the tree bounds used when ``origin_xy`` is omitted (default 30).
    origin_xy : tuple of float or None, optional
        Lower-left growth-grid origin. None uses the tree bounds minus ``margin_m``.
    flame_length_m : float, optional
        Head flame length in metres, used to scale the local flame intensity.
    smoke_strength : float, optional
        Head smoke strength in [0, 1], used to scale the local smoke.
    burn_duration : float, optional
        Per-tree burn duration in scene time units (default 2).

    Returns
    -------
    pandas.DataFrame
        One row per tree with ``tree_id``, ``fragment_id``, ``ignition_time``,
        ``burn_duration``, ``flame_intensity``, ``smoke_strength``, and
        ``post_fire_state``.

    Raises
    ------
    IgnitionSamplingError
        If the inputs are invalid or the growth grid does not cover the trees.
    """
    if not isinstance(trees, TreeInventory):
        raise IgnitionSamplingError("trees must be a TreeInventory")
    if not isinstance(growth, GrowthResult):
        raise IgnitionSamplingError("growth must be a GrowthResult")
    cell = _positive(cell_size_m, "cell_size_m")
    margin = _non_negative(margin_m, "margin_m")
    duration = _positive(burn_duration, "burn_duration")
    flame_length = _non_negative(flame_length_m, "flame_length_m")
    smoke = _fraction(smoke_strength, "smoke_strength")
    if not trees.trees:
        raise IgnitionSamplingError("tree inventory is empty")
    min_x = min(tree.x for tree in trees.trees) - margin
    min_y = min(tree.y for tree in trees.trees) - margin
    origin = (min_x, min_y) if origin_xy is None else (float(origin_xy[0]), float(origin_xy[1]))
    rows, cols = growth.ignition_time_min.shape
    finite = np.isfinite(growth.ignition_time_min)
    if not bool(finite.any()):
        raise IgnitionSamplingError("growth field has no reached cells")
    first = np.unravel_index(
        int(np.argmin(np.where(finite, growth.ignition_time_min, np.inf))), (rows, cols)
    )
    ignition_x = origin[0] + (int(first[1]) + 0.5) * cell
    ignition_y = origin[1] + (int(first[0]) + 0.5) * cell
    head_ros = growth.head_ros_m_min
    output: list[dict[str, object]] = []
    for tree in trees.trees:
        col = int((tree.x - origin[0]) / cell)
        row = int((tree.y - origin[1]) / cell)
        if row < 0 or row >= rows or col < 0 or col >= cols:
            continue
        time_min = float(growth.ignition_time_min[row, col])
        if not math.isfinite(time_min):
            output.append(
                {
                    "tree_id": tree.tree_id,
                    "fragment_id": tree.fragment_id,
                    "ignition_time": float("nan"),
                    "burn_duration": 0.0,
                    "flame_intensity": 0.0,
                    "smoke_strength": 0.0,
                    "post_fire_state": "unburned",
                }
            )
            continue
        angle = math.degrees(math.atan2(tree.x - ignition_x, tree.y - ignition_y)) % 360.0
        local_ros = directional_ros(
            head_ros,
            growth.length_to_breadth,
            angle - growth.effective_wind.azimuth_deg,
        )
        ratio = local_ros / head_ros if head_ros > 0.0 else 0.0
        local_flame_length = flame_length * max(0.05, ratio)
        local_flame = min(1.0, local_flame_length / 10.0) if flame_length > 0.0 else 0.0
        outcome = classify_tree_fire_outcome(
            flame_length_m=local_flame_length,
            height_m=tree.height_m,
            crown_ratio=tree.crown_ratio,
            burned=True,
        )
        output.append(
            {
                "tree_id": tree.tree_id,
                "fragment_id": tree.fragment_id,
                "ignition_time": time_min,
                "burn_duration": duration,
                "flame_intensity": local_flame,
                "smoke_strength": min(1.0, smoke * max(0.05, ratio)),
                "post_fire_state": outcome,
            }
        )
    if not output:
        raise IgnitionSamplingError("growth grid does not cover any tree")
    return pd.DataFrame(
        output,
        columns=[
            "tree_id",
            "fragment_id",
            "ignition_time",
            "burn_duration",
            "flame_intensity",
            "smoke_strength",
            "post_fire_state",
        ],
    )


def _number(value: object, field: str) -> float:
    """Return a finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IgnitionSamplingError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise IgnitionSamplingError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


def _non_negative(value: object, field: str) -> float:
    """Return a finite, non-negative float."""
    number = _number(value, field)
    if number < 0.0:
        raise IgnitionSamplingError(f"{field} must be non-negative")
    return number


def _positive(value: object, field: str) -> float:
    """Return a finite, strictly positive float."""
    number = _number(value, field)
    if number <= 0.0:
        raise IgnitionSamplingError(f"{field} must be positive")
    return number


def _fraction(value: object, field: str) -> float:
    """Return a number in [0, 1]."""
    number = _number(value, field)
    if number < 0.0 or number > 1.0:
        raise IgnitionSamplingError(f"{field} must be between 0 and 1")
    return number
