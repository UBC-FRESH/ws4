"""Spatially explicit fire growth on a site grid.

The growth engine turns the FBP surface and crown-fire behaviour into a perimeter. It uses a
minimum-travel-time / Huygens construction on a regular cell grid: a burning cell sends an
ignition wave to each neighbour with a directional rate of spread from an elliptical template.

The head rate of spread comes from the validated FBP surface and crown layer. The effective
wind speed folds the slope into the wind vector using the FBP slope adjustment. The first slice
is a homogeneous fuel grid with a burnable mask; heterogeneous fuel and the P144 event-log
bridge follow in later P156 tasks.
"""

from __future__ import annotations

import bisect
import heapq
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np

from .crown import fbp_crown_fire
from .fbp import (
    FBP_FUEL_TYPE_TABLE,
    _initial_surface_ros,
    canonical_fuel_type,
)
from .fuel import FireFuelError, _non_negative, _number, _probability
from .fwi import initial_spread_index
from .wind import WindNinjaGrid, wind_grid_at

if TYPE_CHECKING:
    from ws4.ecosystem.events import Event

#: The maximum number of snapshots a growth run will retain.
_DEFAULT_MAX_SNAPSHOTS: Final[int] = 10_000

#: The provenance identifier for the growth model and its fragment bridge.
GROWTH_MODEL_VERSION: Final[str] = "ws4.fire.growth.v1"


def _float_site_grid(
    value: np.ndarray | None,
    name: str,
    rows: int,
    cols: int,
    default: float,
) -> np.ndarray:
    """Return a validated float grid or a constant grid."""
    if value is None:
        return np.full((rows, cols), float(default), dtype=float)
    array = np.asarray(value, dtype=float)
    if array.shape != (rows, cols):
        raise FireFuelError(f"{name} must have shape (rows, cols)")
    if not bool(np.isfinite(array).all()):
        raise FireFuelError(f"{name} must be finite")
    return array.copy()


def _probability_grid(
    value: np.ndarray | None,
    name: str,
    rows: int,
    cols: int,
    default: float,
) -> np.ndarray:
    """Return a validated 0-100 percentage grid or a constant grid."""
    array = _float_site_grid(value, name, rows, cols, default)
    if bool((array < 0.0).any()) or bool((array > 100.0).any()):
        raise FireFuelError(f"{name} must be between 0 and 100")
    return array


@dataclass(frozen=True)
class EffectiveWind:
    """The wind vector after the FBP slope adjustment.

    Attributes
    ----------
    speed_kmh : float
        Effective wind speed in kilometres per hour.
    azimuth_deg : float
        The direction the fire spreads toward, clockwise from north.
    """

    speed_kmh: float
    azimuth_deg: float


@dataclass(frozen=True)
class SiteGrid:
    """A homogeneous fuel grid with one weather and slope condition.

    Parameters
    ----------
    fuel_type : str
        FBP fuel type.
    rows, cols : int
        Grid dimensions.
    cell_size_m : float
        Cell side length in metres.
    ffmc : float
        Fine Fuel Moisture Code.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed.
    wind_direction_deg : float
        Direction the wind comes from, clockwise from north.
    slope_percent : float
        Ground slope in percent.
    aspect_deg : float
        Slope aspect, the direction the slope faces downslope, clockwise from north.
    foliar_moisture_percent : float or None, optional
        Foliar moisture content; None derives it from the site and day.
    latitude_deg, longitude_deg, elevation_m, julian_day : optional
        Site and day inputs for the derived foliar moisture.
    conifer_percent, dead_fir_percent, crown_closure_percent, grass_fuel_load_kg_m2 : optional
        FBP blend and grass parameters.
    burnable : numpy.ndarray or None, optional
        Boolean burnable mask; None makes every cell burnable.
    fuel_type_grid : numpy.ndarray or None, optional
        Per-cell canonical FBP fuel types. ``None`` cells are unburnable. When provided, the
        scalar ``fuel_type`` is only a fallback label for summaries.
    slope_percent_grid, aspect_deg_grid, elevation_m_grid : numpy.ndarray or None, optional
        Per-cell terrain. None uses the corresponding scalar field.
    conifer_percent_grid, dead_fir_percent_grid, crown_closure_percent_grid : optional
        Per-cell FBP blend parameters. None uses the scalar values.
    wind_direction_patch : numpy.ndarray or None, optional
        Per-cell wind-direction override in degrees, or NaN outside the patch.
    """

    fuel_type: str
    rows: int
    cols: int
    cell_size_m: float
    ffmc: float
    bui: float
    wind_kmh: float
    wind_direction_deg: float
    slope_percent: float
    aspect_deg: float
    foliar_moisture_percent: float | None = None
    latitude_deg: float = 55.0
    longitude_deg: float = -120.0
    elevation_m: float = 0.0
    julian_day: int = 180
    conifer_percent: float = 50.0
    dead_fir_percent: float = 35.0
    crown_closure_percent: float = 80.0
    grass_fuel_load_kg_m2: float = 0.35
    burnable: np.ndarray | None = None
    fuel_type_grid: np.ndarray | None = None
    slope_percent_grid: np.ndarray | None = None
    aspect_deg_grid: np.ndarray | None = None
    elevation_m_grid: np.ndarray | None = None
    conifer_percent_grid: np.ndarray | None = None
    dead_fir_percent_grid: np.ndarray | None = None
    crown_closure_percent_grid: np.ndarray | None = None
    wind_direction_patch: np.ndarray | None = None

    def __post_init__(self) -> None:
        """Validate the grid and canonicalize the burnable mask."""
        name = canonical_fuel_type(self.fuel_type)
        if isinstance(self.rows, bool) or not isinstance(self.rows, int) or self.rows <= 0:
            raise FireFuelError("rows must be a positive integer")
        if isinstance(self.cols, bool) or not isinstance(self.cols, int) or self.cols <= 0:
            raise FireFuelError("cols must be a positive integer")
        cell = _number(self.cell_size_m, "cell_size_m")
        if cell <= 0.0:
            raise FireFuelError("cell_size_m must be positive")
        code = _number(self.ffmc, "ffmc")
        if code < 0.0 or code > 101.0:
            raise FireFuelError("ffmc must be between 0 and 101")
        buildup = _non_negative(self.bui, "bui")
        wind = _non_negative(self.wind_kmh, "wind_kmh")
        wind_direction = _number(self.wind_direction_deg, "wind_direction_deg") % 360.0
        slope = _non_negative(self.slope_percent, "slope_percent")
        aspect = _number(self.aspect_deg, "aspect_deg") % 360.0
        fuel_grid: np.ndarray | None = None
        if self.fuel_type_grid is not None:
            raw = np.asarray(self.fuel_type_grid, dtype=object)
            if raw.shape != (self.rows, self.cols):
                raise FireFuelError("fuel_type_grid must have shape (rows, cols)")
            fuel_grid = np.empty((self.rows, self.cols), dtype=object)
            for row in range(self.rows):
                for col in range(self.cols):
                    value = raw[row, col]
                    fuel_grid[row, col] = None if value is None else canonical_fuel_type(str(value))
        if self.burnable is None:
            mask = (
                np.ones((self.rows, self.cols), dtype=bool)
                if fuel_grid is None
                else np.array(
                    [[value is not None for value in row] for row in fuel_grid], dtype=bool
                )
            )
        else:
            mask = np.asarray(self.burnable, dtype=bool)
            if mask.shape != (self.rows, self.cols):
                raise FireFuelError("burnable must have shape (rows, cols)")
            mask = mask.copy()
            if fuel_grid is not None:
                mask &= np.array(
                    [[value is not None for value in row] for row in fuel_grid], dtype=bool
                )
        slope_grid = _float_site_grid(
            self.slope_percent_grid, "slope_percent_grid", self.rows, self.cols, slope
        )
        if bool((slope_grid < 0.0).any()):
            raise FireFuelError("slope_percent_grid must be non-negative")
        aspect_grid = (
            _float_site_grid(self.aspect_deg_grid, "aspect_deg_grid", self.rows, self.cols, aspect)
            % 360.0
        )
        elevation_grid = _float_site_grid(
            self.elevation_m_grid,
            "elevation_m_grid",
            self.rows,
            self.cols,
            self.elevation_m,
        )
        conifer_grid = _probability_grid(
            self.conifer_percent_grid,
            "conifer_percent_grid",
            self.rows,
            self.cols,
            self.conifer_percent,
        )
        dead_fir_grid = _probability_grid(
            self.dead_fir_percent_grid,
            "dead_fir_percent_grid",
            self.rows,
            self.cols,
            self.dead_fir_percent,
        )
        closure_grid = _probability_grid(
            self.crown_closure_percent_grid,
            "crown_closure_percent_grid",
            self.rows,
            self.cols,
            self.crown_closure_percent,
        )
        wind_patch: np.ndarray | None = None
        if self.wind_direction_patch is not None:
            wind_patch = np.asarray(self.wind_direction_patch, dtype=float)
            if wind_patch.shape != (self.rows, self.cols):
                raise FireFuelError("wind_direction_patch must have shape (rows, cols)")
            wind_patch = wind_patch.copy()
        object.__setattr__(self, "fuel_type", name)
        object.__setattr__(self, "cell_size_m", cell)
        object.__setattr__(self, "ffmc", code)
        object.__setattr__(self, "bui", buildup)
        object.__setattr__(self, "wind_kmh", wind)
        object.__setattr__(self, "wind_direction_deg", wind_direction)
        object.__setattr__(self, "slope_percent", slope)
        object.__setattr__(self, "aspect_deg", aspect)
        object.__setattr__(self, "burnable", mask)
        object.__setattr__(self, "fuel_type_grid", fuel_grid)
        object.__setattr__(self, "slope_percent_grid", slope_grid)
        object.__setattr__(self, "aspect_deg_grid", aspect_grid)
        object.__setattr__(self, "elevation_m_grid", elevation_grid)
        object.__setattr__(self, "conifer_percent_grid", conifer_grid)
        object.__setattr__(self, "dead_fir_percent_grid", dead_fir_grid)
        object.__setattr__(self, "crown_closure_percent_grid", closure_grid)
        object.__setattr__(self, "wind_direction_patch", wind_patch)

    @property
    def cell_area_ha(self) -> float:
        """Return the area of one cell in hectares.

        Returns
        -------
        float
            ``cell_size_m² / 10000``.
        """
        return self.cell_size_m**2 / 10_000.0


