"""The optional HTTP surface: a reader over a compiled dataset and its runs.

Every response is something the CLI already wrote — the dataset manifest, a run's summary, its
account values, its reports, its schedule — or the targets file the optimizer reads. The service
holds no model state and computes no value the CLI cannot reproduce. See
``notes/design/ws4-web-frontend.md``.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import mapbox_vector_tile
import mercantile
import numpy as np
import pandas as pd
import yaml
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pyproj import Transformer
from shapely import make_valid
from shapely import transform as shapely_transform
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response

from ..opt.objective import (
    flow_penalty,
    flow_series,
    load_targets,
    normalization_scale,
    penalty,
    period_value,
    raw_penalty,
)
from ..report import target_kind
from .skins import load_skins

SEARCH_JOB_LIMIT: int = 20

_REPORT_SUFFIXES = {".csv", ".html", ".png", ".json", ".txt"}

#: Carbon pool columns grouped for the web summary. Each group is summed per timestep.
_CARBON_POOL_GROUPS = {
    "Biomass": (
        "SoftwoodMerch",
        "SoftwoodFoliage",
        "SoftwoodOther",
        "SoftwoodCoarseRoots",
        "SoftwoodFineRoots",
        "HardwoodMerch",
        "HardwoodFoliage",
        "HardwoodOther",
        "HardwoodCoarseRoots",
        "HardwoodFineRoots",
    ),
    "DOM and soil": (
        "AboveGroundVeryFastSoil",
        "BelowGroundVeryFastSoil",
        "AboveGroundFastSoil",
        "BelowGroundFastSoil",
        "MediumSoil",
        "AboveGroundSlowSoil",
        "BelowGroundSlowSoil",
        "SoftwoodStemSnag",
        "SoftwoodBranchSnag",
        "HardwoodStemSnag",
        "HardwoodBranchSnag",
    ),
    "Products": ("Products",),
}

#: Canonical LiDAR field products, longest prefix first, and their display unit.
_LIDAR_PRODUCTS = (
    ("vri_closure", "VRI closure", "%"),
    ("vri_height", "VRI height", "m"),
    ("tree_height", "Tree height", "m"),
    ("tree_count", "Tree count", "count"),
    ("chm_cover", "CHM cover", "%"),
    ("slope", "Slope", "%"),
    ("chm", "Canopy height (CHM)", "m"),
)


def _lidar_field_label(field: str) -> tuple[str, str]:
    """Return a human label and unit for a canonical ``lidar_*`` field."""
    stem = field.removeprefix("lidar_")
    product, label, unit = next(
        ((prefix, text, unit) for prefix, text, unit in _LIDAR_PRODUCTS if stem.startswith(prefix)),
        ("", "LiDAR", ""),
    )
    statistic = stem[len(product) :].strip("_").replace("_", " ")
    if statistic == "valid pixels":
        unit = "px"
    if statistic:
        label = f"{label} {statistic}"
    return label, unit


def _lidar_column(frame: pd.DataFrame, field: str) -> str | None:
    """Return the column holding a field, preferring canonical then the newest suffix."""
    if field in frame.columns:
        return field
    for suffix in ("_y", "_x"):
        candidate = f"{field}{suffix}"
        if candidate in frame.columns:
            return candidate
    return None


def _run_directory(root: Path, name: str) -> Path:
    """Return a run directory under the root, refusing anything that escapes it."""
    candidate = (root / name).resolve()
    if candidate.parent != root or not candidate.is_dir():
        raise HTTPException(status_code=404, detail=f"no run named {name!r} under {root}")
    return candidate


def _telemetry_files(directory: Path) -> list[Path]:
    """Return the files a live reader should follow.

    A parallel run writes one ``telemetry-<island>.jsonl`` per worker; the canonical
    ``telemetry.jsonl`` is merged only after the search. Following the worker files while the
    run is live avoids reading the same records twice once the merge lands, and a historical
    run with only the canonical file still works.

    Parameters
    ----------
    directory : Path
        The run directory.

    Returns
    -------
    list of Path
        Existing telemetry files, in a stable order.
    """
    workers = sorted(directory.glob("telemetry-*.jsonl"))
    if workers:
        return workers
    merged = directory / "telemetry.jsonl"
    return [merged] if merged.is_file() else []


def _geometry_features(path: Path) -> list[dict[str, Any]]:
    """Return the features of a GeoJSON file, with a normalised ``block_id`` property."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("type") == "FeatureCollection":
        features = list(document.get("features", []))
    elif document.get("type") == "Feature":
        features = [document]
    else:
        raise HTTPException(
            status_code=422,
            detail=f"{path.name} is not a GeoJSON Feature or FeatureCollection",
        )
    for feature in features:
        properties = feature.setdefault("properties", {})
        block = next(
            (properties[key] for key in ("block_id", "BLOCK", "block", "id") if key in properties),
            None,
        )
        if block is not None:
            properties["block_id"] = int(block)
    return features


