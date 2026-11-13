"""Fire-regime distribution formulas and diagnostics.

These are original Python implementations of the published scfm fire-regime and diagnostic
formulas. They operate on fire-size lists and do not run R or SpaDES. This layer validates
distributions and fire-regime statistics; it is not an event-perimeter comparison.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

REGIME_MODEL_VERSION: str = "ws4.fire-regime.scfm-v1"


class FireRegimeError(ValueError):
    """Raised when a fire-regime input is invalid."""


def _positive(value: object, field: str) -> float:
    """Return a finite positive float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FireRegimeError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise FireRegimeError(f"{field} must be positive")
    return number


def _sizes(values: list[float], field: str) -> list[float]:
    """Validate a list of fire sizes."""
    if not values:
        raise FireRegimeError(f"{field} must not be empty")
    result = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise FireRegimeError(f"{field} values must be numbers")
        number = float(value)
        if not math.isfinite(number) or number < 0.0:
            raise FireRegimeError(f"{field} values must be finite and non-negative")
        result.append(number)
    return result


@dataclass(frozen=True)
class FireRegimeParameters:
    """scfm fire-regime parameters for one polygon.

    Attributes
    ----------
    n_fires : int
        Number of historical lightning fires in the epoch.
    ignition_rate : float
        Fires per hectare per year.
    p_escape : float
        Fraction of fires larger than one pixel.
    mean_escaped_size_ha : float
        Mean size of escaped fires.
    max_escaped_size_ha : float
        Maximum escaped fire size.
    empirical_burn_rate : float
        Burned area per hectare per year.
    p_ignition : float
        Annual per-pixel ignition probability.
    max_burn_cells : int
        Rounded escaped mean size in cells.
    """

    n_fires: int
    ignition_rate: float
    p_escape: float
    mean_escaped_size_ha: float
    max_escaped_size_ha: float
    empirical_burn_rate: float
    p_ignition: float
    max_burn_cells: int


def fire_regime_parameters(
    sizes_ha: list[float],
    *,
    years: float,
    burnable_area_ha: float,
    cell_size_ha: float,
) -> FireRegimeParameters:
    """Return scfm fire-regime parameters for one polygon.

    Parameters
    ----------
    sizes_ha : list of float
        Historical fire sizes in hectares.
    years : float
        Length of the fire epoch in years.
    burnable_area_ha : float
        Burnable area of the polygon.
    cell_size_ha : float
        Area of one raster cell in hectares.

    Returns
    -------
    FireRegimeParameters
        The regime parameters. A polygon with no fires has zero ignition and ignition
        probability and NaN size statistics.
    """
    years_value = _positive(years, "years")
    area = _positive(burnable_area_ha, "burnable_area_ha")
    cell = _positive(cell_size_ha, "cell_size_ha")
    if not sizes_ha:
        return FireRegimeParameters(0, 0.0, 0.0, math.nan, math.nan, 0.0, 0.0, 0)
    sizes = _sizes(sizes_ha, "sizes_ha")
    escaped = [size for size in sizes if size > cell]
    ignition_rate = len(sizes) / (years_value * area)
    p_escape = len(escaped) / len(sizes)
    mean_escaped = statistics.fmean(escaped) if escaped else math.nan
    max_escaped = max(escaped) if escaped else math.nan
    empirical = sum(sizes) / (years_value * area)
    max_cells = round(mean_escaped / cell) if escaped else 0
    return FireRegimeParameters(
        n_fires=len(sizes),
        ignition_rate=ignition_rate,
        p_escape=p_escape,
        mean_escaped_size_ha=mean_escaped,
        max_escaped_size_ha=max_escaped,
        empirical_burn_rate=empirical,
        p_ignition=ignition_rate * cell,
        max_burn_cells=max_cells,
    )


