"""Trace a raster curve for curves that are not a single PDF vector path.

The SDMD PDFs draw most isopleths as dashed vector paths. A few crown-closure
curves are printed as dot glyphs, so the vector reader cannot see them. This
module traces those curves on a rendered page using a list of approximate anchor
points and a vertical search window.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .digitise import AxisCalibration

__all__ = ["TraceResult", "trace_raster_curve"]


@dataclass(frozen=True)
class TraceResult:
    """The points recovered from one raster trace.

    Attributes
    ----------
    points : tuple of tuple of float
        The ordered ``(tph, mean_tree_volume_m3)`` points.
    missed : int
        Number of anchors where no dark pixel was found in the search window.
    """

    points: tuple[tuple[float, float], ...]
    missed: int


def trace_raster_curve(
    image: Image.Image,
    calibration: AxisCalibration,
    anchors: Sequence[tuple[float, float]],
    *,
    scale: float = 1.0,
    dark_threshold: int = 90,
    window: int = 22,
) -> TraceResult:
    """Trace a curve from approximate data-space anchors.

    Parameters
    ----------
    image : PIL.Image.Image
        The rendered page.
    calibration : AxisCalibration
        The PDF-axis calibration.
    anchors : sequence of tuple of float
        Approximate ``(tph, mean_tree_volume_m3)`` anchors along the curve.
    scale : float
        Pixels per PDF point, normally ``dpi / 72``.
    dark_threshold : int
        Luminance below which a pixel is treated as curve ink.
    window : int
        Vertical search half-window, in pixels.

    Returns
    -------
    TraceResult
        The recovered points and the number of missed anchors.

    Raises
    ------
    ValueError
        If fewer than two points are recovered.
    """
    if scale <= 0:
        raise ValueError("scale must be positive")
    if window < 0:
        raise ValueError("window must not be negative")
    array = np.asarray(image.convert("L"))
    points: list[tuple[float, float]] = []
    previous: int | None = None
    missed = 0
    for tph, volume in anchors:
        x_pixel = round(calibration.x_for_tph(tph) * scale)
        expected = round(calibration.y_for_volume(volume) * scale)
        low = max(0, expected - window)
        high = min(array.shape[0], expected + window + 1)
        if x_pixel < 0 or x_pixel >= array.shape[1] or low >= high:
            missed += 1
            continue
        dark = np.where(array[low:high, x_pixel] < dark_threshold)[0]
        if len(dark) == 0:
            missed += 1
            continue
        candidates = [low + int(row) for row in dark]
        target = expected if previous is None else previous
        chosen = min(candidates, key=lambda row: abs(row - target))
        previous = chosen
        points.append((float(tph), calibration.volume(chosen / scale)))
    if len(points) < 2:
        raise ValueError("the raster trace recovered fewer than two points")
    points.sort(key=lambda point: point[0])
    return TraceResult(points=tuple(points), missed=missed)
