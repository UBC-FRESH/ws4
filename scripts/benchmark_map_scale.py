#!/usr/bin/env python3
"""Measure the map pipeline on a synthetic large geometry set.

The check builds a point grid, starts the app in-process, and times the first
zoom-0 tile, a zoom-12 tile, and a warm zoom-0 tile. It is a scale gate for the
tile path, not a model benchmark: the geometry is deliberately simple so the
result isolates geometry count, payload size, and cache behaviour.

Run the production-size check with::

    python scripts/benchmark_map_scale.py --fragments 1000000 --check

The default run uses a temporary directory and removes it. Use ``--workdir`` to
keep the generated geometry for inspection.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import TypedDict

import mercantile
from fastapi.testclient import TestClient
from ws4.web.app import create_app


class BenchmarkResult(TypedDict):
    """One scale run's measurements."""

    fragments: int
    geometry_bytes: int
    z0_bytes: int
    z12_bytes: int
    cold_seconds: float
    detail_seconds: float
    warm_seconds: float
    z0_cache: str | None
    z12_cache: str | None
    warm_cache: str | None
    peak_rss_mb: float


DEFAULT_FRAGMENTS: int = 1_000_000
MAX_TILE_BYTES: int = 2_000_000
MAX_COLD_SECONDS: float = 120.0
MAX_WARM_SECONDS: float = 5.0
MAX_RSS_MB: float = 4096.0


def peak_rss_mb() -> float | None:
    """Return the process peak resident set size in MiB, or None when unavailable.

    Returns
    -------
    float or None
        The peak RSS, or None on a platform without the ``resource`` module.
    """
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows without resource
        return None
    usage = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return usage / (1024.0 * 1024.0)
    return usage / 1024.0


def generate_grid(
    count: int,
    path: Path,
    *,
    west: float = -130.0,
    south: float = 50.0,
    east: float = -124.0,
    north: float = 56.0,
) -> int:
    """Write a point grid as a GeoJSON FeatureCollection.

    Parameters
    ----------
    count : int
        Number of points.
    path : Path
        Destination GeoJSON.
    west, south, east, north : float, optional
        Bounds in EPSG:4326.

    Returns
    -------
    int
        The number of features written.

    Raises
    ------
    ValueError
        When ``count`` is not positive.
    """
    if count <= 0:
        raise ValueError("count must be positive")
    side = math.ceil(math.sqrt(count))
    span = max(side - 1, 1)
    step_x = (east - west) / span
    step_y = (north - south) / span
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8") as handle:
        handle.write('{"type":"FeatureCollection","features":[')
        for row in range(side):
            if written >= count:
                break
            for column in range(side):
                if written >= count:
                    break
                feature = {
                    "type": "Feature",
                    "properties": {"block_id": written},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [west + column * step_x, south + row * step_y],
                    },
                }
                if written:
                    handle.write(",")
                handle.write(json.dumps(feature, separators=(",", ":")))
                written += 1
        handle.write("]}")
    return written


def run_benchmark(
    fragments: int,
    *,
    workdir: Path | None = None,
) -> BenchmarkResult:
    """Run the tile timings for one synthetic geometry.

    Parameters
    ----------
    fragments : int
        Number of block points.
    workdir : Path or None, optional
        Directory to use. ``None`` creates and removes a temporary directory.

    Returns
    -------
    BenchmarkResult
        Feature count, geometry bytes, tile bytes, and cold/warm seconds.

    Raises
    ------
    RuntimeError
        When a tile request does not return 200.
    """
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if workdir is None:
        temporary = tempfile.TemporaryDirectory(prefix="ws4-map-scale-")
        root = Path(temporary.name)
    else:
        root = Path(workdir)
        root.mkdir(parents=True, exist_ok=True)
    try:
        dataset = root / "dataset"
        dataset.mkdir(parents=True, exist_ok=True)
        (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
        run = root / "runs" / "scale"
        run.mkdir(parents=True, exist_ok=True)
        (run / "summary.json").write_text('{"status": "ok"}', encoding="utf-8")
        geometry = root / "geometry.geojson"
        generated = generate_grid(fragments, geometry)
        app = create_app(
            dataset=dataset,
            runs=root / "runs",
            geometry=geometry,
            crs="EPSG:4326",
            tile_cache_dir=root / "tile-cache",
        )
        client = TestClient(app)
        started = time.perf_counter()
        zero = client.get(
            "/api/runs/scale/tiles/0/0/0.mvt",
            params={"year": 0, "layer": "blocks"},
        )
        cold_seconds = time.perf_counter() - started
        if zero.status_code != 200:
            raise RuntimeError(f"zoom-0 tile failed: {zero.status_code}")
        tile = mercantile.tile(-127.0, 53.0, 12)
        started = time.perf_counter()
        detail = client.get(
            f"/api/runs/scale/tiles/12/{tile.x}/{tile.y}.mvt",
            params={"year": 0, "layer": "blocks"},
        )
        detail_seconds = time.perf_counter() - started
        if detail.status_code != 200:
            raise RuntimeError(f"zoom-12 tile failed: {detail.status_code}")
        started = time.perf_counter()
        warm = client.get(
            "/api/runs/scale/tiles/0/0/0.mvt",
            params={"year": 0, "layer": "blocks"},
        )
        warm_seconds = time.perf_counter() - started
        if warm.status_code != 200:
            raise RuntimeError(f"warm tile failed: {warm.status_code}")
        return {
            "fragments": generated,
            "geometry_bytes": geometry.stat().st_size,
            "z0_bytes": len(zero.content),
            "z12_bytes": len(detail.content),
            "cold_seconds": round(cold_seconds, 3),
            "detail_seconds": round(detail_seconds, 3),
            "warm_seconds": round(warm_seconds, 3),
            "z0_cache": zero.headers.get("x-ws4-tile-cache"),
            "z12_cache": detail.headers.get("x-ws4-tile-cache"),
            "warm_cache": warm.headers.get("x-ws4-tile-cache"),
            "peak_rss_mb": round(peak_rss_mb() or 0.0, 1),
        }
    finally:
        if temporary is not None:
            temporary.cleanup()


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - scale gate
    """Run the scale benchmark from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when the check passes, and ``1`` when a threshold is exceeded.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragments", type=int, default=DEFAULT_FRAGMENTS)
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = run_benchmark(args.fragments, workdir=args.workdir)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not args.check:
        return 0
    failures: list[str] = []
    if int(result["z0_bytes"]) > MAX_TILE_BYTES:
        failures.append(f"z0 tile {result['z0_bytes']} > {MAX_TILE_BYTES}")
    if int(result["z12_bytes"]) > MAX_TILE_BYTES:
        failures.append(f"z12 tile {result['z12_bytes']} > {MAX_TILE_BYTES}")
    if float(result["cold_seconds"]) > MAX_COLD_SECONDS:
        failures.append(f"cold {result['cold_seconds']}s > {MAX_COLD_SECONDS}s")
    if float(result["warm_seconds"]) > MAX_WARM_SECONDS:
        failures.append(f"warm {result['warm_seconds']}s > {MAX_WARM_SECONDS}s")
    if float(result["peak_rss_mb"]) > MAX_RSS_MB:
        failures.append(f"peak RSS {result['peak_rss_mb']} MiB > {MAX_RSS_MB} MiB")
    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
