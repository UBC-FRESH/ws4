"""Tests for trajectory and kernel controls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ws4.fire.comparison import ComparisonError, DogribCase, observed_mask, run_observed_case
from ws4.fire.observed import load_cfsds_reanalysis_case

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fire" / "cfsds_2009_147"


def _run(
    *,
    snapshot_interval_min: float | None = None,
    neighbor_radius: int = 2,
    flat_terrain: bool = False,
) -> DogribCase:
    """Run one fixture with optional controls."""
    fire = load_cfsds_reanalysis_case(FIXTURE)
    metadata = json.loads((FIXTURE / "metadata.json").read_text(encoding="utf-8"))
    return run_observed_case(
        fire,
        scenario="test",
        ffmc=float(metadata["ffmc"]),
        bui=float(metadata["bui"]),
        duration_min=float(metadata["duration_min"]),
        initial_mask=observed_mask(fire, 0),
        snapshot_interval_min=snapshot_interval_min,
        neighbor_radius=neighbor_radius,
        flat_terrain=flat_terrain,
    )


def test_daily_snapshots_and_radius_one() -> None:
    """Daily snapshots and radius 1 are available."""
    result = _run(snapshot_interval_min=1440.0, neighbor_radius=1)
    assert len(result.growth.snapshots) > 1
    assert result.growth.snapshots[1].time_min == 1440.0


def test_invalid_trajectory_controls_fail() -> None:
    """Invalid interval and radius fail clearly."""
    with pytest.raises(ComparisonError, match="neighbor_radius"):
        _run(neighbor_radius=0)
    with pytest.raises(ComparisonError, match="positive"):
        _run(snapshot_interval_min=0.0)


def test_flat_terrain_runs() -> None:
    """The flat-terrain diagnostic preserves the output contract."""
    result = _run(flat_terrain=True)
    assert result.growth.burned_area_ha > 0