@dataclass(frozen=True)
class BurningConditions:
    """Restrict growth to weather steps that meet the documented burning conditions.

    The thresholds are exclusive, matching the sample scenario wording: an ISI must be
    greater than ``isi_gt``, wind greater than ``wind_gt_kmh``, and relative humidity
    greater than or less than the configured bound. At least one threshold must be set.

    Parameters
    ----------
    isi_gt : float or None, optional
        Minimum exclusive Initial Spread Index.
    wind_gt_kmh : float or None, optional
        Minimum exclusive ten-metre wind speed in km/h.
    relative_humidity_gt_percent : float or None, optional
        Minimum exclusive relative humidity in percent.
    relative_humidity_lt_percent : float or None, optional
        Maximum exclusive relative humidity in percent.
    source : str, optional
        Provenance label for the threshold set.

    Raises
    ------
    FireFuelError
        If no threshold is set, a threshold is negative, or a humidity bound is outside
        [0, 100] or inverted.
    """

    isi_gt: float | None = None
    wind_gt_kmh: float | None = None
    relative_humidity_gt_percent: float | None = None
    relative_humidity_lt_percent: float | None = None
    source: str = ""

    def __post_init__(self) -> None:
        """Validate the threshold set."""
        values = (
            self.isi_gt,
            self.wind_gt_kmh,
            self.relative_humidity_gt_percent,
            self.relative_humidity_lt_percent,
        )
        if all(value is None for value in values):
            raise FireFuelError("at least one burning-condition threshold is required")
        for value, name in (
            (self.isi_gt, "isi_gt"),
            (self.wind_gt_kmh, "wind_gt_kmh"),
        ):
            if value is not None and _non_negative(value, name) < 0.0:
                raise FireFuelError(f"{name} must be non-negative")
        for value, name in (
            (self.relative_humidity_gt_percent, "relative_humidity_gt_percent"),
            (self.relative_humidity_lt_percent, "relative_humidity_lt_percent"),
        ):
            if value is not None and not 0.0 <= _number(value, name) <= 100.0:
                raise FireFuelError(f"{name} must be between 0 and 100")
        if (
            self.relative_humidity_gt_percent is not None
            and self.relative_humidity_lt_percent is not None
            and self.relative_humidity_gt_percent >= self.relative_humidity_lt_percent
        ):
            raise FireFuelError(
                "relative_humidity_gt_percent must be less than relative_humidity_lt_percent"
            )

    def allows(
        self,
        *,
        isi: float,
        wind_kmh: float,
        relative_humidity_percent: float,
    ) -> bool:
        """Return whether a weather step meets every configured threshold.

        Parameters
        ----------
        isi : float
            Initial Spread Index for the step.
        wind_kmh : float
            Ten-metre wind speed for the step.
        relative_humidity_percent : float
            Relative humidity for the step.

        Returns
        -------
        bool
            True when every configured threshold is met.
        """
        if self.isi_gt is not None and not isi > self.isi_gt:
            return False
        if self.wind_gt_kmh is not None and not wind_kmh > self.wind_gt_kmh:
            return False
        if (
            self.relative_humidity_gt_percent is not None
            and not relative_humidity_percent > self.relative_humidity_gt_percent
        ):
            return False
        return not (
            self.relative_humidity_lt_percent is not None
            and relative_humidity_percent >= self.relative_humidity_lt_percent
        )

    def to_dict(self) -> dict[str, object]:
        """Return the threshold set as a JSON-serializable mapping.

        Returns
        -------
        dict
            Configured thresholds and their provenance label.
        """
        return {
            "isi_gt": self.isi_gt,
            "wind_gt_kmh": self.wind_gt_kmh,
            "relative_humidity_gt_percent": self.relative_humidity_gt_percent,
            "relative_humidity_lt_percent": self.relative_humidity_lt_percent,
            "source": self.source,
        }