def _parse_bbox(text: str) -> tuple[float, float, float, float]:
    """Parse a ``minx,miny,maxx,maxy`` bbox string.

    Parameters
    ----------
    text : str
        Four comma-separated numbers.

    Returns
    -------
    tuple of (float, float, float, float)
        The west, south, east, and north bounds.

    Raises
    ------
    ValueError
        When the string does not have four increasing coordinates.
    """
    parts = [float(value) for value in text.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox needs minx,miny,maxx,maxy")
    minx, miny, maxx, maxy = parts
    if minx >= maxx or miny >= maxy:
        raise ValueError("bbox must have minx < maxx and miny < maxy")
    return minx, miny, maxx, maxy


def _bbox_to_source(
    bbox: tuple[float, float, float, float], source_crs: str
) -> tuple[float, float, float, float]:
    """Transform a WGS84 bbox into the source CRS.

    Parameters
    ----------
    bbox : tuple of (float, float, float, float)
        WGS84 west, south, east, and north bounds.
    source_crs : str
        The geometry's CRS.

    Returns
    -------
    tuple of (float, float, float, float)
        The bbox in the source CRS. A WGS84 source is returned unchanged.

    Raises
    ------
    HTTPException
        When the source is not WGS84 and pyproj is not installed.
    """
    if source_crs.upper() in {"EPSG:4326", "WGS84", "CRS:84"}:
        return bbox
    try:
        from pyproj import Transformer
    except ImportError as error:  # pragma: no cover - depends on the install
        raise HTTPException(
            status_code=422, detail="bbox filtering needs pyproj for a non-WGS84 geometry"
        ) from error
    transformer = Transformer.from_crs("EPSG:4326", source_crs, always_xy=True)
    return transformer.transform_bounds(*bbox)


def _feature_bounds(feature: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Return a feature's coordinate bounds without constructing a shapely geometry.

    Parameters
    ----------
    feature : dict
        GeoJSON feature.

    Returns
    -------
    tuple of (float, float, float, float) or None
        West, south, east, and north bounds, or ``None`` when the feature has no
        coordinate pairs.
    """
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        return None
    coordinates = geometry.get("coordinates")
    if coordinates is None:
        return None
    minx = miny = math.inf
    maxx = maxy = -math.inf

    def walk(value: object) -> None:
        nonlocal minx, miny, maxx, maxy
        if not isinstance(value, (list, tuple)):
            return
        if len(value) >= 2:
            first = value[0]
            second = value[1]
            if isinstance(first, (int, float)) and isinstance(second, (int, float)):
                x = float(first)
                y = float(second)
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)
                return
        for child in value:
            walk(child)

    walk(coordinates)
    if minx is math.inf:
        return None
    return minx, miny, maxx, maxy


def _intersects(bbox: tuple[float, float, float, float], feature: dict[str, Any]) -> bool:
    """Report whether a feature's coordinate bounds overlap a bbox.

    Parameters
    ----------
    bbox : tuple of (float, float, float, float)
        Target bounds.
    feature : dict
        GeoJSON feature.

    Returns
    -------
    bool
        ``True`` when the feature bounds overlap the bbox.
    """
    bounds = _feature_bounds(feature)
    if bounds is None:
        return False
    minx, miny, maxx, maxy = bounds
    return not (maxx < bbox[0] or minx > bbox[2] or maxy < bbox[1] or miny > bbox[3])


TILE_EXTENT: int = 4096
TILE_CACHE_VERSION: str = "v8"


def _safe_cache_name(value: str) -> str:
    """Return a filesystem-safe path component.

    Parameters
    ----------
    value : str
        A run name, layer name, or other key.

    Returns
    -------
    str
        Letters, digits, dot, dash, and underscore; every other character becomes
        an underscore.
    """
    return "".join(
        character if character.isalnum() or character in "._-" else "_" for character in value
    )


def _sample_low_zoom(indices: list[int], layer: str, z: int, *, limit: int = 5000) -> list[int]:
    """Return an even sample of the bare block layer below zoom 6.

    Parameters
    ----------
    indices : list of int
        The tile's intersecting feature indices.
    layer : str
        The tile layer.
    z : int
        The zoom level.
    limit : int, optional
        The most block features to return at low zoom.

    Returns
    -------
    list of int
        The original indices, or an even sample for the bare block layer below
        zoom 6.
    """
    if z >= 6 or layer != "blocks":
        return indices
    step = max(1, len(indices) // limit)
    return indices[::step]


def _tile_cache_path(
    root: Path,
    run: str,
    layer: str,
    year: int | None,
    period_start: int | None,
    z: int,
    x: int,
    y: int,
) -> Path:
    """Return the durable cache path for one tile.

    Parameters
    ----------
    root : Path
        Cache root.
    run : str
        Run name.
    layer : str
        Map layer.
    year : int or None
        Period end year.
    period_start : int or None
        Period start year.
    z, x, y : int
        Tile coordinates.

    Returns
    -------
    Path
        A path under ``root`` with sanitized run and layer components.
    """
    return (
        root
        / TILE_CACHE_VERSION
        / _safe_cache_name(run)
        / _safe_cache_name(layer)
        / f"year-{year if year is not None else 'none'}"
        / f"period-{period_start if period_start is not None else 'none'}"
        / str(z)
        / str(x)
        / f"{y}.mvt"
    )


def _compare_cache_path(
    root: Path,
    run: str,
    against: str,
    year: int | None,
    period_start: int | None,
    z: int,
    x: int,
    y: int,
) -> Path:
    """Return the durable cache path for one comparison tile."""
    return _tile_cache_path(
        root,
        run,
        f"compare-vs-{against}",
        year,
        period_start,
        z,
        x,
        y,
    )


def _tile_tolerance(zoom: int) -> float:
    """Return the simplification tolerance in metres for a tile zoom.

    Parameters
    ----------
    zoom : int
        Web Mercator zoom level.

    Returns
    -------
    float
        Tolerance in source metres; zero keeps the original vertices.
    """
    if zoom >= 15:
        return 0.0
    if zoom >= 13:
        return 5.0
    if zoom >= 11:
        return 15.0
    if zoom >= 9:
        return 30.0
    return 50.0


def _tile_coordinates(
    geometry: BaseGeometry,
    bounds: tuple[float, float, float, float],
    extent: int = TILE_EXTENT,
) -> BaseGeometry:
    """Map a Web Mercator geometry into tile-local coordinates.

    Parameters
    ----------
    geometry : BaseGeometry
        A Shapely geometry in EPSG:3857.
    bounds : tuple of (float, float, float, float)
        The tile's west, south, east, and north bounds in EPSG:3857.
    extent : int, optional
        MVT tile extent. The default is 4096.

    Returns
    -------
    BaseGeometry
        The geometry in tile-local coordinates, y down.
    """
    minx, miny, maxx, maxy = bounds
    width = max(maxx - minx, 1e-9)
    height = max(maxy - miny, 1e-9)

    def project(coordinates: np.ndarray) -> np.ndarray:
        x = (coordinates[:, 0] - minx) / width * extent
        y = (maxy - coordinates[:, 1]) / height * extent
        return np.column_stack([x, y])

    return shapely_transform(geometry, project)


def _scalar_properties(properties: dict[str, Any]) -> dict[str, object]:
    """Keep the MVT-safe scalar properties.

    Parameters
    ----------
    properties : dict
        A feature's source properties.

    Returns
    -------
    dict of str to object
        Only strings, booleans, and numbers; lists and ``None`` are dropped.
    """
    result: dict[str, object] = {}
    for key, value in properties.items():
        if isinstance(value, (str, bool, int, float)):
            result[key] = value
    return result


def _to_wgs84(features: list[dict[str, Any]], crs: str) -> list[dict[str, Any]]:
    """Return features transformed from ``crs`` to WGS84 for MapLibre.

    Parameters
    ----------
    features : list of dict
        GeoJSON features in the source CRS.
    crs : str
        The source CRS, for example ``EPSG:3005``.

    Returns
    -------
    list of dict
        Features with WGS84 coordinates. The input features are not mutated.

    Raises
    ------
    HTTPException
        When a non-WGS84 source is requested but pyproj is not installed.
    """
    if crs.upper() in {"EPSG:4326", "WGS84", "CRS:84"}:
        return features
    try:
        from pyproj import Transformer
    except ImportError as error:  # pragma: no cover - depends on the install
        raise HTTPException(
            status_code=409,
            detail=f"MapLibre WGS84 output for {crs} needs pyproj; install the geo extra",
        ) from error
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    def transform(coordinates: object) -> object:
        if (
            isinstance(coordinates, (list, tuple))
            and len(coordinates) >= 2
            and isinstance(coordinates[0], (int, float))
            and isinstance(coordinates[1], (int, float))
        ):
            x, y = transformer.transform(float(coordinates[0]), float(coordinates[1]))
            return [x, y]
        if isinstance(coordinates, (list, tuple)):
            return [transform(item) for item in coordinates]
        return coordinates

    return [
        {
            **feature,
            "geometry": {
                **feature["geometry"],
                "coordinates": transform(feature["geometry"]["coordinates"]),
            },
        }
        for feature in features
        if feature.get("geometry")
    ]


def _geometry_bounds(
    features: list[dict[str, Any]],
) -> tuple[float, float, float, float] | None:
    """Return the west, south, east and north bounds of GeoJSON features.

    Parameters
    ----------
    features : list of dict
        Parsed GeoJSON features in their source CRS.

    Returns
    -------
    tuple of float or None
        ``(west, south, east, north)``, or ``None`` when no finite coordinate exists.
    """
    min_x = math.inf
    min_y = math.inf
    max_x = -math.inf
    max_y = -math.inf

    def visit(coordinates: object) -> None:
        nonlocal min_x, min_y, max_x, max_y
        if (
            isinstance(coordinates, (list, tuple))
            and len(coordinates) >= 2
            and isinstance(coordinates[0], (int, float))
            and isinstance(coordinates[1], (int, float))
        ):
            x = float(coordinates[0])
            y = float(coordinates[1])
            if math.isfinite(x) and math.isfinite(y):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
            return
        if isinstance(coordinates, (list, tuple)):
            for child in coordinates:
                visit(child)

    for feature in features:
        geometry = feature.get("geometry")
        if isinstance(geometry, dict):
            visit(geometry.get("coordinates"))
    if not math.isfinite(min_x):
        return None
    return (min_x, min_y, max_x, max_y)


def _run_period_width(targets_path: Path | None) -> int:
    """Return the run's display period width, from the configured targets.

    A target's ``period_width`` is the accounting period it reads. The map folds years by the
    most common width; a tie picks the shorter width, because inventing a wider period would hide
    a shorter target. No targets means one year per period.

    Parameters
    ----------
    targets_path : Path or None
        The targets YAML the service was started with.

    Returns
    -------
    int
        The period width, at least 1.
    """
    if targets_path is None or not targets_path.is_file():
        return 1
    try:
        targets = load_targets(targets_path)
    except (ValueError, OSError):
        return 1
    widths = [target.period_width for target in targets if target.period_width > 0]
    if not widths:
        return 1
    counts = Counter(widths)
    return min(counts, key=lambda width: (-counts[width], width))


def _run_periods(years: list[int], width: int) -> list[dict[str, object]]:
    """Fold a run's years into the periods the map steps through.

    Parameters
    ----------
    years : list of int
        The run's sorted years.
    width : int
        The period width, in years.

    Returns
    -------
    list of dict
        ``index``, ``start``, ``end`` and ``label`` per period.
    """
    if not years:
        return []
    if width <= 1:
        return [
            {
                "index": index,
                "start": year,
                "end": year,
                "label": f"Year {year}",
            }
            for index, year in enumerate(years)
        ]
    periods: list[dict[str, object]] = []
    start = years[0]
    while start <= years[-1]:
        end = min(start + width - 1, years[-1])
        index = len(periods)
        periods.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "label": f"Years {start}-{end}",
            }
        )
        start = end + 1
    return periods


def create_app(
    *,
    dataset: Path,
    runs: Path,
    targets: Path | None = None,
    geometry: Path | None = None,
    geometry_overview: Path | None = None,
    land_base: Path | None = None,
    allow_runs: bool = False,
    allow_agent: bool = False,
    agent_model: str = "opencode-go/deepseek-v4.1-flash",
    agent_cwd: Path | None = None,
    agent_timeout: float = 600.0,
    topology: Path | None = None,
    patch_accounts: Path | None = None,
    spread_accounts: Path | None = None,
    block_coordinates: Path | None = None,
    route_config: Path | None = None,
    roads: Path | None = None,
    crs: str = "EPSG:4326",
    tile_cache_dir: Path | None = None,
) -> FastAPI:
    """Create the WS4 read API.

    Parameters
    ----------
    dataset : Path
        The compiled dataset whose manifest and tables the service describes.
    runs : Path
        The directory holding run directories, each with a ``summary.json``.
    targets : Path or None, optional
        The targets YAML the optimizer reads. When given, it is readable and replaceable through the
        API; a replacement is validated with the optimizer's own loader before it is written.
    geometry : Path or None, optional
        A GeoJSON file of block polygons or points, joined on ``block_id``. Without it the map
        endpoint refuses with the missing artefact named.
    geometry_overview : Path or None, optional
        A coarser geometry for low-zoom tiles. Detail zooms use ``geometry``; when this is
        ``None`` every zoom uses ``geometry``.
    land_base : Path or None, optional
        A GeoJSON polygon layer drawn under the blocks as the non-forest land base. It is
        optional: without it the basemap shows through gaps between blocks.
    allow_runs : bool, optional
        When true, ``POST /api/runs`` may start a search with the configured dataset and targets.
        False (the default) keeps the service read-only apart from the targets file.
    allow_agent : bool, optional
        When true, ``POST /api/chat`` may run one turn through the OpenCode CLI. The agent can
        read and change files and run commands as the service user, so this is off by default and
        belongs only on a loopback or otherwise trusted service.
    agent_model : str, optional
        The provider/model handed to ``opencode run``. The CLI's own authentication is used;
        WS4 does not read or store the key.
    agent_cwd : Path or None, optional
        The directory the agent runs in. None uses the service's working directory.
    agent_timeout : float, optional
        Seconds one chat turn may run before the endpoint gives up.
    topology : Path or None, optional
        Block topology handed to web-started searches, so they can write patch membership.
    patch_accounts : Path or None, optional
        Patch account definitions handed to web-started searches.
    spread_accounts : Path or None, optional
        Spread-connectivity accounts handed to web-started searches.
    block_coordinates : Path or None, optional
        Block centroids used by the spread accounts.
    route_config : Path or None, optional
        Route model and accounts handed to web-started searches.
    roads : Path or None, optional
        A GeoJSON line layer of the source access roads, drawn as an optional map overlay.
    crs : str, optional
        The source CRS of the geometry and roads. The SVG shell uses the native coordinates;
        ``format=wgs84`` transforms them for MapLibre. Default ``EPSG:4326``.
    tile_cache_dir : Path or None, optional
        Directory for durable MVT tiles. ``None`` keeps tiles in memory only.

    Returns
    -------
    FastAPI
        The application, ready for ``uvicorn`` or a test client.
    """
    dataset = Path(dataset).resolve()
    runs_root = Path(runs).resolve()
    geometry_path = Path(geometry).resolve() if geometry is not None else None
    overview_path = Path(geometry_overview).resolve() if geometry_overview is not None else None
    land_base_path = Path(land_base).resolve() if land_base is not None else None
    targets_path = Path(targets).resolve() if targets is not None else None
    topology_path = Path(topology).resolve() if topology is not None else None
    patch_accounts_path = Path(patch_accounts).resolve() if patch_accounts is not None else None
    spread_accounts_path = Path(spread_accounts).resolve() if spread_accounts is not None else None
    block_coordinates_path = (
        Path(block_coordinates).resolve() if block_coordinates is not None else None
    )
    route_config_path = Path(route_config).resolve() if route_config is not None else None
    roads_path = Path(roads).resolve() if roads is not None else None
    tile_cache_root = Path(tile_cache_dir).resolve() if tile_cache_dir is not None else None
    source_crs = str(crs)
    agent_working_directory = Path(agent_cwd).resolve() if agent_cwd is not None else Path.cwd()
    app = FastAPI(title="WS4", version="0.1.0")
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)

    @app.middleware("http")
    async def no_cache_static(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Serve the shell's assets uncached: a stale script beside a new page is a bug."""
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response

    skins = load_skins(Path(__file__).with_name("skins"))
    static_dir = Path(__file__).with_name("static")
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    def run_dir(name: str) -> Path:
        return _run_directory(runs_root, name)

    def run_entries() -> list[Path]:
        """Return the directories that are runs: a summary or the simulator's account values."""
        return [
            directory
            for directory in (sorted(runs_root.iterdir()) if runs_root.is_dir() else [])
            if directory.is_dir()
            and (
                (directory / "summary.json").is_file()
                or (directory / "account_values.csv").is_file()
                or (directory / "carbon_manifest.json").is_file()
            )
        ]

    def read_csv(run: Path, name: str) -> pd.DataFrame:
        """Read a run table, normalising the legacy ``year``/``period`` clock to ``offset``."""
        path = run / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"the run has no {name}")
        frame = pd.read_csv(path)
        if "offset" not in frame.columns:
            for column in ("year", "period"):
                if column in frame.columns:
                    frame["offset"] = frame[column]
                    break
        return frame

    geometry_cache: list[dict[str, Any]] | None = None
    overview_cache: list[dict[str, Any]] | None = None
    land_base_cache: list[dict[str, Any]] | None = None
    road_cache: list[dict[str, Any]] | None = None
    lidar_cache: dict[str, Any] | None = None

    def land_base_features() -> list[dict[str, Any]]:
        """Return the optional non-forest underlay once, parsed."""
        nonlocal land_base_cache
        if land_base_cache is None:
            land_base_cache = (
                _geometry_features(land_base_path) if land_base_path is not None else []
            )
        return land_base_cache

    def road_features() -> list[dict[str, Any]]:
        """Return the source road lines once, parsed; the overlay is not run-specific."""
        nonlocal road_cache
        if road_cache is None:
            road_cache = _geometry_features(roads_path) if roads_path is not None else []
        return road_cache

    def base_features() -> list[dict[str, Any]]:
        """Return the configured geometry once, parsed; the map copies only the properties."""
        nonlocal geometry_cache
        if geometry_cache is None:
            geometry_cache = _geometry_features(geometry_path) if geometry_path is not None else []
        return geometry_cache

    def overview_features() -> list[dict[str, Any]]:
        """Return the optional coarse geometry once, parsed."""
        nonlocal overview_cache
        if overview_cache is None:
            overview_cache = _geometry_features(overview_path) if overview_path is not None else []
        return overview_cache

    def lidar_dataset() -> dict[str, Any]:
        """Return the registered LiDAR metadata and canonical block values, once.

        The Parquet block table is the authority; the manifest names the public fields. A
        pre-P59 overwrite could leave ``_x``/``_y`` suffixes, so the canonical name wins and
        a suffixed copy is used only when the canonical column is absent.
        """
        nonlocal lidar_cache
        if lidar_cache is not None:
            return lidar_cache
        manifest: dict[str, Any] = {}
        manifest_path = dataset / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                manifest = {}
        metadata = manifest.get("metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        registration = metadata.get("lidar_products")
        if not isinstance(registration, dict):
            sidecar = dataset / "lidar_products.json"
            if sidecar.is_file():
                try:
                    registration = json.loads(sidecar.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    registration = None
        registration = registration if isinstance(registration, dict) else {}
        field_meta = metadata.get("lidar_fields")
        field_meta = field_meta if isinstance(field_meta, dict) else {}
        block_fields = [
            str(field) for field in field_meta.get("block_fields", []) if str(field).strip()
        ]
        block_values: dict[int, dict[str, float]] = {}
        available_fields: list[str] = []
        table_path = dataset / "blocks.parquet"
        if table_path.is_file():
            try:
                blocks = pd.read_parquet(table_path)
            except (OSError, ValueError):
                blocks = None
            if blocks is not None and "block_id" in blocks.columns:
                if not block_fields:
                    block_fields = sorted(
                        str(name)
                        for name in blocks.columns
                        if str(name).startswith("lidar_") and not str(name).endswith(("_x", "_y"))
                    )
                columns: dict[str, str] = {}
                for field in block_fields:
                    column = _lidar_column(blocks, field)
                    if column is not None:
                        columns[field] = column
                available_fields = list(columns)
                if available_fields:
                    for row in blocks[["block_id", *columns.values()]].itertuples(index=False):
                        values: dict[str, float] = {}
                        for field, column in columns.items():
                            value = getattr(row, column)
                            if value is not None and not pd.isna(value):
                                values[field] = float(value)
                        if values:
                            block_values[int(float(str(row.block_id)))] = values
        products = registration.get("products", {})
        lidar_cache = {
            "available": bool(available_fields),
            "bundle_id": registration.get("bundle_id"),
            "bundle_version": registration.get("bundle_version"),
            "source_id": registration.get("source_id"),
            "licence_id": registration.get("licence_id"),
            "native_crs": registration.get("native_crs"),
            "registered_utc": registration.get("registered_utc"),
            "generated_utc": field_meta.get("generated_utc"),
            "products": sorted(str(name) for name in products)
            if isinstance(products, dict)
            else [],
            "fields": [
                {
                    "name": field,
                    "label": _lidar_field_label(field)[0],
                    "unit": _lidar_field_label(field)[1],
                    "support": "block",
                }
                for field in available_fields
            ],
            "fragment_field_count": len(field_meta.get("fragment_fields", [])),
            "block_count": len(block_values),
            "blocks": block_values,
        }
        return lidar_cache

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        """Return the browser application (a dependency-free shell until the map library lands)."""
        page = static_dir / "index.html"
        if not page.is_file():
            return HTMLResponse("<h1>WS4</h1><p>The browser application is not installed.</p>")
        # the shell must never be stale: a cached index with a new script (or the reverse) is a bug
        return HTMLResponse(
            page.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store, must-revalidate"},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return a liveness probe."""
        return {"status": "ok"}

    processes: dict[str, subprocess.Popen[bytes]] = {}

    def _run_command(
        out: Path,
        iterations: int,
        seed: int,
        years: int,
        time_limit: str,
        islands: int,
        patience: int,
    ) -> list[str]:
        """Return the CLI command for a web-started search; only known options are passed."""
        if targets_path is None:
            raise HTTPException(status_code=422, detail="the service was started without --targets")
        command = [
            sys.executable,
            "-m",
            "ws4.cli",
            "optimize",
            "--dataset",
            str(dataset),
            "--targets",
            str(targets_path),
            "--out",
            str(out),
            "--iterations",
            str(iterations),
            "--seed",
            str(seed),
            "--years",
            str(years),
            "--control-file",
            str(out / "control.json"),
            "--patience",
            str(patience),
            "--starts",
            str(islands),
            "--threads",
            str(islands),
        ]
        if time_limit:
            command.extend(["--time-limit", time_limit])
        for flag, path in (
            ("--topology", topology_path),
            ("--patch-accounts", patch_accounts_path),
            ("--spread-accounts", spread_accounts_path),
            ("--block-coordinates", block_coordinates_path),
            ("--route-config", route_config_path),
        ):
            if path is not None:
                command.extend([flag, str(path)])
        return command

    @app.post("/api/runs")
    def start_run(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a search with the configured dataset and targets, when ``allow_runs`` is set."""
        if not allow_runs:
            raise HTTPException(
                status_code=403,
                detail="this service is read-only; start it with --allow-runs to run a search",
            )
        payload = body or {}
        requested = int(payload.get("iterations", 0) or 0)
        continuous = bool(payload.get("continuous", requested <= 0))
        iterations = 1_000_000_000 if continuous else requested
        seed = int(payload.get("seed", 1))
        years = int(payload.get("years", 50))
        requested_islands = payload.get("islands", 1)
        islands = 1 if requested_islands is None else int(requested_islands)
        time_limit = str(payload.get("time_limit", "") or "")
        patience = int(payload.get("patience", 0) or 0)
        if not 1 <= iterations <= 1_000_000_000 or not 1 <= years <= 1000:
            raise HTTPException(status_code=422, detail="iterations or years are out of range")
        if not 0 <= patience <= 1_000_000_000:
            raise HTTPException(
                status_code=422, detail="patience must be a non-negative iteration count"
            )
        if not 1 <= islands <= 64:
            raise HTTPException(status_code=422, detail="islands must be between 1 and 64")
        # A continuous run has no default wall-clock cap; the control file stops it.
        run_id = f"web-{datetime.now():%Y%m%d-%H%M%S}-{seed}"
        out = runs_root / run_id
        if out.exists():
            raise HTTPException(status_code=409, detail=f"run {run_id!r} already exists")
        out.mkdir(parents=True)
        (out / "control.json").write_text('{"action": "run"}\n', encoding="utf-8")
        command = _run_command(out, iterations, seed, years, time_limit, islands, patience)
        console = (out / "console.log").open("wb")
        processes[run_id] = subprocess.Popen(command, stdout=console, stderr=subprocess.STDOUT)
        return {
            "id": run_id,
            "iterations": iterations,
            "continuous": continuous,
            "seed": seed,
            "years": years,
            "islands": islands,
            "time_limit": time_limit,
            "patience": patience,
        }

    @app.post("/api/runs/{run}/control")
    def control_run(run: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Pause, resume or stop a running search through its control file."""
        directory = run_dir(run)
        action = str((body or {}).get("action", "run"))
        if action not in {"run", "pause", "stop"}:
            raise HTTPException(status_code=422, detail=f"unknown control action {action!r}")
        path = directory / "control.json"
        path.write_text(json.dumps({"action": action}) + "\n", encoding="utf-8")
        process = processes.get(run)
        return {
            "id": run,
            "action": action,
            "running": process is not None and process.poll() is None,
        }

    def _last_step(directory: Path) -> dict[str, Any] | None:
        """Return the last telemetry step, searching backwards in chunks.

        A merged schedule diff can be far larger than a fixed tail window, so the search walks
        backwards until it finds a step or has read two megabytes.
        """
        chunk = 65536
        best: dict[str, Any] | None = None
        best_objective = math.inf
        for path in _telemetry_files(directory):
            with path.open("rb") as handle:
                handle.seek(0, 2)
                position = handle.tell()
                tail = b""
                while position > 0 and len(tail) < 2_000_000:
                    size = min(chunk, position)
                    position -= size
                    handle.seek(position)
                    tail = handle.read(size) + tail
                    lines = tail.splitlines()
                    candidates = lines if position == 0 else lines[1:]
                    for line in reversed(candidates):
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if record.get("type") != "step":
                            continue
                        try:
                            objective = float(record.get("objective", "inf"))
                        except (TypeError, ValueError):
                            continue
                        if best is None or objective < best_objective:
                            best = record
                            best_objective = objective
        return best

    @app.get("/api/runs/{run}/status")
    def run_status(run: str) -> dict[str, Any]:
        """Return whether a run is live, its last telemetry step, and its summary when written."""
        directory = run_dir(run)
        process = processes.get(run)
        summary_path = directory / "summary.json"
        summary = (
            json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else None
        )
        has_accounts = (directory / "account_values.csv").is_file()
        if summary is not None or has_accounts:
            state = "done"
        elif process is not None and process.poll() is not None:
            state = "failed"
        else:
            state = "running"
        control_path = directory / "control.json"
        paused = False
        if control_path.is_file():
            try:
                paused = (
                    json.loads(control_path.read_text(encoding="utf-8")).get("action") == "pause"
                )
            except ValueError:
                paused = False
        return {
            "id": run,
            "status": state,
            "running": state == "running",
            "paused": paused,
            "pid": process.pid if process is not None else None,
            "last_step": _last_step(directory),
            "summary": summary,
        }

    def _target_event(record: dict[str, Any]) -> dict[str, Any]:
        """Fold a telemetry targets record over each target's period, keeping its year series."""
        if targets_path is None or not targets_path.is_file():
            return record

        def item_offset(item: dict[str, Any]) -> int:
            """Return an item's offset, accepting legacy telemetry's 0-based year."""
            return int(item["offset"]) if "offset" in item else int(item["year"])

        index = {
            (item_offset(item), str(item["account"])): float(item["value"])
            for item in record.get("values", [])
        }
        series = [{**item, "year": item_offset(item) + 1} for item in record.get("values", [])]
        payload: dict[str, Any] = {
            "type": "targets",
            "iteration": record.get("iteration"),
            "values": [
                {
                    "index": target_index,
                    "account": target.account,
                    "period": target.period,
                    "year": target.year,
                    "flow": target.flow,
                    "value": period_value(index, target),
                }
                for target_index, target in enumerate(load_targets(targets_path))
                if target.active
            ],
            # the optimizer's snapshot already holds every year of the tracked accounts; the
            # panel uses these as the live series behind the period-target value
            "series": series,
        }
        if record.get("island") is not None:
            payload["island"] = record["island"]
        return payload

    @app.get("/api/runs/{run}/events")
    def run_events(run: str) -> Response:
        """Stream the run's telemetry as SSE.

        A parallel search reports several islands. This stream keeps each island's schedule
        apart, follows the island with the lowest objective, and resets the client's map when
        that island changes. Progress is the best step seen, with ``total`` counting every
        island's steps so the panel reports the aggregate rate rather than one worker's.

        A finished run returns **204 No Content**. An EventSource stops reconnecting on 204,
        so a browser behind a buffering proxy cannot turn a completed run into an endless
        stream of retries; the panel's status poll reads the summary instead.
        """
        directory = run_dir(run)
        if (directory / "summary.json").is_file():
            return Response(status_code=204)

        def stream() -> Iterator[str]:
            yield f"event: started\ndata: {json.dumps({'id': run})}\n\n"
            summary = directory / "summary.json"
            if summary.is_file():
                yield f"event: done\ndata: {summary.read_text(encoding='utf-8').strip()}\n\n"
                return
            schedules: dict[str, dict[int, Any]] = {}
            latest_targets: dict[str, dict[str, Any]] = {}
            best_step: dict[str, Any] | None = None
            latest_step: dict[str, Any] | None = None
            best_island = ""
            best_objective = math.inf
            total = 0

            def apply(record: dict[str, Any]) -> None:
                """Fold one telemetry record into the stream's state."""
                nonlocal best_step, latest_step, best_island, best_objective, total
                kind = record.get("type")
                island = str(record.get("island", "") or "")
                if kind == "step":
                    total += 1
                    latest_step = record
                    value = record.get("objective")
                    if not isinstance(value, (int, float, str)):
                        return
                    try:
                        objective = float(value)
                    except ValueError:
                        return
                    if objective < best_objective:
                        best_objective = objective
                        best_island = island
                        best_step = record
                elif kind == "targets":
                    latest_targets[island] = record
                elif kind == "schedule":
                    schedule = schedules.setdefault(island, {})
                    for block, chain in record.get("changed", []):
                        schedule[int(block)] = chain

            offsets: dict[Path, int] = {}
            pending: dict[Path, str] = {}

            def new_records() -> Iterator[dict[str, Any]]:
                """Yield records appended since the previous poll, including new worker files."""
                for path in _telemetry_files(directory):
                    if path not in offsets:
                        offsets[path] = 0
                        pending[path] = ""
                    with path.open("rb") as handle:
                        handle.seek(offsets[path])
                        chunk = handle.read()
                        offsets[path] = handle.tell()
                    text = pending[path] + chunk.decode("utf-8", errors="replace")
                    lines = text.split("\n")
                    pending[path] = lines.pop()
                    for line in lines:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue

            def progress_payload() -> dict[str, Any]:
                """Return the incumbent step with the latest current/accepted fields."""
                payload = dict(best_step or {})
                payload["total"] = total
                if latest_step is not None:
                    for key in ("current", "accepted"):
                        if key in latest_step:
                            payload[key] = latest_step[key]
                    payload["latest_iteration"] = latest_step.get("iteration")
                return payload

            # replay what exists so a client that connects mid-run gets the current schedule
            for record in new_records():
                apply(record)
            emitted_island = best_island
            emitted_step: dict[str, Any] | None = None
            emitted_total = total
            if best_step is not None:
                payload = progress_payload()
                yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
                emitted_step = best_step
            if best_island in latest_targets:
                yield (
                    "event: targets\ndata: "
                    + json.dumps(_target_event(latest_targets[best_island]))
                    + "\n\n"
                )
            if schedules.get(best_island):
                payload = {
                    "type": "schedule",
                    "iteration": 0,
                    "reset": True,
                    "changed": [
                        [block, chain] for block, chain in sorted(schedules[best_island].items())
                    ],
                }
                yield f"event: schedule\ndata: {json.dumps(payload)}\n\n"
            if processes.get(run) is None:
                yield (
                    "event: error\ndata: "
                    + json.dumps({"detail": "the run is not live and has no summary"})
                    + "\n\n"
                )
                return
            ticks = 0
            while True:
                ticks += 1
                if ticks % 20 == 0:
                    yield ": keepalive\n\n"
                # a browser behind a proxy can leave a half-open stream behind; end it and let
                # EventSource reconnect (the replay rebuilds the map) instead of holding a thread
                if ticks >= 1200:
                    yield ": reconnecting\n\n"
                    return
                changed: dict[int, Any] = {}
                targets_to_emit: dict[str, Any] | None = None
                best_changed = False
                for record in new_records():
                    island = str(record.get("island", "") or "")
                    before = best_island
                    apply(record)
                    if best_island != before:
                        best_changed = True
                    if record.get("type") == "schedule" and island == best_island:
                        for block, chain in record.get("changed", []):
                            changed[int(block)] = chain
                    elif record.get("type") == "targets" and island == best_island:
                        targets_to_emit = record
                if best_changed or best_island != emitted_island:
                    schedules_for_best = schedules.get(best_island, {})
                    payload = {
                        "type": "schedule",
                        "iteration": 0,
                        "reset": True,
                        "changed": [
                            [block, chain] for block, chain in sorted(schedules_for_best.items())
                        ],
                    }
                    yield f"event: schedule\ndata: {json.dumps(payload)}\n\n"
                    emitted_island = best_island
                    if best_island in latest_targets:
                        yield (
                            "event: targets\ndata: "
                            + json.dumps(_target_event(latest_targets[best_island]))
                            + "\n\n"
                        )
                        targets_to_emit = None
                elif changed:
                    payload = {
                        "type": "schedule",
                        "iteration": 0,
                        "changed": [[block, chain] for block, chain in sorted(changed.items())],
                    }
                    yield f"event: schedule\ndata: {json.dumps(payload)}\n\n"
                if targets_to_emit is not None:
                    yield (
                        "event: targets\ndata: "
                        + json.dumps(_target_event(targets_to_emit))
                        + "\n\n"
                    )
                if best_step is not None and (
                    best_step is not emitted_step or total != emitted_total
                ):
                    payload = progress_payload()
                    yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
                    emitted_step = best_step
                    emitted_total = total
                summary = directory / "summary.json"
                if summary.is_file():
                    yield f"event: done\ndata: {summary.read_text(encoding='utf-8').strip()}\n\n"
                    return
                process = processes.get(run)
                if process is not None and process.poll() is not None:
                    yield (
                        "event: error\ndata: "
                        + json.dumps({"detail": "the search exited without a summary"})
                        + "\n\n"
                    )
                    return
                time.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/agent")
    def agent_info() -> dict[str, Any]:
        """Report whether the embedded agent is enabled, and which model it would run."""
        return {
            "enabled": allow_agent,
            "model": agent_model,
            "cwd": str(agent_working_directory),
            "available": shutil.which("opencode") is not None,
            "timeout": agent_timeout,
        }

    @app.post("/api/chat")
    def chat(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run one chat turn through the local OpenCode coding agent.

        The agent uses the installed CLI's own authentication and model configuration. It runs
        with the service user's permissions in ``agent_working_directory``; the caller must have
        enabled ``allow_agent``. The reply is the agent's text, with the tools it used summarised
        so the panel can show that something actually ran.
        """
        if not allow_agent:
            raise HTTPException(
                status_code=403,
                detail="the chat agent is disabled; start the service with --allow-agent",
            )
        payload = body or {}
        message = str(payload.get("message", "") or "").strip()
        if not message:
            raise HTTPException(status_code=422, detail="the message is empty")
        if len(message) > 20_000:
            raise HTTPException(status_code=422, detail="the message is too long")
        session = str(payload.get("session", "") or "").strip()
        if session and not session.startswith("ses"):
            raise HTTPException(
                status_code=422,
                detail="a chat session must be an OpenCode session id starting with 'ses'",
            )
        run = str(payload.get("run", "") or "").strip()
        year = payload.get("year")
        executable = shutil.which("opencode")
        if executable is None:
            raise HTTPException(
                status_code=503,
                detail="opencode is not on PATH; install the CLI or put it on the service PATH",
            )
        context = [
            "You are the WS4 assistant embedded in the WS4 web UI.",
            f"The workspace is {agent_working_directory}.",
            f"The compiled dataset is {dataset}.",
            f"Run outputs live in {runs_root}.",
        ]
        if targets_path is not None:
            context.append(f"The targets file is {targets_path}.")
        if run:
            context.append(f"The run open in the UI is {run}.")
        if isinstance(year, int):
            context.append(f"The year open in the UI is {year}.")
        context.append(
            "You may read the repository, run ws4 commands, and edit files when the user asks. "
            "The user sees the reply in a narrow chat panel: keep it compact and concrete, use "
            "short code blocks, and say what you ran. Do not print credentials."
        )
        prompt = "\n".join(context) + "\n\nUser: " + message
        command = [executable, "run", "--model", agent_model, "--format", "json", "--auto"]
        if session:
            command.extend(["--session", session])
        command.append(prompt)
        environment = dict(os.environ)
        for name in ("OPENCODE_SESSION_ID", "OPENCODE_TERMINAL"):
            environment.pop(name, None)
        try:
            completed = subprocess.run(
                command,
                cwd=str(agent_working_directory),
                capture_output=True,
                text=True,
                timeout=agent_timeout,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise HTTPException(
                status_code=504,
                detail=f"the agent did not answer within {agent_timeout:g} seconds",
            ) from error
        except OSError as error:
            raise HTTPException(
                status_code=503, detail=f"could not start opencode: {error}"
            ) from error
        session_id = session
        texts: list[str] = []
        actions: list[dict[str, str]] = []
        errors: list[str] = []
        for line in completed.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            candidate = event.get("sessionID")
            if isinstance(candidate, str) and candidate.startswith("ses"):
                session_id = candidate
            part = event.get("part")
            if not isinstance(part, dict):
                continue
            if event.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
            elif event.get("type") == "tool_use":
                tool = part.get("tool")
                state = part.get("state")
                summary = ""
                if isinstance(state, dict):
                    title = state.get("title")
                    if isinstance(title, str):
                        summary = title
                    inputs = state.get("input")
                    if isinstance(inputs, dict):
                        for key in ("command", "filePath", "path", "pattern", "url", "description"):
                            value = inputs.get(key)
                            if isinstance(value, str) and value.strip():
                                summary = value.strip()
                                break
                if isinstance(tool, str):
                    action = {"tool": tool, "summary": summary[:160]}
                    if action not in actions:
                        actions.append(action)
            elif event.get("type") == "error":
                failure = event.get("error")
                if isinstance(failure, dict) and isinstance(failure.get("message"), str):
                    errors.append(failure["message"])
        reply = "\n\n".join(texts).strip()
        if not reply:
            detail = (
                errors[-1] if errors else (completed.stderr.strip() or "the agent returned no text")
            )
            raise HTTPException(status_code=502, detail=detail[:500])
        return {"reply": reply, "session": session_id, "actions": actions[-12:]}

    @app.get("/api/land-base")
    def land_base_geojson(format: str = Query(default="projected")) -> dict[str, Any]:
        """Return the optional non-forest underlay drawn beneath the blocks."""
        if land_base_path is None or not land_base_path.is_file():
            raise HTTPException(
                status_code=404, detail="no land-base layer is configured (--land-base)"
            )
        features = land_base_features()
        if format == "wgs84":
            features = _to_wgs84(features, source_crs)
        return {"type": "FeatureCollection", "features": features}

    geometry_bounds_cache: dict[str, list[float]] = {}

    @app.get("/api/geometry/bounds")
    def geometry_bounds(format: str = Query(default="projected")) -> dict[str, Any]:
        """Return the configured geometry's extent, optionally in WGS84."""
        if geometry_path is None or not geometry_path.is_file():
            raise HTTPException(
                status_code=404, detail="no geometry layer is configured (--geometry)"
            )
        if format not in {"projected", "wgs84"}:
            raise HTTPException(status_code=422, detail=f"unknown bounds format {format!r}")
        if format not in geometry_bounds_cache:
            native = _geometry_bounds(base_features())
            if native is None:
                raise HTTPException(status_code=404, detail="the geometry has no finite bounds")
            west, south, east, north = native
            if format == "wgs84" and source_crs.upper() not in {"EPSG:4326", "WGS84", "CRS:84"}:
                transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
                points = [transformer.transform(x, y) for x in (west, east) for y in (south, north)]
                west = min(point[0] for point in points)
                east = max(point[0] for point in points)
                south = min(point[1] for point in points)
                north = max(point[1] for point in points)
            geometry_bounds_cache[format] = [west, south, east, north]
        return {
            "bounds": geometry_bounds_cache[format],
            "crs": "EPSG:4326" if format == "wgs84" else source_crs,
        }

    @app.get("/api/roads")
    def roads_geojson(format: str = Query(default="projected")) -> dict[str, Any]:
        """Return the configured source access-road lines for the map overlay."""
        if roads_path is None or not roads_path.is_file():
            raise HTTPException(
                status_code=404, detail="no source road layer is configured (--roads)"
            )
        features = road_features()
        if format == "wgs84":
            features = _to_wgs84(features, source_crs)
        return {"type": "FeatureCollection", "features": features}

    @app.get("/api/runs/{run}/used-roads")
    def used_roads_geojson(
        run: str,
        year: int | None = Query(default=None),
        format: str = Query(default="projected"),
    ) -> dict[str, Any]:
        """Return the run's used road segments for one year, as GeoJSON LineStrings."""
        directory = run_dir(run)
        path = directory / "used_roads.csv"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="the run has no used_roads.csv")
        frame = read_csv(directory, "used_roads.csv")
        if frame.empty:
            return {"type": "FeatureCollection", "year": year or 0, "features": []}
        time_column = "offset" if "offset" in frame.columns else "period"
        if year is None:
            year = int(frame[time_column].min())
        selected = frame[frame[time_column] == year]
        features: list[dict[str, Any]] = []
        for row in selected.to_dict(orient="records"):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [float(row["x1"]), float(row["y1"])],
                            [float(row["x2"]), float(row["y2"])],
                        ],
                    },
                    "properties": {
                        "period": int(row[time_column]),
                        "segment_id": int(row["segment_id"]),
                        "from_vertex": int(row["from_vertex"]),
                        "to_vertex": int(row["to_vertex"]),
                        "volume": float(row["volume"]),
                        "built_length": float(row["built_length"]),
                        "first_use": int(row["first_use"]),
                    },
                }
            )
        if format == "wgs84":
            features = _to_wgs84(features, source_crs)
        return {"type": "FeatureCollection", "year": year, "features": features}

    @app.get("/api/skins")
    def skin_list() -> list[dict[str, Any]]:
        """Return the skin manifests, checked when the service started."""
        return [skin.row() for skin in skins.values()]

    @app.get("/api/skins/{skin_id}")
    def skin_one(skin_id: str) -> dict[str, Any]:
        """Return one skin manifest, or a named 404."""
        skin = skins.get(skin_id)
        if skin is None:
            raise HTTPException(status_code=404, detail=f"no skin named {skin_id!r}")
        return skin.row()

    @app.get("/api/ping")
    def ping(source: str = Query(default="")) -> dict[str, str]:
        """Return a liveness marker; the client calls it when an action begins."""
        return {"ok": "true", "source": source}

    @app.get("/api/summary")
    def summary() -> dict[str, Any]:
        """Return the dataset manifest and the runs found under the configured root."""
        manifest: dict[str, Any] = {}
        manifest_path = dataset / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        found = []
        for directory in run_entries():
            summary_path = directory / "summary.json"
            if summary_path.is_file():
                kind = "search"
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            elif (directory / "carbon_manifest.json").is_file():
                kind = "carbon"
                summary = {"status": "ok", "kind": kind}
            else:
                kind = "simulate"
                summary = {"status": "ok", "kind": kind}
            found.append({"id": directory.name, "kind": kind, "summary": summary})
        return {"dataset": dataset.name, "manifest": manifest, "runs": found}

    @app.get("/api/lidar")
    def lidar_info() -> dict[str, Any]:
        """Return the registered LiDAR provenance and canonical field catalog."""
        info = dict(lidar_dataset())
        info.pop("blocks", None)
        return info

    @app.get("/api/runs/{run}/carbon")
    def carbon_info(run: str) -> dict[str, Any]:
        """Return the run's carbon artifacts, aggregated for the browser."""
        directory = run_dir(run)
        manifest: dict[str, Any] = {}
        manifest_path = directory / "carbon_manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                manifest = {}
        ledger: dict[str, Any] | None = None
        ledger_path = directory / "carbon_ledger.json"
        if ledger_path.is_file():
            try:
                ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                ledger = None

        accounts: list[dict[str, Any]] = []
        account_path = directory / "carbon_accounts.csv"
        if not account_path.is_file() and (directory / "account_values.csv").is_file():
            account_path = directory / "account_values.csv"
        if account_path.is_file():
            frame = pd.read_csv(account_path)
            if "account" in frame.columns and "value" in frame.columns:
                frame = frame[frame["account"].astype(str).str.startswith("carbon.")]
                time_column = "offset" if "offset" in frame.columns else "timestep"
                if time_column in frame.columns:
                    for account, group in frame.groupby("account", sort=True):
                        points = [
                            {"offset": int(float(str(offset))), "value": float(value)}
                            for offset, value in zip(
                                group[time_column].tolist(), group["value"].tolist(), strict=False
                            )
                            if not pd.isna(value)
                        ]
                        if points:
                            accounts.append({"account": str(account), "values": points})

        pools: dict[str, Any] | None = None
        pools_path = directory / "carbon_pools.csv"
        if pools_path.is_file():
            frame = pd.read_csv(pools_path)
            time_column = "timestep" if "timestep" in frame.columns else "offset"
            if time_column in frame.columns:
                numeric = [
                    str(column)
                    for column in frame.columns
                    if column not in ("identifier", "timestep", "offset")
                    and pd.api.types.is_numeric_dtype(frame[column])
                ]
                grouped = frame.groupby(time_column)[numeric].sum()
                timesteps = [int(float(str(value))) for value in grouped.index.tolist()]
                series = [
                    {"name": name, "values": [float(value) for value in grouped[name].tolist()]}
                    for name in numeric
                ]
                composition = []
                for label, names in _CARBON_POOL_GROUPS.items():
                    present = [name for name in names if name in grouped.columns]
                    if not present:
                        continue
                    values = [float(value) for value in grouped[present].sum(axis=1).tolist()]
                    composition.append({"name": label, "values": values})
                pools = {
                    "timesteps": timesteps,
                    "series": series,
                    "composition": composition,
                }

        flux: dict[str, Any] | None = None
        flux_path = directory / "carbon_flux.csv"
        if flux_path.is_file():
            frame = pd.read_csv(flux_path)
            time_column = "timestep" if "timestep" in frame.columns else "offset"
            if time_column in frame.columns:
                numeric = [
                    str(column)
                    for column in frame.columns
                    if column not in ("identifier", "timestep", "offset")
                    and pd.api.types.is_numeric_dtype(frame[column])
                ]
                grouped = frame.groupby(time_column)[numeric].sum()
                flux = {
                    "timesteps": [int(float(str(value))) for value in grouped.index.tolist()],
                    "series": [
                        {"name": name, "values": [float(value) for value in grouped[name].tolist()]}
                        for name in numeric
                    ],
                }

        gcbm: dict[str, Any] | None = None
        compare_path = directory / "gcbm_compare.csv"
        if compare_path.is_file():
            frame = pd.read_csv(compare_path)
            gcbm = {
                "columns": [str(column) for column in frame.columns],
                "rows": [
                    {str(key): value for key, value in row.items()}
                    for row in frame.to_dict(orient="records")
                ],
            }
        files = [
            {"name": path.name, "bytes": path.stat().st_size}
            for path in sorted(directory.iterdir())
            if path.is_file()
            and (
                path.name.startswith("carbon_")
                or path.name in {"gcbm_compare.csv", "gcbm_manifest.json"}
            )
        ]
        available = bool(manifest or accounts or pools or flux or ledger or gcbm)
        return {
            "available": available,
            "manifest": manifest,
            "ledger": ledger,
            "accounts": accounts,
            "pools": pools,
            "flux": flux,
            "gcbm": gcbm,
            "files": files,
        }

    @app.get("/api/runs/{run}/summary")
    def run_summary(run: str) -> dict[str, Any]:
        """Return a run's ``summary.json``."""
        directory = run_dir(run)
        path = directory / "summary.json"
        if path.is_file():
            document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return document
        if (directory / "account_values.csv").is_file():
            return {"status": "ok", "kind": "simulate"}
        raise HTTPException(status_code=404, detail=f"run {run!r} has no summary.json")

    @app.get("/api/runs/{run}/accounts")
    def accounts(
        run: str,
        year: int | None = Query(default=None),
        account: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Return realized account values, optionally filtered by year and account."""
        directory = run_dir(run)
        if (directory / "account_values.csv").is_file():
            frame = read_csv(directory, "account_values.csv")
        elif (directory / "carbon_accounts.csv").is_file():
            frame = read_csv(directory, "carbon_accounts.csv")
        else:
            raise HTTPException(status_code=404, detail="the run has no account_values.csv")
        if year is not None:
            frame = frame[frame["offset"] == year]
        if account is not None:
            frame = frame[frame["account"] == account]
        rows: list[dict[str, Any]] = []
        for row in frame.to_dict(orient="records"):
            record = {str(key): value for key, value in row.items()}
            if "offset" in record and "year" not in record:
                # ``year`` is the display label; a legacy table already carries it.
                record["year"] = int(record["offset"]) + 1
            rows.append(record)
        return rows

    def search_artifact_dir(name: str) -> Path:
        """Return a directory under the runs root that holds a search artifact."""
        candidate = (runs_root / name).resolve()
        if candidate.parent != runs_root or not candidate.is_dir():
            raise HTTPException(
                status_code=404, detail=f"no search artifact named {name!r} under {runs_root}"
            )
        return candidate

    search_jobs: dict[str, dict[str, Any]] = {}

    def prune_search_jobs() -> None:
        """Drop the oldest finished jobs while keeping the in-memory list bounded."""
        for name in list(search_jobs):
            if len(search_jobs) <= SEARCH_JOB_LIMIT:
                break
            job = search_jobs[name]
            if job["process"].poll() is not None:
                del search_jobs[name]

    def new_search_dir(prefix: str) -> Path:
        """Return a fresh output directory under the runs root."""
        out = runs_root / f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}"
        suffix = 1
        while out.exists():
            out = runs_root / f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}-{suffix}"
            suffix += 1
        out.mkdir(parents=True)
        return out

    def script_path(name: str) -> Path:
        """Return a repository script path."""
        return Path(__file__).resolve().parents[2] / "scripts" / name

    def launch_search(kind: str, out: Path, command: list[str]) -> dict[str, Any]:
        """Start one search script and record its process."""
        console = (out / "console.log").open("wb")
        process = subprocess.Popen(
            command,
            stdout=console,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        search_jobs[out.name] = {
            "kind": kind,
            "out": out,
            "process": process,
            "stopped": False,
        }
        prune_search_jobs()
        return {"id": out.name, "kind": kind, "status": "running"}

    @app.post("/api/search/portfolio")
    def start_portfolio(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a target-weight portfolio under the runs root."""
        if not allow_runs:
            raise HTTPException(
                status_code=403, detail="this service is read-only; use --allow-runs"
            )
        if targets_path is None:
            raise HTTPException(status_code=422, detail="the service was started without --targets")
        payload = body or {}
        vary = str(payload.get("vary", "") or "").strip()
        if not vary:
            raise HTTPException(status_code=422, detail="vary is required")
        iterations = int(payload.get("iterations", 20) or 20)
        years = int(payload.get("years", 50) or 50)
        threads = int(payload.get("threads", 1) or 1)
        archive_size = int(payload.get("archive_size", 20) or 20)
        if not 1 <= iterations <= 1_000_000 or not 1 <= years <= 1000:
            raise HTTPException(status_code=422, detail="iterations or years are out of range")
        if not 1 <= threads <= 64 or not 1 <= archive_size <= 100:
            raise HTTPException(status_code=422, detail="threads or archive size is out of range")
        out = new_search_dir("portfolio")
        command = [
            sys.executable,
            str(script_path("portfolio.py")),
            "--dataset",
            str(dataset),
            "--targets",
            str(targets_path),
            "--out",
            str(out),
            "--vary",
            vary,
            "--seeds",
            str(payload.get("seeds", "1") or "1"),
            "--iterations",
            str(iterations),
            "--years",
            str(years),
            "--threads",
            str(threads),
            "--engine",
            str(payload.get("engine", "sa") or "sa"),
            "--archive-size",
            str(archive_size),
            "--max-members",
            str(min(64, int(payload.get("max_members", 64) or 64))),
        ]
        if payload.get("metrics"):
            command.extend(["--metrics", str(payload["metrics"])])
        if payload.get("directions"):
            command.extend(["--directions", str(payload["directions"])])
        return launch_search("portfolio", out, command)

    @app.post("/api/search/tune")
    def start_tune(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a grid or random tuner under the runs root."""
        if not allow_runs:
            raise HTTPException(
                status_code=403, detail="this service is read-only; use --allow-runs"
            )
        if targets_path is None:
            raise HTTPException(status_code=422, detail="the service was started without --targets")
        payload = body or {}
        space = payload.get("space")
        if not isinstance(space, dict) or not space:
            raise HTTPException(status_code=422, detail="space must be a non-empty JSON object")
        iterations = int(payload.get("iterations", 20) or 20)
        years = int(payload.get("years", 50) or 50)
        budget = int(payload.get("budget", 16) or 16)
        threads = int(payload.get("threads", 1) or 1)
        if not 1 <= iterations <= 1_000_000 or not 1 <= years <= 1000:
            raise HTTPException(status_code=422, detail="iterations or years are out of range")
        if not 1 <= budget <= 256 or not 1 <= threads <= 64:
            raise HTTPException(status_code=422, detail="budget or threads is out of range")
        out = new_search_dir("tuning")
        space_path = out / "space.json"
        space_path.write_text(json.dumps(space), encoding="utf-8")
        command = [
            sys.executable,
            str(script_path("tune.py")),
            "--dataset",
            str(dataset),
            "--targets",
            str(targets_path),
            "--space",
            str(space_path),
            "--out",
            str(out),
            "--mode",
            str(payload.get("mode", "grid") or "grid"),
            "--budget",
            str(budget),
            "--seeds",
            str(payload.get("seeds", "1") or "1"),
            "--iterations",
            str(iterations),
            "--years",
            str(years),
            "--threads",
            str(threads),
        ]
        return launch_search("tuning", out, command)

    @app.post("/api/search/{name}/stop")
    def stop_search(name: str) -> dict[str, Any]:
        """Stop a running portfolio or tuner process."""
        job = search_jobs.get(name)
        if job is None:
            raise HTTPException(status_code=404, detail=f"no search job named {name!r}")
        process = job["process"]
        if process.poll() is not None:
            return {"id": name, "status": "finished", "returncode": process.returncode}
        job["stopped"] = True
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except OSError:
            process.terminate()
        return {"id": name, "status": "stopping"}

    @app.get("/api/search/{name}/status")
    def search_status(name: str) -> dict[str, Any]:
        """Return a running search job's status and summary."""
        job = search_jobs.get(name)
        if job is None:
            search_artifact_dir(name)
            return {"id": name, "kind": "artifact", "status": "done", "returncode": 0, "log": ""}
        process = job["process"]
        running = process.poll() is None
        out = job["out"]
        if job.get("stopped"):
            status = "stopping" if running else "stopped"
        elif running:
            status = "running"
        elif (out / "portfolio.json").is_file() or (out / "tuning.json").is_file():
            status = "done"
        else:
            status = "failed"
        log_path = out / "console.log"
        log = (
            log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            if log_path.is_file()
            else ""
        )
        return {
            "id": name,
            "kind": job["kind"],
            "status": status,
            "returncode": process.returncode,
            "log": log,
        }

    @app.get("/api/search")
    def search_artifacts() -> list[dict[str, Any]]:
        """List portfolio, tuner, and LP artifacts under the runs root."""
        artifacts: list[dict[str, Any]] = []
        if not runs_root.is_dir():
            return artifacts
        known: set[str] = set()
        for directory in sorted(runs_root.iterdir()):
            if not directory.is_dir():
                continue
            for filename, kind in (
                ("portfolio.json", "portfolio"),
                ("tuning.json", "tuning"),
                ("lp_sensitivity.json", "lp"),
                ("lp.json", "lp"),
            ):
                path = directory / filename
                if path.is_file():
                    artifacts.append({"id": directory.name, "kind": kind})
                    known.add(directory.name)
                    break
        for name, job in search_jobs.items():
            if name not in known:
                artifacts.append(
                    {
                        "id": name,
                        "kind": job["kind"],
                        "status": "running" if job["process"].poll() is None else "stopped",
                    }
                )
        return artifacts

    @app.get("/api/search/{name}")
    def search_artifact(name: str) -> dict[str, Any]:
        """Return one portfolio, tuner, or LP result for the browser."""
        directory = search_artifact_dir(name)
        for filename, kind in (
            ("portfolio.json", "portfolio"),
            ("tuning.json", "tuning"),
            ("lp_sensitivity.json", "lp"),
            ("lp.json", "lp"),
        ):
            path = directory / filename
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if kind == "portfolio":
                    for member in data.get("members", []):
                        for key in ("targets", "run_dir", "schedule"):
                            value = member.get(key)
                            if not value:
                                continue
                            resolved = Path(str(value)).resolve()
                            if resolved.is_relative_to(directory):
                                member[key] = str(resolved.relative_to(directory))
                            else:
                                member.pop(key, None)
                data["files"] = sorted(
                    str(item.relative_to(directory))
                    for item in directory.rglob("*")
                    if item.is_file()
                )
                return {"id": name, "kind": kind, "data": data}
        raise HTTPException(status_code=404, detail=f"no search artifact in {name!r}")

    @app.get("/api/search/{name}/files/{path:path}")
    def search_file(name: str, path: str) -> FileResponse:
        """Serve a file resolved under one search artifact directory."""
        directory = search_artifact_dir(name)
        candidate = (directory / path).resolve()
        if not candidate.is_relative_to(directory) or not candidate.is_file():
            raise HTTPException(
                status_code=404, detail=f"no file {path!r} in search artifact {name!r}"
            )
        return FileResponse(candidate)

    @app.get("/api/runs/{run}/reports")
    def reports(run: str) -> list[dict[str, Any]]:
        """Return the report files a run wrote."""
        directory = run_dir(run)
        return [
            {"name": path.name, "bytes": path.stat().st_size}
            for path in sorted(directory.iterdir())
            if path.is_file() and path.suffix.lower() in _REPORT_SUFFIXES
        ]

    @app.get("/api/runs/{run}/reports/{name}")
    def report(run: str, name: str) -> FileResponse:
        """Return one report file, refusing a name the run does not hold."""
        directory = run_dir(run)
        path = directory / name
        if path.name != name or path.suffix.lower() not in _REPORT_SUFFIXES or not path.is_file():
            raise HTTPException(status_code=404, detail=f"run {run!r} has no report {name!r}")
        return FileResponse(path)

    @app.get("/api/runs/{run}/periods")
    def periods(run: str) -> dict[str, Any]:
        """Return the run's periods from its schedule, patch membership or account values."""
        directory = run_dir(run)
        offsets: set[int] = set()
        schedule_path = directory / "schedule.csv"
        if schedule_path.is_file():
            schedule = read_csv(directory, "schedule.csv")
            if not schedule.empty and "offset" in schedule.columns:
                offsets.update(
                    int(value)
                    for value in schedule["offset"].astype("int64").tolist()
                    if int(value) >= 0
                )
                accounts = directory / "account_values.csv"
                if accounts.is_file():
                    frame = read_csv(directory, "account_values.csv")
                    if not frame.empty and "offset" in frame.columns:
                        offsets.update(
                            int(value)
                            for value in frame["offset"].astype("int64").tolist()
                            if int(value) >= 0
                        )
        elif (directory / "patch_membership.csv").is_file():
            frame = read_csv(directory, "patch_membership.csv")
            if not frame.empty and "period" in frame.columns:
                offsets.update(int(value) for value in frame["period"].astype("int64").tolist())
        elif (directory / "account_values.csv").is_file():
            frame = read_csv(directory, "account_values.csv")
            if not frame.empty and "offset" in frame.columns:
                offsets.update(
                    int(value)
                    for value in frame["offset"].astype("int64").tolist()
                    if int(value) >= 0
                )
        elif (directory / "carbon_accounts.csv").is_file():
            frame = read_csv(directory, "carbon_accounts.csv")
            if not frame.empty and "offset" in frame.columns:
                offsets.update(
                    int(value)
                    for value in frame["offset"].astype("int64").tolist()
                    if int(value) >= 0
                )
        values = sorted(offsets)
        if values:
            width = _run_period_width(targets_path)
            return {
                "min": values[0],
                "max": values[-1],
                "values": values,
                "period_width": width,
                "periods": _run_periods(values, width),
            }
        return {"min": 0, "max": 0, "values": [], "period_width": 1, "periods": []}

    @app.get("/api/runs/{run}/layers")
    def layer_info(run: str) -> dict[str, Any]:
        """Return the map layers this run can actually draw, and the patch classes it has."""
        directory = run_dir(run)
        schedule = (directory / "schedule.csv").is_file()
        patches = (directory / "patch_membership.csv").is_file()
        patch_classes: list[str] = []
        patch_accounts: list[str] = []
        if patches:
            frame = read_csv(directory, "patch_membership.csv")
            if not frame.empty:
                if "class" in frame:
                    patch_classes = sorted({str(value) for value in frame["class"].dropna()})
                if "account" in frame:
                    patch_accounts = sorted({str(value) for value in frame["account"].dropna()})
        compartments = (directory / "spread_membership.csv").is_file()
        used_roads = (directory / "used_roads.csv").is_file()
        compartment_classes: list[str] = []
        compartment_accounts: list[str] = []
        if compartments:
            frame = read_csv(directory, "spread_membership.csv")
            if not frame.empty:
                if "compartment_class" in frame:
                    compartment_classes = sorted(
                        {str(value) for value in frame["compartment_class"].dropna()}
                    )
                if "account" in frame:
                    compartment_accounts = sorted(
                        {str(value) for value in frame["account"].dropna()}
                    )
        base_attributes: list[dict[str, Any]] = []
        if geometry_path is not None:
            labels = (
                ("compartment", "Compartment"),
                ("theme2", "THEME2"),
                ("theme5", "THEME5"),
                ("strata", "MartStrata"),
                ("lmu", "LMU"),
            )
            values: dict[str, set[str]] = {name: set() for name, _ in labels}
            for feature in base_features():
                properties = feature.get("properties", {})
                for name, _ in labels:
                    value = properties.get(name)
                    if value is not None and str(value) != "":
                        values[name].add(str(value))
            for name, label in labels:
                if values[name]:
                    base_attributes.append(
                        {"name": name, "label": label, "values": sorted(values[name])}
                    )
        return {
            "blocks": True,
            "treatments": schedule,
            "cumulative": schedule,
            "patches": patches,
            "roads": roads_path is not None and roads_path.is_file(),
            "used_roads": used_roads,
            "compartments": compartments,
            "patch_classes": patch_classes,
            "patch_accounts": patch_accounts,
            "compartment_classes": compartment_classes,
            "compartment_accounts": compartment_accounts,
            "base_attributes": base_attributes,
            "roads_reason": (
                ""
                if roads_path is not None and roads_path.is_file()
                else "no source road layer is configured (--roads)"
            ),
            "used_roads_reason": ("" if used_roads else "the run has no used_roads.csv"),
            "compartments_reason": ("" if compartments else "the run has no spread_membership.csv"),
        }

    @app.get("/api/runs/{run}/map")
    def map_features(
        run: str,
        year: int | None = Query(default=None),
        layer: str = Query(default="treatments"),
        account: str | None = Query(default=None),
        period_start: int | None = Query(default=None),
        format: str = Query(default="projected"),
        bbox: str | None = Query(default=None),
        zoom: float | None = Query(default=None),
        lidar: bool = Query(default=False),
    ) -> dict[str, Any]:
        """Return a GeoJSON FeatureCollection of every block for one map layer.

        ``treatments`` is the selected period, ``cumulative`` marks current and earlier
        treatments, ``patches`` colors the selected year's patch membership, ``compartments``
        is the model spread-compartment membership (optionally for one ``account``), and
        ``blocks`` is the bare geometry. ``year`` is the period's end year and ``period_start``
        its first year; without it the period is one year. The layer is the base geometry; the
        properties carry the flags the client needs, so a layer change is one request and no
        second join. ``lidar`` joins the dataset's canonical block LiDAR fields by
        ``block_id``; it is independent of the treatment layer so the client can colour by
        a terrain or canopy field.
        """
        directory = run_dir(run)
        if layer not in ("treatments", "cumulative", "patches", "compartments", "blocks"):
            raise HTTPException(status_code=422, detail=f"unknown layer {layer!r}")
        lidar_blocks = lidar_dataset()["blocks"] if lidar else {}
        if geometry_path is None or not geometry_path.is_file():
            raise HTTPException(
                status_code=409,
                detail="no geometry layer is configured; start the service with --geometry",
            )
        treatments_by_block: dict[int, list[str]] = {}
        current: set[int] = set()
        patches_by_block: dict[int, dict[str, Any]] = {}
        patch_classes: list[str] = []
        compartments_by_block: dict[int, dict[str, Any]] = {}
        compartment_classes: list[str] = []
        compartment_accounts: list[str] = []
        current_treatments: dict[int, list[str]] = {}
        if layer == "compartments":
            if not (directory / "spread_membership.csv").is_file():
                raise HTTPException(status_code=404, detail="the run has no spread_membership.csv")
            frame = read_csv(directory, "spread_membership.csv")
            compartment_accounts = sorted({str(value) for value in frame["account"].dropna()})
            if account is None or account not in compartment_accounts:
                account = compartment_accounts[0] if compartment_accounts else ""
            if year is None:
                year = int(frame["offset"].min()) if not frame.empty else 0
            selected = frame[(frame["offset"] == year) & (frame["account"] == account)]
            for row in selected.to_dict(orient="records"):
                block = int(row["block"])
                compartments_by_block[block] = {
                    "compartment": int(row["compartment"]),
                    "compartment_class": str(row["compartment_class"]),
                    "compartment_area_ha": float(row["compartment_area_ha"]),
                    "area_ha": float(row["area_ha"]),
                }
            compartment_classes = sorted(
                {str(value) for value in frame["compartment_class"].dropna()}
            )
            if (directory / "schedule.csv").is_file():
                schedule = read_csv(directory, "schedule.csv")
                current_rows = schedule[schedule["offset"] == year]
                for block_id, group in current_rows.groupby("block_id"):
                    current_treatments[int(float(str(block_id)))] = sorted(
                        {str(value) for value in group["treatment"]}
                    )
        elif layer == "patches":
            if not (directory / "patch_membership.csv").is_file():
                raise HTTPException(status_code=404, detail="the run has no patch_membership.csv")
            frame = read_csv(directory, "patch_membership.csv")
            time_column = "offset" if "offset" in frame.columns else "period"
            if year is None:
                year = int(frame[time_column].min()) if not frame.empty else 0
            selected = frame[frame[time_column] == year]
            for row in selected.to_dict(orient="records"):
                block = int(row["block"])
                patches_by_block[block] = {
                    "patch": int(row["patch"]),
                    "patch_class": str(row["class"]),
                    "patch_area_ha": float(row["area_ha"]),
                    "patch_account": str(row["account"]),
                }
            patch_classes = sorted({str(value) for value in frame["class"].dropna()})
        elif layer in ("treatments", "cumulative"):
            if not (directory / "schedule.csv").is_file():
                raise HTTPException(status_code=404, detail="the run has no schedule.csv")
            schedule = read_csv(directory, "schedule.csv")
            if year is None:
                year = int(schedule["offset"].min()) if not schedule.empty else 0
            first = year if period_start is None else min(period_start, year)
            selected = schedule[
                schedule["offset"] <= year
                if layer == "cumulative"
                else (schedule["offset"] >= first) & (schedule["offset"] <= year)
            ]
            for block_id, group in selected.groupby("block_id"):
                treatments_by_block[int(float(str(block_id)))] = sorted(
                    {str(value) for value in group["treatment"]}
                )
            if layer == "cumulative":
                current = {
                    int(value)
                    for value in schedule[
                        (schedule["offset"] >= first) & (schedule["offset"] <= year)
                    ]["block_id"].astype("int64")
                }
        else:
            year = 0 if year is None else year
        features: list[dict[str, Any]] = []
        for base in base_features():
            properties = dict(base.get("properties", {}))
            block_value = properties.get("block_id")
            if block_value is None:
                continue
            number = int(block_value)
            if layer == "compartments":
                compartment = compartments_by_block.get(number)
                treatments = current_treatments.get(number, [])
                properties["treatments"] = treatments
                properties["treated"] = bool(treatments)
                properties["current"] = bool(treatments)
                properties["compartment"] = compartment["compartment"] if compartment else None
                properties["compartment_class"] = (
                    compartment["compartment_class"] if compartment else None
                )
                properties["compartment_area_ha"] = (
                    compartment["compartment_area_ha"] if compartment else None
                )
            elif layer == "patches":
                patch = patches_by_block.get(number)
                properties["treatments"] = [patch["patch_account"]] if patch else []
                properties["treated"] = patch is not None
                properties["patch"] = patch["patch"] if patch else None
                properties["patch_class"] = patch["patch_class"] if patch else None
                properties["patch_area_ha"] = patch["patch_area_ha"] if patch else None
                properties["patch_account"] = patch["patch_account"] if patch else None
            elif layer in ("treatments", "cumulative"):
                treatments = treatments_by_block.get(number, [])
                properties["treatments"] = treatments
                properties["treated"] = bool(treatments)
                properties["current"] = number in current if layer == "cumulative" else True
            else:
                properties["treatments"] = []
                properties["treated"] = False
                properties["current"] = False
            if lidar_blocks:
                properties.update(lidar_blocks.get(number, {}))
            features.append(
                {"type": "Feature", "geometry": base.get("geometry"), "properties": properties}
            )
        total_features = len(features)
        total_treated = sum(
            1 for feature in features if bool(feature.get("properties", {}).get("treated"))
        )
        if bbox is not None:
            try:
                requested = _parse_bbox(bbox)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            if format == "wgs84":
                requested = _bbox_to_source(requested, source_crs)
            features = [feature for feature in features if _intersects(requested, feature)]
        overview_mode: str | None = None
        if zoom is not None and zoom < 10:
            for feature in features:
                bounds = _feature_bounds(feature)
                if bounds is None:
                    continue
                minx, miny, maxx, maxy = bounds
                feature["geometry"] = {
                    "type": "Point",
                    "coordinates": [(minx + maxx) / 2.0, (miny + maxy) / 2.0],
                }
                feature["properties"]["overview"] = True
            if layer == "blocks":
                step = max(1, len(features) // 5000)
                features = features[::step]
                overview_mode = "sample"
            else:
                features = [
                    feature
                    for feature in features
                    if bool(feature.get("properties", {}).get("treated"))
                ]
                overview_mode = "treated"
        if format == "wgs84":
            features = _to_wgs84(features, source_crs)
        return {
            "type": "FeatureCollection",
            "features": features,
            "year": year,
            "layer": layer,
            "total_features": total_features,
            "returned_features": len(features),
            "total_treated": total_treated,
            "total_untreated": total_features - total_treated,
            "overview": bool(zoom is not None and zoom < 10),
            "overview_mode": overview_mode,
            "patch_classes": patch_classes,
            "compartment_classes": compartment_classes,
            "compartment_accounts": compartment_accounts,
            "account": account if layer == "compartments" else None,
            "lidar": lidar,
        }

    payload_cache: dict[tuple[str, int | None, str, int | None, str, bool], dict[str, Any]] = {}
    payload_lock = threading.Lock()
    tile_cache: dict[tuple[str, int, int, int, str, int | None, int | None], bytes] = {}
    compare_tile_cache: dict[
        tuple[str, str, int, int, int, int | None, int | None, str], bytes
    ] = {}

    def cached_geometry(
        run: str,
        year: int | None,
        layer: str,
        period_start: int | None,
        account: str | None,
        *,
        overview: bool = False,
    ) -> dict[str, Any]:
        """Build and cache the source-CRS features for one layer and period."""
        key = (run, year, layer, period_start, account or "", overview)
        cached = payload_cache.get(key)
        if cached is not None:
            return cached
        with payload_lock:
            cached = payload_cache.get(key)
            if cached is not None:
                return cached
            payload = map_features(
                run=run,
                year=year,
                layer=layer,
                account=account,
                period_start=period_start,
                format="projected",
                bbox=None,
                zoom=None,
            )
            features = list(payload["features"])
            if overview and overview_path is not None:
                by_block = {
                    int(feature["properties"]["block_id"]): feature["geometry"]
                    for feature in overview_features()
                    if feature.get("properties", {}).get("block_id") is not None
                }
                for feature in features:
                    block = feature.get("properties", {}).get("block_id")
                    if block is not None and int(block) in by_block:
                        feature["geometry"] = by_block[int(block)]
            shapes = [shape(feature["geometry"]) for feature in features]
            entry = {
                "features": features,
                "shapes": shapes,
                "tree": STRtree(shapes),
            }
            payload_cache.clear()
            payload_cache[key] = entry
            return entry

    @app.get("/api/runs/{run}/map-stats")
    def map_stats(
        run: str,
        year: int | None = Query(default=None),
        layer: str = Query(default="treatments"),
        account: str | None = Query(default=None),
        period_start: int | None = Query(default=None),
    ) -> dict[str, int]:
        """Return the full-run feature counts a viewport map does not carry."""
        if layer not in ("blocks", "treatments", "cumulative"):
            raise HTTPException(status_code=422, detail=f"unknown tile layer {layer!r}")
        payload = map_features(
            run=run,
            year=year,
            layer=layer,
            account=account,
            period_start=period_start,
            format="projected",
            bbox=None,
            zoom=None,
        )
        total = len(payload["features"])
        treated = sum(
            1
            for feature in payload["features"]
            if bool(feature.get("properties", {}).get("treated"))
        )
        return {
            "total_features": total,
            "total_treated": treated,
            "total_untreated": total - treated,
        }

    def _treated_blocks(entry: dict[str, Any]) -> set[int]:
        """Return the block ids marked treated in a cached geometry entry."""
        blocks: set[int] = set()
        for feature in entry["features"]:
            properties = feature.get("properties", {})
            block = properties.get("block_id")
            if block is not None and bool(properties.get("treated")):
                blocks.add(int(block))
        return blocks

    def _treated_set(run: str, year: int | None, period_start: int | None) -> set[int]:
        """Return the blocks treated in a run's period, without reading the geometry."""
        directory = run_dir(run)
        schedule_path = directory / "schedule.csv"
        if not schedule_path.is_file():
            raise HTTPException(status_code=404, detail="the run has no schedule.csv")
        schedule = read_csv(directory, "schedule.csv")
        if schedule.empty:
            return set()
        if year is None:
            year = int(schedule["offset"].min())
        first = year if period_start is None else min(period_start, year)
        selected = schedule[(schedule["offset"] >= first) & (schedule["offset"] <= year)]
        return {int(float(str(block))) for block in selected["block_id"].dropna().tolist()}

    @app.get("/api/runs/{run}/compare-stats")
    def compare_stats(
        run: str,
        against: str = Query(...),
        year: int | None = Query(default=None),
        period_start: int | None = Query(default=None),
    ) -> dict[str, int]:
        """Return the full-run A/B/both counts for two runs."""
        run_dir(against)
        treated_a = _treated_set(run, year, period_start)
        treated_b = _treated_set(against, year, period_start)
        total = len(base_features())
        both = len(treated_a & treated_b)
        a_only = len(treated_a - treated_b)
        b_only = len(treated_b - treated_a)
        return {
            "total_features": total,
            "a_only": a_only,
            "b_only": b_only,
            "both": both,
            "neither": max(0, total - a_only - b_only - both),
        }

    @app.get("/api/runs/{run}/compare-tiles/{z}/{x}/{y}.mvt")
    def compare_tile(
        run: str,
        z: int,
        x: int,
        y: int,
        against: str = Query(...),
        year: int | None = Query(default=None),
        period_start: int | None = Query(default=None),
    ) -> Response:
        """Return one MVT tile with an A/B/both flag for each block."""
        if z < 0 or z > 22 or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
            raise HTTPException(status_code=422, detail="tile coordinate out of range")
        run_dir(against)
        cache_key = (run, against, z, x, y, year, period_start, "compare")
        cache_path = (
            _compare_cache_path(tile_cache_root, run, against, year, period_start, z, x, y)
            if tile_cache_root is not None
            else None
        )
        cached_tile = compare_tile_cache.get(cache_key)
        if cached_tile is not None:
            return Response(
                content=cached_tile,
                media_type="application/vnd.mapbox-vector-tile",
                headers={"Cache-Control": "public, max-age=3600", "X-WS4-Tile-Cache": "memory"},
            )
        if cache_path is not None and cache_path.is_file():
            payload = cache_path.read_bytes()
            compare_tile_cache[cache_key] = payload
            return Response(
                content=payload,
                media_type="application/vnd.mapbox-vector-tile",
                headers={"Cache-Control": "public, max-age=3600", "X-WS4-Tile-Cache": "disk"},
            )
        overview = z < 8 and overview_path is not None
        entry_a = cached_geometry(run, year, "treatments", period_start, None, overview=overview)
        entry_b = cached_geometry(
            against, year, "treatments", period_start, None, overview=overview
        )
        treated_a = _treated_blocks(entry_a)
        treated_b = _treated_blocks(entry_b)
        tile = mercantile.Tile(x, y, z)
        mercator = mercantile.xy_bounds(tile)
        to_source = Transformer.from_crs("EPSG:3857", source_crs, always_xy=True)
        to_mercator = Transformer.from_crs(source_crs, "EPSG:3857", always_xy=True)
        source_bounds = to_source.transform_bounds(
            mercator.left, mercator.bottom, mercator.right, mercator.top
        )
        tile_box = box(*source_bounds)
        tolerance = _tile_tolerance(z)
        indices = [int(index) for index in entry_a["tree"].query(tile_box)]
        features: list[dict[str, Any]] = []

        def project(coordinates: np.ndarray) -> np.ndarray:
            xs, ys = to_mercator.transform(coordinates[:, 0], coordinates[:, 1])
            return np.column_stack([xs, ys])

        for index in indices:
            properties = entry_a["features"][index].get("properties", {})
            block = properties.get("block_id")
            if block is None:
                continue
            number = int(block)
            in_a = number in treated_a
            in_b = number in treated_b
            flag = "both" if in_a and in_b else "a" if in_a else "b" if in_b else "none"
            if z < 6 and flag == "none":
                continue
            geometry = entry_a["shapes"][index]
            if not geometry.is_valid:
                geometry = make_valid(geometry)
                if geometry.geom_type == "GeometryCollection":
                    parts = [
                        part
                        for part in geometry.geoms
                        if part.geom_type in ("Polygon", "MultiPolygon")
                    ]
                    geometry = unary_union(parts) if parts else geometry
                if geometry.geom_type not in ("Polygon", "MultiPolygon"):
                    continue
            if tolerance > 0:
                geometry = geometry.simplify(tolerance, preserve_topology=True)
            geometry = geometry.intersection(tile_box)
            if geometry.is_empty:
                continue
            mercator_geometry = shapely_transform(geometry, project)
            tile_properties = _scalar_properties(properties)
            tile_properties["compare"] = flag
            tile_properties["treated"] = flag != "none"
            features.append(
                {
                    "geometry": _tile_coordinates(
                        mercator_geometry,
                        (mercator.left, mercator.bottom, mercator.right, mercator.top),
                    ),
                    "properties": tile_properties,
                }
            )
        payload = mapbox_vector_tile.encode(
            [{"name": "blocks", "features": features}],
            default_options={"extents": TILE_EXTENT, "y_coord_down": True},
        )
        if len(compare_tile_cache) >= 4096:
            compare_tile_cache.clear()
        compare_tile_cache[cache_key] = payload
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_name(f"{cache_path.name}.tmp")
            temporary.write_bytes(payload)
            temporary.replace(cache_path)
        return Response(
            content=payload,
            media_type="application/vnd.mapbox-vector-tile",
            headers={"Cache-Control": "public, max-age=3600", "X-WS4-Tile-Cache": "miss"},
        )

    @app.get("/api/runs/{run}/tiles/{z}/{x}/{y}.mvt")
    def map_tile(
        run: str,
        z: int,
        x: int,
        y: int,
        year: int | None = Query(default=None),
        layer: str = Query(default="treatments"),
        account: str | None = Query(default=None),
        period_start: int | None = Query(default=None),
    ) -> Response:
        """Return one MVT tile for the current viewport and zoom."""
        if layer not in ("blocks", "treatments", "cumulative"):
            raise HTTPException(status_code=422, detail=f"unknown tile layer {layer!r}")
        if z < 0 or z > 22 or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
            raise HTTPException(status_code=422, detail="tile coordinate out of range")
        cache_key = (run, z, x, y, layer, year, period_start)
        cache_path = (
            _tile_cache_path(tile_cache_root, run, layer, year, period_start, z, x, y)
            if tile_cache_root is not None
            else None
        )
        cached_tile = tile_cache.get(cache_key)
        if cached_tile is not None:
            return Response(
                content=cached_tile,
                media_type="application/vnd.mapbox-vector-tile",
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "X-WS4-Tile-Cache": "memory",
                },
            )
        if cache_path is not None and cache_path.is_file():
            payload = cache_path.read_bytes()
            tile_cache[cache_key] = payload
            return Response(
                content=payload,
                media_type="application/vnd.mapbox-vector-tile",
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "X-WS4-Tile-Cache": "disk",
                },
            )
        entry = cached_geometry(
            run,
            year,
            layer,
            period_start,
            account,
            overview=z < 8 and overview_path is not None,
        )
        tile = mercantile.Tile(x, y, z)
        mercator = mercantile.xy_bounds(tile)
        to_source = Transformer.from_crs("EPSG:3857", source_crs, always_xy=True)
        to_mercator = Transformer.from_crs(source_crs, "EPSG:3857", always_xy=True)
        source_bounds = to_source.transform_bounds(
            mercator.left, mercator.bottom, mercator.right, mercator.top
        )
        tile_box = box(*source_bounds)
        tolerance = _tile_tolerance(z)
        indices = [int(index) for index in entry["tree"].query(tile_box)]
        indices = _sample_low_zoom(indices, layer, z)
        if z < 6 and layer != "blocks":
            indices = [
                index
                for index in indices
                if bool(entry["features"][index].get("properties", {}).get("treated"))
            ]
        features: list[dict[str, Any]] = []

        def project(coordinates: np.ndarray) -> np.ndarray:
            xs, ys = to_mercator.transform(coordinates[:, 0], coordinates[:, 1])
            return np.column_stack([xs, ys])

        for index in indices:
            properties = entry["features"][index].get("properties", {})
            geometry = entry["shapes"][index]
            if not geometry.is_valid:
                geometry = make_valid(geometry)
                if geometry.geom_type == "GeometryCollection":
                    parts = [
                        part
                        for part in geometry.geoms
                        if part.geom_type in ("Polygon", "MultiPolygon")
                    ]
                    geometry = unary_union(parts) if parts else geometry
                if geometry.geom_type not in ("Polygon", "MultiPolygon"):
                    continue
            if tolerance > 0:
                geometry = geometry.simplify(tolerance, preserve_topology=True)
            geometry = geometry.intersection(tile_box)
            if geometry.is_empty:
                continue
            mercator_geometry = shapely_transform(geometry, project)
            features.append(
                {
                    "geometry": _tile_coordinates(
                        mercator_geometry,
                        (mercator.left, mercator.bottom, mercator.right, mercator.top),
                    ),
                    "properties": _scalar_properties(properties),
                }
            )
        payload = mapbox_vector_tile.encode(
            [{"name": "blocks", "features": features}],
            default_options={"extents": TILE_EXTENT, "y_coord_down": True},
        )
        if len(tile_cache) >= 4096:
            tile_cache.clear()
        tile_cache[cache_key] = payload
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_name(f"{cache_path.name}.tmp")
            temporary.write_bytes(payload)
            temporary.replace(cache_path)
        return Response(
            content=payload,
            media_type="application/vnd.mapbox-vector-tile",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-WS4-Tile-Cache": "miss",
            },
        )

    def _realized_rows(directory: Path) -> list[dict[str, Any]]:
        """Return each target's realized period value, computed by the optimizer's own rule."""
        if targets_path is None or not targets_path.is_file():
            return []
        values = read_csv(directory, "account_values.csv")
        index: dict[tuple[int, str], float] = {}
        for year, account, value in zip(
            values["offset"], values["account"], values["value"], strict=True
        ):
            key = (int(year), str(account))
            index[key] = index.get(key, 0.0) + float(value)
        rows: list[dict[str, Any]] = []
        horizon = max((year for year, _ in index), default=-1) + 1
        for target_index, target in enumerate(load_targets(targets_path)):
            if target.flow:
                series = flow_series(index, target, horizon)
                flow_values = list(series.values())
                value = (
                    max(flow_values)
                    if target.maximum is not None and flow_values
                    else min(flow_values)
                    if flow_values
                    else 0.0
                )
                status = "inactive"
                if target.active:
                    status = "met"
                    if flow_penalty(index, target, horizon) > 0.0:
                        if (
                            target.maximum is not None
                            and flow_values
                            and max(flow_values) > target.maximum
                        ):
                            status = "above"
                        else:
                            status = "below"
            else:
                value = period_value(index, target)
                status = "inactive"
                if target.active:
                    status = "met"
                    if target.minimum is not None and value < target.minimum:
                        status = "below"
                    elif target.maximum is not None and value > target.maximum:
                        status = "above"
            rows.append(
                {
                    "index": target_index,
                    "account": target.account,
                    "period": target.period,
                    "year": target.year,
                    "period_width": target.period_width,
                    "flow": target.flow,
                    "value": value,
                    "raw_penalty": None if target.flow else raw_penalty(value, target),
                    "penalty": None if target.flow else penalty(value, target),
                    "scale": normalization_scale(target),
                    "normalization": target.normalization,
                    "priority": target.priority,
                    "kind": target_kind(target),
                    "status": status,
                    "active": target.active,
                }
            )
        return rows

    def _target_rows() -> list[dict[str, Any]]:
        """Return the targets as rows the browser can edit, keeping any notes."""
        if targets_path is None or not targets_path.is_file():
            return []
        raw = yaml.safe_load(targets_path.read_text(encoding="utf-8")) or {}
        entries = raw.get("targets", []) if isinstance(raw, dict) else []
        rows: list[dict[str, Any]] = []
        for target_index, target in enumerate(load_targets(targets_path)):
            row: dict[str, Any] = {
                "index": target_index,
                "account": target.account,
                "period": target.period,
                "year": target.year,
                "period_width": target.period_width,
                "flow": target.flow,
                "minimum": target.minimum,
                "maximum": target.maximum,
                "min_weight": target.min_weight,
                "max_weight": target.max_weight,
                "normalization": target.normalization,
                "priority": target.priority,
                "kind": target_kind(target),
                "active": target.active,
            }
            if target_index < len(entries) and isinstance(entries[target_index], dict):
                notes = entries[target_index].get("notes")
                if notes is not None:
                    row["notes"] = notes
            rows.append(row)
        return rows

    def _write_targets(document: str) -> int:
        """Validate a targets document with the optimizer's loader, then replace the file."""
        if targets_path is None:
            raise HTTPException(status_code=404, detail="the service was started without --targets")
        parsed = yaml.safe_load(document)
        if not isinstance(parsed, dict) or not parsed.get("targets"):
            raise HTTPException(
                status_code=422,
                detail="the targets document needs a non-empty 'targets' list",
            )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", dir=targets_path.parent, delete=False, encoding="utf-8"
        ) as handle:
            handle.write(document)
            candidate = Path(handle.name)
        try:
            targets = load_targets(candidate)
        except Exception as error:  # the loader's message is the refusal the CLI would give
            candidate.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(error)) from error
        if targets_path.is_file():
            shutil.copy2(targets_path, targets_path.with_name(targets_path.name + ".bak"))
        shutil.move(str(candidate), targets_path)
        return len(targets)

    @app.get("/api/targets", response_class=PlainTextResponse)
    def get_targets() -> str:
        """Return the targets YAML as written."""
        if targets_path is None:
            raise HTTPException(status_code=404, detail="the service was started without --targets")
        if not targets_path.is_file():
            raise HTTPException(status_code=404, detail=f"no targets file at {targets_path.name}")
        return targets_path.read_text(encoding="utf-8")

    @app.put("/api/targets")
    @app.post("/api/targets")
    def put_targets(body: Annotated[str, Body(media_type="text/yaml")]) -> dict[str, Any]:
        """Validate and replace the targets YAML."""
        return {"targets": _write_targets(body)}

    @app.get("/api/targets.json")
    def get_targets_json() -> list[dict[str, Any]]:
        """Return the parsed targets, for an editor that does not parse YAML."""
        return _target_rows()

    @app.get("/api/runs/{run}/targets")
    def run_targets(run: str) -> list[dict[str, Any]]:
        """Return the run's realized value for each target, over the target's own period."""
        return _realized_rows(run_dir(run))

    @app.get("/api/runs/{run}/target-series")
    def run_target_series(run: str) -> dict[str, Any]:
        """Return every target account's bounds and active state for every run period."""
        directory = run_dir(run)
        if targets_path is None or not targets_path.is_file():
            return {"periods": [], "accounts": []}
        values = read_csv(directory, "account_values.csv")
        years = sorted(
            {
                int(float(str(value)))
                for value in values["offset"].tolist()
                if int(float(str(value))) >= 0
            }
        )
        width = _run_period_width(targets_path)
        periods = _run_periods(years, width)
        targets = load_targets(targets_path)
        accounts: dict[str, dict[str, Any]] = {}
        for target_index, target in enumerate(targets):
            entry = accounts.setdefault(
                target.account,
                {
                    "account": target.account,
                    "flow": target.flow,
                    "kind": target_kind(target),
                    "periods": [
                        {
                            "index": int(str(period["index"])),
                            "start": int(str(period["start"])),
                            "end": int(str(period["end"])),
                            "label": str(period["label"]),
                            "minimum": None,
                            "maximum": None,
                            "active": False,
                            "target_indices": [],
                        }
                        for period in periods
                    ],
                },
            )
            if target.period is not None and target.period > 0:
                period_index = target.period - 1
            else:
                end = target.end_offset()
                period_index = next(
                    (
                        int(str(period["index"]))
                        for period in periods
                        if int(str(period["start"])) <= end <= int(str(period["end"]))
                    ),
                    -1,
                )
            if period_index < 0 or period_index >= len(entry["periods"]):
                continue
            cell = entry["periods"][period_index]
            if target.minimum is not None:
                cell["minimum"] = float(target.minimum)
            if target.maximum is not None:
                cell["maximum"] = float(target.maximum)
            cell["active"] = bool(cell["active"] or target.active)
            cell["target_indices"].append(target_index)
        return {"periods": periods, "accounts": list(accounts.values())}

    @app.put("/api/targets.json")
    @app.post("/api/targets.json")
    def put_targets_json(
        rows: Annotated[list[dict[str, Any]], Body()],
    ) -> dict[str, Any]:
        """Validate and replace the targets from a JSON list, writing the optimizer's YAML."""
        if not rows:
            raise HTTPException(status_code=422, detail="the targets list is empty")
        # ``kind`` is derived for the browser; it is not a targets-file field.
        cleaned = [{key: value for key, value in row.items() if key != "kind"} for row in rows]
        document = yaml.safe_dump({"targets": cleaned}, sort_keys=False)
        return {"targets": _write_targets(document)}

    return app
