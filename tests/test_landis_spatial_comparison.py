"""WS4-vs-Biomass_core spatial trajectory comparison."""

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

_FIXTURE = Path(__file__).parent / "fixtures" / "landis_spatial_reference" / "simulationOutput.csv"


def _state() -> CohortState:
    """Build the P200 initial cohorts as two WS4 fragments."""
    _schema, base, _edges = synthetic_grid(1, 2)
    rows = []
    for fragment in (1, 2):
        for cohort_id, species, age in ((1, "Pice_Gla", 20), (2, "Popu_Tre", 30)):
            rows.append(
                {
                    "fragment_id": fragment,
                    "cohort_id": cohort_id,
                    "species": species,
                    "age": age,
                    "area_fraction": 1.0,
                    "biomass_t_ha": 1000.0,
                    "fuel_t_ha": 0.0,
                    "snag_t_ha": 0.0,
                    "attributes_json": "{}",
                }
            )
    return CohortState(
        cohorts=pd.DataFrame(rows, columns=base.cohorts.columns),
        schema=base.schema,
        fragment_areas=base.fragment_areas,
    )


def _trajectory() -> list[float]:
    """Run ten annual LANDIS steps and return mean biomass per pixel."""
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
    for year in range(10):
        context = ProcessContext(year, "growth", "p202")
        for event in process.events(state, context):
            state = process.apply(state, event)
        by_fragment = (
            (state.cohorts["biomass_t_ha"] * state.cohorts["area_fraction"])
            .groupby(state.cohorts["fragment_id"])
            .sum()
        )
        values.append(float(by_fragment.mean()))
    return values


def test_ws4_trajectory_matches_the_reference_at_year_one() -> None:
    trajectory = _trajectory()
    reference = pd.read_csv(_FIXTURE)

    assert trajectory[0] == pytest.approx(2694.6167, abs=1e-3)
    assert reference.loc[1, "Biomass"] == 2694


def test_ws4_trajectory_has_a_known_year_ten_mismatch() -> None:
    trajectory = _trajectory()
    reference = pd.read_csv(_FIXTURE)
    simulated = trajectory[-1]
    expected = float(str(reference.loc[2, "Biomass"]))

    assert simulated == pytest.approx(8832.0582, abs=1e-3)
    assert simulated < expected
    assert (simulated - expected) / expected == pytest.approx(-0.0664, abs=1e-4)
