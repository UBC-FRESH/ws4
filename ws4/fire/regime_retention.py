"""Size-dependent retention model for the P164.9 multi-year calibration.

The P164.8 model retained a fixed fraction of the potential fire size. That model
cannot represent a historical distribution with a strong mode near 20-50 ha when
the potential sample contains mostly much larger fires: it either collapses to the
minimum support area or escapes to a large fraction of the potential size.

This module keeps the escape hazard and the escaped-size component, but gives the
contained component its own log-normal size distribution. The contained median can
also scale weakly with potential size.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Final

from .regime_calibration import PotentialFire, RegimeCalibrationError, RegimeMetrics, size_metrics

CONTAINED_MEDIAN_HA_BOUNDS: Final[tuple[float, float]] = (6.25, 2_000.0)
CONTAINED_SIGMA_BOUNDS: Final[tuple[float, float]] = (0.15, 1.5)
CONTAINED_EXPONENT_BOUNDS: Final[tuple[float, float]] = (0.0, 1.0)
ESCAPED_FRACTION_BOUNDS: Final[tuple[float, float]] = (0.01, 1.0)
ESCAPED_SIGMA_BOUNDS: Final[tuple[float, float]] = (0.05, 0.6)
ESCAPE_CAP_BOUNDS: Final[tuple[float, float]] = (5_000.0, 30_000.0)
INTERCEPT_BOUNDS: Final[tuple[float, float]] = (-7.0, -3.0)
MIN_AREA_HA: Final[float] = 6.25


@dataclass(frozen=True)
class RetentionParameters:
    """Parameters of the size-dependent retention model.

    Parameters
    ----------
    contained_median_ha : float
        Median contained area at a 1,000 ha potential fire.
    contained_sigma : float
        Log-normal sigma of the contained area.
    contained_exponent : float
        Scaling of contained median with potential area; zero is independent, one is
        proportional.
    escaped_fraction_median : float
        Median retained fraction after escape.
    escaped_fraction_sigma : float
        Log-sigma of the escaped fraction.
    escape_cap_ha : float
        Absolute escaped-area cap.
    intercept : float
        Escape hazard logit intercept.
    """

    contained_median_ha: float
    contained_sigma: float
    contained_exponent: float
    escaped_fraction_median: float
    escaped_fraction_sigma: float
    escape_cap_ha: float
    intercept: float

    def __post_init__(self) -> None:
        """Validate all parameters against their bounds."""
        for value, field, bounds in (
            (self.contained_median_ha, "contained_median_ha", CONTAINED_MEDIAN_HA_BOUNDS),
            (self.contained_sigma, "contained_sigma", CONTAINED_SIGMA_BOUNDS),
            (self.contained_exponent, "contained_exponent", CONTAINED_EXPONENT_BOUNDS),
            (self.escaped_fraction_median, "escaped_fraction_median", ESCAPED_FRACTION_BOUNDS),
            (self.escaped_fraction_sigma, "escaped_fraction_sigma", ESCAPED_SIGMA_BOUNDS),
            (self.escape_cap_ha, "escape_cap_ha", ESCAPE_CAP_BOUNDS),
            (self.intercept, "intercept", INTERCEPT_BOUNDS),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RegimeCalibrationError(f"{field} must be a number")
            number = float(value)
            if not math.isfinite(number) or number < bounds[0] or number > bounds[1]:
                raise RegimeCalibrationError(f"{field} is outside its bounds")

    def to_dict(self) -> dict[str, float]:
        """Return the parameters as a JSON-serializable mapping.

        Returns
        -------
        dict of str to float
            Parameter names and values.
        """
        return {
            "contained_median_ha": self.contained_median_ha,
            "contained_sigma": self.contained_sigma,
            "contained_exponent": self.contained_exponent,
            "escaped_fraction_median": self.escaped_fraction_median,
            "escaped_fraction_sigma": self.escaped_fraction_sigma,
            "escape_cap_ha": self.escape_cap_ha,
            "intercept": self.intercept,
        }

    def escape_probability(self, record: PotentialFire) -> float:
        """Return the escape probability for one potential fire.

        Parameters
        ----------
        record : PotentialFire
            Potential-fire record.

        Returns
        -------
        float
            Escape probability in ``(0, 1)``.
        """
        logit = (
            self.intercept
            + 0.5 * math.log1p(record.active_days)
            + 0.2 * max(0.0, record.fwi - 10.0) / 10.0
            + 0.1 * max(0.0, record.bui - 50.0) / 50.0
            + 0.1 * max(0.0, record.wind_kmh - 5.0) / 10.0
        )
        return 1.0 / (1.0 + math.exp(-logit))


@dataclass(frozen=True)
class RetentionOutcome:
    """One retained-size outcome.

    Attributes
    ----------
    escaped : bool
        Whether the fire escaped containment.
    target_area_ha : float
        Final area in hectares.
    """

    escaped: bool
    target_area_ha: float


def draw_retention(
    parameters: RetentionParameters,
    rng: random.Random,
    record: PotentialFire,
) -> RetentionOutcome:
    """Draw one retained fire size.

    Parameters
    ----------
    parameters : RetentionParameters
        Model parameters.
    rng : random.Random
        Deterministic random source.
    record : PotentialFire
        Potential-fire record.

    Returns
    -------
    RetentionOutcome
        Escape state and final area.
    """
    potential = float(record.potential_ha)
    escaped = rng.random() < parameters.escape_probability(record)
    if escaped:
        fraction = math.exp(
            math.log(parameters.escaped_fraction_median)
            + parameters.escaped_fraction_sigma * rng.gauss(0.0, 1.0)
        )
        area = min(parameters.escape_cap_ha, potential * min(1.0, max(1e-6, fraction)))
    else:
        contained = math.exp(
            math.log(parameters.contained_median_ha)
            + parameters.contained_exponent * math.log(max(potential, 1.0) / 1_000.0)
            + parameters.contained_sigma * rng.gauss(0.0, 1.0)
        )
        area = min(potential, max(MIN_AREA_HA, contained))
    return RetentionOutcome(escaped=escaped, target_area_ha=area)


def simulate_retention(
    parameters: RetentionParameters,
    records: list[PotentialFire],
    seed: int,
) -> list[float]:
    """Simulate retained sizes with one deterministic draw per record.

    Parameters
    ----------
    parameters : RetentionParameters
        Model parameters.
    records : list of PotentialFire
        Potential-fire records.
    seed : int
        Deterministic seed.

    Returns
    -------
    list of float
        Final areas in hectares.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise RegimeCalibrationError("seed must be a non-negative integer")
    rng = random.Random(seed)
    return [draw_retention(parameters, rng, record).target_area_ha for record in records]


