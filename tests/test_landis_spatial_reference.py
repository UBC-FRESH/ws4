"""Contract test for the captured spatial Biomass_core reference."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_FIXTURE = Path(__file__).parent / "fixtures" / "landis_spatial_reference" / "simulationOutput.csv"


def test_spatial_reference_fixture_is_stable() -> None:
    frame = pd.read_csv(_FIXTURE)

    assert list(frame.columns) == [
        "ecoregionGroup",
        "NofCell",
        "Year",
        "Biomass",
        "ANPP",
        "Mortality",
        "Regeneration",
    ]
    assert frame["NofCell"].tolist() == [100, 100, 100]
    assert frame["Year"].tolist() == [0, 0, 10]
    assert frame["Biomass"].tolist() == [2000, 2694, 9460]
    assert frame["ANPP"].tolist() == [0, 762, 920]
    assert frame["Mortality"].tolist() == [0, 66, 294]
    assert frame["Regeneration"].tolist() == [0, 0, 2]