@dataclass(frozen=True)
class FireRegimeDiagnostics:
    """scfm-style comparison of simulated fires with a historical regime.

    Attributes
    ----------
    burnable_area_ha : float
        Burnable area.
    target_ignitions : float
        Expected ignitions per year.
    achieved_ignitions : float
        Simulated ignitions per year.
    target_escapes : float
        Expected escapes per year.
    achieved_escapes : float
        Simulated escapes per year.
    model_mean_size_ha : float
        Mean simulated escaped-fire size.
    historical_mean_size_ha : float
        Historical mean escaped-fire size.
    historical_median_size_ha : float
        Historical median escaped-fire size.
    achieved_fri_years : float
        Simulated fire return interval.
    target_fri_years : float
        Historical fire return interval.
    """

    burnable_area_ha: float
    target_ignitions: float
    achieved_ignitions: float
    target_escapes: float
    achieved_escapes: float
    model_mean_size_ha: float
    historical_mean_size_ha: float
    historical_median_size_ha: float
    achieved_fri_years: float
    target_fri_years: float

    def to_dict(self) -> dict[str, float]:
        """Return the diagnostics as a JSON-serializable mapping.

        Returns
        -------
        dict
            All diagnostic values.
        """
        return {
            "burnable_area_ha": self.burnable_area_ha,
            "target_ignitions": self.target_ignitions,
            "achieved_ignitions": self.achieved_ignitions,
            "target_escapes": self.target_escapes,
            "achieved_escapes": self.achieved_escapes,
            "model_mean_size_ha": self.model_mean_size_ha,
            "historical_mean_size_ha": self.historical_mean_size_ha,
            "historical_median_size_ha": self.historical_median_size_ha,
            "achieved_fri_years": self.achieved_fri_years,
            "target_fri_years": self.target_fri_years,
        }


def fire_regime_diagnostics(
    *,
    burnable_area_ha: float,
    years: float,
    ignition_rate: float,
    p_escape: float,
    historical_sizes_ha: list[float],
    simulated_sizes_ha: list[float],
    cell_size_ha: float,
    empirical_burn_rate: float | None = None,
) -> FireRegimeDiagnostics:
    """Return scfm-style fire-regime diagnostics.

    Parameters
    ----------
    burnable_area_ha : float
        Burnable area.
    years : float
        Simulation/epoch length in years.
    ignition_rate : float
        Target fires per hectare per year.
    p_escape : float
        Target escape probability.
    historical_sizes_ha : list of float
        Historical fire sizes.
    simulated_sizes_ha : list of float
        Simulated fire sizes.
    cell_size_ha : float
        Area of one raster cell in hectares.
    empirical_burn_rate : float or None, optional
        Historical burn rate override. None derives it from the historical sizes.

    Returns
    -------
    FireRegimeDiagnostics
        Target/achieved diagnostics.
    """
    area = _positive(burnable_area_ha, "burnable_area_ha")
    time = _positive(years, "years")
    rate = _positive(ignition_rate, "ignition_rate")
    escape_probability = _positive(p_escape, "p_escape")
    if escape_probability > 1.0:
        raise FireRegimeError("p_escape must be between 0 and 1")
    cell = _positive(cell_size_ha, "cell_size_ha")
    historical = _sizes(historical_sizes_ha, "historical_sizes_ha")
    simulated = _sizes(simulated_sizes_ha, "simulated_sizes_ha")
    historical_escaped = [size for size in historical if size > cell]
    simulated_escaped = [size for size in simulated if size > cell]
    historical_mean = statistics.fmean(historical_escaped) if historical_escaped else 0.0
    historical_median = statistics.median(historical_escaped) if historical_escaped else 0.0
    model_mean = statistics.fmean(simulated_escaped) if simulated_escaped else 0.0
    target_ignitions = rate * area
    achieved_ignitions = len(simulated) / time
    target_escapes = escape_probability * target_ignitions
    achieved_escapes = len(simulated_escaped) / time
    simulated_burned = sum(simulated_escaped)
    achieved_fri = math.inf if simulated_burned <= 0.0 else time / (simulated_burned / area)
    historical_burn_rate = (
        _positive(empirical_burn_rate, "empirical_burn_rate")
        if empirical_burn_rate is not None
        else sum(historical) / (time * area)
    )
    target_fri = math.inf if historical_burn_rate <= 0.0 else 1.0 / historical_burn_rate
    return FireRegimeDiagnostics(
        burnable_area_ha=area,
        target_ignitions=target_ignitions,
        achieved_ignitions=achieved_ignitions,
        target_escapes=target_escapes,
        achieved_escapes=achieved_escapes,
        model_mean_size_ha=model_mean,
        historical_mean_size_ha=historical_mean,
        historical_median_size_ha=historical_median,
        achieved_fri_years=achieved_fri,
        target_fri_years=target_fri,
    )
