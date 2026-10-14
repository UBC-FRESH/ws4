"""Curve evaluation for the simulator."""

from __future__ import annotations

import numpy as np
import pandas as pd


def curve_value(curves: pd.DataFrame, curve_id: int, x: float) -> float:
    """Evaluate a long-format curve at ``x`` by linear interpolation.

    Values below the first point and above the last point are clamped to the
    endpoint values, matching the model's interpolation contract.

    Parameters
    ----------
    curves : pandas.DataFrame
        The ``curves`` table, with ``curve_id``, ``x``, and ``y`` columns.
    curve_id : int
        The curve to evaluate.
    x : float
        The domain value (for example, an offset age).

    Returns
    -------
    float
        The interpolated value, or ``0.0`` when the curve has no points.
    """
    points = curves[curves["curve_id"] == curve_id].sort_values("x")
    if points.empty:
        return 0.0
    xs = points["x"].to_numpy(dtype=float)
    ys = points["y"].to_numpy(dtype=float)
    return float(np.interp(x, xs, ys))
