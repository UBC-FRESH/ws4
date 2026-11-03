"""Tests for the raster crown-closure trace helper."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw
from ws4.sdmd.digitise import calibrate_axes
from ws4.sdmd.trace import trace_raster_curve


def test_trace_follows_a_dotted_curve() -> None:
    """The tracer recovers points from a dotted diagonal image."""
    calibration = calibrate_axes(((1.0, 0.0), (100.0, 299.0)), ((0.01, 299.0), (1.0, 0.0)))
    image = Image.new("L", (300, 300), 255)
    draw = ImageDraw.Draw(image)
    truth = [(float(tph), 0.2 * (float(tph) / 10.0) ** -0.6) for tph in range(10, 101, 10)]
    for tph, volume in truth:
        x = round(calibration.x_for_tph(tph))
        y = round(calibration.y_for_volume(volume))
        draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill=0)
    result = trace_raster_curve(image, calibration, truth, window=8)
    assert len(result.points) >= 8
    assert result.missed == 0
    for (_, expected), (_, actual) in zip(truth, result.points, strict=True):
        assert actual == max(actual, 0.0)
        assert abs(actual - expected) / expected < 0.15


def test_trace_reports_missing_anchors_and_rejects_an_empty_trace() -> None:
    """A blank image yields misses and no curve."""
    calibration = calibrate_axes(((1.0, 0.0), (100.0, 299.0)), ((0.01, 299.0), (1.0, 0.0)))
    image = Image.new("L", (300, 300), 255)
    with pytest.raises(ValueError, match="fewer than two"):
        trace_raster_curve(image, calibration, ((10.0, 0.1), (20.0, 0.05)), window=3)
