"""Tests for the observed-perimeter comparison harness."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from ws4.fire.comparison import (
    ComparisonError,
    centroid,
    compare_masks,
    observed_mask,
    orientation,
    perimeter_length,
    rasterize_rings,
    reference_weather,
    run_dogrib_case,
)
from ws4.fire.observed import ObservedGrid, load_dogrib

FIXTURE = Path(__file__).parent / "fixtures" / "fire" / "dogrib"


def test_compare_masks_reports_area_perimeter_overlap_and_orientation() -> None:
    grid = ObservedGrid(3, 3, 0.0, 0.0, 10.0, -9999.0, "local")
    simulated = np.array([[1, 1, 0], [1, 0, 0], [0, 0, 0]], dtype=bool)
    observed = np.array([[1, 1, 1], [1, 0, 0], [0, 0, 0]], dtype=bool)

    metrics = compare_masks(simulated, observed, grid)

    assert metrics.area_sim_ha == pytest.approx(0.03)
    assert metrics.area_obs_ha == pytest.approx(0.04)
    assert metrics.area_bias == pytest.approx(-0.25)
    assert metrics.perimeter_sim_m == pytest.approx(80.0)
    assert metrics.perimeter_obs_m == pytest.approx(100.0)
    assert metrics.perimeter_bias == pytest.approx(-0.2)
    assert metrics.iou == pytest.approx(0.75)
    assert metrics.sorensen == pytest.approx(6 / 7)
    assert metrics.centroid_distance_m == pytest.approx(math.hypot(4.1666667, 0.8333333))


def test_rasterize_rings_and_perimeter_length() -> None:
    grid = ObservedGrid(4, 4, 0.0, 0.0, 10.0, -9999.0, "local")
    ring = ((0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0))

    mask = rasterize_rings((ring,), grid)

    assert mask.sum() == 4
    assert perimeter_length(mask, 10.0) == pytest.approx(80.0)
    assert centroid(mask, grid) == pytest.approx((10.0, 10.0))


def test_orientation_is_axial() -> None:
    horizontal = np.zeros((5, 9), dtype=bool)
    horizontal[2, :] = True
    vertical = horizontal.T
    assert orientation(horizontal) == pytest.approx(0.0)
    assert orientation(vertical) == pytest.approx(90.0)


def test_reference_weather_matches_the_dogrib_stream() -> None:
    fire = load_dogrib(FIXTURE)
    weather = reference_weather(fire)

    assert weather["ffmc"] == pytest.approx(92.7, abs=0.2)
    assert weather["bui"] == pytest.approx(105.0, abs=0.5)
    assert weather["wind_kmh"] == pytest.approx(21.0)
    assert weather["wind_direction_deg"] == pytest.approx(267.6, abs=1.0)


def test_observed_masks_match_the_recorded_perimeters() -> None:
    fire = load_dogrib(FIXTURE)
    start = observed_mask(fire, 0)
    final = observed_mask(fire, -1)

    assert start.sum() * fire.grid.cell_size_m**2 / 10_000.0 == pytest.approx(935.1, rel=0.01)
    assert final.sum() * fire.grid.cell_size_m**2 / 10_000.0 == pytest.approx(10223.3, rel=0.01)


def test_dogrib_case_runs_and_serializes() -> None:
    fire = load_dogrib(FIXTURE)
    case = run_dogrib_case(fire, scenario="test", duration_min=60.0)

    assert case.start_cells > 0
    assert case.growth.burned_area_ha > 0.0
    assert 0.0 <= case.metrics.iou <= 1.0
    assert 0.0 <= case.metrics.sorensen <= 1.0
    assert json.loads(json.dumps(case.to_dict()))["scenario"] == "test"


def test_empty_observed_mask_fails() -> None:
    grid = ObservedGrid(2, 2, 0.0, 0.0, 10.0, -9999.0, "local")
    with pytest.raises(ComparisonError, match="empty"):
        compare_masks(np.zeros((2, 2), dtype=bool), np.zeros((2, 2), dtype=bool), grid)


def test_bad_ring_fails() -> None:
    grid = ObservedGrid(2, 2, 0.0, 0.0, 10.0, -9999.0, "local")
    with pytest.raises(ComparisonError, match="three points"):
        rasterize_rings((((0.0, 0.0), (1.0, 1.0)),), grid)
