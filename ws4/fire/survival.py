"""Survival, escape, and contained-area distributions for a fire.

Containment is not a single radius. A fire either remains inside a contained-area target or
survives suppression and reaches a bounded escape size. This module owns that decision and the
two size distributions so calibration code does not invent them independently.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Final

from .fuel import FireFuelError

SURVIVAL_MODEL_VERSION: Final[str] = "ws4.fire.survival.v1"


def _finite(value: float, field: str) -> float:
    """Return a finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FireFuelError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise FireFuelError(f"{field} must be finite")
    return number


def _positive(value: float, field: str) -> float:
    """Return a positive finite float."""
    number = _finite(value, field)
    if number <= 0.0:
        raise FireFuelError(f"{field} must be positive")
    return number


@dataclass(frozen=True)
class SurvivalConfig:
    """Parameters of the survival and escape process.

    Parameters
    ----------
    contained_median_ha : float, optional
        Median contained-area target in hectares (default 20).
    contained_sigma : float, optional
        Log-sigma of the contained-area distribution (default 0.8).
    escape_median_ha : float, optional
        Median escaped-fire size in hectares (default 2,500).
    escape_sigma : float, optional
        Log-sigma of the escaped-fire size distribution (default 0.8).
    escape_cap_ha : float, optional
        Maximum escaped-fire size in hectares (default 12,000).
    intercept : float, optional
        Logit intercept for escape probability (default -4).
    duration_weight : float, optional
        Log-duration weight in the escape logit (default 0.5).
    fwi_weight : float, optional
        FWI weight in the escape logit (default 0.2).
    bui_weight : float, optional
        BUI weight in the escape logit (default 0.1).
    wind_weight : float, optional
        Wind weight in the escape logit (default 0.1).
    """

    contained_median_ha: float = 20.0
    contained_sigma: float = 0.8
    escape_median_ha: float = 2_500.0
    escape_sigma: float = 0.8
    escape_cap_ha: float = 12_000.0
    intercept: float = -4.0
    duration_weight: float = 0.5
    fwi_weight: float = 0.2
    bui_weight: float = 0.1
    wind_weight: float = 0.1

    def __post_init__(self) -> None:
        """Validate the distribution and hazard parameters."""
        object.__setattr__(
            self, "contained_median_ha", _positive(self.contained_median_ha, "contained_median_ha")
        )
        object.__setattr__(
            self, "contained_sigma", _positive(self.contained_sigma, "contained_sigma")
        )
        object.__setattr__(
            self, "escape_median_ha", _positive(self.escape_median_ha, "escape_median_ha")
        )
        object.__setattr__(self, "escape_sigma", _positive(self.escape_sigma, "escape_sigma"))
        object.__setattr__(self, "escape_cap_ha", _positive(self.escape_cap_ha, "escape_cap_ha"))
        if self.escape_median_ha > self.escape_cap_ha:
            raise FireFuelError("escape_median_ha must not exceed escape_cap_ha")
        object.__setattr__(self, "intercept", _finite(self.intercept, "intercept"))
        object.__setattr__(
            self, "duration_weight", _finite(self.duration_weight, "duration_weight")
        )
        object.__setattr__(self, "fwi_weight", _finite(self.fwi_weight, "fwi_weight"))
        object.__setattr__(self, "bui_weight", _finite(self.bui_weight, "bui_weight"))
        object.__setattr__(self, "wind_weight", _finite(self.wind_weight, "wind_weight"))

    def escape_probability(
        self,
        *,
        active_days: float,
        fwi: float,
        bui: float,
        wind_kmh: float,
        fuel_hazard: float = 0.0,
    ) -> float:
        """Return the probability that a fire escapes containment.

        Parameters
        ----------
        active_days : float
            Active-spread duration in days.
        fwi : float
            Fire Weather Index.
        bui : float
            Buildup Index.
        wind_kmh : float
            Ten-metre wind speed.
        fuel_hazard : float, optional
            Additional fuel/landscape hazard contribution (default zero).

        Returns
        -------
        float
            Escape probability in ``(0, 1)``.
        """
        days = _finite(active_days, "active_days")
        fwi_value = _finite(fwi, "fwi")
        bui_value = _finite(bui, "bui")
        wind = _finite(wind_kmh, "wind_kmh")
        hazard = _finite(fuel_hazard, "fuel_hazard")
        if days < 0.0 or fwi_value < 0.0 or bui_value < 0.0 or wind < 0.0:
            raise FireFuelError("active_days, fwi, bui, and wind_kmh must be non-negative")
        logit = (
            self.intercept
            + self.duration_weight * math.log1p(days)
            + self.fwi_weight * max(0.0, fwi_value - 10.0) / 10.0
            + self.bui_weight * max(0.0, bui_value - 50.0) / 50.0
            + self.wind_weight * max(0.0, wind - 5.0) / 10.0
            + hazard
        )
        return 1.0 / (1.0 + math.exp(-logit))


