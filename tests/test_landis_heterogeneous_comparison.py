"""Heterogeneous WS4-vs-Biomass_core spatial comparison."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.ecosystem.fire import synthetic_grid
from ws4.ecosystem.landis import (
    LandisSpeciesTraits,
    LandisSuccessionConfig,
    LandisSuccessionProcess,
)
from ws4.ecosystem.process import ProcessContext
from ws4.ecosystem.state import CohortState

_FIXTURE = (
    Path(__file__).parent / "fixtures" / "landis_heterogeneous_reference" / "simulationOutput.csv"
)


def _state() -> CohortState:
    """Build the four-fragment heterogeneous initial state."""
    _schema, base, _edges = synthetic_grid(1, 4)
    values = (
        (10, 500.0, 20, 500.0),
        (50, 2000.0, 60, 2000.0),
        (100, 5000.0, 80, 3000.0),
        (20, 1000.0, 30, 1000.0),
    )
    rows: list[dict[str, object]] = []
    for fragment, (age_pice, b_pice, age_popu, b_popu) in enumerate(values, start=1):
        rows.extend(
            (
                {
                    "fragment_id": fragment,
                    "cohort_id": 1,
                    "species": "Pice_Gla",
                    "age": age_pice,
                    "area_fraction": 1.0,
                    "biomass_t_ha": b_pice,
                    "fuel_t_ha": 0.0,
                    "snag_t_ha": 0.0,
                    "attributes_json": "{}",
                },
                {
                    "fragment_id": fragment,
                    "cohort_id": 2,
                    "species": "Popu_Tre",
                    "age": age_popu,
                    "area_fraction": 1.0,
                    "biomass_t_ha": b_popu,
                    "fuel_t_ha": 0.0,
                    "snag_t_ha": 0.0,
                    "attributes_json": "{}",
                },
            )
        )
    return CohortState(
        cohorts=pd.DataFrame(rows, columns=base.cohorts.columns),
        schema=base.schema,
        fragment_areas=base.fragment_areas,
    )


def _trajectory() -> list[float]:
    """Run eleven annual LANDIS updates and return mean biomass."""
    traits = {
        "Pice_Gla": LandisSpeciesTraits(
            max_b=30000, max_anpp=1000, growthcurve=0.25, mortalityshape=15, longevity=200
        ),
        "Popu_Tre": LandisSpeciesTraits(
            max_b=30000, max_anpp=1000, growthcurve=0.25, mortalityshape=25, longevity=150
        ),
    }
    process = LandisSuccessionProcess(
        LandisSuccessionConfig(species=traits, succession_timestep=10, stage="nonSpinup")
    )
    state = _state()
    values = []
    for year in range(11):
        context = ProcessContext(year, "growth", "p211")
        for event in process.events(state, context):
            state = process.apply(state, event)
        by_fragment = (
            (state.cohorts["biomass_t_ha"] * state.cohorts["area_fraction"])
            .groupby(state.cohorts["fragment_id"])
            .sum()
        )
        values.append(float(by_fragment.mean()))
    return values


def test_heterogeneous_trajectory_matches_the_reference() -> None:
    trajectory = _trajectory()
    reference = pd.read_csv(_FIXTURE)
    expected = float(str(reference.loc[2, "Biomass"]))

    assert trajectory[0] == pytest.approx(4420.0, abs=1e-3)
    assert trajectory[-1] == pytest.approx(10809.75, abs=1e-3)
    assert (trajectory[-1] - expected) / expected == pytest.approx(-0.00113, abs=1e-5)
