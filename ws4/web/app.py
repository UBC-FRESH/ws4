"""The optional HTTP surface: a reader over a compiled dataset and its runs.

Every response is something the CLI already wrote — the dataset manifest, a run's summary, its
account values, its reports, its schedule — or the targets file the optimizer reads. The service
holds no model state and computes no value the CLI cannot reproduce. See
``notes/design/ws4-web-frontend.md``.
"""

from __future__ import annotations

import html
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from ..opt.objective import load_targets

_REPORT_SUFFIXES = {".csv", ".html", ".png", ".json", ".txt"}


def _run_directory(root: Path, name: str) -> Path:
    """Return a run directory under the root, refusing anything that escapes it."""
    candidate = (root / name).resolve()
    if candidate.parent != root or not candidate.is_dir():
        raise HTTPException(status_code=404, detail=f"no run named {name!r} under {root}")
    return candidate


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


def create_app(
    *,
    dataset: Path,
    runs: Path,
    targets: Path | None = None,
    geometry: Path | None = None,
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

    Returns
    -------
    FastAPI
        The application, ready for ``uvicorn`` or a test client.
    """
    dataset = Path(dataset).resolve()
    runs_root = Path(runs).resolve()
    geometry_path = Path(geometry).resolve() if geometry is not None else None
    targets_path = Path(targets).resolve() if targets is not None else None
    app = FastAPI(title="WS4", version="0.1.0")

    def run_dir(name: str) -> Path:
        return _run_directory(runs_root, name)

    def read_csv(run: Path, name: str) -> pd.DataFrame:
        path = run / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"the run has no {name}")
        return pd.read_csv(path)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        """Return a minimal landing page until the browser application lands (P18.2)."""
        found = []
        for directory in sorted(runs_root.iterdir()) if runs_root.is_dir() else []:
            if not directory.is_dir():
                continue
            name = html.escape(directory.name)
            found.append(
                f'<li><a href="api/runs/{name}/summary">{name}</a>'
                f' &middot; <a href="api/runs/{name}/accounts">accounts</a>'
                f' &middot; <a href="api/runs/{name}/reports">reports</a></li>'
            )
        listing = "".join(found) or "<li>no runs found</li>"
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>WS4</title>
<style>body{{font-family:system-ui,sans-serif;max-width:52rem;margin:3rem auto;line-height:1.5}}
code{{background:#f2f2f2;padding:.1rem .3rem}}</style></head>
<body><h1>WS4</h1>
<p>Dataset: <code>{html.escape(dataset.name)}</code></p>
<h2>Runs</h2><ul>{listing}</ul>
<h2>API</h2>
<p><a href="api/summary">api/summary</a> &middot; <a href="docs">OpenAPI docs</a>
&middot; <a href="health">health</a></p>
<p>The browser front end is P18.2; this page is the service's landing page.</p>
</body></html>"""

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return a liveness probe."""
        return {"status": "ok"}

    @app.get("/api/summary")
    def summary() -> dict[str, Any]:
        """Return the dataset manifest and the runs found under the configured root."""
        manifest: dict[str, Any] = {}
        manifest_path = dataset / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        found = []
        for directory in sorted(runs_root.iterdir()) if runs_root.is_dir() else []:
            if not directory.is_dir():
                continue
            entry: dict[str, Any] = {"id": directory.name}
            summary_path = directory / "summary.json"
            if summary_path.is_file():
                entry["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
            found.append(entry)
        return {"dataset": dataset.name, "manifest": manifest, "runs": found}

    @app.get("/api/runs/{run}/summary")
    def run_summary(run: str) -> dict[str, Any]:
        """Return a run's ``summary.json``."""
        directory = run_dir(run)
        path = directory / "summary.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"run {run!r} has no summary.json")
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return document

    @app.get("/api/runs/{run}/accounts")
    def accounts(
        run: str,
        year: int | None = Query(default=None),
        account: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Return realized account values, optionally filtered by year and account."""
        frame = read_csv(run_dir(run), "account_values.csv")
        if year is not None:
            frame = frame[frame["year"] == year]
        if account is not None:
            frame = frame[frame["account"] == account]
        return [
            {str(key): value for key, value in row.items()}
            for row in frame.to_dict(orient="records")
        ]

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

    @app.get("/api/runs/{run}/map")
    def map_features(
        run: str,
        year: int | None = Query(default=None),
        layer: str = Query(default="treatments"),
    ) -> dict[str, Any]:
        """Return a GeoJSON FeatureCollection for a run and a year.

        The only layer in this first cut is ``treatments``: the blocks the schedule treats in the
        year, as properties on the geometry. Unsupported layer names are refused by name.
        """
        directory = run_dir(run)
        if layer != "treatments":
            raise HTTPException(status_code=422, detail=f"unknown layer {layer!r}")
        if geometry_path is None or not geometry_path.is_file():
            raise HTTPException(
                status_code=409,
                detail="no geometry layer is configured; start the service with --geometry",
            )
        schedule = read_csv(directory, "schedule.csv")
        if year is None:
            year = int(schedule["period"].min()) if not schedule.empty else 0
        treated = schedule[schedule["period"] == year]
        treatments = treated.groupby("block_id")["treatment"].apply(
            lambda values: sorted(set(values))
        )
        features = _geometry_features(geometry_path)
        selected = []
        for feature in features:
            block = feature.get("properties", {}).get("block_id")
            if block is None:
                continue
            row = treatments.get(int(block))
            if row is None:
                continue
            feature["properties"]["treatments"] = list(row)
            selected.append(feature)
        return {"type": "FeatureCollection", "features": selected, "year": year, "layer": layer}

    @app.get("/api/targets", response_class=PlainTextResponse)
    def get_targets() -> str:
        """Return the targets YAML as written."""
        if targets_path is None:
            raise HTTPException(status_code=404, detail="the service was started without --targets")
        if not targets_path.is_file():
            raise HTTPException(status_code=404, detail=f"no targets file at {targets_path.name}")
        return targets_path.read_text(encoding="utf-8")

    @app.put("/api/targets")
    def put_targets(body: str = Body(..., media_type="text/yaml")) -> dict[str, Any]:
        """Validate and replace the targets YAML with the optimizer's own loader."""
        if targets_path is None:
            raise HTTPException(status_code=404, detail="the service was started without --targets")
        document = yaml.safe_load(body)
        if not isinstance(document, dict) or not document.get("targets"):
            raise HTTPException(
                status_code=422,
                detail="the targets document needs a non-empty 'targets' list",
            )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", dir=targets_path.parent, delete=False, encoding="utf-8"
        ) as handle:
            handle.write(body)
            candidate = Path(handle.name)
        try:
            parsed = load_targets(candidate)
        except Exception as error:  # the loader's message is the refusal the CLI would give
            candidate.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(error)) from error
        shutil.move(str(candidate), targets_path)
        return {"targets": len(parsed)}

    return app
