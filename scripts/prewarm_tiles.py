#!/usr/bin/env python3
"""Pre-warm the durable MVT tile cache for a model tree.

The script opens the ws4 app in-process with the same dataset, runs, geometry, and
``--tile-cache`` directory as the service, walks a tile pyramid over the model's
bounds, and requests each selected layer and period. The durable cache then serves
the first real browser request from disk instead of rebuilding the tile.

The default is deliberately small: zoom 6, the first year, the blocks layer. Pass
``--zooms``, ``--layers``, and ``--period-width`` for a fuller warm.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import mercantile
from fastapi.testclient import TestClient
from ws4.web.app import create_app

DEFAULT_ZOOMS: tuple[int, ...] = (6,)
DEFAULT_LAYERS: tuple[str, ...] = ("blocks",)
TILE_LAYERS: tuple[str, ...] = ("blocks", "treatments", "cumulative")


def _parse_csv(text: str) -> list[str]:
    """Split a comma list, rejecting an empty value."""
    values = [item.strip() for item in text.split(",") if item.strip()]
    if not values:
        raise ValueError("expected at least one value")
    return values


def parse_zooms(text: str) -> tuple[int, ...]:
    """Parse ``0-6`` or ``0,2,6`` into zoom levels.

    Parameters
    ----------
    text : str
        A range or comma list.

    Returns
    -------
    tuple of int
        The zoom levels, in the order given.

    Raises
    ------
    ValueError
        When a level is outside 0-22 or the range is reversed.
    """
    levels: list[int] = []
    for part in _parse_csv(text):
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"reversed zoom range: {part!r}")
            levels.extend(range(start, end + 1))
        else:
            levels.append(int(part))
    if any(level < 0 or level > 22 for level in levels):
        raise ValueError("zooms must be between 0 and 22")
    return tuple(dict.fromkeys(levels))


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    """Parse ``west,south,east,north`` in WGS84.

    Parameters
    ----------
    text : str
        Four comma-separated numbers.

    Returns
    -------
    tuple of float
        The bounds.

    Raises
    ------
    ValueError
        When the text does not contain four finite numbers.
    """
    values = [float(item) for item in _parse_csv(text)]
    if len(values) != 4:
        raise ValueError("bbox must be west,south,east,north")
    return values[0], values[1], values[2], values[3]


def geometry_bounds(path: Path) -> tuple[float, float, float, float]:
    """Return the WGS84 bounds of a GeoJSON document.

    Parameters
    ----------
    path : Path
        GeoJSON Feature or FeatureCollection.

    Returns
    -------
    tuple of float
        West, south, east, and north.

    Raises
    ------
    ValueError
        When the document has no coordinates.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    west = south = float("inf")
    east = north = float("-inf")

    def visit(value: object) -> None:
        nonlocal west, south, east, north
        if (
            isinstance(value, list)
            and len(value) >= 2
            and all(isinstance(item, (int, float)) for item in value[:2])
        ):
            x, y = float(value[0]), float(value[1])
            west, south = min(west, x), min(south, y)
            east, north = max(east, x), max(north, y)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)

    visit(document)
    if not all(value not in (float("inf"), float("-inf")) for value in (west, south, east, north)):
        raise ValueError(f"{path} has no coordinates")
    return west, south, east, north


def periods(horizon: int, width: int) -> list[tuple[int, int | None]]:
    """Return ``(year, period_start)`` pairs for a horizon.

    Parameters
    ----------
    horizon : int
        Simulation horizon in years.
    width : int
        Accounting period width; 0 or 1 means one request per year.

    Returns
    -------
    list of (int, int or None)
        The end year and period start for each request.
    """
    if width <= 1:
        return [(year, None) for year in range(max(1, horizon))]
    return [
        (min(end, horizon) - 1, start)
        for start, end in ((start, start + width) for start in range(0, horizon, width))
        if start < horizon
    ]