@dataclass(frozen=True)
class RelativeSuppressionConfig:
    """Suppression expressed as a fraction of the potential fire size.

    Parameters
    ----------
    contained_fraction_median : float, optional
        Median fraction of the potential fire left after containment (default 0.15).
    contained_fraction_sigma : float, optional
        Log-sigma of the contained fraction (default 0.8).
    escaped_fraction_median : float, optional
        Median fraction of the potential fire left after escape (default 0.85).
    escaped_fraction_sigma : float, optional
        Log-sigma of the escaped fraction (default 0.25).
    escape_cap_ha : float, optional
        Absolute escaped-area cap in hectares (default 12,000).
    min_area_ha : float, optional
        Minimum retained area in hectares (default 1.0).
    intercept : float, optional
        Logit intercept for escape probability (default -4).
    duration_weight : float, optional
        Log-duration weight in the escape logit (default 0.5).
    fwi_weight : float, optional
        FWI weight in the escape logit (default 0.2).
    bui_weight : float, optional
        BUI weight in the escape logit (default 0.1).
    wind_weight : float, optional
        Wind weight in the escape logit (default 0.1).
    contained_median_ha : float or None, optional
        If set, use a log-normal contained-size distribution with this median at a
        1,000 ha potential fire instead of a fixed contained fraction.
    contained_exponent : float, optional
        Scaling of the contained median with potential size. Zero is independent;
        one is proportional (default 0).
    """

    contained_fraction_median: float = 0.15
    contained_fraction_sigma: float = 0.8
    escaped_fraction_median: float = 0.85
    escaped_fraction_sigma: float = 0.25
    escape_cap_ha: float = 12_000.0
    min_area_ha: float = 1.0
    intercept: float = -4.0
    duration_weight: float = 0.5
    fwi_weight: float = 0.2
    bui_weight: float = 0.1
    wind_weight: float = 0.1
    contained_median_ha: float | None = None
    contained_exponent: float = 0.0

    def __post_init__(self) -> None:
        """Validate the relative suppression parameters."""
        for field in ("contained_fraction_median", "escaped_fraction_median"):
            value = _positive(getattr(self, field), field)
            if value > 1.0:
                raise FireFuelError(f"{field} must be between 0 and 1")
        object.__setattr__(
            self,
            "contained_fraction_sigma",
            _positive(self.contained_fraction_sigma, "contained_fraction_sigma"),
        )
        object.__setattr__(
            self,
            "escaped_fraction_sigma",
            _positive(self.escaped_fraction_sigma, "escaped_fraction_sigma"),
        )
        object.__setattr__(self, "escape_cap_ha", _positive(self.escape_cap_ha, "escape_cap_ha"))
        object.__setattr__(self, "min_area_ha", _positive(self.min_area_ha, "min_area_ha"))
        if self.contained_median_ha is not None:
            object.__setattr__(
                self,
                "contained_median_ha",
                _positive(self.contained_median_ha, "contained_median_ha"),
            )
        object.__setattr__(
            self,
            "contained_exponent",
            max(0.0, min(1.0, _finite(self.contained_exponent, "contained_exponent"))),
        )
        object.__setattr__(self, "intercept", _finite(self.intercept, "intercept"))
        object.__setattr__(
            self, "duration_weight", _finite(self.duration_weight, "duration_weight")
        )
        object.__setattr__(self, "fwi_weight", _finite(self.fwi_weight, "fwi_weight"))
        object.__setattr__(self, "bui_weight", _finite(self.bui_weight, "bui_weight"))
        object.__setattr__(self, "wind_weight", _finite(self.wind_weight, "wind_weight"))

    def escape_probability(
        self,
        *,
        active_days: float,
        fwi: float,
        bui: float,
        wind_kmh: float,
        fuel_hazard: float = 0.0,
    ) -> float:
        """Return the probability that a potential fire escapes suppression.

        Parameters
        ----------
        active_days : float
            Active-spread duration in days.
        fwi : float
            Fire Weather Index.
        bui : float
            Buildup Index.
        wind_kmh : float
            Ten-metre wind speed.
        fuel_hazard : float, optional
            Additional fuel/landscape hazard contribution (default zero).

        Returns
        -------
        float
            Escape probability in ``(0, 1)``.
        """
        days = _finite(active_days, "active_days")
        fwi_value = _finite(fwi, "fwi")
        bui_value = _finite(bui, "bui")
        wind = _finite(wind_kmh, "wind_kmh")
        hazard = _finite(fuel_hazard, "fuel_hazard")
        if days < 0.0 or fwi_value < 0.0 or bui_value < 0.0 or wind < 0.0:
            raise FireFuelError("active_days, fwi, bui, and wind_kmh must be non-negative")
        logit = (
            self.intercept
            + self.duration_weight * math.log1p(days)
            + self.fwi_weight * max(0.0, fwi_value - 10.0) / 10.0
            + self.bui_weight * max(0.0, bui_value - 50.0) / 50.0
            + self.wind_weight * max(0.0, wind - 5.0) / 10.0
            + hazard
        )
        return 1.0 / (1.0 + math.exp(-logit))


