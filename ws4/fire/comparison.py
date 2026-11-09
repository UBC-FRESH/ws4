"""Compare a simulated perimeter with an observed fire perimeter.

The comparison is deliberately raster-based: the observed rings and the simulated burned mask
are both rasterized onto the same grid, then scored with the same functions. The metrics are
area bias, perimeter bias, centroid distance, intersection over union, Sorensen coefficient,
and principal-axis orientation.

The Dogrib case starts from the observed 13:00 perimeter and grows for the 6.7-hour fire run.
It is a homogeneous-fuel approximation of a heterogeneous fire; the report names that limit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .fwi import DailyWeather, FWIState, fwi_sequence, initial_fwi_state
from .growth import (
    GrowthConfig,
    GrowthResult,
    SiteGrid,
    grow_fire,
    slope_aspect_from_elevation,
)
from .observed import ObservedFire, ObservedGrid


class ComparisonError(RuntimeError):
    """Raised when a perimeter comparison cannot be built."""


@dataclass(frozen=True)
class PerimeterMetrics:
    """The raster comparison between one simulated and one observed perimeter.

    Parameters
    ----------
    area_sim_ha : float
        Simulated burned area.
    area_obs_ha : float
        Observed burned area.
    area_bias : float
        ``(sim - obs) / obs``.
    perimeter_sim_m : float
        Simulated raster perimeter.
    perimeter_obs_m : float
        Observed raster perimeter.
    perimeter_bias : float
        ``(sim - obs) / obs``.
    centroid_distance_m : float
        Distance between the two raster centroids.
    iou : float
        Intersection over union.
    sorensen : float
        Sorensen-Dice coefficient.
    orientation_error_deg : float
        Smallest axial angle difference between the principal axes, in degrees.
    """

    area_sim_ha: float
    area_obs_ha: float
    area_bias: float
    perimeter_sim_m: float
    perimeter_obs_m: float
    perimeter_bias: float
    centroid_distance_m: float
    iou: float
    sorensen: float
    orientation_error_deg: float

    def to_dict(self) -> dict[str, float]:
        """Return the metrics as a JSON-serializable mapping.

        Returns
        -------
        dict
            All metric values.
        """
        return {
            "area_sim_ha": self.area_sim_ha,
            "area_obs_ha": self.area_obs_ha,
            "area_bias": self.area_bias,
            "perimeter_sim_m": self.perimeter_sim_m,
            "perimeter_obs_m": self.perimeter_obs_m,
            "perimeter_bias": self.perimeter_bias,
            "centroid_distance_m": self.centroid_distance_m,
            "iou": self.iou,
            "sorensen": self.sorensen,
            "orientation_error_deg": self.orientation_error_deg,
        }


@dataclass(frozen=True)
class DogribCase:
    """Base-case Dogrib simulation and its comparison.

    Parameters
    ----------
    scenario : str
        Scenario label.
    fuel_type : str
        FBP fuel-type label; for a heterogeneous run this is the fallback label.
    fuel_mode : str
        Fuel description, such as ``homogeneous C2`` or ``observed grid``.
    ffmc : float
        Fine Fuel Moisture Code.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed.
    wind_direction_deg : float
        Direction the wind comes from.
    slope_percent : float
        Homogeneous slope.
    aspect_deg : float
        Homogeneous aspect.
    duration_min : float
        Simulation duration.
    growth : GrowthResult
        The growth result.
    metrics : PerimeterMetrics
        Comparison against the observed final perimeter.
    start_cells : int
        Number of ignition cells seeded from the observed start perimeter.
    """

    scenario: str
    fuel_type: str
    fuel_mode: str
    ffmc: float
    bui: float
    wind_kmh: float
    wind_direction_deg: float
    slope_percent: float
    aspect_deg: float
    duration_min: float
    growth: GrowthResult
    metrics: PerimeterMetrics
    start_cells: int

    def to_dict(self) -> dict[str, object]:
        """Return the case summary as a JSON-serializable mapping.

        Returns
        -------
        dict
            Scenario inputs, growth summary, and metrics.
        """
        return {
            "scenario": self.scenario,
            "fuel_type": self.fuel_type,
            "fuel_mode": self.fuel_mode,
            "ffmc": self.ffmc,
            "bui": self.bui,
            "wind_kmh": self.wind_kmh,
            "wind_direction_deg": self.wind_direction_deg,
            "slope_percent": self.slope_percent,
            "aspect_deg": self.aspect_deg,
            "duration_min": self.duration_min,
            "start_cells": self.start_cells,
            "growth": {
                "burned_area_ha": self.growth.burned_area_ha,
                "perimeter_m": self.growth.perimeter_m,
                "head_ros_m_min": self.growth.head_ros_m_min,
                "length_to_breadth": self.growth.length_to_breadth,
                "effective_wind_kmh": self.growth.effective_wind.speed_kmh,
                "spread_azimuth_deg": self.growth.effective_wind.azimuth_deg,
            },
            "metrics": self.metrics.to_dict(),
        }


def rasterize_rings(
    rings: tuple[tuple[tuple[float, float], ...], ...],
    grid: ObservedGrid,
) -> np.ndarray:
    """Rasterize projected exterior rings onto the observed grid.

    Parameters
    ----------
    rings : tuple of tuple of (float, float)
        Projected exterior rings in metres.
    grid : ObservedGrid
        Target grid.

    Returns
    -------
    numpy.ndarray
        Boolean mask with one cell per grid cell.

    Raises
    ------
    ComparisonError
        If rings or grid are invalid.
    """
    if not rings:
        raise ComparisonError("at least one ring is required")
    mask = np.zeros((grid.nrows, grid.ncols), dtype=bool)
    for ring in rings:
        if len(ring) < 3:
            raise ComparisonError("a perimeter ring needs at least three points")
        min_x = min(point[0] for point in ring)
        max_x = max(point[0] for point in ring)
        min_y = min(point[1] for point in ring)
        max_y = max(point[1] for point in ring)
        col_start = max(0, math.floor((min_x - grid.xll) / grid.cell_size_m))
        col_end = min(grid.ncols - 1, math.floor((max_x - grid.xll) / grid.cell_size_m))
        row_start = max(0, grid.nrows - 1 - math.floor((max_y - grid.yll) / grid.cell_size_m))
        row_end = min(
            grid.nrows - 1,
            grid.nrows - 1 - math.floor((min_y - grid.yll) / grid.cell_size_m),
        )
        for row in range(row_start, row_end + 1):
            y = grid.yll + (grid.nrows - row - 0.5) * grid.cell_size_m
            for col in range(col_start, col_end + 1):
                x = grid.xll + (col + 0.5) * grid.cell_size_m
                if _point_in_ring(x, y, ring):
                    mask[row, col] = True
    return mask


def perimeter_length(mask: np.ndarray, cell_size_m: float) -> float:
    """Return the exposed cell-edge perimeter of a raster mask.

    Parameters
    ----------
    mask : numpy.ndarray
        Boolean burned mask.
    cell_size_m : float
        Cell side length in metres.

    Returns
    -------
    float
        Exposed edge length in metres.
    """
    if mask.ndim != 2:
        raise ComparisonError("mask must be two-dimensional")
    rows, cols = mask.shape
    edges = 0
    for row in range(rows):
        for col in range(cols):
            if not bool(mask[row, col]):
                continue
            if row == 0 or not bool(mask[row - 1, col]):
                edges += 1
            if row == rows - 1 or not bool(mask[row + 1, col]):
                edges += 1
            if col == 0 or not bool(mask[row, col - 1]):
                edges += 1
            if col == cols - 1 or not bool(mask[row, col + 1]):
                edges += 1
    return edges * cell_size_m


def centroid(mask: np.ndarray, grid: ObservedGrid) -> tuple[float, float]:
    """Return the area centroid of a raster mask in projected metres.

    Parameters
    ----------
    mask : numpy.ndarray
        Boolean mask.
    grid : ObservedGrid
        Grid geometry.

    Returns
    -------
    tuple of float
        ``(x, y)`` centroid.

    Raises
    ------
    ComparisonError
        If the mask is empty.
    """
    rows, cols = np.where(mask)
    if len(rows) == 0:
        raise ComparisonError("cannot compute a centroid for an empty mask")
    x = grid.xll + (float(np.mean(cols)) + 0.5) * grid.cell_size_m
    y = grid.yll + (grid.nrows - float(np.mean(rows)) - 0.5) * grid.cell_size_m
    return x, y


def orientation(mask: np.ndarray) -> float:
    """Return the principal-axis orientation of a raster mask in degrees.

    The angle is axial: 0 and 180 degrees describe the same axis.

    Parameters
    ----------
    mask : numpy.ndarray
        Boolean mask.

    Returns
    -------
    float
        Orientation in degrees in ``[0, 180)``. Zero is returned for an isotropic mask.
    """
    rows, cols = np.where(mask)
    if len(rows) < 3:
        return 0.0
    coordinates = np.column_stack((cols.astype(float), -rows.astype(float)))
    coordinates -= coordinates.mean(axis=0)
    covariance = np.cov(coordinates, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if float(eigenvalues[-1]) <= 1e-12:
        return 0.0
    vector = eigenvectors[:, -1]
    angle = math.degrees(math.atan2(float(vector[1]), float(vector[0]))) % 180.0
    return angle


def compare_masks(
    simulated: np.ndarray,
    observed: np.ndarray,
    grid: ObservedGrid,
) -> PerimeterMetrics:
    """Compare two raster masks with the observed-fire metrics.

    Parameters
    ----------
    simulated : numpy.ndarray
        Simulated burned mask.
    observed : numpy.ndarray
        Observed burned mask.
    grid : ObservedGrid
        Shared grid geometry.

    Returns
    -------
    PerimeterMetrics
        Area, perimeter, centroid, overlap, and orientation metrics.

    Raises
    ------
    ComparisonError
        If the masks have different shapes or the observed mask is empty.
    """
    if simulated.shape != observed.shape:
        raise ComparisonError("simulated and observed masks must have the same shape")
    observed_cells = int(observed.sum())
    simulated_cells = int(simulated.sum())
    if observed_cells == 0:
        raise ComparisonError("observed mask is empty")
    cell_area = grid.cell_size_m**2 / 10_000.0
    area_obs = observed_cells * cell_area
    area_sim = simulated_cells * cell_area
    intersection = int(np.logical_and(simulated, observed).sum())
    union = int(np.logical_or(simulated, observed).sum())
    sim_x, sim_y = centroid(simulated, grid) if simulated_cells else (math.nan, math.nan)
    obs_x, obs_y = centroid(observed, grid)
    distance = math.hypot(sim_x - obs_x, sim_y - obs_y) if simulated_cells else math.nan
    sim_perimeter = perimeter_length(simulated, grid.cell_size_m)
    obs_perimeter = perimeter_length(observed, grid.cell_size_m)
    orientation_error = _orientation_error(orientation(simulated), orientation(observed))
    return PerimeterMetrics(
        area_sim_ha=area_sim,
        area_obs_ha=area_obs,
        area_bias=0.0 if area_obs == 0.0 else (area_sim - area_obs) / area_obs,
        perimeter_sim_m=sim_perimeter,
        perimeter_obs_m=obs_perimeter,
        perimeter_bias=0.0
        if obs_perimeter == 0.0
        else (sim_perimeter - obs_perimeter) / obs_perimeter,
        centroid_distance_m=distance,
        iou=0.0 if union == 0 else intersection / union,
        sorensen=0.0
        if simulated_cells + observed_cells == 0
        else 2.0 * intersection / (simulated_cells + observed_cells),
        orientation_error_deg=orientation_error,
    )


def observed_mask(fire: ObservedFire, perimeter_index: int) -> np.ndarray:
    """Rasterize one observed perimeter.

    Parameters
    ----------
    fire : ObservedFire
        Observed fire.
    perimeter_index : int
        Index into ``fire.perimeters``.

    Returns
    -------
    numpy.ndarray
        Boolean observed mask.

    Raises
    ------
    ComparisonError
        If the index is out of range.
    """
    if perimeter_index < 0:
        perimeter_index += len(fire.perimeters)
    if perimeter_index < 0 or perimeter_index >= len(fire.perimeters):
        raise ComparisonError("perimeter index is out of range")
    return rasterize_rings(fire.perimeters[perimeter_index].rings_projected, fire.grid)


def reference_weather(fire: ObservedFire) -> dict[str, float]:
    """Return a reproducible reference weather state from the event stream.

    The helper aggregates the hourly stream to daily noon observations, uses the Prometheus
    starting DMC 64 and DC 535, and runs the WS4 FWI sequence. The event-day FFMC and BUI are
    returned with the median event-window wind.

    Parameters
    ----------
    fire : ObservedFire
        Observed fire.

    Returns
    -------
    dict
        ``ffmc``, ``bui``, ``wind_kmh``, and ``wind_direction_deg``.

    Raises
    ------
    ComparisonError
        If the weather stream cannot produce a daily sequence.
    """
    weather = fire.weather.copy()
    weather["date"] = weather["local_time"].dt.date
    daily: list[DailyWeather] = []
    for _, group in weather.groupby("date", sort=True):
        noon = group[group["local_time"].dt.hour == 13]
        if noon.empty:
            continue
        row = noon.iloc[0]
        previous = weather[
            (weather["local_time"] > row["local_time"] - pd.Timedelta(hours=24))
            & (weather["local_time"] <= row["local_time"])
        ]
        daily.append(
            DailyWeather(
                year=int(row["local_time"].year),
                month=int(row["local_time"].month),
                day=int(row["local_time"].day),
                temperature_c=float(row["temperature_c"]),
                relative_humidity_percent=float(row["relative_humidity_percent"]),
                wind_kmh=float(row["wind_speed_kmh"]),
                precipitation_mm=float(previous["precipitation_mm"].sum()),
                latitude_deg=51.65,
            )
        )
    if not daily:
        raise ComparisonError("weather stream has no daily noon observations")
    states: tuple[FWIState, ...] = fwi_sequence(
        daily, initial=initial_fwi_state(ffmc=85.0, dmc=64.0, dc=535.0)
    )
    event_day = next(
        (index for index, item in enumerate(daily) if item.month == 10 and item.day == 16),
        len(daily) - 1,
    )
    state = states[event_day]
    window = fire.weather_between(fire.event_start, fire.event_end)
    wind = float(window["wind_speed_kmh"].median())
    direction = _circular_median(window["wind_direction_deg"].to_numpy(dtype=float))
    return {
        "ffmc": state.ffmc,
        "bui": state.bui,
        "wind_kmh": wind,
        "wind_direction_deg": direction,
    }


def run_dogrib_case(
    fire: ObservedFire,
    *,
    scenario: str = "base",
    fuel_type: str = "C2",
    heterogeneous: bool = False,
    ffmc: float | None = None,
    bui: float | None = None,
    wind_kmh: float | None = None,
    wind_direction_deg: float | None = None,
    slope_percent: float = 32.0,
    aspect_deg: float = 180.0,
    duration_min: float = 402.0,
) -> DogribCase:
    """Run one Dogrib base or sensitivity case and compare it with the final perimeter.

    Parameters
    ----------
    fire : ObservedFire
        Dogrib observed fire.
    scenario : str, optional
        Scenario label.
    fuel_type : str, optional
        Homogeneous FBP fuel-type fallback (default ``C2``).
    heterogeneous : bool, optional
        Use the observed per-cell fuel, blend, and terrain grids (default False).
    ffmc, bui, wind_kmh, wind_direction_deg : float or None, optional
        Weather overrides; None uses :func:`reference_weather`.
    slope_percent : float, optional
        Homogeneous slope (default 32).
    aspect_deg : float, optional
        Homogeneous aspect (default 180).
    duration_min : float, optional
        Simulation duration (default 402 minutes, the 6.7-hour run).

    Returns
    -------
    DogribCase
        The simulated growth and comparison metrics.

    Raises
    ------
    ComparisonError
        If the start perimeter has no burnable cells or the case cannot run.
    """
    weather = reference_weather(fire)
    ffmc_value = weather["ffmc"] if ffmc is None else ffmc
    bui_value = weather["bui"] if bui is None else bui
    wind_value = weather["wind_kmh"] if wind_kmh is None else wind_kmh
    direction_value = (
        weather["wind_direction_deg"] if wind_direction_deg is None else wind_direction_deg
    )
    rows, cols = fire.grid.nrows, fire.grid.ncols
    if heterogeneous:
        fuel_grid = fire.fbp_fuel_grid()
        conifer_grid, dead_grid, closure_grid = fire.fbp_blend_grids()
        slope_grid, aspect_grid = slope_aspect_from_elevation(
            fire.elevation_m, fire.grid.cell_size_m, nodata=fire.grid.nodata
        )
        burnable = np.array([[value is not None for value in row] for row in fuel_grid], dtype=bool)
        fuel_mode = "observed grid"
    else:
        observed_fuels = fire.fuel_type_grid()
        burnable = np.array(
            [[value is not None for value in row] for row in observed_fuels], dtype=bool
        )
        fuel_grid = None
        slope_grid = np.full((rows, cols), slope_percent, dtype=float)
        aspect_grid = np.full((rows, cols), aspect_deg, dtype=float)
        conifer_grid = np.full((rows, cols), 50.0, dtype=float)
        dead_grid = np.full((rows, cols), 35.0, dtype=float)
        closure_grid = np.full((rows, cols), 80.0, dtype=float)
        fuel_mode = f"homogeneous {fuel_type}"
    start_mask = observed_mask(fire, 0)
    start_mask &= burnable
    start_cells = tuple(
        (int(row), int(col)) for row, col in zip(*np.where(start_mask), strict=True)
    )
    if not start_cells:
        raise ComparisonError("observed start perimeter has no burnable cells")
    grid = SiteGrid(
        fuel_type=fuel_type,
        rows=rows,
        cols=cols,
        cell_size_m=fire.grid.cell_size_m,
        ffmc=ffmc_value,
        bui=bui_value,
        wind_kmh=wind_value,
        wind_direction_deg=direction_value,
        slope_percent=slope_percent,
        aspect_deg=aspect_deg,
        burnable=burnable,
        fuel_type_grid=fuel_grid,
        slope_percent_grid=slope_grid,
        aspect_deg_grid=aspect_grid,
        elevation_m_grid=fire.elevation_m,
        conifer_percent_grid=conifer_grid,
        dead_fir_percent_grid=dead_grid,
        crown_closure_percent_grid=closure_grid,
    )
    growth = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=start_cells,
            max_time_min=duration_min,
            snapshot_interval_min=duration_min,
            neighbor_radius=2,
        ),
    )
    simulated = np.isfinite(growth.ignition_time_min)
    observed = observed_mask(fire, -1)
    metrics = compare_masks(simulated, observed, fire.grid)
    return DogribCase(
        scenario=scenario,
        fuel_type=fuel_type,
        fuel_mode=fuel_mode,
        ffmc=ffmc_value,
        bui=bui_value,
        wind_kmh=wind_value,
        wind_direction_deg=direction_value,
        slope_percent=slope_percent,
        aspect_deg=aspect_deg,
        duration_min=duration_min,
        growth=growth,
        metrics=metrics,
        start_cells=len(start_cells),
    )


def _point_in_ring(x: float, y: float, ring: tuple[tuple[float, float], ...]) -> bool:
    """Return whether a point is inside a polygon ring using ray casting."""
    inside = False
    count = len(ring)
    for index in range(count):
        x1, y1 = ring[index]
        x2, y2 = ring[(index + 1) % count]
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
    return inside


def _orientation_error(first: float, second: float) -> float:
    """Return the smallest axial angle difference in degrees."""
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def _circular_median(values: np.ndarray) -> float:
    """Return a circular median direction in degrees."""
    radians = np.radians(values)
    mean = math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean()))
    return math.degrees(mean) % 360.0