@dataclass(frozen=True)
class WeatherStep:
    """One piecewise-constant weather interval for time-dependent growth.

    Parameters
    ----------
    start_min : float
        Interval start in minutes from ignition.
    wind_kmh : float
        Ten-metre wind speed.
    wind_direction_deg : float
        Direction the wind comes from, clockwise from north.
    ffmc, bui : float or None, optional
        Moisture codes for this interval. None uses the site-grid values.
    relative_humidity_percent : float or None, optional
        Relative humidity in percent, required when burning conditions are enabled.
    """

    start_min: float
    wind_kmh: float
    wind_direction_deg: float
    ffmc: float | None = None
    bui: float | None = None
    relative_humidity_percent: float | None = None

    def __post_init__(self) -> None:
        """Validate the weather step."""
        if _non_negative(self.start_min, "start_min") < 0.0:
            raise FireFuelError("start_min must be non-negative")
        _non_negative(self.wind_kmh, "wind_kmh")
        _number(self.wind_direction_deg, "wind_direction_deg")
        if self.ffmc is not None and not 0.0 <= _number(self.ffmc, "ffmc") <= 101.0:
            raise FireFuelError("ffmc must be between 0 and 101")
        if self.bui is not None:
            _non_negative(self.bui, "bui")
        if self.relative_humidity_percent is not None and not (
            0.0 <= _number(self.relative_humidity_percent, "relative_humidity_percent") <= 100.0
        ):
            raise FireFuelError("relative_humidity_percent must be between 0 and 100")


@dataclass(frozen=True)
class GrowthConfig:
    """The ignition and snapshot configuration of a growth run.

    Parameters
    ----------
    ignition_cells : tuple of (int, int)
        Ignition cells as ``(row, col)``.
    max_time_min : float, optional
        The maximum simulated time in minutes (default 240).
    snapshot_interval_min : float, optional
        The snapshot interval in minutes (default 30).
    allow_diagonal : bool, optional
        Use the eight-neighbourhood (default True); False uses four neighbours.
    neighbor_radius : int, optional
        Primitive-direction radius in [1, 3]. One is the eight-neighbourhood, two is the
        sixteen-direction ring, and three is the twenty-four-direction ring (default 2).
    weather_steps : tuple of WeatherStep or None, optional
        Piecewise-constant weather. None uses one constant state from the site grid.
    wind_patch_end_min : float or None, optional
        Stop applying the site-grid wind-direction patch after this time.
    burning_conditions : BurningConditions or None, optional
        Weather-step thresholds. They require ``weather_steps`` with relative humidity.
    wind_grids : dict of int to WindNinjaGrid or None, optional
        Spatial wind inputs keyed by domain-average direction. They require
        ``weather_steps`` and select the nearest direction grid for each step.
    """

    ignition_cells: tuple[tuple[int, int], ...]
    max_time_min: float = 240.0
    snapshot_interval_min: float = 30.0
    allow_diagonal: bool = True
    neighbor_radius: int = 2
    weather_steps: tuple[WeatherStep, ...] | None = None
    wind_patch_end_min: float | None = None
    burning_conditions: BurningConditions | None = None
    wind_grids: dict[int, WindNinjaGrid] | None = None

    def __post_init__(self) -> None:
        """Validate the growth configuration."""
        if not self.ignition_cells:
            raise FireFuelError("at least one ignition cell is required")
        for cell in self.ignition_cells:
            if len(cell) != 2:
                raise FireFuelError("ignition cells must be (row, col) pairs")
        if _non_negative(self.max_time_min, "max_time_min") <= 0.0:
            raise FireFuelError("max_time_min must be positive")
        if _non_negative(self.snapshot_interval_min, "snapshot_interval_min") <= 0.0:
            raise FireFuelError("snapshot_interval_min must be positive")
        if isinstance(self.neighbor_radius, bool) or not isinstance(self.neighbor_radius, int):
            raise FireFuelError("neighbor_radius must be an integer")
        if self.neighbor_radius < 1 or self.neighbor_radius > 3:
            raise FireFuelError("neighbor_radius must be between 1 and 3")
        if self.weather_steps is not None:
            if not self.weather_steps:
                raise FireFuelError("weather_steps must not be empty")
            previous = -1.0
            for step in self.weather_steps:
                if not isinstance(step, WeatherStep):
                    raise FireFuelError("weather_steps must contain WeatherStep values")
                if step.start_min <= previous:
                    raise FireFuelError("weather_steps must be ordered by start_min")
                previous = step.start_min
            if self.weather_steps[0].start_min != 0.0:
                raise FireFuelError("the first weather step must start at 0")
        if self.burning_conditions is not None:
            if not isinstance(self.burning_conditions, BurningConditions):
                raise FireFuelError("burning_conditions must be a BurningConditions value")
            if self.weather_steps is None:
                raise FireFuelError("burning_conditions require weather_steps")
            if any(step.relative_humidity_percent is None for step in self.weather_steps):
                raise FireFuelError(
                    "burning_conditions require relative_humidity_percent on every weather step"
                )
        if self.wind_grids is not None:
            if not self.wind_grids:
                raise FireFuelError("wind_grids must not be empty")
            if self.weather_steps is None:
                raise FireFuelError("wind_grids require weather_steps")
            if any(not isinstance(key, int) for key in self.wind_grids):
                raise FireFuelError("wind_grids keys must be integer directions")
            if any(not isinstance(value, WindNinjaGrid) for value in self.wind_grids.values()):
                raise FireFuelError("wind_grids values must be WindNinjaGrid objects")
        if (
            self.wind_patch_end_min is not None
            and _non_negative(self.wind_patch_end_min, "wind_patch_end_min") <= 0.0
        ):
            raise FireFuelError("wind_patch_end_min must be positive")


@dataclass(frozen=True)
class GrowthSnapshot:
    """The burned area and perimeter at one time.

    Attributes
    ----------
    time_min : float
        Simulation time in minutes.
    burned_cells : int
        Number of burned cells.
    area_ha : float
        Burned area in hectares.
    perimeter_m : float
        Exposed burned-cell edge length in metres.
    """

    time_min: float
    burned_cells: int
    area_ha: float
    perimeter_m: float

    def to_dict(self) -> dict[str, float]:
        """Return the snapshot as a JSON-serializable mapping.

        Returns
        -------
        dict
            Time, cell count, area, and perimeter.
        """
        return {
            "time_min": self.time_min,
            "burned_cells": float(self.burned_cells),
            "area_ha": self.area_ha,
            "perimeter_m": self.perimeter_m,
        }


@dataclass(frozen=True)
class FragmentIgnition:
    """The earliest growth-front arrival in one dataset fragment.

    Attributes
    ----------
    fragment_id : int
        The positive dataset fragment id.
    ignition_time_min : float
        The earliest cell ignition time in minutes.
    area_ha : float
        The burned area inside the fragment in hectares.
    burned_cells : int
        The number of burned cells inside the fragment.
    """

    fragment_id: int
    ignition_time_min: float
    area_ha: float
    burned_cells: int

    def to_dict(self) -> dict[str, float]:
        """Return the ignition as a JSON-serializable mapping.

        Returns
        -------
        dict
            Fragment id, ignition time, area, and cell count.
        """
        return {
            "fragment_id": float(self.fragment_id),
            "ignition_time_min": self.ignition_time_min,
            "area_ha": self.area_ha,
            "burned_cells": float(self.burned_cells),
        }


