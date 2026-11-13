"""Exact reference tests for the LANDIS-II succession kernel.

The expected values come from the public Predictive Ecology ``Biomass_core`` tests. They are
numeric reference facts, not copied implementation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from ws4.ecosystem.landis import (
    LandisError,
    calculate_age_mortality,
    calculate_anpp,
    calculate_competition,
    calculate_growth_mortality,
    calculate_sum_b,
)

_ANPP_SPINUP = (np.nan,) * 10 + (
    381.8944,
    408.3121,
    420.7571,
    427.8567,
    432.226,
    434.9859,
    436.7111,
    437.7309,
    438.2493,
    438.4,
    572.8416,
    612.4682,
    631.1357,
    641.785,
    648.339,
    652.4788,
    655.0666,
    656.5963,
    657.3739,
    657.6,
    763.7888,
    816.6243,
    841.5142,
    855.7134,
    864.4519,
    869.9718,
    873.4221,
    875.4617,
    876.4985,
    876.8,
    954.736,
    1020.7804,
    1051.8928,
    1069.6417,
    1080.5649,
    1087.4647,
    1091.7776,
    1094.3271,
    1095.6232,
    1096.0,
)

_ANPP_NONSPINUP = (
    190.9472,
    204.1561,
    210.3786,
    213.9283,
    216.113,
    217.4929,
    218.3555,
    218.8654,
    219.1246,
    219.2,
    *_ANPP_SPINUP[10:],
)

_GROWTH_REF = (
    73.0667,
    125.2571,
    164.4,
    194.8444,
    219.2,
    219.2,
    219.2,
    219.2,
    219.2,
    219.2,
    146.1333,
    250.5143,
    328.8,
    389.6889,
    438.4,
    438.4,
    438.4,
    438.4,
    438.4,
    438.4,
    219.2,
    375.7714,
    493.2,
    584.5333,
    657.6,
    657.6,
    657.6,
    657.6,
    657.6,
    657.6,
    292.2667,
    501.0286,
    657.6,
    700.0,
    700.0,
    700.0,
    700.0,
    700.0,
    700.0,
    700.0,
    365.3333,
    626.2857,
    700.0,
    700.0,
    700.0,
    700.0,
    700.0,
    700.0,
    700.0,
    700.0,
)


def _anpp_frame(*, spinup: bool) -> pd.DataFrame:
    """Build the ANPP reference grid."""
    b_ap = np.tile(np.arange(0.1, 1.01, 0.1), 5)
    b_pm = np.repeat(np.arange(0.2, 1.01, 0.2), 10)
    age = np.array([0] * 10 + list(range(11, 51))) if spinup else np.arange(1, 51)
    return pd.DataFrame(
        {
            "bAP": b_ap,
            "bPM": b_pm,
            "age": age,
            "growthcurve": 0.25,
            "maxANPP": 1096.0,
        }
    )


def test_anpp_matches_the_reference_values() -> None:
    spinup = calculate_anpp(_anpp_frame(spinup=True), stage="spinup")
    non_spinup = calculate_anpp(_anpp_frame(spinup=False), stage="nonSpinup")

    np.testing.assert_allclose(spinup["aNPPAct"].to_numpy(), _ANPP_SPINUP, atol=1e-4)
    np.testing.assert_allclose(non_spinup["aNPPAct"].to_numpy(), _ANPP_NONSPINUP, atol=1e-4)


def _growth_frame() -> pd.DataFrame:
    """Build the growth/mortality reference grid."""
    b_ap = np.tile(np.arange(0.2, 2.01, 0.2), 10)
    b_pm = np.tile(np.repeat(np.arange(0.2, 1.01, 0.2), 10), 2)
    age = np.repeat([0, 1], 50)
    return pd.DataFrame(
        {
            "bAP": b_ap,
            "bPM": b_pm,
            "age": age,
            "B": 700.0,
            "maxANPP": 1096.0,
        }
    )


def test_growth_mortality_matches_the_reference_values() -> None:
    frame = _growth_frame()
    spinup = calculate_growth_mortality(frame, stage="spinup")
    non_spinup = calculate_growth_mortality(frame, stage="nonSpinup")

    expected_spinup = np.array([*[np.nan] * 50, *_GROWTH_REF])
    expected_non_spinup = np.array([*_GROWTH_REF, *_GROWTH_REF])
    np.testing.assert_allclose(spinup["mBio"].to_numpy(), expected_spinup, atol=1e-4)
    np.testing.assert_allclose(non_spinup["mBio"].to_numpy(), expected_non_spinup, atol=1e-4)


def _competition_frame() -> pd.DataFrame:
    """Build the competition reference rows."""
    return pd.DataFrame(
        {
            "pixelGroup": [*[1] * 13, *[2] * 10],
            "age": [0, 0, 0, 0, 0, 6, 7, 8, 9, 10, 20, 30, 50, 0, 0, 0, 0, 5, 6, 7, 8, 9, 10],
            "B": [*range(1, 14), *range(1, 11)],
            "maxB": 40.0,
            "sumB": [36.0] * 13 + [0.0] * 10,
        }
    )


def test_competition_matches_the_reference_values() -> None:
    frame = _competition_frame()
    spinup = calculate_competition(frame, stage="spinup")
    non_spinup = calculate_competition(frame, stage="nonSpinup")

    expected_spinup_bap = (
        [np.nan] * 5
        + [
            0.6,
            0.6364,
            0.6667,
            0.6923,
            0.7143,
            0.7333,
            0.75,
            0.7647,
        ]
        + [np.nan] * 4
        + [0.1111, 0.1304, 0.1489, 0.1667, 0.1837, 0.2]
    )
    expected_spinup_bpm = (
        [np.nan] * 5
        + [
            0.0809,
            0.0937,
            0.1063,
            0.1189,
            0.1314,
            0.1439,
            0.1563,
            0.1686,
        ]
        + [np.nan] * 4
        + [0.1135, 0.135, 0.1563, 0.1774, 0.1984, 0.2193]
    )
    expected_non_spinup_bap = [
        0.2,
        0.3333,
        0.4286,
        0.5,
        0.5556,
        0.6,
        0.6364,
        0.6667,
        0.6923,
        0.7143,
        0.7333,
        0.75,
        0.7647,
        0.0244,
        0.0476,
        0.0698,
        0.0909,
        0.1111,
        0.1304,
        0.1489,
        0.1667,
        0.1837,
        0.2,
    ]
    expected_non_spinup_bpm = [
        0.0122,
        0.0236,
        0.0347,
        0.0456,
        0.0563,
        0.067,
        0.0775,
        0.088,
        0.0984,
        0.1088,
        0.1191,
        0.1294,
        0.1396,
        0.0199,
        0.0385,
        0.0566,
        0.0744,
        0.092,
        0.1094,
        0.1267,
        0.1438,
        0.1608,
        0.1778,
    ]

    np.testing.assert_allclose(
        spinup["bAP"].fillna(-1).to_numpy(), np.nan_to_num(expected_spinup_bap, nan=-1), atol=1e-4
    )
    np.testing.assert_allclose(
        spinup["bPM"].fillna(-1).to_numpy(), np.nan_to_num(expected_spinup_bpm, nan=-1), atol=1e-4
    )
    np.testing.assert_allclose(non_spinup["bAP"].to_numpy(), expected_non_spinup_bap, atol=1e-4)
    np.testing.assert_allclose(non_spinup["bPM"].to_numpy(), expected_non_spinup_bpm, atol=1e-4)


def _sum_b_frame() -> pd.DataFrame:
    """Build the sumB reference rows."""
    return pd.DataFrame(
        {
            "pixelGroup": [1] * 13 + [2] * 10,
            "age": [*range(1, 11), 20, 30, 50, *range(1, 11)],
            "B": list(range(1, 14)) + list(range(1, 11)),
        }
    )


def test_sum_b_matches_the_reference_values() -> None:
    frame = _sum_b_frame()
    eighteen = calculate_sum_b(frame, last_reg=10, current_time=18, succession_timestep=10)
    nineteen = calculate_sum_b(frame, last_reg=10, current_time=19, succession_timestep=10)

    assert eighteen["sumB"].tolist() == [36.0] * 13 + [0.0] * 10
    assert nineteen["sumB"].tolist() == [46.0] * 13 + [10.0] * 10


def test_age_mortality_caps_at_biomass() -> None:
    frame = pd.DataFrame(
        {
            "age": [0, 10, 100],
            "B": [100.0, 100.0, 100.0],
            "longevity": [100.0, 100.0, 100.0],
            "mortalityshape": [2.0, 2.0, 2.0],
        }
    )
    result = calculate_age_mortality(frame, stage="nonSpinup")

    assert (result["mAge"] <= 100.0 + 1e-9).all()


def test_bad_stage_and_missing_columns_fail() -> None:
    with pytest.raises(LandisError, match="stage"):
        calculate_anpp(pd.DataFrame(), stage="bad")
    with pytest.raises(LandisError, match="missing"):
        calculate_competition(pd.DataFrame({"age": [1]}))