def prewarm(
    *,
    dataset: Path,
    runs: Path,
    geometry: Path,
    tile_cache: Path,
    geometry_overview: Path | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    zooms: tuple[int, ...] = DEFAULT_ZOOMS,
    layers: tuple[str, ...] = DEFAULT_LAYERS,
    run: str | None = None,
    horizon: int = 1,
    period_width: int = 0,
    max_tiles: int = 5000,
    crs: str = "EPSG:4326",
) -> dict[str, object]:
    """Warm the durable tile cache and return a JSON-ready report.

    Parameters
    ----------
    dataset : Path
        Compiled ws4 dataset.
    runs : Path
        Run directory.
    geometry : Path
        Detail block geometry.
    tile_cache : Path
        Durable tile cache directory.
    geometry_overview : Path or None, optional
        Coarser low-zoom geometry.
    bbox : tuple of float or None, optional
        WGS84 bounds. ``None`` reads the geometry.
    zooms : tuple of int, optional
        Zoom levels to warm.
    layers : tuple of str, optional
        Tile layers to warm.
    run : str or None, optional
        A single run name; ``None`` warms every run with a summary or account values.
    horizon : int, optional
        Simulation horizon for the period walk.
    period_width : int, optional
        Accounting period width; 0 means the first year only.
    max_tiles : int, optional
        Safety cap on requests.
    crs : str, optional
        CRS of the geometry.

    Returns
    -------
    dict of str to object
        Counts, bytes, seconds, cache-header counts, and the cache directory.

    Raises
    ------
    ValueError
        When a layer, zoom, or tile count is invalid.
    """
    unknown = [layer for layer in layers if layer not in TILE_LAYERS]
    if unknown:
        raise ValueError(f"unknown layer(s): {', '.join(unknown)}")
    if not zooms:
        raise ValueError("at least one zoom is required")
    if max_tiles < 1:
        raise ValueError("max_tiles must be positive")
    if bbox is None:
        bbox = geometry_bounds(geometry_overview or geometry)
    app = create_app(
        dataset=dataset,
        runs=runs,
        geometry=geometry,
        geometry_overview=geometry_overview,
        crs=crs,
        tile_cache_dir=tile_cache,
    )
    client = TestClient(app)
    if run is None:
        run_names = sorted(
            directory.name
            for directory in runs.iterdir()
            if directory.is_dir()
            and (
                (directory / "summary.json").is_file()
                or (directory / "account_values.csv").is_file()
            )
        )
    else:
        run_names = [run]
    request_periods = periods(horizon, period_width)
    started = time.perf_counter()
    requested = 0
    failed = 0
    total_bytes = 0
    cache_headers: Counter[str] = Counter()
    for zoom in zooms:
        for tile in mercantile.tiles(bbox[0], bbox[1], bbox[2], bbox[3], [zoom]):
            for run_name in run_names:
                for layer in layers:
                    for year, period_start in request_periods:
                        if requested >= max_tiles:
                            break
                        params: dict[str, object] = {"year": year, "layer": layer}
                        if period_start is not None:
                            params["period_start"] = period_start
                        response = client.get(
                            f"/api/runs/{run_name}/tiles/{zoom}/{tile.x}/{tile.y}.mvt",
                            params=params,
                        )
                        requested += 1
                        total_bytes += len(response.content)
                        cache_headers[response.headers.get("x-ws4-tile-cache", "none")] += 1
                        if response.status_code != 200:
                            failed += 1
    return {
        "dataset": str(dataset),
        "runs": run_names,
        "layers": list(layers),
        "zooms": list(zooms),
        "bbox": list(bbox),
        "tile_cache": str(tile_cache),
        "requested": requested,
        "failed": failed,
        "bytes": total_bytes,
        "seconds": round(time.perf_counter() - started, 3),
        "cache_headers": dict(cache_headers),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the pre-warm from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when every tile answered, and ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--geometry-overview", type=Path, default=None)
    parser.add_argument("--tile-cache", type=Path, required=True)
    parser.add_argument(
        "--bbox",
        default=None,
        help="west,south,east,north in WGS84; use --bbox=-130,50,-124,56 for negative west/south",
    )
    parser.add_argument("--zooms", default="6")
    parser.add_argument("--layers", default="blocks")
    parser.add_argument("--run", default=None)
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--period-width", type=int, default=0)
    parser.add_argument("--max-tiles", type=int, default=5000)
    parser.add_argument("--crs", default="EPSG:4326")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = prewarm(
        dataset=args.dataset,
        runs=args.runs,
        geometry=args.geometry,
        geometry_overview=args.geometry_overview,
        tile_cache=args.tile_cache,
        bbox=parse_bbox(args.bbox) if args.bbox else None,
        zooms=parse_zooms(args.zooms),
        layers=tuple(_parse_csv(args.layers)),
        run=args.run,
        horizon=args.horizon,
        period_width=args.period_width,
        max_tiles=args.max_tiles,
        crs=args.crs,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
