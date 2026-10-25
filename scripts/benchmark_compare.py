#!/usr/bin/env python3
"""Benchmark comparison MVT tiles cold and warm.

This is an opt-in operation check, not a CI gate. It requests the compare tile for
every tile intersecting a WGS84 bbox, then repeats the pass to measure the durable
cache. Budgets fail the command when exceeded.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode

import mercantile


def benchmark(  # pragma: no cover - opt-in network probe
    url: str,
    run_a: str,
    run_b: str,
    *,
    zoom: int,
    bbox: tuple[float, float, float, float],
    year: int,
    period_start: int | None,
    max_cold_seconds: float,
    max_warm_seconds: float,
) -> dict[str, object]:
    """Return cold and warm timings for the compare tiles in one bbox.

    Parameters
    ----------
    url : str
        Service root.
    run_a : str
        First run.
    run_b : str
        Second run.
    zoom : int
        Tile zoom.
    bbox : tuple of float
        WGS84 west, south, east, north.
    year : int
        Period end year.
    period_start : int or None
        Period start year.
    max_cold_seconds : float
        First-tile cold budget.
    max_warm_seconds : float
        First-tile warm budget.

    Returns
    -------
    dict of str to object
        Timings, bytes, failures, budgets, and the pass flag.
    """
    tiles = list(mercantile.tiles(bbox[0], bbox[1], bbox[2], bbox[3], [zoom]))
    base = url.rstrip("/")
    params = {"against": run_b, "year": year, "v": "v8"}
    if period_start is not None:
        params["period_start"] = period_start
    query = urlencode(params)

    def pass_once() -> tuple[float, float, int, int]:
        first = 0.0
        total = 0.0
        total_bytes = 0
        failed = 0
        for index, tile in enumerate(tiles):
            started = time.perf_counter()
            request_url = (
                f"{base}/api/runs/{run_a}/compare-tiles/{zoom}/{tile.x}/{tile.y}.mvt?{query}"
            )
            try:
                from urllib.request import urlopen

                with urlopen(request_url, timeout=120) as response:
                    payload = response.read()
                    total_bytes += len(payload)
                    if response.status != 200:
                        failed += 1
            except HTTPError as error:
                failed += 1
                error.read()
            elapsed = time.perf_counter() - started
            if index == 0:
                first = elapsed
            total += elapsed
        return first, total, total_bytes, failed

    cold_first, cold_total, cold_bytes, cold_failed = pass_once()
    warm_first, warm_total, warm_bytes, warm_failed = pass_once()
    return {
        "url": base,
        "run_a": run_a,
        "run_b": run_b,
        "zoom": zoom,
        "tiles": len(tiles),
        "cold_first_seconds": round(cold_first, 3),
        "cold_seconds": round(cold_total, 3),
        "warm_first_seconds": round(warm_first, 3),
        "warm_seconds": round(warm_total, 3),
        "cold_bytes": cold_bytes,
        "warm_bytes": warm_bytes,
        "cold_failures": cold_failed,
        "warm_failures": warm_failed,
        "max_cold_seconds": max_cold_seconds,
        "max_warm_seconds": max_warm_seconds,
        "ok": (
            cold_failed == 0
            and warm_failed == 0
            and cold_first <= max_cold_seconds
            and warm_first <= max_warm_seconds
        ),
    }


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - opt-in network probe
    """Run the compare benchmark from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when all tiles and budgets pass, ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8022/")
    parser.add_argument("--run-a", required=True)
    parser.add_argument("--run-b", required=True)
    parser.add_argument("--zoom", type=int, default=9)
    parser.add_argument("--bbox", default="-114.75,49.62,-114.13,50.40")
    parser.add_argument("--year", type=int, default=9)
    parser.add_argument("--period-start", type=int, default=0)
    parser.add_argument("--max-cold-seconds", type=float, default=120.0)
    parser.add_argument("--max-warm-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)
    bbox = tuple(float(part) for part in args.bbox.split(","))
    if len(bbox) != 4:
        print("bbox must be west,south,east,north", file=sys.stderr)
        return 1
    report = benchmark(
        args.url,
        args.run_a,
        args.run_b,
        zoom=args.zoom,
        bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
        year=args.year,
        period_start=args.period_start,
        max_cold_seconds=args.max_cold_seconds,
        max_warm_seconds=args.max_warm_seconds,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
