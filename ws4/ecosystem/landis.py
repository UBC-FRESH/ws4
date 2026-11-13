"""LANDIS-II Biomass Succession kernel equations.

This is an original Python implementation of the published LANDIS-II Biomass Succession
equations. The Predictive Ecology ``Biomass_core`` tests are used as a reference oracle; no
third-party code is copied. The functions operate on a cohort table with the same columns used
by the published tests and by the WS4 cohort state.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import pandas as pd

LANDIS_KERNEL_VERSION: Final[str] = "landis-biomass-succession-v3.2.1"
STAGES: Final[tuple[str, ...]] = ("spinup", "nonSpinup")


class LandisError(ValueError):
    """Raised when a LANDIS kernel input is invalid."""


def _stage(stage: str) -> str:
    """Return one of the two accepted stages."""
    if stage not in STAGES:
        raise LandisError(f"stage must be one of: {', '.join(STAGES)}")
    return stage


def _required(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    """Require columns and numeric values."""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise LandisError(f"cohort table is missing: {', '.join(missing)}")


def calculate_sum_b(
    cohort_data: pd.DataFrame,
    *,
    last_reg: int,
    current_time: int,
    succession_timestep: int,
) -> pd.DataFrame:
    """Return cohort data with LANDIS ``sumB`` per pixel group.

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``pixelGroup``, ``age``, and ``B``.
    last_reg : int
        Last regeneration time.
    current_time : int
        Current simulation time.
    succession_timestep : int
        Succession time step.

    Returns
    -------
    pandas.DataFrame
        A copy with the ``sumB`` column.
    """
    _required(cohort_data, ("pixelGroup", "age", "B"))
    if succession_timestep <= 0:
        raise LandisError("succession_timestep must be positive")
    frame = cohort_data.copy()
    if current_time == last_reg + succession_timestep - 2:
        include = frame["age"] > succession_timestep
    else:
        include = frame["age"] >= succession_timestep
    sums = frame.loc[include].groupby("pixelGroup", sort=False)["B"].sum()
    frame["sumB"] = frame["pixelGroup"].map(sums).fillna(0.0)
    return frame


def calculate_competition(cohort_data: pd.DataFrame, *, stage: str = "nonSpinup") -> pd.DataFrame:
    """Return cohort data with LANDIS ``bAP`` and ``bPM`` competition indices.

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``pixelGroup``, ``age``, ``B``, ``maxB``, and ``sumB``.
    stage : str, optional
        ``spinup`` or ``nonSpinup`` (default).

    Returns
    -------
    pandas.DataFrame
        A copy with ``bAP`` and ``bPM``.
    """
    stage = _stage(stage)
    _required(cohort_data, ("pixelGroup", "age", "B", "maxB", "sumB"))
    frame = cohort_data.copy()
    frame["bAP"] = np.nan
    frame["bPM"] = np.nan
    eligible = frame["age"] > 0 if stage == "spinup" else pd.Series(True, index=frame.index)
    if not bool(eligible.any()):
        return frame
    subset = frame.loc[eligible]
    potential = np.maximum(1.0, subset["maxB"] - subset["sumB"] + subset["B"])
    b_ap: pd.Series = subset["B"] / potential
    multiplier = np.maximum(np.power(np.maximum(subset["B"], 0.0), 0.95), 1.0)
    totals = (
        pd.Series(multiplier, index=subset.index).groupby(subset["pixelGroup"]).transform("sum")
    )
    frame.loc[eligible, "bAP"] = b_ap
    frame.loc[eligible, "bPM"] = multiplier / totals
    return frame


def calculate_anpp(cohort_data: pd.DataFrame, *, stage: str = "nonSpinup") -> pd.DataFrame:
    """Return cohort data with LANDIS actual ANPP (``aNPPAct``).

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``age``, ``bAP``, ``bPM``, ``growthcurve``, and ``maxANPP``.
    stage : str, optional
        ``spinup`` or ``nonSpinup`` (default).

    Returns
    -------
    pandas.DataFrame
        A copy with ``aNPPAct``.
    """
    stage = _stage(stage)
    _required(cohort_data, ("age", "bAP", "bPM", "growthcurve", "maxANPP"))
    frame = cohort_data.copy()
    frame["aNPPAct"] = np.nan
    eligible = frame["age"] > 0 if stage == "spinup" else pd.Series(True, index=frame.index)
    if not bool(eligible.any()):
        return frame
    subset = frame.loc[eligible]
    exponent = np.power(subset["bAP"], subset["growthcurve"])
    raw = subset["maxANPP"] * math.e * exponent * np.exp(-exponent) * subset["bPM"]
    frame.loc[eligible, "aNPPAct"] = np.minimum(subset["maxANPP"] * subset["bPM"], raw)
    return frame


def calculate_growth_mortality(
    cohort_data: pd.DataFrame, *, stage: str = "nonSpinup"
) -> pd.DataFrame:
    """Return cohort data with LANDIS developmental mortality (``mBio``).

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``age``, ``B``, ``bAP``, ``bPM``, and ``maxANPP``.
    stage : str, optional
        ``spinup`` or ``nonSpinup`` (default).

    Returns
    -------
    pandas.DataFrame
        A copy with ``mBio``.
    """
    stage = _stage(stage)
    _required(cohort_data, ("age", "B", "bAP", "bPM", "maxANPP"))
    frame = cohort_data.copy()
    frame["mBio"] = np.nan
    eligible = frame["age"] > 0 if stage == "spinup" else pd.Series(True, index=frame.index)
    if not bool(eligible.any()):
        return frame
    subset = frame.loc[eligible]
    base = np.where(
        subset["bAP"] > 1.0,
        subset["maxANPP"] * subset["bPM"],
        subset["maxANPP"] * (2.0 * subset["bAP"]) / (1.0 + subset["bAP"]) * subset["bPM"],
    )
    capped = np.minimum(np.minimum(subset["B"], base), subset["maxANPP"] * subset["bPM"])
    frame.loc[eligible, "mBio"] = capped
    return frame


def calculate_age_mortality(
    cohort_data: pd.DataFrame,
    *,
    stage: str = "nonSpinup",
    spinup_mortality_fraction: float = 0.0,
) -> pd.DataFrame:
    """Return cohort data with LANDIS age-related mortality (``mAge``).

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``age``, ``B``, ``longevity``, and ``mortalityshape``.
    stage : str, optional
        ``spinup`` or ``nonSpinup`` (default).
    spinup_mortality_fraction : float, optional
        Additional annual mortality during spin-up (default zero).

    Returns
    -------
    pandas.DataFrame
        A copy with ``mAge``.
    """
    stage = _stage(stage)
    _required(cohort_data, ("age", "B", "longevity", "mortalityshape"))
    if spinup_mortality_fraction < 0.0 or not math.isfinite(spinup_mortality_fraction):
        raise LandisError("spinup_mortality_fraction must be finite and non-negative")
    frame = cohort_data.copy()
    frame["mAge"] = np.nan
    eligible = frame["age"] > 0 if stage == "spinup" else pd.Series(True, index=frame.index)
    if not bool(eligible.any()):
        return frame
    subset = frame.loc[eligible]
    age_mortality = subset["B"] * (
        np.exp((subset["age"] / subset["longevity"]) * subset["mortalityshape"])
        / np.exp(subset["mortalityshape"])
    )
    if stage == "spinup":
        age_mortality = age_mortality + subset["B"] * spinup_mortality_fraction
    frame.loc[eligible, "mAge"] = np.minimum(subset["B"], age_mortality)
    return frame
