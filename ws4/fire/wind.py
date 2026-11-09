"""WindNinja wind-grid inputs for observed-fire scenarios.

The Dogrib sample distributes conservation-of-mass and conservation-of-mass-and-momentum
WindNinja grids as paired angle and velocity ESRI ASCII rasters. This module reads and
validates the pairs, records their provenance, and selects the nearest direction grid for a
weather step. It does not run WindNinja.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .fuel import FireFuelError, _non_negative, _number
from .observed import ObservedGrid, read_ascii_grid

_WIND_NAME_RE = re.compile(r"windninja_(\d+)_(\d+)_(\d+)m_(ang|vel)\.asc$")


@dataclass(frozen=True)
class WindNinjaGrid:
    """A validated WindNinja angle/velocity pair on one grid.

    Parameters
    ----------
    direction_deg : int
        Domain-average wind direction named by the source files.
    angle_deg : numpy.ndarray
        Wind direction grid in degrees clockwise from north.
    speed_kmh : numpy.ndarray
        Wind speed grid in km/h.
    geometry : ObservedGrid
        Grid geometry shared by the pair.
    method : str
        WindNinja method label, such as ``conservation_of_mass``.
    source : str
        Provenance label for the archive or directory.
    """

    direction_deg: int
    angle_deg: np.ndarray
    speed_kmh: np.ndarray
    geometry: ObservedGrid
    method: str
    source: str

    def __post_init__(self) -> None:
        """Validate shapes, values, and provenance."""
        if isinstance(self.direction_deg, bool) or not isinstance(self.direction_deg, int):
            raise FireFuelError("direction_deg must be an integer")
        if not 0 <= self.direction_deg <= 360:
            raise FireFuelError("direction_deg must be between 0 and 360")
        angle = np.asarray(self.angle_deg, dtype=float)
        speed = np.asarray(self.speed_kmh, dtype=float)
        expected = (self.geometry.nrows, self.geometry.ncols)
        if angle.shape != expected or speed.shape != expected:
            raise FireFuelError("WindNinja grids must match the geometry shape")
        if not np.isfinite(angle).all() or not np.isfinite(speed).all():
            raise FireFuelError("WindNinja grids must be finite")
        if bool((angle < 0.0).any()) or bool((angle > 360.0).any()):
            raise FireFuelError("WindNinja angles must be between 0 and 360 degrees")
        if bool((speed < 0.0).any()):
            raise FireFuelError("WindNinja speeds must be non-negative")
        if not self.method:
            raise FireFuelError("method must be non-empty")
        if not self.source:
            raise FireFuelError("source must be non-empty")

    def to_dict(self) -> dict[str, object]:
        """Return the grid provenance and shape as a JSON-serializable mapping.

        Returns
        -------
        dict
            Direction, method, source, and geometry.
        """
        return {
            "direction_deg": self.direction_deg,
            "method": self.method,
            "source": self.source,
            "geometry": self.geometry.to_dict(),
        }


def read_windninja_pair(
    angle_path: str | Path,
    speed_path: str | Path,
    *,
    direction_deg: int,
    method: str,
    source: str,
    crs: str,
) -> WindNinjaGrid:
    """Read and validate one WindNinja angle/velocity pair.

    Parameters
    ----------
    angle_path, speed_path : str or Path
        ESRI ASCII angle and velocity rasters.
    direction_deg : int
        Domain-average wind direction named by the files.
    method : str
        Method label for provenance.
    source : str
        Source label for provenance.
    crs : str
        PROJ string for the grid.

    Returns
    -------
    WindNinjaGrid
        The validated pair.

    Raises
    ------
    FireFuelError
        If either grid is invalid or the pair does not share one geometry.
    """
    angle, angle_grid = read_ascii_grid(angle_path, crs=crs)
    speed, speed_grid = read_ascii_grid(speed_path, crs=crs)
    if angle_grid != speed_grid:
        raise FireFuelError("WindNinja angle and velocity grids must share one geometry")
    return WindNinjaGrid(
        direction_deg=direction_deg,
        angle_deg=angle,
        speed_kmh=speed,
        geometry=angle_grid,
        method=method,
        source=source,
    )


def load_windninja_directory(
    root: str | Path,
    *,
    method: str,
    source: str,
    crs: str,
) -> dict[int, WindNinjaGrid]:
    """Load every paired WindNinja grid in one directory.

    Parameters
    ----------
    root : str or Path
        Directory containing ``windninja_<dir>_<speed>_<res>m_ang.asc`` and ``..._vel.asc``.
    method : str
        Method label for provenance.
    source : str
        Source label for provenance.
    crs : str
        PROJ string for the grids.

    Returns
    -------
    dict of int to WindNinjaGrid
        Grids keyed by domain-average direction.

    Raises
    ------
    FireFuelError
        If a direction is incomplete or a file name is not a WindNinja pair.
    """
    directory = Path(root)
    if not directory.is_dir():
        raise FireFuelError(f"WindNinja directory does not exist: {directory}")
    pairs: dict[int, dict[str, Path]] = {}
    for path in sorted(directory.glob("windninja_*_*_*m_*.asc")):
        match = _WIND_NAME_RE.fullmatch(path.name)
        if match is None:
            raise FireFuelError(f"invalid WindNinja file name: {path.name}")
        direction = int(match.group(1))
        kind = match.group(4)
        pairs.setdefault(direction, {})[kind] = path
    if not pairs:
        raise FireFuelError("no WindNinja grids found")
    result: dict[int, WindNinjaGrid] = {}
    for direction, pair in sorted(pairs.items()):
        if set(pair) != {"ang", "vel"}:
            raise FireFuelError(f"WindNinja direction {direction} is missing a pair")
        result[direction] = read_windninja_pair(
            pair["ang"],
            pair["vel"],
            direction_deg=direction,
            method=method,
            source=source,
            crs=crs,
        )
    return result


def nearest_wind_direction(directions: list[int] | tuple[int, ...], target_deg: float) -> int:
    """Return the available direction with the smallest circular distance.

    Parameters
    ----------
    directions : list of int or tuple of int
        Available domain-average directions.
    target_deg : float
        Requested wind direction.

    Returns
    -------
    int
        The nearest available direction.

    Raises
    ------
    FireFuelError
        If no direction is available.
    """
    if not directions:
        raise FireFuelError("at least one wind-grid direction is required")
    target = _number(target_deg, "target_deg") % 360.0
    return min(
        directions,
        key=lambda direction: min(
            abs(target - direction) % 360.0,
            360.0 - abs(target - direction) % 360.0,
        ),
    )


def wind_grid_at(
    grids: dict[int, WindNinjaGrid],
    *,
    row: int,
    col: int,
    direction_deg: float,
) -> tuple[float, float]:
    """Return the nearest-direction grid's speed and direction at one cell.

    Parameters
    ----------
    grids : dict of int to WindNinjaGrid
        Loaded grids.
    row, col : int
        Cell indices.
    direction_deg : float
        Weather-step wind direction used to select the grid.

    Returns
    -------
    tuple of float
        Wind speed in km/h and direction in degrees.

    Raises
    ------
    FireFuelError
        If the cell is outside the grid or no grid exists.
    """
    selected = nearest_wind_direction(tuple(grids), direction_deg)
    grid = grids[selected]
    if row < 0 or row >= grid.geometry.nrows or col < 0 or col >= grid.geometry.ncols:
        raise FireFuelError("wind-grid cell is outside the grid")
    speed = float(grid.speed_kmh[row, col])
    direction = float(grid.angle_deg[row, col])
    return _non_negative(speed, "speed_kmh"), _number(direction, "angle_deg") % 360.0


def angular_distance(first_deg: float, second_deg: float) -> float:
    """Return the smallest absolute angular distance between two directions.

    Parameters
    ----------
    first_deg, second_deg : float
        Directions in degrees.

    Returns
    -------
    float
        Distance in degrees in [0, 180].
    """
    difference = abs(_number(first_deg, "first_deg") - _number(second_deg, "second_deg"))
    return min(difference % 360.0, 360.0 - difference % 360.0)


def grid_cell_for_xy(geometry: ObservedGrid, x: float, y: float) -> tuple[int, int]:
    """Return the north-first grid cell containing a projected point.

    Parameters
    ----------
    geometry : ObservedGrid
        Target grid geometry.
    x, y : float
        Projected coordinates.

    Returns
    -------
    tuple of int
        ``(row, col)`` indices.

    Raises
    ------
    FireFuelError
        If the point is outside the grid.
    """
    if not geometry.contains(x, y):
        raise FireFuelError("point is outside the wind grid")
    col = int((x - geometry.xll) // geometry.cell_size_m)
    row = geometry.nrows - 1 - int((y - geometry.yll) // geometry.cell_size_m)
    return row, col
