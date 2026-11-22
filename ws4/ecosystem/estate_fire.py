"""Load the calibrated TSA24 layer stack and build its estate fire source.

The compiled dataset is the estate contract; the layer manifest and calibration JSON are
inputs to the calibrated fire regime. This module keeps that boundary explicit so callers
do not need to rebuild the raster stack or the region map in application code.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from ..fire.growth import FragmentSupport, GrowthConfig, SiteGrid
from ..fire.survival import RelativeSuppressionConfig
from .growth_fire import GrowthFireSource, SurvivalIgnition, build_relative_fire_source


class EstateFireError(ValueError):
    """Raised when a calibrated estate layer or region input is invalid."""


def _positive(value: float, field: str) -> float:
    """Return a finite positive number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EstateFireError(f"{field} must be a number")
    number = float(value)
    if not np.isfinite(number) or number <= 0.0:
        raise EstateFireError(f"{field} must be positive")
    return number


def _shape(value: int, field: str) -> int:
    """Return a positive integer shape."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EstateFireError(f"{field} must be a positive integer")
    return value


def load_estate_grid(
    manifest_path: Path,
    *,
    rows: int,
    cols: int,
    origin_x: float,
    origin_y: float,
    cell_size_m: float,
    support_mask: np.ndarray,
    default_fuel_type: str = "C2",
) -> SiteGrid:
    """Build a full-estate site grid from a tiled layer manifest.

    Every support cell must be covered by at least one tile. Non-support cells may remain
    outside the tile bounds.

    Parameters
    ----------
    manifest_path : Path
        JSON manifest containing a ``tiles`` array. Each tile has ``minx``, ``miny``,
        ``maxx``, ``maxy``, ``tile_id``, and ``path`` entries.
    rows, cols : int
        Full-estate grid dimensions.
    origin_x, origin_y : float
        North-west origin of the full-estate grid in the projected CRS.
    cell_size_m : float
        Cell side length in metres.
    support_mask : numpy.ndarray
        Boolean mask of cells represented by the compiled dataset.
    default_fuel_type : str, optional
        Scalar FBP fallback fuel label (default ``"C2"``).

    Returns
    -------
    SiteGrid
        Grid with per-cell fuel, forest, crown, conifer, and terrain layers.

    Raises
    ------
    EstateFireError
        If the manifest, tile paths, shapes, or support coverage are invalid.
    """
    row_count = _shape(rows, "rows")
    col_count = _shape(cols, "cols")
    cell = _positive(cell_size_m, "cell_size_m")
    x0 = float(origin_x)
    y0 = float(origin_y)
    mask = np.asarray(support_mask, dtype=bool)
    if mask.shape != (row_count, col_count):
        raise EstateFireError("support_mask must have shape (rows, cols)")
    try:
        payload = json.loads(Path(manifest_path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise EstateFireError(f"cannot read layer manifest: {error}") from error
    tiles = payload.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        raise EstateFireError("layer manifest must contain a non-empty tiles array")

    fuel = np.empty((row_count, col_count), dtype=object)
    fuel[:] = None
    forest = np.zeros((row_count, col_count), dtype=bool)
    crown = np.zeros((row_count, col_count), dtype=float)
    conifer = np.zeros((row_count, col_count), dtype=float)
    elevation = np.zeros((row_count, col_count), dtype=float)
    slope = np.zeros((row_count, col_count), dtype=float)
    aspect = np.zeros((row_count, col_count), dtype=float)
    covered = np.zeros((row_count, col_count), dtype=bool)

    manifest_dir = Path(manifest_path).parent
    for entry in tiles:
        if not isinstance(entry, dict):
            raise EstateFireError("every layer tile must be an object")
        try:
            minx = float(entry["minx"])
            maxy = float(entry["maxy"])
            path_value = str(entry["path"])
            tile_id = str(entry["tile_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise EstateFireError(f"layer tile is missing a required field: {error}") from error
        path = Path(path_value)
        if not path.is_absolute():
            path = manifest_dir / path.name
        if not path.is_file():
            raise EstateFireError(f"layer tile {tile_id!r} does not exist: {path}")
        c0 = round((minx - x0) / cell)
        r0 = round((y0 - maxy) / cell)
        try:
            with np.load(path, allow_pickle=True) as layer:
                fuel_tile = np.asarray(layer["fuel"], dtype=object)
                forest_tile = np.asarray(layer["forest"], dtype=bool)
                height = min(fuel_tile.shape[0], row_count - r0)
                width = min(fuel_tile.shape[1], col_count - c0)
                if height <= 0 or width <= 0:
                    raise EstateFireError(f"layer tile {tile_id!r} lies outside the grid")
                if forest_tile.shape[:2] != fuel_tile.shape[:2]:
                    raise EstateFireError(f"layer tile {tile_id!r} has mismatched arrays")
                fuel[r0 : r0 + height, c0 : c0 + width] = fuel_tile[:height, :width]
                forest[r0 : r0 + height, c0 : c0 + width] = forest_tile[:height, :width]
                crown[r0 : r0 + height, c0 : c0 + width] = layer["crown"][:height, :width]
                conifer[r0 : r0 + height, c0 : c0 + width] = layer["conifer"][:height, :width]
                elevation[r0 : r0 + height, c0 : c0 + width] = layer["dem"][:height, :width]
                slope[r0 : r0 + height, c0 : c0 + width] = layer["slope"][:height, :width]
                aspect[r0 : r0 + height, c0 : c0 + width] = layer["aspect"][:height, :width]
                covered[r0 : r0 + height, c0 : c0 + width] = True
        except EstateFireError:
            raise
        except (KeyError, OSError, ValueError) as error:
            raise EstateFireError(f"cannot read layer tile {tile_id!r}: {error}") from error

    missing = int((mask & ~covered).sum())
    if missing:
        raise EstateFireError(f"{missing} support cells are not covered by the layer manifest")
    burnable = forest & mask
    return SiteGrid(
        fuel_type=default_fuel_type,
        rows=row_count,
        cols=col_count,
        cell_size_m=cell,
        ffmc=92.0,
        bui=80.0,
        wind_kmh=10.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
        fuel_type_grid=fuel,
        burnable=burnable,
        crown_closure_percent_grid=crown,
        conifer_percent_grid=conifer,
        dead_fir_percent_grid=np.zeros((row_count, col_count), dtype=float),
        slope_percent_grid=slope,
        aspect_deg_grid=aspect,
        elevation_m_grid=elevation,
    )


def load_calibrated_regions(
    calibration_path: Path,
    tiles_manifest_path: Path,
    *,
    rows: int,
    cols: int,
    origin_x: float,
    origin_y: float,
    cell_size_m: float,
    min_area_ha: float = 6.25,
) -> tuple[dict[int, RelativeSuppressionConfig], np.ndarray]:
    """Load the regional suppression map for the calibrated tile rectangles.

    Parameters
    ----------
    calibration_path : Path
        JSON with one entry per calibrated tile and a ``parameters`` object.
    tiles_manifest_path : Path
        Fixed tile manifest with ``id``, ``minx``, ``miny``, ``maxx``, and ``maxy``.
    rows, cols : int
        Full-estate grid dimensions.
    origin_x, origin_y : float
        North-west origin of the full-estate grid in the projected CRS.
    cell_size_m : float
        Cell side length in metres.
    min_area_ha : float, optional
        Minimum fire area used by the suppression model (default ``6.25``).

    Returns
    -------
    tuple of (dict of int to RelativeSuppressionConfig, numpy.ndarray)
        Configurations keyed by region id and the region grid. Region zero uses the
        median calibration and applies outside the fixed calibration tiles.

    Raises
    ------
    EstateFireError
        If the calibration or tile manifest is invalid.
    """
    row_count = _shape(rows, "rows")
    col_count = _shape(cols, "cols")
    cell = _positive(cell_size_m, "cell_size_m")
    minimum = _positive(min_area_ha, "min_area_ha")
    try:
        raw = json.loads(Path(calibration_path).read_text())
        tile_payload = json.loads(Path(tiles_manifest_path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise EstateFireError(f"cannot read calibration input: {error}") from error
    if not isinstance(raw, dict) or not raw:
        raise EstateFireError("calibration must be a non-empty object")
    tiles = tile_payload.get("tiles")
    if not isinstance(tiles, list):
        raise EstateFireError("tiles manifest must contain a tiles array")

    def make(parameters: object) -> RelativeSuppressionConfig:
        if not isinstance(parameters, dict):
            raise EstateFireError("calibration parameters must be an object")
        try:
            return RelativeSuppressionConfig(
                contained_fraction_median=float(parameters["contained_fraction_median"]),
                contained_fraction_sigma=float(parameters["contained_fraction_sigma"]),
                escaped_fraction_median=float(parameters["escaped_fraction_median"]),
                escaped_fraction_sigma=float(parameters["escaped_fraction_sigma"]),
                escape_cap_ha=float(parameters["escape_cap_ha"]),
                min_area_ha=minimum,
                intercept=float(parameters["intercept"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise EstateFireError(f"invalid calibration parameters: {error}") from error

    parameter_sets: list[dict[str, object]] = []
    for entry in raw.values():
        if not isinstance(entry, dict):
            continue
        parameters = entry.get("parameters")
        if isinstance(parameters, dict):
            parameter_sets.append(parameters)
    if not parameter_sets:
        raise EstateFireError("calibration contains no parameter sets")
    sample = parameter_sets[0]
    median: dict[str, float] = {}
    for key in sample:
        numbers: list[float] = []
        try:
            for parameters in parameter_sets:
                value = parameters[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{key} must be numeric")
                numbers.append(float(value))
        except (KeyError, TypeError, ValueError) as error:
            raise EstateFireError(f"calibration parameters are incomplete: {error}") from error
        median[key] = float(np.median(numbers))
    configs: dict[int, RelativeSuppressionConfig] = {0: make(median)}
    region_grid = np.zeros((row_count, col_count), dtype=np.int32)
    for index, tile in enumerate(tiles, start=1):
        if not isinstance(tile, dict):
            raise EstateFireError("every tile manifest entry must be an object")
        try:
            minx = float(tile["minx"])
            miny = float(tile["miny"])
            maxx = float(tile["maxx"])
            maxy = float(tile["maxy"])
            tile_id = str(tile["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise EstateFireError(f"tile manifest entry is invalid: {error}") from error
        entry = raw.get(tile_id)
        if isinstance(entry, dict):
            configs[index] = make(entry.get("parameters"))
        else:
            configs[index] = configs[0]
        c0 = max(0, int((minx - float(origin_x)) // cell))
        c1 = min(col_count, int((maxx - float(origin_x)) // cell) + 1)
        r0 = max(0, int((float(origin_y) - maxy) // cell))
        r1 = min(row_count, int((float(origin_y) - miny) // cell) + 1)
        region_grid[r0:r1, c0:c1] = index
    return configs, region_grid


def build_estate_fire_source(
    support: FragmentSupport,
    *,
    layer_manifest: Path,
    calibration: Path,
    tiles_manifest: Path,
    origin_x: float,
    origin_y: float,
    cell_size_m: float,
    ignitions_by_year: Mapping[int, Sequence[SurvivalIgnition]],
    growth: GrowthConfig | None = None,
    seed: int = 0,
) -> tuple[GrowthFireSource, SiteGrid, np.ndarray]:
    """Build the calibrated fire source for an estate dataset.

    Parameters
    ----------
    support : FragmentSupport
        Area-weighted fragment support grid.
    layer_manifest : Path
        Full-estate layer manifest.
    calibration : Path
        Regional fire-size calibration JSON.
    tiles_manifest : Path
        Fixed calibration tile manifest.
    origin_x, origin_y : float
        North-west origin of the full-estate grid in the projected CRS.
    cell_size_m : float
        Cell side length in metres.
    ignitions_by_year : mapping of int to sequence of SurvivalIgnition
        Ignition inputs by simulation year.
    growth : GrowthConfig or None, optional
        Base growth configuration. The default uses one minimal ignition setup; the
        source replaces ignition cells and time per fire.
    seed : int, optional
        Deterministic survival seed (default zero).

    Returns
    -------
    tuple of (GrowthFireSource, SiteGrid, numpy.ndarray)
        Fire source, full-estate site grid, and region grid.

    Raises
    ------
    EstateFireError
        If the support grid, layer manifest, calibration, or growth inputs are invalid.
    """
    support_mask = np.zeros((support.rows, support.cols), dtype=bool)
    support_mask.ravel()[support.cell_index] = True
    grid = load_estate_grid(
        layer_manifest,
        rows=support.rows,
        cols=support.cols,
        origin_x=origin_x,
        origin_y=origin_y,
        cell_size_m=cell_size_m,
        support_mask=support_mask,
    )
    configs, regions = load_calibrated_regions(
        calibration,
        tiles_manifest,
        rows=support.rows,
        cols=support.cols,
        origin_x=origin_x,
        origin_y=origin_y,
        cell_size_m=cell_size_m,
    )
    base = growth or GrowthConfig(ignition_cells=((0, 0),))
    source = build_relative_fire_source(
        grid,
        base,
        support,
        ignitions_by_year,
        configs,
        region_grid=regions,
        seed=seed,
    )
    return source, grid, regions
