"""FOFEM/Ryan--Amman tree-mortality equation and validation metrics.

The model is the generic FOFEM crown-scorch equation:

``Pm = 1 / (1 + exp(-1.941 - 6.316 * (1 - exp(-BT)) + 0.000535 * CS^2))``

where bark thickness ``BT`` is in inches and crown volume scorched ``CS`` is in percent.
Bark thickness is the species coefficient times DBH in inches. This is a published screening
model, not a BC-calibrated mortality model.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

#: Scene species labels mapped to FTM/PLANTS codes.
SPECIES_CODES: Final[dict[str, str]] = {
    "PL": "PICO",
    "PICO": "PICO",
    "LODGEPOLE": "PICO",
    "FD": "PSME",
    "PSME": "PSME",
    "DOUGLASFIR": "PSME",
    "PY": "PIPO",
    "PIPO": "PIPO",
    "PONDEROSA": "PIPO",
    "SW": "PIGL",
    "PIGL": "PIGL",
    "WHITESPRUCE": "PIGL",
    "SE": "PIEN",
    "PIEN": "PIEN",
    "ENGELMANN": "PIEN",
    "BL": "ABLA",
    "ABLA": "ABLA",
    "SUBAALPINE": "ABLA",
    "ABCO": "ABCO",
    "WHITEFIR": "ABCO",
    "LT": "LAOC",
    "LAOC": "LAOC",
    "LARCH": "LAOC",
    "AT": "POTR5",
    "POTR5": "POTR5",
    "ASPEN": "POTR5",
}

#: Species bark-thickness coefficients from the FTM species table.
BARK_COEFFICIENTS: Final[dict[str, float]] = {
    "PICO": 0.028,
    "PSME": 0.063,
    "PIPO": 0.063,
    "LAOC": 0.063,
    "ABLA": 0.041,
    "ABCO": 0.048,
    "PIEN": 0.036,
    "PIMA": 0.032,
    "PIGL": 0.025,
    "POTR5": 0.044,
}

_INTERCEPT: Final[float] = -1.941
_BARK_COEFFICIENT: Final[float] = 6.316
_SCORCH_COEFFICIENT: Final[float] = 0.000535


def mortality_probability(
    *,
    dbh_cm: float,
    crown_volume_scorched_pct: float,
    bark_coefficient: float,
) -> float:
    """Return FOFEM generic tree-mortality probability.

    Parameters
    ----------
    dbh_cm : float
        Diameter at breast height in centimetres; must be at least 2.54 cm.
    crown_volume_scorched_pct : float
        Crown volume scorched in percent, in [0, 100].
    bark_coefficient : float
        Species bark-thickness coefficient in inches per inch DBH.

    Returns
    -------
    float
        Probability of mortality within three years.

    Raises
    ------
    ValueError
        If a value is outside the equation's applicable range.
    """
    if not 2.54 <= dbh_cm <= 500.0:
        raise ValueError("dbh_cm must be between 2.54 and 500")
    if not 0.0 <= crown_volume_scorched_pct <= 100.0:
        raise ValueError("crown_volume_scorched_pct must be in [0, 100]")
    if bark_coefficient <= 0.0:
        raise ValueError("bark_coefficient must be positive")
    bark_in = bark_coefficient * dbh_cm / 2.54
    logit = (
        _INTERCEPT
        - _BARK_COEFFICIENT * (1.0 - math.exp(-bark_in))
        + _SCORCH_COEFFICIENT * crown_volume_scorched_pct**2
    )
    return 1.0 / (1.0 + math.exp(-logit))


def species_mortality(
    *,
    species_code: str,
    dbh_cm: float,
    crown_volume_scorched_pct: float,
) -> float:
    """Return mortality probability for a supported species code.

    Parameters
    ----------
    species_code : str
        PLANTS species code, such as ``PICO``.
    dbh_cm : float
        Diameter at breast height in centimetres.
    crown_volume_scorched_pct : float
        Crown volume scorched in percent.

    Returns
    -------
    float
        Probability of mortality within three years.

    Raises
    ------
    KeyError
        If the species has no bark-thickness coefficient.
    """
    try:
        coefficient = BARK_COEFFICIENTS[species_code.upper()]
    except KeyError as error:
        raise KeyError(f"no bark-thickness coefficient for {species_code!r}") from error
    return mortality_probability(
        dbh_cm=dbh_cm,
        crown_volume_scorched_pct=crown_volume_scorched_pct,
        bark_coefficient=coefficient,
    )


def crown_volume_scorched_pct(
    *,
    flame_length_m: float,
    height_m: float,
    crown_ratio: float,
) -> float:
    """Estimate crown volume scorched from flame length and crown geometry.

    Parameters
    ----------
    flame_length_m : float
        Local flame length in metres.
    height_m : float
        Tree height in metres.
    crown_ratio : float
        Live crown length divided by height, in [0, 1].

    Returns
    -------
    float
        Crown volume scorched in percent, in [0, 100].
    """
    if flame_length_m < 0.0:
        raise ValueError("flame_length_m must be non-negative")
    if height_m <= 0.0:
        raise ValueError("height_m must be positive")
    if not 0.0 <= crown_ratio <= 1.0:
        raise ValueError("crown_ratio must be in [0, 1]")
    if flame_length_m == 0.0 or crown_ratio == 0.0:
        return 0.0
    flame_ft = flame_length_m / 0.3048
    scorch_ft = (flame_ft / 0.45) ** 2.174 * 0.667
    scorch_m = scorch_ft * 0.3048
    crown_length = height_m * crown_ratio
    crown_base = height_m - crown_length
    scorched_length = min(crown_length, max(0.0, scorch_m - crown_base))
    if crown_length <= 0.0:
        return 0.0
    value = 100.0 * (scorched_length * (2.0 * crown_length - scorched_length) / crown_length**2)
    return float(value)


def tree_mortality_probability(
    *,
    species: str,
    dbh_cm: float,
    flame_length_m: float,
    height_m: float,
    crown_ratio: float,
) -> float | None:
    """Return screening mortality probability for one scene tree.

    Parameters
    ----------
    species : str
        Scene species label.
    dbh_cm : float
        Diameter at breast height in centimetres.
    flame_length_m : float
        Local flame length in metres.
    height_m : float
        Tree height in metres.
    crown_ratio : float
        Live crown length divided by height.

    Returns
    -------
    float or None
        Probability in [0, 1], or None for an unsupported species.
    """
    code = SPECIES_CODES.get(species.upper().replace(" ", "").replace("-", ""))
    if code is None:
        return None
    scorch = crown_volume_scorched_pct(
        flame_length_m=flame_length_m,
        height_m=height_m,
        crown_ratio=crown_ratio,
    )
    return species_mortality(
        species_code=code,
        dbh_cm=dbh_cm,
        crown_volume_scorched_pct=scorch,
    )


def rank_auc(observed: np.ndarray, predicted: np.ndarray) -> float:
    """Return the rank-based area under the ROC curve.

    Parameters
    ----------
    observed : numpy.ndarray
        Binary observations.
    predicted : numpy.ndarray
        Predicted probabilities.

    Returns
    -------
    float
        AUC, or NaN when one class is absent.
    """
    y = np.asarray(observed, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if y.shape != p.shape or y.ndim != 1:
        raise ValueError("observed and predicted must be one-dimensional and equal length")
    positive = y == 1.0
    negative = y == 0.0
    n_positive = int(positive.sum())
    n_negative = int(negative.sum())
    if not n_positive or not n_negative:
        return float("nan")
    order = np.argsort(p)
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1, dtype=float)
    return float(
        (ranks[positive].sum() - n_positive * (n_positive + 1) / 2.0) / (n_positive * n_negative)
    )


def brier_score(observed: np.ndarray, predicted: np.ndarray) -> float:
    """Return the Brier score.

    Parameters
    ----------
    observed : numpy.ndarray
        Binary observations.
    predicted : numpy.ndarray
        Predicted probabilities.

    Returns
    -------
    float
        Mean squared error.
    """
    y = np.asarray(observed, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if y.shape != p.shape or y.ndim != 1:
        raise ValueError("observed and predicted must be one-dimensional and equal length")
    return float(np.mean((p - y) ** 2))
