#!/usr/bin/env python3
"""Check the map service under a reverse-proxy path prefix.

The service is mounted at ``/prefix`` on a parent FastAPI app. The check requests
the shell, its static assets, the API summary, a viewport map, and an MVT tile
through that prefix. It also asserts that the shell and script use relative URLs,
which is what makes a path prefix work without a rewrite rule.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from ws4.web.app import create_app


def _check(client: TestClient, path: str) -> dict[str, object]:
    """Request one path and return a JSON-ready check result."""
    response = client.get(path)
    return {
        "path": path,
        "status": response.status_code,
        "bytes": len(response.content),
        "ok": response.status_code == 200,
    }


def check_prefix(
    *,
    dataset: Path,
    runs: Path,
    geometry: Path,
    prefix: str = "/ws4",
    tile_cache: Path | None = None,
    crs: str = "EPSG:4326",
) -> dict[str, object]:
    """Mount the service under a prefix and check every public surface.

    Parameters
    ----------
    dataset : Path
        Compiled ws4 dataset.
    runs : Path
        Run directory.
    geometry : Path
        Block geometry.
    prefix : str, optional
        Path prefix, such as ``/ws4``.
    tile_cache : Path or None, optional
        Optional durable tile cache.
    crs : str, optional
        CRS of the geometry.

    Returns
    -------
    dict of str to object
        The prefix, each check, and an overall ``ok``.

    Raises
    ------
    ValueError
        When the prefix is not a non-empty absolute path.
    """
    if not prefix.startswith("/") or prefix in {"", "/"}:
        raise ValueError("prefix must be an absolute non-root path, such as /ws4")
    prefix = prefix.rstrip("/")
    service = create_app(
        dataset=dataset,
        runs=runs,
        geometry=geometry,
        crs=crs,
        tile_cache_dir=tile_cache,
    )
    parent = FastAPI()
    parent.mount(prefix, service)
    client = TestClient(parent)
    run_names = sorted(
        directory.name
        for directory in runs.iterdir()
        if directory.is_dir()
        and ((directory / "summary.json").is_file() or (directory / "account_values.csv").is_file())
    )
    if not run_names:
        raise ValueError("runs has no run directory")
    run = run_names[0]
    checks = [
        _check(client, f"{prefix}/"),
        _check(client, f"{prefix}/static/style.css"),
        _check(client, f"{prefix}/static/app.js"),
        _check(client, f"{prefix}/api/summary"),
        _check(client, f"{prefix}/api/runs/{run}/map?year=0&layer=blocks&format=wgs84"),
        _check(client, f"{prefix}/api/runs/{run}/tiles/0/0/0.mvt?year=0&layer=blocks"),
    ]
    shell = client.get(f"{prefix}/")
    script = client.get(f"{prefix}/static/app.js")
    relative = 'href="static/' in shell.text and "api/" in script.text
    return {
        "prefix": prefix,
        "run": run,
        "checks": checks,
        "relative_urls": relative,
        "ok": relative and all(bool(check["ok"]) for check in checks),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the path-prefix check from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when every check answers, and ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--prefix", default="/ws4")
    parser.add_argument("--tile-cache", type=Path, default=None)
    parser.add_argument("--crs", default="EPSG:4326")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = check_prefix(
        dataset=args.dataset,
        runs=args.runs,
        geometry=args.geometry,
        prefix=args.prefix,
        tile_cache=args.tile_cache,
        crs=args.crs,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
