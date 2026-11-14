"""Parity against the published Biomass_core R kernel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from ws4.ecosystem.landis import (
    calculate_age_mortality,
    calculate_anpp,
    calculate_competition,
    calculate_growth_mortality,
    calculate_sum_b,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "landis_r_parity"


def _read(name: str) -> pd.DataFrame:
    """Read one fixture CSV."""
    return pd.read_csv(_FIXTURES / name)


def _same(actual: pd.Series, expected: pd.Series) -> None:
    """Assert numeric parity with the R output."""
    np.testing.assert_allclose(actual.to_numpy(), expected.to_numpy(), atol=1e-8, rtol=0)


def test_age_mortality_matches_the_r_kernel() -> None:
    frame = _read("age_in.csv")
    _same(
        calculate_age_mortality(frame, stage="spinup", spinup_mortality_fraction=0.001)["mAge"],
        _read("age_spinup_out.csv")["mAge"],
    )
    _same(
        calculate_age_mortality(frame, stage="nonSpinup", spinup_mortality_fraction=0.001)["mAge"],
        _read("age_non_out.csv")["mAge"],
    )


def test_anpp_matches_the_r_kernel() -> None:
    frame = _read("anpp_in.csv")
    _same(calculate_anpp(frame, stage="spinup")["aNPPAct"], _read("anpp_spinup_out.csv")["aNPPAct"])
    _same(
        calculate_anpp(frame, stage="nonSpinup")["aNPPAct"],
        _read("anpp_non_out.csv")["aNPPAct"],
    )


def test_growth_mortality_matches_the_r_kernel() -> None:
    frame = _read("growth_in.csv")
    _same(
        calculate_growth_mortality(frame, stage="spinup")["mBio"],
        _read("growth_spinup_out.csv")["mBio"],
    )
    _same(
        calculate_growth_mortality(frame, stage="nonSpinup")["mBio"],
        _read("growth_non_out.csv")["mBio"],
    )


def test_competition_matches_the_r_kernel() -> None:
    frame = _read("comp_in.csv")
    spinup = calculate_competition(frame, stage="spinup")
    _same(spinup["bAP"], _read("comp_spinup_out.csv")["bAP"])
    _same(spinup["bPM"], _read("comp_spinup_out.csv")["bPM"])
    non_spinup = calculate_competition(frame, stage="nonSpinup")
    _same(non_spinup["bAP"], _read("comp_non_out.csv")["bAP"])
    _same(non_spinup["bPM"], _read("comp_non_out.csv")["bPM"])


def test_sum_b_matches_the_r_kernel() -> None:
    frame = _read("sumb_in.csv")
    _same(
        calculate_sum_b(frame, last_reg=10, current_time=18, succession_timestep=10)["sumB"],
        _read("sumb_18_out.csv")["sumB"],
    )
    _same(
        calculate_sum_b(frame, last_reg=10, current_time=19, succession_timestep=10)["sumB"],
        _read("sumb_19_out.csv")["sumB"],
    )
