"""Benchmark the Huygens growth engine against the public FBP ellipse.

The FBP System publishes an elliptical fire-growth model: the head, back, and flank
distances follow from the head rate of spread and the length-to-breadth ratio. This module
turns that model into an analytic perimeter and compares it with a ``grow_fire`` run.

The comparison validates geometry, not independent fire behaviour: the same FBP head ROS
feeds both the analytic ellipse and the growth engine. The standard-case tests validate the
head ROS against ``cffdrs`` and the R ``Rothermel`` package; this module checks that the
spatial construction preserves the ellipse.

The module also runs a deterministic weather/fuel-moisture scenario ensemble and reports
empirical quantiles and exceedance probabilities. It is not a Monte Carlo sampler.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from .crown import fbp_crown_fire
from .fuel import FireFuelError
from .growth import (
    GrowthConfig,
    GrowthResult,
    SiteGrid,
    effective_wind,
    grow_fire,
    length_to_breadth,
)

#: The largest grid a benchmark run will build, to keep an accidental run bounded.
MAX_BENCHMARK_CELLS: Final[int] = 1201


@dataclass(frozen=True)
class EllipseMetrics:
    """The analytic FBP ellipse at one duration.

    Parameters
    ----------
    duration_min : float
        Fire duration in minutes.
    head_ros_m_min : float
        Head rate of spread in metres per minute.
    length_to_breadth : float
        Fire ellipse length-to-breadth ratio.
    head_distance_m : float
        Distance from the ignition focus to the head.
    back_distance_m : float
        Distance from the ignition focus to the back.
    length_m : float
        Ellipse length.
    width_m : float
        Ellipse width.
    area_ha : float
        Ellipse area in hectares.
    perimeter_m : float
        Ellipse perimeter from the Ramanujan approximation.
    """

    duration_min: float
    head_ros_m_min: float
    length_to_breadth: float
    head_distance_m: float
    back_distance_m: float
    length_m: float
    width_m: float
    area_ha: float
    perimeter_m: float

    def to_dict(self) -> dict[str, float]:
        """Return the metrics as a JSON-serializable mapping.

        Returns
        -------
        dict
            Duration, ROS, ellipse axes, area, and perimeter.
        """
        return {
            "duration_min": self.duration_min,
            "head_ros_m_min": self.head_ros_m_min,
            "length_to_breadth": self.length_to_breadth,
            "head_distance_m": self.head_distance_m,
            "back_distance_m": self.back_distance_m,
            "length_m": self.length_m,
            "width_m": self.width_m,
            "area_ha": self.area_ha,
            "perimeter_m": self.perimeter_m,
        }


@dataclass(frozen=True)
class GrowthComparison:
    """The measured-minus-analytic comparison for one growth run.

    Parameters
    ----------
    measured_length_m : float
        Bounding-box length of the burned raster.
    measured_width_m : float
        Bounding-box width of the burned raster.
    length_relative_error : float
        Relative error in length.
    width_relative_error : float
        Relative error in width.
    area_relative_error : float
        Relative error in area.
    perimeter_relative_error : float
        Relative error in the raster perimeter.
    """

    measured_length_m: float
    measured_width_m: float
    length_relative_error: float
    width_relative_error: float
    area_relative_error: float
    perimeter_relative_error: float

    def to_dict(self) -> dict[str, float]:
        """Return the comparison as a JSON-serializable mapping.

        Returns
        -------
        dict
            Measured axes and relative errors.
        """
        return {
            "measured_length_m": self.measured_length_m,
            "measured_width_m": self.measured_width_m,
            "length_relative_error": self.length_relative_error,
            "width_relative_error": self.width_relative_error,
            "area_relative_error": self.area_relative_error,
            "perimeter_relative_error": self.perimeter_relative_error,
        }


@dataclass(frozen=True)
class WeatherScenario:
    """One deterministic weather/fuel-moisture benchmark scenario.

    Parameters
    ----------
    scenario_id : str
        Stable scenario label.
    fuel_type : str
        FBP fuel type.
    ffmc : float
        Fine Fuel Moisture Code.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed.
    wind_direction_deg : float, optional
        Direction the wind comes from (default 270, a west wind).
    slope_percent : float, optional
        Ground slope in percent (default 0).
    aspect_deg : float, optional
        Slope aspect (default 0).
    duration_min : float, optional
        Fire duration in minutes (default 60).
    """

    scenario_id: str
    fuel_type: str
    ffmc: float
    bui: float
    wind_kmh: float
    wind_direction_deg: float = 270.0
    slope_percent: float = 0.0
    aspect_deg: float = 0.0
    duration_min: float = 60.0


def ellipse_metrics(
    head_ros_m_min: float,
    length_to_breadth: float,
    duration_min: float,
) -> EllipseMetrics:
    """Return the analytic FBP ellipse at one duration.

    Parameters
    ----------
    head_ros_m_min : float
        Head rate of spread in metres per minute.
    length_to_breadth : float
        Fire ellipse length-to-breadth ratio; one is a circle.
    duration_min : float
        Fire duration in minutes.

    Returns
    -------
    EllipseMetrics
        Head, back, length, width, area, and perimeter.

    Raises
    ------
    FireFuelError
        If a value is negative, the duration is not positive, or the length-to-breadth
        ratio is below one.
    """
    ros = _non_negative(head_ros_m_min, "head_ros_m_min")
    ratio = _number(length_to_breadth, "length_to_breadth")
    if ratio < 1.0:
        raise FireFuelError("length_to_breadth must be at least one")
    duration = _positive(duration_min, "duration_min")
    if ros == 0.0:
        return EllipseMetrics(duration, 0.0, ratio, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    eccentricity = (ratio**2 - 1.0) / (ratio**2 + 1.0)
    head_distance = ros * duration
    back_distance = head_distance * (1.0 - eccentricity) / (1.0 + eccentricity)
    length = head_distance + back_distance
    semi_major = length / 2.0
    semi_minor = semi_major * math.sqrt(max(0.0, 1.0 - eccentricity**2))
    area = math.pi * semi_major * semi_minor / 10_000.0
    perimeter = math.pi * (
        3.0 * (semi_major + semi_minor)
        - math.sqrt((3.0 * semi_major + semi_minor) * (semi_major + 3.0 * semi_minor))
    )
    return EllipseMetrics(
        duration_min=duration,
        head_ros_m_min=ros,
        length_to_breadth=ratio,
        head_distance_m=head_distance,
        back_distance_m=back_distance,
        length_m=length,
        width_m=2.0 * semi_minor,
        area_ha=area,
        perimeter_m=perimeter,
    )


def compare_growth_to_ellipse(
    result: GrowthResult,
    expected: EllipseMetrics,
) -> GrowthComparison:
    """Compare a growth run with an analytic ellipse.

    Parameters
    ----------
    result : GrowthResult
        A completed homogeneous growth run.
    expected : EllipseMetrics
        The analytic ellipse for the same fuel, weather, and duration.

    Returns
    -------
    GrowthComparison
        Measured bounding-box axes and relative errors.

    Raises
    ------
    FireFuelError
        If the result or ellipse is invalid.
    """
    if not isinstance(result, GrowthResult):
        raise FireFuelError("result must be a GrowthResult")
    if not isinstance(expected, EllipseMetrics):
        raise FireFuelError("expected must be EllipseMetrics")
    burned = np.isfinite(result.ignition_time_min)
    if not bool(burned.any()):
        measured_length = 0.0
        measured_width = 0.0
    else:
        rows, cols = np.where(burned)
        measured_length = (int(np.max(cols)) - int(np.min(cols)) + 1) * result.grid.cell_size_m
        measured_width = (int(np.max(rows)) - int(np.min(rows)) + 1) * result.grid.cell_size_m
    return GrowthComparison(
        measured_length_m=measured_length,
        measured_width_m=measured_width,
        length_relative_error=_relative(measured_length, expected.length_m),
        width_relative_error=_relative(measured_width, expected.width_m),
        area_relative_error=_relative(result.burned_area_ha, expected.area_ha),
        perimeter_relative_error=_relative(result.perimeter_m, expected.perimeter_m),
    )


def run_growth_ensemble(
    scenarios: Sequence[WeatherScenario],
    *,
    cell_size_m: float = 10.0,
    neighbor_radius: int = 2,
) -> pd.DataFrame:
    """Run a deterministic scenario ensemble through the growth engine.

    Parameters
    ----------
    scenarios : sequence of WeatherScenario
        The scenarios to run.
    cell_size_m : float, optional
        Grid cell size in metres (default 10).
    neighbor_radius : int, optional
        Primitive-direction radius passed to ``GrowthConfig`` (default 2).

    Returns
    -------
    pandas.DataFrame
        One row per scenario with the kernel inputs, analytic ellipse, measured growth,
        and relative errors.

    Raises
    ------
    FireFuelError
        If a scenario is invalid or the required grid would exceed the benchmark guard.
    """
    if not scenarios:
        raise FireFuelError("at least one scenario is required")
    rows: list[dict[str, object]] = []
    for scenario in scenarios:
        if not isinstance(scenario, WeatherScenario):
            raise FireFuelError("scenarios must be WeatherScenario instances")
        wind = effective_wind(
            scenario.fuel_type,
            scenario.ffmc,
            scenario.bui,
            scenario.wind_kmh,
            scenario.wind_direction_deg,
            scenario.slope_percent,
            scenario.aspect_deg,
        )
        crown = fbp_crown_fire(
            scenario.fuel_type,
            scenario.ffmc,
            scenario.bui,
            wind.speed_kmh,
        )
        ratio = length_to_breadth(scenario.fuel_type, wind.speed_kmh)
        expected = ellipse_metrics(crown.rate_of_spread_m_min, ratio, scenario.duration_min)
        cells = _grid_cells(expected, cell_size_m)
        grid = SiteGrid(
            fuel_type=scenario.fuel_type,
            rows=cells,
            cols=cells,
            cell_size_m=cell_size_m,
            ffmc=scenario.ffmc,
            bui=scenario.bui,
            wind_kmh=scenario.wind_kmh,
            wind_direction_deg=scenario.wind_direction_deg,
            slope_percent=scenario.slope_percent,
            aspect_deg=scenario.aspect_deg,
        )
        result = grow_fire(
            grid,
            GrowthConfig(
                ignition_cells=((cells // 2, cells // 2),),
                max_time_min=scenario.duration_min,
                snapshot_interval_min=scenario.duration_min,
                neighbor_radius=neighbor_radius,
            ),
        )
        comparison = compare_growth_to_ellipse(result, expected)
        row: dict[str, object] = {
            "scenario_id": scenario.scenario_id,
            "fuel_type": scenario.fuel_type,
            "ffmc": scenario.ffmc,
            "bui": scenario.bui,
            "wind_kmh": scenario.wind_kmh,
            "effective_wind_kmh": wind.speed_kmh,
            "spread_azimuth_deg": wind.azimuth_deg,
            "head_ros_m_min": crown.rate_of_spread_m_min,
            "length_to_breadth": ratio,
            "duration_min": scenario.duration_min,
            "expected_area_ha": expected.area_ha,
            "expected_perimeter_m": expected.perimeter_m,
            "measured_area_ha": result.burned_area_ha,
            "measured_perimeter_m": result.perimeter_m,
        }
        row.update(comparison.to_dict())
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_ensemble(
    frame: pd.DataFrame,
    thresholds: Sequence[float],
    *,
    column: str = "measured_area_ha",
) -> dict[str, object]:
    """Summarize an ensemble with quantiles and exceedance probabilities.

    Parameters
    ----------
    frame : pandas.DataFrame
        The output of :func:`run_growth_ensemble`.
    thresholds : sequence of float
        Area thresholds in hectares.
    column : str, optional
        The value column to summarize (default ``measured_area_ha``).

    Returns
    -------
    dict
        Count, mean, minimum, maximum, P10/P50/P90, and exceedance probabilities keyed by
        ``p_area_ge_<threshold>``.

    Raises
    ------
    FireFuelError
        If the frame is empty or the column is missing.
    """
    if frame.empty:
        raise FireFuelError("ensemble frame is empty")
    if column not in frame:
        raise FireFuelError(f"ensemble frame has no {column!r} column")
    values = [float(value) for value in frame[column]]
    if any(not math.isfinite(value) for value in values):
        raise FireFuelError(f"{column} must be finite")
    summary: dict[str, object] = {
        "count": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
        "p10": _quantile(values, 0.1),
        "p50": _quantile(values, 0.5),
        "p90": _quantile(values, 0.9),
    }
    for threshold in thresholds:
        summary[f"p_area_ge_{threshold:g}"] = sum(value >= threshold for value in values) / len(
            values
        )
    return summary


def _relative(measured: float, expected: float) -> float:
    """Return a relative error, using zero for an exact zero comparison."""
    if expected == 0.0:
        return 0.0 if measured == 0.0 else math.inf
    return (measured - expected) / expected


def _quantile(values: Sequence[float], probability: float) -> float:
    """Return a linearly interpolated quantile."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _grid_cells(expected: EllipseMetrics, cell_size_m: float) -> int:
    """Return an odd grid size that contains the analytic ellipse with a margin."""
    cell = _positive(cell_size_m, "cell_size_m")
    radius = max(expected.length_m, expected.width_m, 100.0)
    cells = math.ceil(radius / cell) * 2 + 21
    if cells > MAX_BENCHMARK_CELLS:
        raise FireFuelError(
            f"benchmark grid would be {cells} cells; raise cell_size_m or shorten duration"
        )
    return cells if cells % 2 == 1 else cells + 1


def _number(value: object, field: str) -> float:
    """Return a finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FireFuelError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise FireFuelError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


def _non_negative(value: object, field: str) -> float:
    """Return a finite, non-negative float."""
    number = _number(value, field)
    if number < 0.0:
        raise FireFuelError(f"{field} must be non-negative")
    return number


def _positive(value: object, field: str) -> float:
    """Return a finite, strictly positive float."""
    number = _number(value, field)
    if number <= 0.0:
        raise FireFuelError(f"{field} must be positive")
    return number
