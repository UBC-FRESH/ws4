"""Observed-fire contracts for perimeter validation.

The P156 kernel and growth engine are validated against standard cases and the public FBP
ellipse. This module adds the next layer: a public observed fire with a perimeter, ignition,
weather, fuel, and terrain. It defines the file contract and loads the Prometheus Dogrib
sample dataset; it does not score a simulation. The comparison harness is P157.2.

The observed-fire record is read-only. It records the source, projection, time zone, units,
event window, and every field the comparison needs, so a validation result can be reproduced
without a hidden calibration step.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from .fbp import canonical_fuel_type

OBSERVED_FIRE_VERSION: Final[str] = "ws4.observed-fire.v1"
DOGRIB_CRS: Final[str] = (
    "+proj=tmerc +lat_0=0 +lon_0=-115 +k=0.9992 +x_0=500000 +y_0=0 +datum=NAD83 +units=m +no_defs"
)
DOGRIB_SOURCE: Final[str] = (
    "Prometheus sample dataset Dogrib_v624.zip; "
    "http://www.firegrowthmodel.ca/prometheus/downloads/Dogrib_v624.zip"
)


class ObservedFireError(RuntimeError):
    """Raised when an observed-fire fixture is missing or inconsistent."""


@dataclass(frozen=True)
class ObservedGrid:
    """The ESRI ASCII grid geometry of an observed-fire fixture.

    Parameters
    ----------
    ncols : int
        Number of columns.
    nrows : int
        Number of rows.
    xll : float
        X coordinate of the lower-left cell corner.
    yll : float
        Y coordinate of the lower-left cell corner.
    cell_size_m : float
        Cell side length in metres.
    nodata : float
        No-data value.
    crs : str
        PROJ string of the grid projection.
    """

    ncols: int
    nrows: int
    xll: float
    yll: float
    cell_size_m: float
    nodata: float
    crs: str

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return the grid bounds as ``(min_x, min_y, max_x, max_y)``.

        Returns
        -------
        tuple of float
            Grid bounds in projected metres.
        """
        return (
            self.xll,
            self.yll,
            self.xll + self.ncols * self.cell_size_m,
            self.yll + self.nrows * self.cell_size_m,
        )

    def contains(self, x: float, y: float) -> bool:
        """Return whether a point lies inside the grid bounds.

        Parameters
        ----------
        x, y : float
            Projected coordinates.

        Returns
        -------
        bool
            True when the point is inside the grid.
        """
        min_x, min_y, max_x, max_y = self.bounds
        return min_x <= x <= max_x and min_y <= y <= max_y

    def to_dict(self) -> dict[str, object]:
        """Return the grid geometry as a JSON-serializable mapping.

        Returns
        -------
        dict
            Grid dimensions, origin, cell size, no-data value, and CRS.
        """
        return {
            "ncols": self.ncols,
            "nrows": self.nrows,
            "xll": self.xll,
            "yll": self.yll,
            "cell_size_m": self.cell_size_m,
            "nodata": self.nodata,
            "crs": self.crs,
            "bounds": list(self.bounds),
        }


@dataclass(frozen=True)
class ObservedPerimeter:
    """One observed perimeter at one time.

    Parameters
    ----------
    observed_at : datetime
        Local time of the perimeter.
    rings_lonlat : tuple of tuple of (float, float)
        Exterior rings in longitude/latitude; a perimeter may contain spot fires.
    rings_projected : tuple of tuple of (float, float)
        Exterior rings in the grid projection, metres.
    source : str
        Source label or file name.
    """

    observed_at: datetime
    rings_lonlat: tuple[tuple[tuple[float, float], ...], ...]
    rings_projected: tuple[tuple[tuple[float, float], ...], ...]
    source: str

    @property
    def area_ha(self) -> float:
        """Return the total projected area of all rings in hectares.

        Returns
        -------
        float
            Sum of polygon areas from the shoelace formula.
        """
        total = 0.0
        for ring in self.rings_projected:
            area = 0.0
            for index, (x1, y1) in enumerate(ring):
                x2, y2 = ring[(index + 1) % len(ring)]
                area += x1 * y2 - x2 * y1
            total += abs(area) / 2.0
        return total / 10_000.0

    def to_dict(self) -> dict[str, object]:
        """Return the perimeter metadata as a JSON-serializable mapping.

        Returns
        -------
        dict
            Time, source, polygon count, total points, and area.
        """
        return {
            "observed_at": self.observed_at.isoformat(),
            "source": self.source,
            "polygons": len(self.rings_projected),
            "points": sum(len(ring) for ring in self.rings_projected),
            "area_ha": self.area_ha,
        }