@dataclass(frozen=True)
class RelativeSuppressionOutcome:
    """The retained fraction and bounded area of one potential fire.

    Attributes
    ----------
    escaped : bool
        Whether the fire escaped containment.
    retained_fraction : float
        Fraction of the potential area retained.
    target_area_ha : float
        Final area target in hectares.
    max_burned_area_ha : float
        Growth cap for the fire.
    """

    escaped: bool
    retained_fraction: float
    target_area_ha: float
    max_burned_area_ha: float


def draw_relative_suppression(
    config: RelativeSuppressionConfig,
    rng: random.Random,
    *,
    potential_area_ha: float,
    active_days: float,
    fwi: float,
    bui: float,
    wind_kmh: float,
    fuel_hazard: float = 0.0,
) -> RelativeSuppressionOutcome:
    """Apply relative suppression to one potential fire.

    Parameters
    ----------
    config : RelativeSuppressionConfig
        Relative suppression parameters.
    rng : random.Random
        Deterministic random source.
    potential_area_ha : float
        Unsuppressed potential fire area.
    active_days : float
        Active-spread duration in days.
    fwi : float
        Fire Weather Index.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed.
    fuel_hazard : float, optional
        Additional fuel/landscape hazard contribution.

    Returns
    -------
    RelativeSuppressionOutcome
        Escape state, retained fraction, and bounded area.
    """
    potential = _positive(potential_area_ha, "potential_area_ha")
    probability = config.escape_probability(
        active_days=active_days,
        fwi=fwi,
        bui=bui,
        wind_kmh=wind_kmh,
        fuel_hazard=fuel_hazard,
    )
    escaped = rng.random() < probability
    if escaped:
        fraction = math.exp(
            math.log(config.escaped_fraction_median)
            + config.escaped_fraction_sigma * rng.gauss(0.0, 1.0)
        )
        retained = min(1.0, max(1e-6, fraction))
        area = min(config.escape_cap_ha, potential * retained)
    elif config.contained_median_ha is not None:
        contained = math.exp(
            math.log(config.contained_median_ha)
            + config.contained_exponent * math.log(max(potential, 1.0) / 1_000.0)
            + config.contained_fraction_sigma * rng.gauss(0.0, 1.0)
        )
        area = min(potential, max(config.min_area_ha, contained))
        retained = min(1.0, max(1e-6, area / potential))
    else:
        fraction = math.exp(
            math.log(config.contained_fraction_median)
            + config.contained_fraction_sigma * rng.gauss(0.0, 1.0)
        )
        retained = min(1.0, max(1e-6, fraction))
        area = min(potential, max(config.min_area_ha, potential * retained))
    return RelativeSuppressionOutcome(
        escaped=escaped,
        retained_fraction=retained,
        target_area_ha=area,
        max_burned_area_ha=area,
    )


@dataclass(frozen=True)
class SurvivalOutcome:
    """One survival decision and its bounded fire size.

    Attributes
    ----------
    escaped : bool
        Whether the fire escaped containment.
    target_area_ha : float
        Contained target area, or the escaped-fire size when escaped.
    max_burned_area_ha : float
        Growth cap for the fire.
    """

    escaped: bool
    target_area_ha: float
    max_burned_area_ha: float


def draw_survival(
    config: SurvivalConfig,
    rng: random.Random,
    *,
    active_days: float,
    fwi: float,
    bui: float,
    wind_kmh: float,
    fuel_hazard: float = 0.0,
) -> SurvivalOutcome:
    """Draw one survival outcome.

    Parameters
    ----------
    config : SurvivalConfig
        Survival and size parameters.
    rng : random.Random
        Deterministic random source.
    active_days : float
        Active-spread duration in days.
    fwi : float
        Fire Weather Index.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed.
    fuel_hazard : float, optional
        Additional fuel/landscape hazard contribution (default zero).

    Returns
    -------
    SurvivalOutcome
        Escape state and bounded size.
    """
    probability = config.escape_probability(
        active_days=active_days,
        fwi=fwi,
        bui=bui,
        wind_kmh=wind_kmh,
        fuel_hazard=fuel_hazard,
    )
    if rng.random() < probability:
        area = math.exp(
            math.log(config.escape_median_ha) + config.escape_sigma * rng.gauss(0.0, 1.0)
        )
        area = min(area, config.escape_cap_ha)
        return SurvivalOutcome(escaped=True, target_area_ha=area, max_burned_area_ha=area)
    area = math.exp(
        math.log(config.contained_median_ha) + config.contained_sigma * rng.gauss(0.0, 1.0)
    )
    return SurvivalOutcome(escaped=False, target_area_ha=area, max_burned_area_ha=area)