@dataclass(frozen=True)
class GrowthResult:
    """The output of one growth run.

    Attributes
    ----------
    grid : SiteGrid
        The site grid.
    config : GrowthConfig
        The growth configuration.
    ignition_time_min : numpy.ndarray
        Ignition time per cell; infinity for unburned cells.
    snapshots : tuple of GrowthSnapshot
        Area and perimeter snapshots.
    burned_area_ha : float
        Final burned area.
    perimeter_m : float
        Final perimeter.
    effective_wind : EffectiveWind
        The slope-adjusted wind.
    head_ros_m_min : float
        The representative head rate of spread used by the ellipse.
    length_to_breadth : float
        The representative ellipse length-to-breadth ratio.
    head_ros_grid : numpy.ndarray or None, optional
        Per-cell head rate of spread for a heterogeneous grid.
    length_to_breadth_grid : numpy.ndarray or None, optional
        Per-cell length-to-breadth ratio for a heterogeneous grid.
    spread_azimuth_deg_grid : numpy.ndarray or None, optional
        Per-cell spread azimuth for a heterogeneous grid.
    """

    grid: SiteGrid
    config: GrowthConfig
    ignition_time_min: np.ndarray
    snapshots: tuple[GrowthSnapshot, ...]
    burned_area_ha: float
    perimeter_m: float
    effective_wind: EffectiveWind
    head_ros_m_min: float
    length_to_breadth: float
    head_ros_grid: np.ndarray | None = None
    length_to_breadth_grid: np.ndarray | None = None
    spread_azimuth_deg_grid: np.ndarray | None = None

    def summary(self) -> dict[str, object]:
        """Return a stable summary of the growth run.

        Returns
        -------
        dict
            The fuel type, effective wind, ellipse, final area and perimeter, and snapshots.
        """
        return {
            "fuel_type": (
                "heterogeneous" if self.grid.fuel_type_grid is not None else self.grid.fuel_type
            ),
            "effective_wind_kmh": self.effective_wind.speed_kmh,
            "spread_azimuth_deg": self.effective_wind.azimuth_deg,
            "head_ros_m_min": self.head_ros_m_min,
            "length_to_breadth": self.length_to_breadth,
            "weather_mode": (
                "time_dependent" if self.config.weather_steps is not None else "constant"
            ),
            "weather_steps": len(self.config.weather_steps or ()),
            "burning_conditions": (
                None
                if self.config.burning_conditions is None
                else self.config.burning_conditions.to_dict()
            ),
            "wind_grids": (
                None
                if self.config.wind_grids is None
                else {
                    "directions": sorted(self.config.wind_grids),
                    "method": next(iter(self.config.wind_grids.values())).method,
                    "source": next(iter(self.config.wind_grids.values())).source,
                }
            ),
            "burned_area_ha": self.burned_area_ha,
            "perimeter_m": self.perimeter_m,
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }


def _invert_basic_isi(fuel_type: str, rate_of_spread: float) -> float:
    """Invert a simple FBP RSI relation to an ISI."""
    fuel = FBP_FUEL_TYPE_TABLE[fuel_type]
    if fuel.a <= 0.0 or fuel.b <= 0.0 or fuel.c <= 0.0:
        raise FireFuelError(f"fuel type {fuel_type!r} has no invertible RSI relation")
    value = 1.0 - (rate_of_spread / fuel.a) ** (1.0 / fuel.c)
    if value >= 0.01:
        return math.log(value) / (-fuel.b)
    return math.log(0.01) / (-fuel.b)


def _invert_o1_isi(fuel_type: str, rate_of_spread: float, crown_closure_percent: float) -> float:
    """Invert the O1 RSI relation."""
    fuel = FBP_FUEL_TYPE_TABLE[fuel_type]
    cf = (
        0.005 * (math.exp(0.061 * crown_closure_percent) - 1.0)
        if crown_closure_percent < 58.8
        else 0.176 + 0.02 * (crown_closure_percent - 58.8)
    )
    value = 1.0 - (rate_of_spread / (cf * fuel.a)) ** (1.0 / fuel.c)
    if value >= 0.01:
        return math.log(value) / (-fuel.b)
    return math.log(0.01) / (-fuel.b)