def _observed_fuel_parameters(label: str) -> tuple[str, float, float, float]:
    """Map one observed lookup label to a canonical FBP fuel and blend parameters."""
    text = label.strip()
    if text.lower() == "non-fuel":
        raise ValueError("non-fuel label has no FBP parameters")
    conifer_match = re.search(r"\((\d+)\s*PC\)", text, flags=re.IGNORECASE)
    conifer = float(conifer_match.group(1)) if conifer_match else 50.0
    base = text.split("/")[0].strip()
    base = re.sub(r"\(.*?\)", "", base).strip()
    lowered = text.lower()
    if "o-1a" in lowered and "o-1b" in lowered:
        base = "O1B"
    elif "d-1" in lowered and "d-2" in lowered:
        base = "D1"
    elif "m-3" in lowered and "m-4" in lowered:
        base = "M3"
    elif "m-1" in lowered and "m-2" in lowered:
        base = "M1"
    if base.strip().upper().replace("-", "") == "D2":
        base = "D1"
    try:
        fuel = canonical_fuel_type(base)
    except Exception as error:
        raise ValueError(f"unsupported observed FBP fuel label: {label!r}") from error
    return fuel, conifer, 35.0, 80.0


@dataclass(frozen=True)
class ObservedFire:
    """A public observed fire and the inputs needed to compare a simulation.

    Parameters
    ----------
    fire_id : str
        Stable fire identifier.
    name : str
        Human-readable fire name.
    source : str
        Source and archive label.
    licence : str
        Licence or attribution note.
    time_zone : str
        Time-zone label for the weather and perimeter times.
    event_start : datetime
        Start of the comparison window.
    event_end : datetime
        End of the comparison window.
    ignition_lonlat : tuple of float
        Ignition point in longitude/latitude.
    ignition_xy : tuple of float
        Ignition point in grid projection, metres.
    grid : ObservedGrid
        Grid geometry.
    fuel_codes : numpy.ndarray
        Raw FBP fuel-grid values.
    elevation_m : numpy.ndarray
        Elevation grid in metres.
    fuel_lookup : mapping of int to str or None
        Fuel-grid value to FBP fuel type, or None for non-fuel.
    perimeters : tuple of ObservedPerimeter
        Observed perimeters, sorted by time.
    weather : pandas.DataFrame
        Hourly weather with typed columns.
    provenance : dict
        Source, archive, access date, and assumptions.
    """

    fire_id: str
    name: str
    source: str
    licence: str
    time_zone: str
    event_start: datetime
    event_end: datetime
    ignition_lonlat: tuple[float, float]
    ignition_xy: tuple[float, float]
    grid: ObservedGrid
    fuel_codes: np.ndarray
    elevation_m: np.ndarray
    fuel_lookup: Mapping[int, str | None]
    perimeters: tuple[ObservedPerimeter, ...]
    weather: pd.DataFrame
    provenance: Mapping[str, object]

    @property
    def version(self) -> str:
        """Return the observed-fire contract version.

        Returns
        -------
        str
            The contract version.
        """
        return OBSERVED_FIRE_VERSION

    def fuel_type_at(self, row: int, col: int) -> str | None:
        """Return the FBP fuel type at a grid cell.

        Parameters
        ----------
        row, col : int
            Grid coordinates.

        Returns
        -------
        str or None
            FBP fuel type, or None for non-fuel/no-data.

        Raises
        ------
        ObservedFireError
            If the cell is outside the grid or has an unknown code.
        """
        if row < 0 or row >= self.grid.nrows or col < 0 or col >= self.grid.ncols:
            raise ObservedFireError("fuel cell is outside the observed grid")
        code = int(self.fuel_codes[row, col])
        if code not in self.fuel_lookup:
            raise ObservedFireError(f"unknown observed fuel code: {code}")
        return self.fuel_lookup[code]

    def fuel_type_grid(self) -> np.ndarray:
        """Return the FBP fuel type for every grid cell.

        Returns
        -------
        numpy.ndarray
            Object array of fuel-type strings or None.
        """
        result = np.empty(self.fuel_codes.shape, dtype=object)
        for row in range(self.grid.nrows):
            for col in range(self.grid.ncols):
                result[row, col] = self.fuel_type_at(row, col)
        return result

    def fbp_fuel_grid(self) -> np.ndarray:
        """Return the canonical FBP fuel type for every grid cell.

        Returns
        -------
        numpy.ndarray
            Object array of canonical fuel names or ``None`` for non-fuel cells.

        Raises
        ------
        ObservedFireError
            If a lookup label cannot be mapped to a supported FBP type.
        """
        fuel, _conifer, _dead, _closure = self._fbp_parameters()
        return fuel

    def fbp_blend_grids(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return per-cell conifer, dead-fir, and crown-closure percentages.

        Returns
        -------
        tuple of numpy.ndarray
            Conifer percent, dead-fir percent, and crown closure percent.

        Raises
        ------
        ObservedFireError
            If a lookup label cannot be mapped to a supported FBP type.
        """
        _fuel, conifer, dead, closure = self._fbp_parameters()
        return conifer, dead, closure

    def _fbp_parameters(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return per-cell FBP fuel and blend grids from the lookup table."""
        cache: dict[int, tuple[str | None, float, float, float]] = {}
        for code, label in self.fuel_lookup.items():
            if label is None:
                cache[code] = (None, 50.0, 35.0, 80.0)
                continue
            try:
                cache[code] = _observed_fuel_parameters(label)
            except ValueError as error:
                raise ObservedFireError(str(error)) from error
        fuel = np.empty(self.fuel_codes.shape, dtype=object)
        conifer = np.full(self.fuel_codes.shape, 50.0, dtype=float)
        dead = np.full(self.fuel_codes.shape, 35.0, dtype=float)
        closure = np.full(self.fuel_codes.shape, 80.0, dtype=float)
        for row in range(self.grid.nrows):
            for col in range(self.grid.ncols):
                code = int(self.fuel_codes[row, col])
                if code not in cache:
                    raise ObservedFireError(f"unknown observed fuel code: {code}")
                fuel[row, col], conifer[row, col], dead[row, col], closure[row, col] = cache[code]
        return fuel, conifer, dead, closure

    def weather_between(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Return the hourly weather rows in a closed time window.

        Parameters
        ----------
        start, end : datetime
            Window boundaries in the fixture's local time.

        Returns
        -------
        pandas.DataFrame
            Weather rows between the boundaries.

        Raises
        ------
        ObservedFireError
            If the window is empty or outside the weather stream.
        """
        if start > end:
            raise ObservedFireError("weather window start must not be after end")
        frame = self.weather[
            (self.weather["local_time"] >= start) & (self.weather["local_time"] <= end)
        ]
        if frame.empty:
            raise ObservedFireError("weather stream does not cover the requested window")
        return frame.reset_index(drop=True)

    def to_dict(self) -> dict[str, object]:
        """Return a stable, JSON-serializable summary of the observed fire.

        Returns
        -------
        dict
            Source, grid, event window, ignition, perimeters, weather range, and fuel counts.
        """
        return {
            "schema_version": OBSERVED_FIRE_VERSION,
            "fire_id": self.fire_id,
            "name": self.name,
            "source": self.source,
            "licence": self.licence,
            "time_zone": self.time_zone,
            "event_start": self.event_start.isoformat(),
            "event_end": self.event_end.isoformat(),
            "ignition_lonlat": list(self.ignition_lonlat),
            "ignition_xy": list(self.ignition_xy),
            "grid": self.grid.to_dict(),
            "perimeters": [item.to_dict() for item in self.perimeters],
            "weather_rows": len(self.weather),
            "weather_start": self.weather["local_time"].min().isoformat(),
            "weather_end": self.weather["local_time"].max().isoformat(),
            "fuel_codes": sorted(int(code) for code in np.unique(self.fuel_codes)),
            "provenance": dict(self.provenance),
        }


def read_ascii_grid(path: str | Path, *, crs: str = DOGRIB_CRS) -> tuple[np.ndarray, ObservedGrid]:
    """Read an ESRI ASCII grid.

    Parameters
    ----------
    path : str or Path
        ASCII grid file.
    crs : str, optional
        PROJ string of the grid projection.

    Returns
    -------
    tuple of (numpy.ndarray, ObservedGrid)
        The grid values and geometry.

    Raises
    ------
    ObservedFireError
        If the header is incomplete or the data shape is wrong.
    """
    source = Path(path)
    if not source.is_file():
        raise ObservedFireError(f"ASCII grid does not exist: {source}")
    header: dict[str, float] = {}
    with source.open(encoding="utf-8") as handle:
        for _ in range(6):
            line = handle.readline()
            if not line:
                raise ObservedFireError(f"ASCII grid header is incomplete: {source}")
            parts = line.split()
            if len(parts) < 2:
                raise ObservedFireError(f"ASCII grid header is malformed: {line!r}")
            header[parts[0].lower()] = float(parts[1])
        values = np.loadtxt(handle, dtype=float)
    required = {"ncols", "nrows", "xllcorner", "yllcorner", "cellsize", "nodata_value"}
    missing = required - set(header)
    if missing:
        raise ObservedFireError(f"ASCII grid header is missing: {sorted(missing)}")
    ncols = int(header["ncols"])
    nrows = int(header["nrows"])
    if values.shape != (nrows, ncols):
        raise ObservedFireError(
            f"ASCII grid data shape {values.shape} does not match {(nrows, ncols)}"
        )
    cell = float(header["cellsize"])
    if cell <= 0.0:
        raise ObservedFireError("ASCII grid cellsize must be positive")
    grid = ObservedGrid(
        ncols=ncols,
        nrows=nrows,
        xll=float(header["xllcorner"]),
        yll=float(header["yllcorner"]),
        cell_size_m=cell,
        nodata=float(header["nodata_value"]),
        crs=crs,
    )
    return values, grid


def read_kml_rings(path: str | Path) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Read all exterior rings from a KML file.

    Inner rings (holes) are ignored. A perimeter may contain multiple exterior polygons.

    Parameters
    ----------
    path : str or Path
        KML file.

    Returns
    -------
    tuple of tuple of (float, float)
        Longitude/latitude exterior rings.

    Raises
    ------
    ObservedFireError
        If the KML has no usable exterior Polygon coordinates.
    """
    source = Path(path)
    if not source.is_file():
        raise ObservedFireError(f"KML does not exist: {source}")
    tree = ET.parse(source)
    coordinates = tree.findall(".//{*}outerBoundaryIs//{*}coordinates")
    if not coordinates:
        raise ObservedFireError(f"KML has no exterior Polygon coordinates: {source}")
    rings: list[tuple[tuple[float, float], ...]] = []
    for node in coordinates:
        if not node.text:
            continue
        ring: list[tuple[float, float]] = []
        for token in node.text.split():
            parts = token.split(",")
            if len(parts) < 2:
                raise ObservedFireError(f"KML coordinate is malformed: {token!r}")
            ring.append((float(parts[0]), float(parts[1])))
        if len(ring) >= 2 and ring[0] == ring[-1]:
            ring.pop()
        if len(ring) < 3:
            raise ObservedFireError(f"KML ring has fewer than three points: {source}")
        rings.append(tuple(ring))
    if not rings:
        raise ObservedFireError(f"KML has no usable exterior rings: {source}")
    return tuple(rings)


def read_kml_point(path: str | Path) -> tuple[float, float]:
    """Read the first Point from a KML file.

    Parameters
    ----------
    path : str or Path
        KML file.

    Returns
    -------
    tuple of float
        Longitude and latitude.

    Raises
    ------
    ObservedFireError
        If the KML has no usable Point coordinates.
    """
    source = Path(path)
    if not source.is_file():
        raise ObservedFireError(f"KML does not exist: {source}")
    tree = ET.parse(source)
    coordinates = tree.findall(".//{*}Point//{*}coordinates")
    if not coordinates or not coordinates[0].text:
        raise ObservedFireError(f"KML has no Point coordinates: {source}")
    parts = coordinates[0].text.strip().split(",")
    if len(parts) < 2:
        raise ObservedFireError(f"KML point is malformed: {coordinates[0].text!r}")
    return float(parts[0]), float(parts[1])


def read_weather(path: str | Path) -> pd.DataFrame:
    """Read the Dogrib hourly weather stream.

    Parameters
    ----------
    path : str or Path
        CSV with ``HOURLY``, ``HOUR``, ``TEMP``, ``RH``, ``WD``, ``WS``, and ``PRECIP``.

    Returns
    -------
    pandas.DataFrame
        Weather rows with ``local_time``, ``temperature_c``, ``relative_humidity_percent``,
        ``wind_direction_deg``, ``wind_speed_kmh``, and ``precipitation_mm``.

    Raises
    ------
    ObservedFireError
        If a required column is missing or a value is invalid.
    """
    source = Path(path)
    if not source.is_file():
        raise ObservedFireError(f"weather CSV does not exist: {source}")
    frame = pd.read_csv(source)
    required = {"HOURLY", "HOUR", "TEMP", "RH", "WD", "WS", "PRECIP"}
    missing = required - set(frame.columns)
    if missing:
        raise ObservedFireError(f"weather CSV is missing: {sorted(missing)}")
    frame = frame.copy()
    frame["local_time"] = pd.to_datetime(
        frame["HOURLY"], format="%d/%m/%Y", errors="coerce"
    ) + pd.to_timedelta(frame["HOUR"].astype(int), unit="h")
    if frame["local_time"].isna().any():
        raise ObservedFireError("weather CSV has an unparseable HOURLY date")
    typed = frame.rename(
        columns={
            "TEMP": "temperature_c",
            "RH": "relative_humidity_percent",
            "WD": "wind_direction_deg",
            "WS": "wind_speed_kmh",
            "PRECIP": "precipitation_mm",
        }
    )
    for column in (
        "temperature_c",
        "relative_humidity_percent",
        "wind_direction_deg",
        "wind_speed_kmh",
        "precipitation_mm",
    ):
        typed[column] = pd.to_numeric(typed[column], errors="coerce")
        if typed[column].isna().any():
            raise ObservedFireError(f"weather column {column!r} has invalid values")
    return (
        typed[
            [
                "local_time",
                "temperature_c",
                "relative_humidity_percent",
                "wind_direction_deg",
                "wind_speed_kmh",
                "precipitation_mm",
            ]
        ]
        .sort_values("local_time")
        .reset_index(drop=True)
    )


def load_dogrib(directory: str | Path) -> ObservedFire:
    """Load the pinned Dogrib fire fixture.

    Parameters
    ----------
    directory : str or Path
        Directory containing the Prometheus Dogrib files.

    Returns
    -------
    ObservedFire
        The validated observed fire.

    Raises
    ------
    ObservedFireError
        If a file is missing, the grids disagree, a fuel code is unknown, the ignition point
        is outside the grid, or the weather does not cover the event window.
    """
    root = Path(directory)
    fuel_codes, fuel_grid = read_ascii_grid(root / "fbp_fuel_type.asc")
    elevation, elevation_grid = read_ascii_grid(root / "elevation.asc")
    if (
        fuel_grid.ncols,
        fuel_grid.nrows,
        fuel_grid.xll,
        fuel_grid.yll,
        fuel_grid.cell_size_m,
        fuel_grid.crs,
    ) != (
        elevation_grid.ncols,
        elevation_grid.nrows,
        elevation_grid.xll,
        elevation_grid.yll,
        elevation_grid.cell_size_m,
        elevation_grid.crs,
    ):
        raise ObservedFireError("fuel and elevation grids have different geometry")
    lookup_frame = pd.read_csv(root / "fbp_lookup_table.csv")
    if not {"grid_value", "fuel_type"}.issubset(lookup_frame.columns):
        raise ObservedFireError("fuel lookup table needs grid_value and fuel_type")
    lookup: dict[int, str | None] = {}
    for row in lookup_frame.itertuples(index=False):
        code = int(str(row.grid_value))
        name = str(row.fuel_type).strip()
        lookup[code] = None if name.lower() == "non-fuel" else name
    lookup[int(fuel_grid.nodata)] = None
    unknown = sorted({int(code) for code in np.unique(fuel_codes)} - set(lookup))
    if unknown:
        raise ObservedFireError(f"fuel grid has unknown codes: {unknown[:10]}")
    weather = read_weather(root / "weather_B3_hourly_20010925to1030.csv")
    perimeter_paths = sorted(root.glob("perimeter_rwf085_*.kml"))
    if len(perimeter_paths) < 2:
        raise ObservedFireError("observed fire needs at least two perimeter snapshots")
    ignition_lonlat = read_kml_point(root / "ignition_point_20011016_1300.kml")
    try:
        from pyproj import Transformer
    except ImportError as error:  # pragma: no cover - pyproj is a declared dependency
        raise ObservedFireError("pyproj is required to load observed-fire KML") from error
    transformer = Transformer.from_crs("EPSG:4326", fuel_grid.crs, always_xy=True)
    ignition_xy = transformer.transform(*ignition_lonlat)
    if not fuel_grid.contains(*ignition_xy):
        raise ObservedFireError("ignition point is outside the observed grid")
    perimeters: list[ObservedPerimeter] = []
    for path in perimeter_paths:
        match = re.search(r"perimeter_rwf085_(\d{8})_(\d{4})\.kml$", path.name)
        if match is None:
            raise ObservedFireError(f"perimeter filename has no timestamp: {path.name}")
        observed_at = datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M")
        rings_lonlat = read_kml_rings(path)
        rings_projected = tuple(
            tuple(transformer.transform(lon, lat) for lon, lat in ring) for ring in rings_lonlat
        )
        points = [point for ring in rings_projected for point in ring]
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_y = max(point[1] for point in points)
        grid_min_x, grid_min_y, grid_max_x, grid_max_y = fuel_grid.bounds
        if max_x < grid_min_x or min_x > grid_max_x or max_y < grid_min_y or min_y > grid_max_y:
            raise ObservedFireError(f"perimeter {path.name} does not overlap the observed grid")
        perimeters.append(
            ObservedPerimeter(
                observed_at=observed_at,
                rings_lonlat=rings_lonlat,
                rings_projected=rings_projected,
                source=path.name,
            )
        )
    perimeters.sort(key=lambda item: item.observed_at)
    event_start = datetime(2001, 10, 16, 13, 0)
    event_end = datetime(2001, 10, 17, 11, 52)
    if weather["local_time"].min() > event_start or weather["local_time"].max() < event_end:
        raise ObservedFireError("weather stream does not cover the event window")
    if not weather["local_time"].diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise ObservedFireError("weather stream has a gap between hourly records")
    if event_start >= event_end:
        raise ObservedFireError("event window must be increasing")
    provenance = {
        "source": DOGRIB_SOURCE,
        "archive": "web.archive.org/web/20220120133307",
        "accessed": "2026-11-08",
        "fire_id": "RWF085",
        "event": "second growth spurt, 2001-10-16 13:00 to 2001-10-17 11:52 local",
        "projection": "NAD83 custom Transverse Mercator, lon_0=-115, k=0.9992",
        "notes": (
            "Prometheus sample dataset. The weather and perimeter times are local time. "
            "The fuel grid uses FBP fuel values; non-fuel values map to None."
        ),
    }
    return ObservedFire(
        fire_id="RWF085",
        name="Dogrib fire",
        source=DOGRIB_SOURCE,
        licence="Prometheus public sample dataset; attribution retained; no explicit licence file.",
        time_zone="local (America/Edmonton)",
        event_start=event_start,
        event_end=event_end,
        ignition_lonlat=ignition_lonlat,
        ignition_xy=ignition_xy,
        grid=fuel_grid,
        fuel_codes=fuel_codes,
        elevation_m=elevation,
        fuel_lookup=lookup,
        perimeters=tuple(perimeters),
        weather=weather,
        provenance=provenance,
    )


def observed_fire_summary(fire: ObservedFire) -> str:
    """Return a compact JSON summary of an observed fire.

    Parameters
    ----------
    fire : ObservedFire
        The observed fire.

    Returns
    -------
    str
        Indented JSON summary.
    """
    return json.dumps(fire.to_dict(), indent=2, sort_keys=True)
