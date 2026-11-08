"""Spatially explicit fire growth on a site grid.

The growth engine turns the FBP surface and crown-fire behaviour into a perimeter. It uses a
minimum-travel-time / Huygens construction on a regular cell grid: a burning cell sends an
ignition wave to each neighbour with a directional rate of spread from an elliptical template.

The head rate of spread comes from the validated FBP surface and crown layer. The effective
wind speed folds the slope into the wind vector using the FBP slope adjustment. The first slice
is a homogeneous fuel grid with a burnable mask; heterogeneous fuel and the P144 event-log
bridge follow in later P154 tasks.
"""

from __future__ import annotations

import heapq
import math
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

if TYPE_CHECKING:
    from ws4.ecosystem.events import Event

#: The maximum number of snapshots a growth run will retain.
_DEFAULT_MAX_SNAPSHOTS: Final[int] = 10_000

#: The provenance identifier for the growth model and its fragment bridge.
GROWTH_MODEL_VERSION: Final[str] = "ws4.fire.growth.v1"


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
        if self.burnable is None:
            mask = np.ones((self.rows, self.cols), dtype=bool)
        else:
            mask = np.asarray(self.burnable, dtype=bool)
            if mask.shape != (self.rows, self.cols):
                raise FireFuelError("burnable must have shape (rows, cols)")
            mask = mask.copy()
        object.__setattr__(self, "fuel_type", name)
        object.__setattr__(self, "cell_size_m", cell)
        object.__setattr__(self, "ffmc", code)
        object.__setattr__(self, "bui", buildup)
        object.__setattr__(self, "wind_kmh", wind)
        object.__setattr__(self, "wind_direction_deg", wind_direction)
        object.__setattr__(self, "slope_percent", slope)
        object.__setattr__(self, "aspect_deg", aspect)
        object.__setattr__(self, "burnable", mask)

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
    """

    ignition_cells: tuple[tuple[int, int], ...]
    max_time_min: float = 240.0
    snapshot_interval_min: float = 30.0
    allow_diagonal: bool = True

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
        The head rate of spread used by the ellipse.
    length_to_breadth : float
        The ellipse length-to-breadth ratio.
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

    def summary(self) -> dict[str, object]:
        """Return a stable summary of the growth run.

        Returns
        -------
        dict
            The fuel type, effective wind, ellipse, final area and perimeter, and snapshots.
        """
        return {
            "fuel_type": self.grid.fuel_type,
            "effective_wind_kmh": self.effective_wind.speed_kmh,
            "spread_azimuth_deg": self.effective_wind.azimuth_deg,
            "head_ros_m_min": self.head_ros_m_min,
            "length_to_breadth": self.length_to_breadth,
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
    wind = effective_wind(
        grid.fuel_type,
        grid.ffmc,
        grid.bui,
        grid.wind_kmh,
        grid.wind_direction_deg,
        grid.slope_percent,
        grid.aspect_deg,
        conifer_percent=grid.conifer_percent,
        dead_fir_percent=grid.dead_fir_percent,
        crown_closure_percent=grid.crown_closure_percent,
    )
    crown = fbp_crown_fire(
        grid.fuel_type,
        grid.ffmc,
        grid.bui,
        wind.speed_kmh,
        foliar_moisture_percent=grid.foliar_moisture_percent,
        latitude_deg=grid.latitude_deg,
        longitude_deg=grid.longitude_deg,
        elevation_m=grid.elevation_m,
        julian_day=grid.julian_day,
        conifer_percent=grid.conifer_percent,
        dead_fir_percent=grid.dead_fir_percent,
        crown_closure_percent=grid.crown_closure_percent,
        grass_fuel_load_kg_m2=grid.grass_fuel_load_kg_m2,
    )
    head_ros = crown.rate_of_spread_m_min
    lb = length_to_breadth(grid.fuel_type, wind.speed_kmh)
    ignition = np.full((grid.rows, grid.cols), np.inf, dtype=float)
    queue: list[tuple[float, int, int]] = []
    for row, col in config.ignition_cells:
        ignition[row, col] = 0.0
        heapq.heappush(queue, (0.0, row, col))
    offsets = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    if config.allow_diagonal:
        offsets += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
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
            distance = grid.cell_size_m * math.hypot(drow, dcol)
            direction = math.degrees(math.atan2(dcol, -drow)) % 360.0
            relative = math.radians(direction - wind.azimuth_deg)
            ros = _direction_ros(head_ros, lb, relative)
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
