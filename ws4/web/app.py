"""The optional HTTP surface: a reader over a compiled dataset and its runs.

Every response is something the CLI already wrote — the dataset manifest, a run's summary, its
account values, its reports, its schedule — or the targets file the optimizer reads. The service
holds no model state and computes no value the CLI cannot reproduce. See
``notes/design/ws4-web-frontend.md``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
import yaml
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..opt.objective import load_targets
from .skins import load_skins

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
    allow_runs: bool = False,
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
    allow_runs : bool, optional
        When true, ``POST /api/runs`` may start a search with the configured dataset and targets.
        False (the default) keeps the service read-only apart from the targets file.

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
            )
        ]

    def read_csv(run: Path, name: str) -> pd.DataFrame:
        path = run / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"the run has no {name}")
        return pd.read_csv(path)

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

    def _run_command(out: Path, iterations: int, seed: int, years: int) -> list[str]:
        """Return the CLI command for a web-started search; only known options are passed."""
        if targets_path is None:
            raise HTTPException(status_code=422, detail="the service was started without --targets")
        return [
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
        ]

    @app.post("/api/runs")
    def start_run(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a search with the configured dataset and targets, when ``allow_runs`` is set."""
        if not allow_runs:
            raise HTTPException(
                status_code=403,
                detail="this service is read-only; start it with --allow-runs to run a search",
            )
        payload = body or {}
        iterations = int(payload.get("iterations", 500))
        seed = int(payload.get("seed", 1))
        years = int(payload.get("years", 50))
        if not 1 <= iterations <= 1_000_000 or not 1 <= years <= 1000:
            raise HTTPException(status_code=422, detail="iterations or years are out of range")
        run_id = f"web-{datetime.now():%Y%m%d-%H%M%S}-{seed}"
        out = runs_root / run_id
        if out.exists():
            raise HTTPException(status_code=409, detail=f"run {run_id!r} already exists")
        command = _run_command(out, iterations, seed, years)
        out.mkdir(parents=True)
        console = (out / "console.log").open("wb")
        processes[run_id] = subprocess.Popen(command, stdout=console, stderr=subprocess.STDOUT)
        return {"id": run_id, "iterations": iterations, "seed": seed, "years": years}

    def _last_step(directory: Path) -> dict[str, Any] | None:
        """Return the last telemetry step, reading only the file's tail."""
        path = directory / "telemetry.jsonl"
        if not path.is_file():
            return None
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 8192))
            tail = handle.read().decode("utf-8", errors="replace").splitlines()
        for line in reversed(tail):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") == "step":
                step: dict[str, Any] = record
                return step
        return None

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
        return {
            "id": run,
            "status": state,
            "running": state == "running",
            "pid": process.pid if process is not None else None,
            "last_step": _last_step(directory),
            "summary": summary,
        }

    @app.get("/api/runs/{run}/events")
    def run_events(run: str) -> StreamingResponse:
        """Stream the run's telemetry as SSE: progress per step, then done or error."""
        directory = run_dir(run)

        def stream() -> Iterator[str]:
            yield f"event: started\ndata: {json.dumps({'id': run})}\n\n"
            telemetry = directory / "telemetry.jsonl"
            seen = 0
            ticks = 0
            while True:
                ticks += 1
                if ticks % 20 == 0:
                    yield ": keepalive\n\n"
                if telemetry.is_file():
                    lines = telemetry.read_text(encoding="utf-8").splitlines()
                    for line in lines[seen:]:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if record.get("type") == "step":
                            yield f"event: progress\ndata: {json.dumps(record)}\n\n"
                        elif record.get("type") == "targets":
                            yield f"event: targets\ndata: {json.dumps(record)}\n\n"
                        elif record.get("type") == "schedule":
                            yield f"event: schedule\ndata: {json.dumps(record)}\n\n"
                    seen = len(lines)
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
            else:
                kind = "simulate"
                summary = {"status": "ok", "kind": kind}
            found.append({"id": directory.name, "kind": kind, "summary": summary})
        return {"dataset": dataset.name, "manifest": manifest, "runs": found}

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

    @app.get("/api/runs/{run}/periods")
    def periods(run: str) -> dict[str, Any]:
        """Return the schedule's periods, so the period control has the run's own range."""
        schedule = read_csv(run_dir(run), "schedule.csv")
        if schedule.empty:
            return {"min": 0, "max": 0, "values": []}
        values = sorted({int(value) for value in schedule["period"].astype("int64").tolist()})
        return {"min": values[0], "max": values[-1], "values": values}

    @app.get("/api/runs/{run}/map")
    def map_features(
        run: str,
        year: int | None = Query(default=None),
        layer: str = Query(default="treatments"),
    ) -> dict[str, Any]:
        """Return a GeoJSON FeatureCollection of every block, with the year's treatment flags.

        The layer is the base geometry; ``treated`` and ``treatments`` are properties on each
        feature, so the client can style and toggle without a second request. An unsupported
        layer name is refused by name.
        """
        directory = run_dir(run)
        if layer not in ("treatments", "blocks"):
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
        treatments_by_block = {
            int(str(block)): sorted({str(value) for value in group["treatment"]})
            for block, group in treated.groupby("block_id")
        }
        features = _geometry_features(geometry_path)
        for feature in features:
            properties = feature.get("properties", {})
            block = properties.get("block_id")
            if block is None:
                continue
            treatments = treatments_by_block.get(int(block), [])
            properties["treatments"] = treatments
            properties["treated"] = bool(treatments)
        return {"type": "FeatureCollection", "features": features, "year": year, "layer": layer}

    def _target_rows() -> list[dict[str, Any]]:
        """Return the targets as rows the browser can edit."""
        if targets_path is None or not targets_path.is_file():
            return []
        return [
            {
                "account": target.account,
                "year": target.year,
                "period_width": target.period_width,
                "minimum": target.minimum,
                "maximum": target.maximum,
                "min_weight": target.min_weight,
                "max_weight": target.max_weight,
            }
            for target in load_targets(targets_path)
        ]

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
    def put_targets(body: Annotated[str, Body(media_type="text/yaml")]) -> dict[str, Any]:
        """Validate and replace the targets YAML."""
        return {"targets": _write_targets(body)}

    @app.get("/api/targets.json")
    def get_targets_json() -> list[dict[str, Any]]:
        """Return the parsed targets, for an editor that does not parse YAML."""
        return _target_rows()

    @app.put("/api/targets.json")
    def put_targets_json(
        rows: Annotated[list[dict[str, Any]], Body()],
    ) -> dict[str, Any]:
        """Validate and replace the targets from a JSON list, writing the optimizer's YAML."""
        if not rows:
            raise HTTPException(status_code=422, detail="the targets list is empty")
        document = yaml.safe_dump({"targets": rows}, sort_keys=False)
        return {"targets": _write_targets(document)}

    return app
