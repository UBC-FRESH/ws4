"""Tests for the standalone carbon-curve compiler helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.carbon.curves import _curve_rows, _schedule_for_curve
from ws4.carbon.libcbm import CarbonRun, CbmDefaultsReference


def test_natural_schedule_is_empty() -> None:
    """A non-regenerating track has no clearcut schedule."""
    schedule = _schedule_for_curve(
        target_track=None,
        treatment=None,
        rotation_age=120,
        mode="cycle",
    )
    assert schedule.empty
    assert list(schedule.columns) == ["block_id", "treatment", "offset"]


def test_single_and_cycle_schedules() -> None:
    """Cycle mode repeats the clearcut and targets the regenerated class after the first cut."""
    single = _schedule_for_curve(
        target_track="managed",
        treatment="cc",
        rotation_age=120,
        mode="single",
    )
    assert len(single) == 1
    assert single.iloc[0]["offset"] == 119
    assert "target_track" not in single.columns

    cycle = _schedule_for_curve(
        target_track="managed",
        treatment="cc",
        rotation_age=120,
        mode="cycle",
    )
    assert len(cycle) == 5
    assert cycle["offset"].tolist() == [119, 239, 359, 479, 599]
    assert pd.isna(cycle.iloc[0]["target_track"])
    assert cycle.iloc[1]["target_track"] == "managed"
    assert cycle.iloc[1]["target_area_ha"] == 1.0


def _run() -> CarbonRun:
    """Return a two-step synthetic run with enough pools for the curve writer."""
    pools = pd.DataFrame(
        {
            "timestep": [0, 1],
            "identifier": [1, 1],
            "SoftwoodMerch": [10.0, 12.0],
            "SoftwoodFoliage": [1.0, 1.2],
            "AboveGroundSlowSoil": [2.0, 2.1],
            "Products": [0.0, 0.5],
        }
    )
    flux = pd.DataFrame(
        {
            "timestep": [0, 1],
            "identifier": [1, 1],
            "DeltaBiomass_AG": [1.0, 1.1],
            "DeltaBiomass_BG": [0.5, 0.6],
            "TurnoverFolLitterInput": [0.2, 0.2],
            "DecaySlowAGToAir": [0.1, 0.1],
            "DisturbanceMerchToAir": [0.0, 0.0],
        }
    )
    return CarbonRun(
        pools=pools,
        flux=flux,
        classifiers=pd.DataFrame(),
        state=pd.DataFrame(),
        libcbm_version="2.10.2",
        defaults=CbmDefaultsReference(
            path=Path("cbm_defaults.db"), version="1.2.9300.391", sha256="b" * 64
        ),
    )


def test_curve_rows_name_stock_and_flux_outputs() -> None:
    """The curve writer emits the documented stock, merch, and emission columns."""
    frame = _curve_rows(_run(), track_name="track-1", start=0, length=1)
    assert list(frame["track_name"].unique()) == ["track-1"]
    assert frame["age"].tolist() == [0, 1]
    assert frame.loc[1, "merch_tc_ha"] == 12.0
    assert frame.loc[1, "ecosystem_tc_ha"] == pytest.approx(15.3)
    assert frame.loc[1, "net_emission_tc_ha"] == pytest.approx(-1.8)
