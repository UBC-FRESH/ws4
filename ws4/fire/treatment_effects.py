"""Measured pre/post fuel-treatment effects from the public FFS dataset."""

from __future__ import annotations

import pandas as pd

UNIT_KEYS: tuple[str, str, str] = ("SITE_CODE", "UNIT_CODE", "TREATMENT_NAME")
SURFACE_FUEL_COLUMNS: tuple[str, ...] = (
    "ONE_HOUR_FUELS",
    "TEN_HOUR_FUELS",
    "HUNDRED_HOUR_FUELS",
    "SOUND_1000_HOUR_FUELS",
    "ROTTEN_1000_HOUR_FUELS",
)


class TreatmentEffectError(ValueError):
    """Raised when FFS treatment-effect inputs are invalid."""


def surface_fuel_total(frame: pd.DataFrame) -> pd.Series:
    """Return total surface fuel load from the FFS fuel-size columns.

    Parameters
    ----------
    frame : pandas.DataFrame
        FFS unit-fuel table.

    Returns
    -------
    pandas.Series
        Sum of the one-, ten-, hundred-, and thousand-hour fuel loads.
    """
    missing = sorted(set(SURFACE_FUEL_COLUMNS) - set(frame.columns))
    if missing:
        raise TreatmentEffectError(f"missing fuel columns: {', '.join(missing)}")
    values = frame.loc[:, SURFACE_FUEL_COLUMNS].fillna(0.0).to_numpy(dtype=float).sum(axis=1)
    return pd.Series(values, index=frame.index, name="surface_fuel_total")


def pair_pre_post(
    frame: pd.DataFrame,
    value: str,
    *,
    pre_code: int = -1,
    post_code: int = 1,
) -> pd.DataFrame:
    """Pair pre- and post-treatment values for each FFS unit.

    Parameters
    ----------
    frame : pandas.DataFrame
        FFS table with unit keys, treatment name, sample year code, and value.
    value : str
        Numeric value column.
    pre_code : int, optional
        Pre-treatment sample year code (default -1).
    post_code : int, optional
        Post-treatment sample year code (default 1).

    Returns
    -------
    pandas.DataFrame
        One row per unit with ``pre``, ``post``, and ``pct_change``.
    """
    required = {*UNIT_KEYS, "SAMPLE_YEAR_CODE", value}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise TreatmentEffectError(f"missing columns: {', '.join(missing)}")
    selected = frame.loc[
        frame["SAMPLE_YEAR_CODE"].isin([pre_code, post_code]),
        [*UNIT_KEYS, "SAMPLE_YEAR_CODE", value],
    ].copy()
    selected[value] = pd.to_numeric(selected[value], errors="coerce")
    selected = selected.dropna(subset=[value])
    paired = selected.pivot_table(
        index=list(UNIT_KEYS),
        columns="SAMPLE_YEAR_CODE",
        values=value,
        aggfunc="first",
    )
    if pre_code not in paired.columns or post_code not in paired.columns:
        raise TreatmentEffectError("pre and post sample codes must both be present")
    paired = paired.rename(columns={pre_code: "pre", post_code: "post"}).dropna()
    if (paired["pre"] == 0.0).any():
        raise TreatmentEffectError("pre-treatment values must be non-zero")
    paired["pct_change"] = (paired["post"] - paired["pre"]) / paired["pre"] * 100.0
    return paired.reset_index()


def summarize_effects(
    paired: pd.DataFrame,
    *,
    treatment: str = "TREATMENT_NAME",
) -> pd.DataFrame:
    """Summarize percent change by treatment.

    Parameters
    ----------
    paired : pandas.DataFrame
        Output of :func:`pair_pre_post`.
    treatment : str, optional
        Treatment label column (default ``TREATMENT_NAME``).

    Returns
    -------
    pandas.DataFrame
        Count, median, quartiles, minimum, and maximum percent change.
    """
    if treatment not in paired.columns or "pct_change" not in paired.columns:
        raise TreatmentEffectError("paired frame needs treatment and pct_change columns")
    summary = paired.groupby(treatment)["pct_change"].agg(
        n="count",
        median="median",
        q25=lambda values: values.quantile(0.25),
        q75=lambda values: values.quantile(0.75),
        minimum="min",
        maximum="max",
    )
    return summary.reset_index()
