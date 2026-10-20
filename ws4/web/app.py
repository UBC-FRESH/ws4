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
import subprocess
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
import yaml
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from ..opt.objective import load_targets, period_value
from .skins import load_skins

_REPORT_SUFFIXES = {".csv", ".html", ".png", ".json", ".txt"}


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


def create_app(
    *,
    dataset: Path,
    runs: Path,
    targets: Path | None = None,
    geometry: Path | None = None,
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

    Returns
    -------
    FastAPI
        The application, ready for ``uvicorn`` or a test client.
    """
    dataset = Path(dataset).resolve()
    runs_root = Path(runs).resolve()
    geometry_path = Path(geometry).resolve() if geometry is not None else None
    targets_path = Path(targets).resolve() if targets is not None else None
    topology_path = Path(topology).resolve() if topology is not None else None
    patch_accounts_path = Path(patch_accounts).resolve() if patch_accounts is not None else None
    spread_accounts_path = Path(spread_accounts).resolve() if spread_accounts is not None else None
    block_coordinates_path = (
        Path(block_coordinates).resolve() if block_coordinates is not None else None
    )
    route_config_path = Path(route_config).resolve() if route_config is not None else None
    roads_path = Path(roads).resolve() if roads is not None else None
    agent_working_directory = Path(agent_cwd).resolve() if agent_cwd is not None else Path.cwd()
    app = FastAPI(title="WS4", version="0.1.0")

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
            )
        ]

    def read_csv(run: Path, name: str) -> pd.DataFrame:
        path = run / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"the run has no {name}")
        return pd.read_csv(path)

    geometry_cache: list[dict[str, Any]] | None = None
    road_cache: list[dict[str, Any]] | None = None

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
        if not 1 <= iterations <= 1_000_000_000 or not 1 <= years <= 1000:
            raise HTTPException(status_code=422, detail="iterations or years are out of range")
        if not 1 <= islands <= 64:
            raise HTTPException(status_code=422, detail="islands must be between 1 and 64")
        if continuous and not time_limit:
            time_limit = "24:00:00"
        run_id = f"web-{datetime.now():%Y%m%d-%H%M%S}-{seed}"
        out = runs_root / run_id
        if out.exists():
            raise HTTPException(status_code=409, detail=f"run {run_id!r} already exists")
        out.mkdir(parents=True)
        (out / "control.json").write_text('{"action": "run"}\n', encoding="utf-8")
        command = _run_command(out, iterations, seed, years, time_limit, islands)
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
        index = {
            (int(item["year"]), str(item["account"])): float(item["value"])
            for item in record.get("values", [])
        }
        payload: dict[str, Any] = {
            "type": "targets",
            "iteration": record.get("iteration"),
            "values": [
                {
                    "account": target.account,
                    "year": target.year,
                    "value": period_value(index, target),
                }
                for target in load_targets(targets_path)
                if target.active
            ],
            # the optimizer's snapshot already holds every year of the tracked accounts; the
            # panel uses these as the live series behind the period-target value
            "series": record.get("values", []),
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
            best_island = ""
            best_objective = math.inf
            total = 0

            def apply(record: dict[str, Any]) -> None:
                """Fold one telemetry record into the stream's state."""
                nonlocal best_step, best_island, best_objective, total
                kind = record.get("type")
                island = str(record.get("island", "") or "")
                if kind == "step":
                    total += 1
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

            # replay what exists so a client that connects mid-run gets the current schedule
            for record in new_records():
                apply(record)
            emitted_island = best_island
            emitted_step: dict[str, Any] | None = None
            emitted_total = total
            if best_step is not None:
                payload = dict(best_step)
                payload["total"] = total
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
                    payload = dict(best_step)
                    payload["total"] = total
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

    @app.get("/api/roads")
    def roads_geojson() -> dict[str, Any]:
        """Return the configured source access-road lines for the map overlay."""
        if roads_path is None or not roads_path.is_file():
            raise HTTPException(
                status_code=404, detail="no source road layer is configured (--roads)"
            )
        return {"type": "FeatureCollection", "features": road_features()}

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
        """Return the run's periods from its schedule, patch membership or account values."""
        directory = run_dir(run)
        for name, column in (
            ("schedule.csv", "period"),
            ("patch_membership.csv", "year"),
            ("account_values.csv", "year"),
        ):
            if not (directory / name).is_file():
                continue
            frame = read_csv(directory, name)
            if frame.empty:
                continue
            values = sorted({int(value) for value in frame[column].astype("int64").tolist()})
            if values:
                return {"min": values[0], "max": values[-1], "values": values}
        return {"min": 0, "max": 0, "values": []}

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
            "compartments": False,
            "patch_classes": patch_classes,
            "patch_accounts": patch_accounts,
            "base_attributes": base_attributes,
            "roads_reason": (
                ""
                if roads_path is not None and roads_path.is_file()
                else "no source road layer is configured (--roads)"
            ),
            "compartments_reason": "no compartment membership artifact is written by a run",
        }

    @app.get("/api/runs/{run}/map")
    def map_features(
        run: str,
        year: int | None = Query(default=None),
        layer: str = Query(default="treatments"),
    ) -> dict[str, Any]:
        """Return a GeoJSON FeatureCollection of every block for one map layer.

        ``treatments`` is the selected period, ``cumulative`` marks current and earlier
        treatments, ``patches`` colors the selected year's patch membership, and ``blocks`` is
        the bare geometry. The layer is the base geometry; the properties carry the flags the
        client needs, so a layer change is one request and no second join.
        """
        directory = run_dir(run)
        if layer not in ("treatments", "cumulative", "patches", "blocks"):
            raise HTTPException(status_code=422, detail=f"unknown layer {layer!r}")
        if geometry_path is None or not geometry_path.is_file():
            raise HTTPException(
                status_code=409,
                detail="no geometry layer is configured; start the service with --geometry",
            )
        treatments_by_block: dict[int, list[str]] = {}
        current: set[int] = set()
        patches_by_block: dict[int, dict[str, Any]] = {}
        patch_classes: list[str] = []
        if layer == "patches":
            if not (directory / "patch_membership.csv").is_file():
                raise HTTPException(status_code=404, detail="the run has no patch_membership.csv")
            frame = read_csv(directory, "patch_membership.csv")
            if year is None:
                year = int(frame["year"].min()) if not frame.empty else 0
            selected = frame[frame["year"] == year]
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
                year = int(schedule["period"].min()) if not schedule.empty else 0
            selected = schedule[
                schedule["period"] <= year if layer == "cumulative" else schedule["period"] == year
            ]
            for block_id, group in selected.groupby("block_id"):
                treatments_by_block[int(float(str(block_id)))] = sorted(
                    {str(value) for value in group["treatment"]}
                )
            if layer == "cumulative":
                current = {
                    int(value)
                    for value in schedule[schedule["period"] == year]["block_id"].astype("int64")
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
            if layer == "patches":
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
            features.append(
                {"type": "Feature", "geometry": base.get("geometry"), "properties": properties}
            )
        return {
            "type": "FeatureCollection",
            "features": features,
            "year": year,
            "layer": layer,
            "patch_classes": patch_classes,
        }

    def _realized_rows(directory: Path) -> list[dict[str, Any]]:
        """Return each target's realized period value, computed by the optimizer's own rule."""
        if targets_path is None or not targets_path.is_file():
            return []
        values = read_csv(directory, "account_values.csv")
        index: dict[tuple[int, str], float] = {}
        for year, account, value in zip(
            values["year"], values["account"], values["value"], strict=True
        ):
            key = (int(year), str(account))
            index[key] = index.get(key, 0.0) + float(value)
        rows: list[dict[str, Any]] = []
        for target in load_targets(targets_path):
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
                    "account": target.account,
                    "year": target.year,
                    "period_width": target.period_width,
                    "value": value,
                    "status": status,
                    "active": target.active,
                }
            )
        return rows

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
                "active": target.active,
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

    @app.put("/api/targets.json")
    @app.post("/api/targets.json")
    def put_targets_json(
        rows: Annotated[list[dict[str, Any]], Body()],
    ) -> dict[str, Any]:
        """Validate and replace the targets from a JSON list, writing the optimizer's YAML."""
        if not rows:
            raise HTTPException(status_code=422, detail="the targets list is empty")
        document = yaml.safe_dump({"targets": rows}, sort_keys=False)
        return {"targets": _write_targets(document)}

    return app