def retention_candidates(seed: int, count: int = 1_000) -> tuple[RetentionParameters, ...]:
    """Return deterministic log-uniform candidates inside the retention bounds.

    Parameters
    ----------
    seed : int
        Fixed search seed.
    count : int, optional
        Number of candidates.

    Returns
    -------
    tuple of RetentionParameters
        Candidate parameters.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise RegimeCalibrationError("seed must be a non-negative integer")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise RegimeCalibrationError("count must be a positive integer")
    rng = random.Random(seed)

    def log_uniform(bounds: tuple[float, float]) -> float:
        return math.pow(10.0, rng.uniform(math.log10(bounds[0]), math.log10(bounds[1])))

    def uniform(bounds: tuple[float, float]) -> float:
        return rng.uniform(bounds[0], bounds[1])

    return tuple(
        RetentionParameters(
            contained_median_ha=log_uniform(CONTAINED_MEDIAN_HA_BOUNDS),
            contained_sigma=uniform(CONTAINED_SIGMA_BOUNDS),
            contained_exponent=uniform(CONTAINED_EXPONENT_BOUNDS),
            escaped_fraction_median=log_uniform(ESCAPED_FRACTION_BOUNDS),
            escaped_fraction_sigma=uniform(ESCAPED_SIGMA_BOUNDS),
            escape_cap_ha=uniform(ESCAPE_CAP_BOUNDS),
            intercept=uniform(INTERCEPT_BOUNDS),
        )
        for _ in range(count)
    )


def metrics_for(
    parameters: RetentionParameters,
    records: list[PotentialFire],
    seed: int,
) -> RegimeMetrics:
    """Return metrics for five deterministic draws per record.

    Parameters
    ----------
    parameters : RetentionParameters
        Model parameters.
    records : list of PotentialFire
        Potential-fire records.
    seed : int
        Deterministic seed.

    Returns
    -------
    RegimeMetrics
        Pooled metrics for five draws per record.
    """
    values: list[float] = []
    for rep in range(5):
        values.extend(simulate_retention(parameters, records, seed + rep))
    return size_metrics(values)