def effective_wind(
    fuel_type: str,
    ffmc: float,
    bui: float,
    wind_kmh: float,
    wind_direction_deg: float,
    slope_percent: float,
    aspect_deg: float,
    *,
    conifer_percent: float = 50.0,
    dead_fir_percent: float = 35.0,
    crown_closure_percent: float = 80.0,
) -> EffectiveWind:
    """Fold slope into the wind vector using the FBP slope adjustment.

    Parameters
    ----------
    fuel_type : str
        FBP fuel type.
    ffmc : float
        Fine Fuel Moisture Code.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed.
    wind_direction_deg : float
        Direction the wind comes from.
    slope_percent : float
        Ground slope in percent.
    aspect_deg : float
        Slope aspect.
    conifer_percent, dead_fir_percent, crown_closure_percent : optional
        FBP blend and grass parameters.

    Returns
    -------
    EffectiveWind
        The effective wind speed and the spread azimuth.

    Raises
    ------
    FireFuelError
        If an input is invalid or a C6 slope adjustment is requested.
    """
    name = canonical_fuel_type(fuel_type)
    code = _number(ffmc, "ffmc")
    if code < 0.0 or code > 101.0:
        raise FireFuelError("ffmc must be between 0 and 101")
    _non_negative(bui, "bui")
    wind = _non_negative(wind_kmh, "wind_kmh")
    wind_direction = _number(wind_direction_deg, "wind_direction_deg") % 360.0
    slope = _non_negative(slope_percent, "slope_percent")
    aspect = _number(aspect_deg, "aspect_deg") % 360.0
    conifer = _probability(conifer_percent / 100.0, "conifer_percent") * 100.0
    dead_fir = _probability(dead_fir_percent / 100.0, "dead_fir_percent") * 100.0
    closure = _probability(crown_closure_percent / 100.0, "crown_closure_percent") * 100.0
    if slope <= 0.0:
        return EffectiveWind(wind, (wind_direction + 180.0) % 360.0)
    if name == "C6":
        raise FireFuelError("C6 slope adjustment is not implemented; use flat ground")
    slope_factor = 10.0 if slope >= 70.0 else math.exp(3.533 * (slope / 100.0) ** 1.2)
    isz = initial_spread_index(code, 0.0, fbp=True)
    if name in {"M1", "M2"}:
        rsz_c2 = _initial_surface_ros(
            "C2",
            isz,
            conifer_percent=conifer,
            dead_fir_percent=dead_fir,
            crown_closure_percent=closure,
        )
        rsz_d1 = _initial_surface_ros(
            "D1",
            isz,
            conifer_percent=conifer,
            dead_fir_percent=dead_fir,
            crown_closure_percent=closure,
        )
        isf_c2 = _invert_basic_isi("C2", rsz_c2 * slope_factor)
        isf_d1 = _invert_basic_isi("D1", rsz_d1 * slope_factor)
        isf = conifer / 100.0 * isf_c2 + (1.0 - conifer / 100.0) * isf_d1
    elif name in {"M3", "M4"}:
        rsz_base = _initial_surface_ros(
            name,
            isz,
            conifer_percent=conifer,
            dead_fir_percent=100.0,
            crown_closure_percent=closure,
        )
        rsz_d1 = _initial_surface_ros(
            "D1",
            isz,
            conifer_percent=conifer,
            dead_fir_percent=dead_fir,
            crown_closure_percent=closure,
        )
        isf_base = _invert_basic_isi(name, rsz_base * slope_factor)
        isf_d1 = _invert_basic_isi("D1", rsz_d1 * slope_factor)
        isf = dead_fir / 100.0 * isf_base + (1.0 - dead_fir / 100.0) * isf_d1
    elif name in {"O1A", "O1B"}:
        rsz = _initial_surface_ros(
            name,
            isz,
            conifer_percent=conifer,
            dead_fir_percent=dead_fir,
            crown_closure_percent=closure,
        )
        isf = _invert_o1_isi(name, rsz * slope_factor, closure)
    else:
        rsz = _initial_surface_ros(
            name,
            isz,
            conifer_percent=conifer,
            dead_fir_percent=dead_fir,
            crown_closure_percent=closure,
        )
        isf = _invert_basic_isi(name, rsz * slope_factor)
    fm = 147.2772 * (101.0 - code) / (59.5 + code)
    f_fuel = 91.9 * math.exp(-0.1386 * fm) * (1.0 + (fm**5.31) / 49_300_000.0)
    ratio = isf / (0.208 * f_fuel)
    if ratio <= 0.0:
        raise FireFuelError("slope adjustment produced a non-positive effective wind")
    wse = (1.0 / 0.05039) * math.log(ratio)
    if wse > 40.0 and isf < 0.999 * 2.496 * f_fuel:
        inner = 1.0 - isf / (2.496 * f_fuel)
        wse = 112.45 if inner <= 0.0 else 28.0 - (1.0 / 0.0818) * math.log(inner)
    elif wse > 40.0:
        wse = 112.45
    wind_azimuth = math.radians((wind_direction + 180.0) % 360.0)
    slope_azimuth = math.radians((aspect + 180.0) % 360.0)
    wx = wind * math.sin(wind_azimuth) + wse * math.sin(slope_azimuth)
    wy = wind * math.cos(wind_azimuth) + wse * math.cos(slope_azimuth)
    speed = math.hypot(wx, wy)
    if speed <= 0.0:
        return EffectiveWind(0.0, 0.0)
    azimuth = math.degrees(math.acos(max(-1.0, min(1.0, wy / speed))))
    if wx < 0.0:
        azimuth = 360.0 - azimuth
    return EffectiveWind(speed, azimuth % 360.0)


def length_to_breadth(fuel_type: str, effective_wind_kmh: float) -> float:
    """Return the FBP fire ellipse length-to-breadth ratio.

    Parameters
    ----------
    fuel_type : str
        FBP fuel type.
    effective_wind_kmh : float
        Effective wind speed.

    Returns
    -------
    float
        The length-to-breadth ratio.
    """
    name = canonical_fuel_type(fuel_type)
    wind = _non_negative(effective_wind_kmh, "effective_wind_kmh")
    if name in {"O1A", "O1B"}:
        return 1.1 * wind**0.464 if wind >= 1.0 else 1.0
    return float(1.0 + 8.729 * (1.0 - math.exp(-0.03 * wind)) ** 2.155)


def _direction_ros(head_ros: float, length_breadth: float, angle_rad: float) -> float:
    """Return the elliptical ROS in a direction relative to the head."""
    if length_breadth <= 1.0:
        return head_ros
    eccentricity = (length_breadth**2 - 1.0) / (length_breadth**2 + 1.0)
    denominator = 1.0 - eccentricity * math.cos(angle_rad)
    if denominator <= 0.0:
        return 0.0
    return float(head_ros * (1.0 - eccentricity) / denominator)


def directional_ros(head_ros_m_min: float, length_breadth: float, angle_deg: float) -> float:
    """Return the elliptical rate of spread in a direction relative to the head.

    Parameters
    ----------
    head_ros_m_min : float
        Head-fire rate of spread.
    length_breadth : float
        Fire ellipse length-to-breadth ratio.
    angle_deg : float
        Direction relative to the head, in degrees.

    Returns
    -------
    float
        Directional rate of spread in metres per minute.
    """
    return _direction_ros(head_ros_m_min, length_breadth, math.radians(angle_deg))


def _line_is_burnable(burnable: np.ndarray, row: int, col: int, drow: int, dcol: int) -> bool:
    """Return whether every cell between a source and a target is burnable."""
    steps = max(abs(drow), abs(dcol))
    for step in range(1, steps):
        middle_row = row + round(drow * step / steps)
        middle_col = col + round(dcol * step / steps)
        if not bool(burnable[middle_row, middle_col]):
            return False
    return True


def _neighbor_offsets(allow_diagonal: bool, radius: int) -> list[tuple[int, int]]:
    """Return the primitive neighbour offsets for the growth update."""
    if not allow_diagonal:
        return [(0, 1), (0, -1), (1, 0), (-1, 0)]
    offsets: list[tuple[int, int]] = []
    for drow in range(-radius, radius + 1):
        for dcol in range(-radius, radius + 1):
            if drow == 0 and dcol == 0:
                continue
            if math.gcd(abs(drow), abs(dcol)) != 1:
                continue
            offsets.append((drow, dcol))
    return offsets


