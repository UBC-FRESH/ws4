"""Bridge the raster fire-growth result into the cohort process."""

from __future__ import annotations

import numpy as np
import pytest
from ws4.ecosystem.events import Event
from ws4.ecosystem.fire import synthetic_grid
from ws4.ecosystem.growth_fire import GrowthFireSource, build_growth_fire_source
from ws4.ecosystem.process import ProcessContext
from ws4.ecosystem.state import CohortState
from ws4.fire.growth import FragmentIgnition, FragmentSupport, GrowthConfig, SiteGrid


def _state() -> CohortState:
    """Return one fragment with one live cohort and 100 ha."""
    _schema, base, _edges = synthetic_grid(1, 1)
    frame = base.cohorts.copy()
    return CohortState(
        cohorts=frame.reset_index(drop=True),
        schema=base.schema,
        fragment_areas={1: 100.0},
    )


def test_growth_source_emits_area_fraction_and_applies_mortality() -> None:
    source = GrowthFireSource(
        {
            0: (
                FragmentIgnition(
                    fragment_id=1, ignition_time_min=30.0, area_ha=50.0, burned_cells=2
                ),
            )
        }
    )
    events = source.events(_state(), ProcessContext(0, "propagation", "growth"))

    assert isinstance(events[0], Event)
    assert events[0].event_type == "fire"
    assert events[0].magnitude == pytest.approx(0.5)
    updated = source.apply_many(_state(), events)
    updated.check_area_conservation()
    dead = updated.cohorts[updated.cohorts["biomass_t_ha"] == 0.0]
    assert float(dead["area_fraction"].sum()) == pytest.approx(0.5)


def test_growth_source_builds_from_a_site_grid() -> None:
    grid = SiteGrid(
        fuel_type="C2",
        rows=5,
        cols=5,
        cell_size_m=100.0,
        ffmc=90.0,
        bui=60.0,
        wind_kmh=10.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
        burnable=np.ones((5, 5), dtype=bool),
    )
    fragments = np.ones((5, 5), dtype=int)
    source = build_growth_fire_source(
        grid,
        GrowthConfig(ignition_cells=((2, 2),), max_time_min=30.0, snapshot_interval_min=10.0),
        fragments,
        {0: ((2, 2),)},
    )

    assert source.ignitions
    assert source.ignitions[0][0].fragment_id == 1
    assert source.ignitions[0][0].area_ha > 0.0


def test_growth_source_builds_from_a_fragment_support() -> None:
    grid = SiteGrid(
        fuel_type="C2",
        rows=5,
        cols=5,
        cell_size_m=100.0,
        ffmc=90.0,
        bui=60.0,
        wind_kmh=10.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
        burnable=np.ones((5, 5), dtype=bool),
    )
    support = FragmentSupport(
        rows=5,
        cols=5,
        cell_index=np.array([12]),
        fragment_id=np.array([7]),
        weight=np.array([0.5]),
    )
    source = build_growth_fire_source(
        grid,
        GrowthConfig(ignition_cells=((2, 2),), max_time_min=30.0, snapshot_interval_min=10.0),
        support,
        {0: ((2, 2),)},
    )

    assert source.ignitions[0][0].fragment_id == 7
    assert source.ignitions[0][0].area_ha == pytest.approx(0.5)
