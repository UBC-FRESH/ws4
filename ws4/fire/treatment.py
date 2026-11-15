"""Published fuel-treatment effect evidence and comparison gates.

This module records published treatment-effect ranges and classifies a supplied
treated-versus-untreated metric. It does not simulate a treatment prescription: WS4 has no
thinning, prescribed-fire, or fuel-load treatment pathway yet. A treated simulation must not be
reported as validation against these values until that pathway exists.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

import numpy as np

from .fbp import canonical_fuel_type
from .observed import ObservedFire

Position = Literal["below", "within", "above"]


@dataclass(frozen=True)
class TreatmentEvidence:
    """One published treatment-effect range.

    Parameters
    ----------
    treatment : str
        Treatment label.
    metric : str
        Metric identifier; currently ``severity_reduction_fraction``.
    low : float
        Lower bound of the reported reduction, in [0, 1].
    high : float
        Upper bound of the reported reduction, in [0, 1].
    source : str
        Published source.
    basis : str
        What the range represents and its caveats.
    """

    treatment: str
    metric: str
    low: float
    high: float
    source: str
    basis: str

    def __post_init__(self) -> None:
        """Validate the evidence fields."""
        if not self.treatment or not self.metric or not self.source or not self.basis:
            raise ValueError("treatment evidence fields must be non-empty")
        if not 0.0 <= self.low <= self.high <= 1.0:
            raise ValueError("treatment evidence bounds must be ordered in [0, 1]")

    def position(self, value: float) -> Position:
        """Classify a reduction fraction against the published range.

        Parameters
        ----------
        value : float
            Reduction fraction in [0, 1].

        Returns
        -------
        str
            ``below``, ``within``, or ``above``.
        """
        if not 0.0 <= value <= 1.0:
            raise ValueError("reduction fraction must be in [0, 1]")
        if value < self.low:
            return "below"
        if value > self.high:
            return "above"
        return "within"

    def to_dict(self) -> dict[str, object]:
        """Return the evidence as a JSON-serializable mapping.

        Returns
        -------
        dict
            Treatment, metric, bounds, source, and basis.
        """
        return {
            "treatment": self.treatment,
            "metric": self.metric,
            "low": self.low,
            "high": self.high,
            "source": self.source,
            "basis": self.basis,
        }


# Published values, not universal acceptance thresholds.
TREATMENT_EVIDENCE: Final[tuple[TreatmentEvidence, ...]] = (
    TreatmentEvidence(
        treatment="thinning_plus_prescribed_fire",
        metric="severity_reduction_fraction",
        low=0.62,
        high=0.72,
        source="Davis et al. 2024, Forest Ecology and Management 561:121885",
        basis=(
            "Mean reduction in subsequent wildfire severity within treated areas; "
            "western US conifer forests, not a BC-specific transfer value."
        ),
    ),
    TreatmentEvidence(
        treatment="prescribed_fire_only",
        metric="severity_reduction_fraction",
        low=0.62,
        high=0.62,
        source="Davis et al. 2024, Forest Ecology and Management 561:121885",
        basis="Mean reduction in subsequent wildfire severity within treated areas.",
    ),
    TreatmentEvidence(
        treatment="thinning_plus_pile_burning",
        metric="severity_reduction_fraction",
        low=0.62,
        high=0.62,
        source="Davis et al. 2024, Forest Ecology and Management 561:121885",
        basis="Mean reduction in subsequent wildfire severity within treated areas.",
    ),
    TreatmentEvidence(
        treatment="thinning_only",
        metric="severity_reduction_fraction",
        low=0.27,
        high=0.27,
        source="Davis et al. 2024, Forest Ecology and Management 561:121885",
        basis=(
            "Mean reduction in subsequent wildfire severity; less effective than "
            "treatments that also reduce surface fuels."
        ),
    ),
    TreatmentEvidence(
        treatment="treatment_older_than_10_years",
        metric="severity_reduction_fraction",
        low=0.28,
        high=0.28,
        source="Davis et al. 2024, Forest Ecology and Management 561:121885",
        basis=(
            "Mean reduction for treatments older than 10 years; effectiveness "
            "declines as fuels rebuild."
        ),
    ),
)


def reduction_fraction(baseline: float, treated: float) -> float:
    """Return the fractional reduction from baseline to treated.

    Parameters
    ----------
    baseline : float
        Untreated metric value; must be positive.
    treated : float
        Treated metric value; must be non-negative.

    Returns
    -------
    float
        ``(baseline - treated) / baseline``.
    """
    if baseline <= 0.0:
        raise ValueError("baseline must be positive")
    if treated < 0.0:
        raise ValueError("treated must be non-negative")
    return (baseline - treated) / baseline


def evidence_for(
    treatment: str,
    *,
    metric: str = "severity_reduction_fraction",
) -> TreatmentEvidence:
    """Return the evidence entry for one treatment and metric.

    Parameters
    ----------
    treatment : str
        Treatment label.
    metric : str, optional
        Metric identifier (default ``severity_reduction_fraction``).

    Returns
    -------
    TreatmentEvidence
        Matching published evidence.

    Raises
    ------
    KeyError
        If no matching evidence entry exists.
    """
    for item in TREATMENT_EVIDENCE:
        if item.treatment == treatment and item.metric == metric:
            return item
    raise KeyError(f"no treatment evidence for {treatment!r}/{metric!r}")


def apply_fuel_treatment(
    fire: ObservedFire,
    *,
    mask: np.ndarray,
    replacement: str,
    code: int | None = None,
) -> ObservedFire:
    """Return a copy of the fire with masked cells converted to one FBP fuel type.

    Parameters
    ----------
    fire : ObservedFire
        Source observed fire.
    mask : numpy.ndarray
        Boolean treatment mask with the fire-grid shape.
    replacement : str
        FBP fuel type assigned to treated cells.
    code : int or None, optional
        New fuel-grid code; defaults to one above the current maximum.

    Returns
    -------
    ObservedFire
        Copy with treated fuel codes and an explicit lookup entry.

    Raises
    ------
    ValueError
        If the mask is invalid, includes non-fuel cells, or the code collides.
    """
    if mask.shape != fire.fuel_codes.shape:
        raise ValueError("treatment mask shape must match the fire grid")
    masked = np.asarray(mask, dtype=bool)
    if not masked.any():
        raise ValueError("treatment mask must contain at least one cell")
    fuel_grid = fire.fbp_fuel_grid()
    burnable = np.array(
        [[value is not None for value in row] for row in fuel_grid],
        dtype=bool,
    )
    if np.any(masked & ~burnable):
        raise ValueError("treatment mask includes non-fuel cells")
    fuel_type = canonical_fuel_type(replacement)
    new_code = max(fire.fuel_lookup) + 1 if code is None else int(code)
    if new_code in fire.fuel_lookup:
        raise ValueError(f"fuel-grid code {new_code} is already in use")
    codes = np.array(fire.fuel_codes, copy=True)
    codes[masked] = new_code
    lookup = dict(fire.fuel_lookup)
    lookup[new_code] = fuel_type
    return replace(fire, fuel_codes=codes, fuel_lookup=lookup)


def classify_effect(
    *,
    baseline: float,
    treated: float,
    treatment: str,
    metric: str = "severity_reduction_fraction",
) -> dict[str, object]:
    """Compare a treated-versus-untreated effect with published evidence.

    Parameters
    ----------
    baseline : float
        Untreated metric value.
    treated : float
        Treated metric value.
    treatment : str
        Treatment label.
    metric : str, optional
        Metric identifier (default ``severity_reduction_fraction``).

    Returns
    -------
    dict
        Reduction fraction, published interval, position, and evidence metadata.
    """
    evidence = evidence_for(treatment, metric=metric)
    reduction = reduction_fraction(baseline, treated)
    return {
        "treatment": treatment,
        "metric": metric,
        "reduction_fraction": reduction,
        "position": evidence.position(reduction),
        "published_low": evidence.low,
        "published_high": evidence.high,
        "source": evidence.source,
        "basis": evidence.basis,
    }