def slope_aspect_from_elevation(
    elevation_m: np.ndarray,
    cell_size_m: float,
    *,
    nodata: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Derive slope percent and downslope aspect from a north-first elevation grid.

    Parameters
    ----------
    elevation_m : numpy.ndarray
        Elevation in metres. Row zero is the north edge, following the ESRI ASCII grid
        convention used by the observed-fire fixture.
    cell_size_m : float
        Cell side length in metres.
    nodata : float or None, optional
        No-data value. No-data cells are filled with the valid-cell mean before the gradient.

    Returns
    -------
    tuple of numpy.ndarray
        Slope percent in ``[0, 70]`` and downslope aspect in degrees clockwise from north.

    Raises
    ------
    FireFuelError
        If the grid is invalid or has no valid elevation cells.
    """
    elevation = np.asarray(elevation_m, dtype=float)
    if elevation.ndim != 2:
        raise FireFuelError("elevation_m must be two-dimensional")
    cell = _number(cell_size_m, "cell_size_m")
    if cell <= 0.0:
        raise FireFuelError("cell_size_m must be positive")
    valid = np.isfinite(elevation)
    if nodata is not None:
        valid &= elevation != float(nodata)
    if not bool(valid.any()):
        raise FireFuelError("elevation grid has no valid cells")
    filled = elevation.copy()
    filled[~valid] = float(np.mean(elevation[valid]))
    row_gradient, col_gradient = np.gradient(filled, cell)
    north_gradient = -row_gradient
    slope = np.minimum(100.0 * np.hypot(col_gradient, north_gradient), 70.0)
    aspect = np.degrees(np.arctan2(-col_gradient, -north_gradient)) % 360.0
    aspect = np.where(slope > 1e-9, aspect, 0.0)
    slope[~valid] = 0.0
    aspect[~valid] = 0.0
    return slope, aspect


def _cell_behaviour(
    grid: SiteGrid,
    row: int,
    col: int,
    ffmc: float,
    bui: float,
    wind_kmh: float,
    wind_direction_deg: float,
) -> tuple[float, float, EffectiveWind] | None:
    """Return local head ROS, length-to-breadth, and wind for one cell."""
    fuel = grid.fuel_type if grid.fuel_type_grid is None else grid.fuel_type_grid[row, col]
    if fuel is None:
        return None
    slope = float(np.asarray(grid.slope_percent_grid)[row, col])
    aspect = float(np.asarray(grid.aspect_deg_grid)[row, col])
    elevation = float(np.asarray(grid.elevation_m_grid)[row, col])
    conifer = float(np.asarray(grid.conifer_percent_grid)[row, col])
    dead_fir = float(np.asarray(grid.dead_fir_percent_grid)[row, col])
    closure = float(np.asarray(grid.crown_closure_percent_grid)[row, col])
    wind = effective_wind(
        fuel,
        ffmc,
        bui,
        wind_kmh,
        wind_direction_deg,
        slope,
        aspect,
        conifer_percent=conifer,
        dead_fir_percent=dead_fir,
        crown_closure_percent=closure,
    )
    crown = fbp_crown_fire(
        fuel,
        ffmc,
        bui,
        wind.speed_kmh,
        foliar_moisture_percent=grid.foliar_moisture_percent,
        latitude_deg=grid.latitude_deg,
        longitude_deg=grid.longitude_deg,
        elevation_m=elevation,
        julian_day=grid.julian_day,
        conifer_percent=conifer,
        dead_fir_percent=dead_fir,
        crown_closure_percent=closure,
        grass_fuel_load_kg_m2=grid.grass_fuel_load_kg_m2,
    )
    return crown.rate_of_spread_m_min, length_to_breadth(fuel, wind.speed_kmh), wind


def _local_behaviour(
    grid: SiteGrid,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, EffectiveWind]:
    """Return per-cell head ROS, length-to-breadth, and spread azimuth."""
    rows, cols = grid.rows, grid.cols
    burnable = np.asarray(grid.burnable, dtype=bool)
    head_grid = np.zeros((rows, cols), dtype=float)
    lb_grid = np.ones((rows, cols), dtype=float)
    azimuth_grid = np.zeros((rows, cols), dtype=float)
    representative: EffectiveWind | None = None
    cache: dict[tuple[int, int], tuple[float, float, EffectiveWind]] = {}
    for row, col in zip(*np.where(burnable), strict=True):
        key = (row, col)
        cached = cache.get(key)
        if cached is None:
            wind_direction = grid.wind_direction_deg
            if grid.wind_direction_patch is not None:
                patch = float(grid.wind_direction_patch[row, col])
                if np.isfinite(patch):
                    wind_direction = patch
            value = _cell_behaviour(
                grid,
                int(row),
                int(col),
                grid.ffmc,
                grid.bui,
                grid.wind_kmh,
                wind_direction,
            )
            if value is None:
                continue
            cached = value
            cache[key] = cached
        head_grid[row, col], lb_grid[row, col], wind_value = cached
        azimuth_grid[row, col] = wind_value.azimuth_deg
        if representative is None:
            representative = wind_value
    if representative is None:
        raise FireFuelError("grid has no burnable fuel cells")
    return head_grid, lb_grid, azimuth_grid, representative


def _dynamic_arrival(
    behaviour: Callable[[int, int, int], tuple[float, float, EffectiveWind] | None],
    steps: tuple[WeatherStep, ...],
    starts: list[float],
    row: int,
    col: int,
    distance: float,
    direction: float,
    start_time: float,
    step_index: int,
) -> float:
    """Return the first arrival time along an edge with piecewise-constant weather."""
    time = start_time
    remaining = distance
    index = step_index
    while index < len(steps):
        value = behaviour(row, col, index)
        if value is None:
            return math.inf
        head, ratio, wind = value
        step_end = starts[index + 1] if index + 1 < len(starts) else math.inf
        if head <= 0.0:
            time = step_end
            index += 1
            continue
        relative = math.radians(direction - wind.azimuth_deg)
        ros = _direction_ros(head, ratio, relative)
        if ros <= 0.0:
            time = step_end
            index += 1
            continue
        available = step_end - time
        if available <= 1e-9:
            index += 1
            continue
        needed = remaining / ros
        if needed <= available:
            return time + needed
        remaining -= ros * available
        time = step_end
        index += 1
    return math.inf


def _grow_fire_time_dependent(grid: SiteGrid, config: GrowthConfig) -> GrowthResult:
    """Grow a fire with piecewise-constant weather."""
    steps = config.weather_steps
    if steps is None:
        raise FireFuelError("time-dependent growth needs weather_steps")
    burnable = np.asarray(grid.burnable, dtype=bool)
    summary_head, summary_lb, _summary_az, representative = _local_behaviour(grid)
    active = burnable & (summary_head > 0.0)
    if not bool(active.any()):
        raise FireFuelError("grid has no burnable fuel cells with a positive rate of spread")
    cache: dict[tuple[int, int, int], tuple[float, float, EffectiveWind] | None] = {}

    def behaviour(row: int, col: int, index: int) -> tuple[float, float, EffectiveWind] | None:
        key = (row, col, index)
        if key in cache:
            return cache[key]
        step = steps[index]
        if config.burning_conditions is not None:
            humidity = step.relative_humidity_percent
            if humidity is None:
                raise FireFuelError(
                    "burning_conditions require relative_humidity_percent on every weather step"
                )
            isi = initial_spread_index(
                grid.ffmc if step.ffmc is None else step.ffmc,
                step.wind_kmh,
                fbp=True,
            )
            if not config.burning_conditions.allows(
                isi=isi,
                wind_kmh=step.wind_kmh,
                relative_humidity_percent=humidity,
            ):
                blocked = (
                    0.0,
                    1.0,
                    EffectiveWind(step.wind_kmh, step.wind_direction_deg),
                )
                cache[key] = blocked
                return blocked
        wind_kmh = step.wind_kmh
        wind_direction = step.wind_direction_deg
        if config.wind_grids is not None:
            wind_kmh, wind_direction = wind_grid_at(
                config.wind_grids,
                row=row,
                col=col,
                direction_deg=step.wind_direction_deg,
            )
        patch_active = (
            config.wind_patch_end_min is None or step.start_min < config.wind_patch_end_min
        )
        if patch_active and grid.wind_direction_patch is not None:
            patch = float(grid.wind_direction_patch[row, col])
            if np.isfinite(patch):
                wind_direction = patch
        value = _cell_behaviour(
            grid,
            row,
            col,
            grid.ffmc if step.ffmc is None else step.ffmc,
            grid.bui if step.bui is None else step.bui,
            wind_kmh,
            wind_direction,
        )
        cache[key] = value
        return value

    starts = [step.start_min for step in steps]
    ignition = np.full((grid.rows, grid.cols), np.inf, dtype=float)
    queue: list[tuple[float, int, int]] = []
    for row, col in config.ignition_cells:
        ignition[row, col] = 0.0
        heapq.heappush(queue, (0.0, row, col))
    offsets = _neighbor_offsets(config.allow_diagonal, config.neighbor_radius)
    while queue:
        time, row, col = heapq.heappop(queue)
        if time > config.max_time_min:
            break
        if time > ignition[row, col] + 1e-12:
            continue
        step_index = max(0, bisect.bisect_right(starts, time) - 1)
        for drow, dcol in offsets:
            nrow = row + drow
            ncol = col + dcol
            if nrow < 0 or nrow >= grid.rows or ncol < 0 or ncol >= grid.cols:
                continue
            if not bool(burnable[nrow, ncol]):
                continue
            if not _line_is_burnable(burnable, row, col, drow, dcol):
                continue
            distance = grid.cell_size_m * math.hypot(drow, dcol)
            direction = math.degrees(math.atan2(dcol, -drow)) % 360.0
            arrival = _dynamic_arrival(
                behaviour,
                steps,
                starts,
                row,
                col,
                distance,
                direction,
                time,
                step_index,
            )
            if (
                math.isfinite(arrival)
                and arrival <= config.max_time_min
                and arrival < ignition[nrow, ncol] - 1e-12
            ):
                ignition[nrow, ncol] = arrival
                heapq.heappush(queue, (arrival, nrow, ncol))
    snapshots: list[GrowthSnapshot] = []
    time_value = 0.0
    while time_value <= config.max_time_min + 1e-9:
        burned = ignition <= time_value + 1e-12
        area, perimeter = _area_and_perimeter(burned, grid)
        snapshots.append(
            GrowthSnapshot(
                time_min=time_value,
                burned_cells=int(burned.sum()),
                area_ha=area,
                perimeter_m=perimeter,
            )
        )
        time_value += config.snapshot_interval_min
    final = snapshots[-1] if snapshots else GrowthSnapshot(0.0, 0, 0.0, 0.0)
    return GrowthResult(
        grid=grid,
        config=config,
        ignition_time_min=ignition,
        snapshots=tuple(snapshots),
        burned_area_ha=final.area_ha,
        perimeter_m=final.perimeter_m,
        effective_wind=representative,
        head_ros_m_min=float(np.mean(summary_head[active])),
        length_to_breadth=float(np.mean(summary_lb[active])),
        head_ros_grid=summary_head,
        length_to_breadth_grid=summary_lb,
        spread_azimuth_deg_grid=_summary_az,
    )


def grow_fire(grid: SiteGrid, config: GrowthConfig) -> GrowthResult:
    """Grow a fire on a homogeneous site grid.

    Parameters
    ----------
    grid : SiteGrid
        The site grid.
    config : GrowthConfig
        The ignition and snapshot configuration.

    Returns
    -------
    GrowthResult
        Ignition times, snapshots, area, perimeter, and the ellipse parameters.

    Raises
    ------
    FireFuelError
        If an ignition cell is outside the grid or unburnable, or the grid has no burnable
        cells.
    """
    if not isinstance(grid, SiteGrid):
        raise FireFuelError("grid must be a SiteGrid")
    if not isinstance(config, GrowthConfig):
        raise FireFuelError("config must be a GrowthConfig")
    burnable = np.asarray(grid.burnable, dtype=bool)
    if not bool(burnable.any()):
        raise FireFuelError("grid has no burnable cells")
    for row, col in config.ignition_cells:
        if row < 0 or row >= grid.rows or col < 0 or col >= grid.cols:
            raise FireFuelError(f"ignition cell ({row}, {col}) is outside the grid")
        if not bool(burnable[row, col]):
            raise FireFuelError(f"ignition cell ({row}, {col}) is unburnable")
    if config.weather_steps is not None:
        return _grow_fire_time_dependent(grid, config)
    head_grid, lb_grid, azimuth_grid, wind = _local_behaviour(grid)
    active = burnable & (head_grid > 0.0)
    if not bool(active.any()):
        raise FireFuelError("grid has no burnable fuel cells with a positive rate of spread")
    head_ros = float(np.mean(head_grid[active]))
    lb = float(np.mean(lb_grid[active]))
    ignition = np.full((grid.rows, grid.cols), np.inf, dtype=float)
    queue: list[tuple[float, int, int]] = []
    for row, col in config.ignition_cells:
        ignition[row, col] = 0.0
        heapq.heappush(queue, (0.0, row, col))
    offsets = _neighbor_offsets(config.allow_diagonal, config.neighbor_radius)
    while queue:
        time, row, col = heapq.heappop(queue)
        if time > config.max_time_min:
            break
        if time > ignition[row, col] + 1e-12:
            continue
        for drow, dcol in offsets:
            nrow = row + drow
            ncol = col + dcol
            if nrow < 0 or nrow >= grid.rows or ncol < 0 or ncol >= grid.cols:
                continue
            if not bool(burnable[nrow, ncol]):
                continue
            if not _line_is_burnable(burnable, row, col, drow, dcol):
                continue
            distance = grid.cell_size_m * math.hypot(drow, dcol)
            direction = math.degrees(math.atan2(dcol, -drow)) % 360.0
            relative = math.radians(direction - azimuth_grid[row, col])
            ros = _direction_ros(head_grid[row, col], lb_grid[row, col], relative)
            if ros <= 0.0:
                continue
            arrival = time + distance / ros
            if arrival <= config.max_time_min and arrival < ignition[nrow, ncol] - 1e-12:
                ignition[nrow, ncol] = arrival
                heapq.heappush(queue, (arrival, nrow, ncol))
    snapshots: list[GrowthSnapshot] = []
    time_value = 0.0
    while time_value <= config.max_time_min + 1e-9:
        burned = ignition <= time_value + 1e-12
        area, perimeter = _area_and_perimeter(burned, grid)
        snapshots.append(
            GrowthSnapshot(
                time_min=time_value,
                burned_cells=int(burned.sum()),
                area_ha=area,
                perimeter_m=perimeter,
            )
        )
        time_value += config.snapshot_interval_min
    final = snapshots[-1] if snapshots else GrowthSnapshot(0.0, 0, 0.0, 0.0)
    return GrowthResult(
        grid=grid,
        config=config,
        ignition_time_min=ignition,
        snapshots=tuple(snapshots),
        burned_area_ha=final.area_ha,
        perimeter_m=final.perimeter_m,
        effective_wind=wind,
        head_ros_m_min=head_ros,
        length_to_breadth=lb,
        head_ros_grid=head_grid,
        length_to_breadth_grid=lb_grid,
        spread_azimuth_deg_grid=azimuth_grid,
    )


def _area_and_perimeter(burned: np.ndarray, grid: SiteGrid) -> tuple[float, float]:
    """Return the area and exposed perimeter of a burned mask."""
    count = int(burned.sum())
    area = count * grid.cell_area_ha
    perimeter_cells = 0
    rows, cols = burned.shape
    for row in range(rows):
        for col in range(cols):
            if not burned[row, col]:
                continue
            if row == 0 or not burned[row - 1, col]:
                perimeter_cells += 1
            if row == rows - 1 or not burned[row + 1, col]:
                perimeter_cells += 1
            if col == 0 or not burned[row, col - 1]:
                perimeter_cells += 1
            if col == cols - 1 or not burned[row, col + 1]:
                perimeter_cells += 1
    return area, perimeter_cells * grid.cell_size_m


def _fragment_grid(value: object, shape: tuple[int, int]) -> np.ndarray:
    """Return a validated fragment-id grid.

    Parameters
    ----------
    value : object
        A two-dimensional integer array; zero means no fragment.
    shape : tuple of int
        The expected array shape.

    Returns
    -------
    numpy.ndarray
        The fragment-id grid.

    Raises
    ------
    FireFuelError
        If the array is not a two-dimensional integer grid of the expected shape or it
        contains a negative id.
    """
    array = np.asarray(value)
    if array.ndim != 2 or array.shape != shape:
        raise FireFuelError("fragment_grid must have the same shape as the growth grid")
    if not np.issubdtype(array.dtype, np.integer):
        raise FireFuelError("fragment_grid must be an integer array")
    if bool((array < 0).any()):
        raise FireFuelError("fragment_grid ids must be non-negative")
    return array.astype(np.int64, copy=False)


def fragment_ignition_times(
    result: GrowthResult,
    fragment_grid: np.ndarray,
) -> tuple[FragmentIgnition, ...]:
    """Summarize the growth front by dataset fragment.

    Parameters
    ----------
    result : GrowthResult
        A completed growth run.
    fragment_grid : numpy.ndarray
        A two-dimensional integer grid of fragment ids, shape ``(rows, cols)``. Zero means
        no fragment.

    Returns
    -------
    tuple of FragmentIgnition
        One entry per fragment reached by the front, sorted by ignition time then id.

    Raises
    ------
    FireFuelError
        If the fragment grid is invalid.
    """
    if not isinstance(result, GrowthResult):
        raise FireFuelError("result must be a GrowthResult")
    grid = _fragment_grid(fragment_grid, (result.grid.rows, result.grid.cols))
    burned = np.isfinite(result.ignition_time_min)
    entries: list[FragmentIgnition] = []
    for fragment_id in sorted(int(value) for value in np.unique(grid) if int(value) > 0):
        cells = grid == fragment_id
        reached = cells & burned
        count = int(reached.sum())
        if count == 0:
            continue
        times = result.ignition_time_min[reached]
        entries.append(
            FragmentIgnition(
                fragment_id=fragment_id,
                ignition_time_min=float(np.min(times)),
                area_ha=count * result.grid.cell_area_ha,
                burned_cells=count,
            )
        )
    return tuple(sorted(entries, key=lambda entry: (entry.ignition_time_min, entry.fragment_id)))


def fragment_ignition_events(
    result: GrowthResult,
    fragment_grid: np.ndarray,
    *,
    scenario_id: str = "default",
    year: int = 0,
    minutes_per_year: float = 525_600.0,
    process_id: str = "fire",
    fire_id: str = "growth",
) -> tuple[Event, ...]:
    """Convert a growth front to P144 ignition events.

    The events use the P144 ``ws4.ecosystem.events.Event`` record. Growth time is in minutes
    and the event clock is in years, so each ignition is placed at
    ``year + ignition_time_min / minutes_per_year``. The event carries the growth inputs and
    outputs as attributes so the fragment log can be checked against the growth field.

    Parameters
    ----------
    result : GrowthResult
        A completed growth run.
    fragment_grid : numpy.ndarray
        A two-dimensional integer grid of fragment ids. Zero means no fragment.
    scenario_id : str, optional
        The scenario id stamped on every event (default ``default``).
    year : int, optional
        The annual accounting year (default 0).
    minutes_per_year : float, optional
        The minutes per simulation year (default 525600, 365 days).
    process_id : str, optional
        The process id stamped on every event (default ``fire``).
    fire_id : str, optional
        The fire identifier used in event ids (default ``growth``).

    Returns
    -------
    tuple of Event
        One ignition event per reached fragment, sorted by event time.

    Raises
    ------
    FireFuelError
        If the fragment grid is invalid, the year is not a non-negative integer, the minutes
        per year is not positive, or a growth ignition spans more than one year.
    """
    if isinstance(year, bool) or not isinstance(year, int) or year < 0:
        raise FireFuelError("year must be a non-negative integer")
    if not isinstance(minutes_per_year, (int, float)) or isinstance(minutes_per_year, bool):
        raise FireFuelError("minutes_per_year must be a number")
    if minutes_per_year <= 0.0 or not math.isfinite(float(minutes_per_year)):
        raise FireFuelError("minutes_per_year must be finite and positive")
    if not isinstance(process_id, str) or not process_id.strip():
        raise FireFuelError("process_id must be a non-empty string")
    if not isinstance(fire_id, str) or not fire_id.strip():
        raise FireFuelError("fire_id must be a non-empty string")
    from ws4.ecosystem.events import Event

    events: list[Event] = []
    for ignition in fragment_ignition_times(result, fragment_grid):
        event_time = year + ignition.ignition_time_min / float(minutes_per_year)
        if math.floor(event_time) != year:
            raise FireFuelError("a growth ignition spans more than one simulated year")
        event = Event(
            event_id=f"{fire_id}-fragment-{year}-{ignition.fragment_id}",
            process_id=process_id,
            event_type="fire_ignition",
            time=event_time,
            year=year,
            phase="ignition",
            source=GROWTH_MODEL_VERSION,
            scenario_id=scenario_id,
            fragment_ids=(ignition.fragment_id,),
            magnitude=result.head_ros_m_min,
            area_ha=ignition.area_ha,
            attributes=(
                ("growth_model", GROWTH_MODEL_VERSION),
                ("ignition_time_min", ignition.ignition_time_min),
                ("fuel_type", result.grid.fuel_type),
                ("ffmc", result.grid.ffmc),
                ("bui", result.grid.bui),
                ("wind_kmh", result.grid.wind_kmh),
                ("effective_wind_kmh", result.effective_wind.speed_kmh),
                ("spread_azimuth_deg", result.effective_wind.azimuth_deg),
                ("head_ros_m_min", result.head_ros_m_min),
                ("length_to_breadth", result.length_to_breadth),
                ("slope_percent", result.grid.slope_percent),
                ("aspect_deg", result.grid.aspect_deg),
                ("burned_cells", float(ignition.burned_cells)),
                ("cell_size_m", result.grid.cell_size_m),
            ),
        )
        events.append(event)
    return tuple(events)
