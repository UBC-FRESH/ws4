"""Tests for the PDF-to-isopleth helpers."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from ws4.sdmd.digitise import (
    PathCandidate,
    PrintedLabel,
    calibrate_axes,
    load_spec,
    match_printed_labels,
    ordered_curve,
    read_labelled_curves,
)


def test_calibrate_axes_round_trips_a_log_axis() -> None:
    """The log fit maps printed ticks back to their values."""
    calibration = calibrate_axes(
        ((200.0, 100.0), (2000.0, 300.0)),
        ((0.01, 400.0), (0.1, 200.0)),
    )
    assert calibration.tph(100.0) == pytest.approx(200.0)
    assert calibration.tph(300.0) == pytest.approx(2000.0)
    assert calibration.volume(400.0) == pytest.approx(0.01)
    assert calibration.volume(200.0) == pytest.approx(0.1)
    assert calibration.x_for_tph(632.4555) == pytest.approx(200.0, abs=1e-3)
    assert calibration.y_for_volume(0.0316228) == pytest.approx(300.0, abs=1e-3)


def test_calibrate_axes_needs_two_distinct_ticks() -> None:
    """A single tick or a repeated position cannot define an axis."""
    with pytest.raises(ValueError, match="at least two"):
        calibrate_axes(((200.0, 100.0),), ((0.01, 400.0), (0.1, 200.0)))
    with pytest.raises(ValueError, match="distinct"):
        calibrate_axes(((200.0, 100.0), (300.0, 100.0)), ((0.01, 400.0), (0.1, 200.0)))


def test_ordered_curve_sorts_and_averages_duplicates() -> None:
    """Curve points are sorted by TPH and duplicate positions are averaged."""
    curve = ordered_curve(((1000.0, 0.2), (500.0, 0.1), (1000.0, 0.3)))
    assert curve == ((500.0, 0.1), (1000.0, 0.25))


def test_ordered_curve_rejects_non_positive_points() -> None:
    """Zero or negative diagram coordinates are refused."""
    with pytest.raises(ValueError, match="positive"):
        ordered_curve(((0.0, 0.1), (500.0, 0.2)))


def test_match_printed_labels_assigns_nearest_distinct_paths() -> None:
    """Two labels close to two paths are assigned one-to-one."""
    paths = (
        PathCandidate(10, ((100.0, 200.0), (200.0, 180.0))),
        PathCandidate(11, ((100.0, 100.0), (200.0, 80.0))),
    )
    labels = (PrintedLabel(6.0, 150.0, 191.0), PrintedLabel(12.0, 150.0, 89.0))
    matches = match_printed_labels(labels, paths)
    assert [(item.value, item.path_index) for item in matches] == [(6.0, 10), (12.0, 11)]


def test_match_printed_labels_refuses_a_duplicate_path() -> None:
    """Two labels may not claim the same path."""
    paths = (PathCandidate(10, ((100.0, 200.0), (200.0, 180.0))),)
    labels = (PrintedLabel(6.0, 150.0, 191.0), PrintedLabel(12.0, 150.0, 189.0))
    with pytest.raises(ValueError, match="both claim"):
        match_printed_labels(labels, paths)


def test_match_printed_labels_refuses_a_distant_label() -> None:
    """A label far from every candidate is not assigned by guesswork."""
    paths = (PathCandidate(10, ((100.0, 200.0), (200.0, 180.0))),)
    labels = (PrintedLabel(6.0, 500.0, 500.0),)
    with pytest.raises(ValueError, match="nearest path"):
        match_printed_labels(labels, paths, max_distance=5.0)


def test_match_printed_labels_refuses_unordered_values() -> None:
    """A larger label must sit on a higher curve for top height and QMD."""
    paths = (
        PathCandidate(10, ((100.0, 200.0), (200.0, 180.0))),
        PathCandidate(11, ((100.0, 100.0), (200.0, 80.0))),
    )
    labels = (PrintedLabel(6.0, 150.0, 89.0), PrintedLabel(12.0, 150.0, 191.0))
    with pytest.raises(ValueError, match="not vertically ordered"):
        match_printed_labels(labels, paths)


def test_read_labelled_curves_matches_printed_labels(tmp_path: Path) -> None:
    """A dashed pair and its printed labels import as two paths."""
    pymupdf = pytest.importorskip("pymupdf")
    path = tmp_path / "synthetic.pdf"
    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.draw_line((50, 250), (350, 150), color=(0, 0, 0), width=1.5, dashes="[ 3 2 ] 0")
    page.draw_line((50, 150), (350, 50), color=(0, 0, 0), width=1.5, dashes="[ 3 2 ] 0")
    page.insert_text((100, 231), "6 m", fontsize=10)
    page.insert_text((100, 131), "12 m", fontsize=10)
    document.save(path)
    calibration = calibrate_axes(((100.0, 50.0), (1000.0, 350.0)), ((0.01, 250.0), (1.0, 50.0)))
    curves = read_labelled_curves(
        path,
        dash="[ 3 2 ] 0",
        width=1.5,
        unit="m",
        calibration=calibration,
    )
    assert [(curve.value, curve.path_index) for curve in curves] == [(6.0, 0), (12.0, 1)]
    assert curves[0].points[0] == pytest.approx((100.0, 0.01))
    assert curves[1].points[-1] == pytest.approx((1000.0, 1.0))


def test_load_spec_reads_the_review_decisions(tmp_path: Path) -> None:
    """A spec carries the axis ticks, path indices, and printed values."""
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "diagram_id": "test",
                "species_group": "FDI",
                "region": "Interior",
                "bec_zone": "IDF",
                "bec_subzone": "dk",
                "site_index": 18.0,
                "citation": "test",
                "version": "1",
                "licence": "test",
                "pdf_path": "source.pdf",
                "x_ticks": [[200.0, 100.0], [2000.0, 300.0]],
                "y_ticks": [[0.01, 400.0], [0.1, 200.0]],
                "curves": [
                    {
                        "kind": "qmd",
                        "value": 20.0,
                        "unit": "cm",
                        "path_index": 4,
                        "dash": "[ 6 4 ] 0",
                        "width": 1.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    spec = load_spec(spec_path)
    assert spec.pdf_path == tmp_path / "source.pdf"
    assert spec.curves[0].path_index == 4
    assert spec.curves[0].dash == "[ 6 4 ] 0"
    assert math.isclose(spec.site_index, 18.0)
