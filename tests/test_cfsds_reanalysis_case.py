"""Tests for the CFSDS hourly-reanalysis fixture."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.fire.observed import load_cfsds_reanalysis_case

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fire" / "cfsds_2003_526"


def test_reanalysis_fixture_loads() -> None:
    """The generated fixture satisfies the observed-fire contract."""
    fire = load_cfsds_reanalysis_case(FIXTURE)
    assert fire.fire_id == "2003_526"
    assert fire.grid.crs == "EPSG:26911"
    assert fire.grid.ncols == 90
    assert fire.grid.nrows == 76
    assert len(fire.perimeters) == 2
    assert fire.perimeters[0].area_ha < fire.perimeters[-1].area_ha
    assert fire.event_start < fire.event_end
    assert fire.weather["local_time"].diff().dropna().eq(pd.Timedelta(hours=1)).all()
    assert fire.weather["local_time"].iloc[0] >= fire.event_start
    assert fire.weather["local_time"].iloc[-1] <= fire.event_end
    assert fire.fuel_type_at(0, 0) is None or isinstance(fire.fuel_type_at(0, 0), str)
