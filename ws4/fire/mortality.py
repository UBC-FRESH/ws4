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
