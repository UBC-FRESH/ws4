"""Allowlisted command console for the WS4 web UI.

The console is deliberately not a shell. A caller selects one allowlisted WS4 command
and supplies typed parameters. The server resolves every path inside configured read-only
roots, builds an argv array, and launches a single process group without a shell.

Jobs run in ``runs/console-<timestamp>-<id>/``. Output is streamed to a bounded file,
cancelled with the whole process group, and recorded in ``runs/console-audit.jsonl``.
The feature is disabled unless a token is configured.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

TIME_LIMIT_RE = re.compile(r"^(\d{2}):([0-5]\d):([0-5]\d)$")
SEEDS_RE = re.compile(r"^\d+(,\d+)*$")
ACCOUNTS_RE = re.compile(r"^[A-Za-z0-9_.-]+(,[A-Za-z0-9_.-]+)*$")


class ConsoleCommand(StrEnum):
    """Commands the allowlisted console may launch."""

    simulate = "simulate"
    optimize = "optimize"
    state_watch = "state-watch"
    gpu_run = "gpu-run"
    report = "report"


class ConsoleJobRequest(BaseModel):
    """Typed parameters for one console job.

    Unknown fields are rejected by ``extra="forbid"``. The command-specific builder
    rejects fields that are valid for another command.

    Parameters
    ----------
    command : ConsoleCommand
        Allowlisted command to launch.
    schedule : str or None, optional
        Schedule CSV for ``simulate``.
    targets : str or None, optional
        Targets YAML for commands that read targets.
    initial_schedule : str or None, optional
        Initial schedule CSV.
    run : str or None, optional
        Existing run directory for ``report``.
    candidate_index : str or None, optional
        Compact candidate index for ``state-watch``.
    candidate_cache : str or None, optional
        Candidate cache for ``state-watch``.
    seed_state : str or None, optional
        Resident seed-state cache.
    seed_schedule : str or None, optional
        Seed schedule for ``gpu-run``.
    table : str or None, optional
        Effect table for ``gpu-run``.
    cache_dir : str or None, optional
        Simulator and candidate cache directory.
    years : int or None, optional
        Simulation horizon.
    iterations : int or None, optional
        Search iteration budget.
    period_width : int or None, optional
        Years per period for ``state-watch``.
    time_limit : str or None, optional
        Optimizer wall-clock limit in HH:MM:SS.
    seed : int or None, optional
        Optimizer random seed.
    engine : str or None, optional
        CPU optimizer engine.
    islands : int or None, optional
        Parallel optimizer islands.
    population : int or None, optional
        GPU population size.
    generations : int or None, optional
        GPU generation count.
    device : str or None, optional
        GPU device, ``cpu`` or ``cuda``.
    seeds : str or None, optional
        Comma-separated GPU seeds.
    accounts : str or None, optional
        Comma-separated watched accounts.
    lns_weight : float or None, optional
        LNS move probability.
    lns_destroy : float or None, optional
        LNS destroy fraction.
    lns_max_destroy : int or None, optional
        Maximum blocks destroyed by one LNS move.
    """

    model_config = ConfigDict(extra="forbid")

    command: ConsoleCommand
    schedule: str | None = Field(default=None, max_length=4096)
    targets: str | None = Field(default=None, max_length=4096)
    initial_schedule: str | None = Field(default=None, max_length=4096)
    run: str | None = Field(default=None, max_length=4096)
    candidate_index: str | None = Field(default=None, max_length=4096)
    candidate_cache: str | None = Field(default=None, max_length=4096)
    seed_state: str | None = Field(default=None, max_length=4096)
    seed_schedule: str | None = Field(default=None, max_length=4096)
    table: str | None = Field(default=None, max_length=4096)
    cache_dir: str | None = Field(default=None, max_length=4096)
    years: int | None = None
    iterations: int | None = None
    period_width: int | None = None
    time_limit: str | None = Field(default=None, max_length=8)
    seed: int | None = None
    engine: str | None = Field(default=None, max_length=32)
    islands: int | None = None
    population: int | None = None
    generations: int | None = None
    device: str | None = Field(default=None, max_length=16)
    seeds: str | None = Field(default=None, max_length=256)
    accounts: str | None = Field(default=None, max_length=4096)
    lns_weight: float | None = None
    lns_destroy: float | None = None
    lns_max_destroy: int | None = None


class ConsoleError(Exception):
    """Base error with an HTTP status for a rejected console operation."""

    status_code = 400


class ConsoleValidationError(ConsoleError):
    """A command or parameter failed validation before launch."""

    status_code = 422


class ConsoleBusyError(ConsoleError):
    """A console job is already active."""

    status_code = 409


class ConsoleRateLimitError(ConsoleError):
    """The console job rate limit was reached."""

    status_code = 429


class ConsoleAuthError(ConsoleError):
    """The bearer token was missing or wrong."""

    status_code = 401


@dataclass(frozen=True)
class ConsoleConfig:
    """Filesystem and quota configuration for one console instance.

    Parameters
    ----------
    dataset : Path
        Compiled dataset handed to every command.
    runs : Path
        Run root. Job directories and the audit file live here.
    roots : tuple of Path
        Read-only roots that input paths must stay inside.
    token : str
        Bearer token required by every console endpoint.
    workspace : str
        Human-readable workspace label recorded in the audit.
    targets : Path or None, optional
        Default targets file.
    initial_schedule : Path or None, optional
        Default initial schedule.
    timeout_seconds : float, optional
        Wall-clock limit for one job. Defaults to 180 seconds.
    max_output_bytes : int, optional
        Maximum captured stdout/stderr bytes. Defaults to one megabyte.
    max_jobs_per_minute : int, optional
        Sliding-window job start limit. Defaults to six.
    """

    dataset: Path
    runs: Path
    roots: tuple[Path, ...]
    token: str
    workspace: str
    targets: Path | None = None
    initial_schedule: Path | None = None
    timeout_seconds: float = 180.0
    max_output_bytes: int = 1_000_000
    max_jobs_per_minute: int = 6


COMMAND_FIELDS: dict[ConsoleCommand, frozenset[str]] = {
    ConsoleCommand.simulate: frozenset({"schedule", "years"}),
    ConsoleCommand.optimize: frozenset(
        {
            "targets",
            "initial_schedule",
            "years",
            "iterations",
            "time_limit",
            "seed",
            "engine",
            "islands",
            "lns_weight",
            "lns_destroy",
            "lns_max_destroy",
        }
    ),
    ConsoleCommand.state_watch: frozenset(
        {
            "targets",
            "candidate_index",
            "candidate_cache",
            "initial_schedule",
            "seed_state",
            "years",
            "iterations",
            "period_width",
            "accounts",
            "lns_weight",
            "lns_destroy",
            "lns_max_destroy",
        }
    ),
    ConsoleCommand.gpu_run: frozenset(
        {
            "targets",
            "seed_schedule",
            "table",
            "cache_dir",
            "seeds",
            "years",
            "population",
            "generations",
            "device",
        }
    ),
    ConsoleCommand.report: frozenset({"run", "targets"}),
}

COMMAND_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "simulate",
        "description": "Simulate a schedule over the mounted dataset.",
        "fields": (
            {"name": "schedule", "label": "Schedule CSV", "kind": "file", "required": True},
            {"name": "years", "label": "Years", "kind": "number", "default": 200},
        ),
    },
    {
        "name": "optimize",
        "description": "Run the CPU optimizer and write a run summary.",
        "fields": (
            {"name": "targets", "label": "Targets YAML", "kind": "file"},
            {"name": "initial_schedule", "label": "Initial schedule", "kind": "file"},
            {"name": "years", "label": "Years", "kind": "number", "default": 50},
            {"name": "iterations", "label": "Iterations", "kind": "number", "default": 500},
            {
                "name": "time_limit",
                "label": "Time limit (HH:MM:SS)",
                "kind": "text",
                "default": "00:03:00",
            },
            {"name": "seed", "label": "Seed", "kind": "number", "default": 42},
            {"name": "engine", "label": "Engine", "kind": "text", "default": "sa"},
            {"name": "islands", "label": "Islands", "kind": "number", "default": 0},
            {"name": "lns_weight", "label": "LNS weight", "kind": "number", "default": 0.0},
        ),
    },
    {
        "name": "state-watch",
        "description": "Run the resident-state search and write exactness telemetry.",
        "fields": (
            {"name": "targets", "label": "Targets YAML", "kind": "file"},
            {"name": "candidate_index", "label": "Candidate index", "kind": "file"},
            {"name": "candidate_cache", "label": "Candidate cache", "kind": "file"},
            {"name": "initial_schedule", "label": "Initial schedule", "kind": "file"},
            {"name": "seed_state", "label": "Seed state", "kind": "file"},
            {"name": "years", "label": "Years", "kind": "number", "default": 200},
            {"name": "iterations", "label": "Iterations", "kind": "number", "default": 100000},
            {"name": "period_width", "label": "Period width", "kind": "number", "default": 10},
            {"name": "accounts", "label": "Watched accounts", "kind": "text"},
            {"name": "lns_weight", "label": "LNS weight", "kind": "number", "default": 0.2},
            {"name": "lns_destroy", "label": "LNS destroy", "kind": "number", "default": 0.1},
            {
                "name": "lns_max_destroy",
                "label": "LNS max destroy",
                "kind": "number",
                "default": 64,
            },
        ),
    },
    {
        "name": "gpu-run",
        "description": "Run the exact GPU population search with an effect table.",
        "fields": (
            {"name": "targets", "label": "Targets YAML", "kind": "file"},
            {"name": "seed_schedule", "label": "Seed schedule", "kind": "file", "required": True},
            {"name": "table", "label": "Effect table", "kind": "file", "required": True},
            {"name": "cache_dir", "label": "Cache directory", "kind": "dir", "required": True},
            {"name": "seeds", "label": "Seeds", "kind": "text", "default": "7"},
            {"name": "years", "label": "Years", "kind": "number", "default": 200},
            {"name": "population", "label": "Population", "kind": "number", "default": 64},
            {"name": "generations", "label": "Generations", "kind": "number", "default": 1000},
            {"name": "device", "label": "Device", "kind": "text", "default": "cuda"},
        ),
    },
    {
        "name": "report",
        "description": "Write a report from an existing run directory.",
        "fields": (
            {"name": "run", "label": "Run directory", "kind": "dir", "required": True},
            {"name": "targets", "label": "Targets YAML", "kind": "file"},
        ),
    },
)


def _bounded_int(name: str, value: int | None, low: int, high: int) -> int | None:
    """Validate an optional integer range."""
    if value is None:
        return None
    if not low <= int(value) <= high:
        raise ConsoleValidationError(f"{name} must be between {low} and {high}")
    return int(value)


def _bounded_float(name: str, value: float | None, low: float, high: float) -> float | None:
    """Validate an optional float range."""
    if value is None:
        return None
    number = float(value)
    if not low <= number <= high:
        raise ConsoleValidationError(f"{name} must be between {low} and {high}")
    return number


def _resolve_input(
    value: str,
    *,
    label: str,
    roots: tuple[Path, ...],
    kind: str = "file",
) -> Path:
    """Resolve an input path, require the expected kind, and enforce read-only roots."""
    if not value.strip():
        raise ConsoleValidationError(f"{label} is required")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        base = roots[0] if roots else Path.cwd()
        candidate = base / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ConsoleValidationError(f"{label} does not exist: {value}") from error
    if kind == "file" and not resolved.is_file():
        raise ConsoleValidationError(f"{label} must be a file: {value}")
    if kind == "dir" and not resolved.is_dir():
        raise ConsoleValidationError(f"{label} must be a directory: {value}")
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise ConsoleValidationError(f"{label} is outside the configured input roots")
    return resolved


def _resolve_optional(
    value: str | None,
    *,
    label: str,
    roots: tuple[Path, ...],
    kind: str = "file",
) -> Path | None:
    """Resolve an optional input path."""
    if value is None or not value.strip():
        return None
    return _resolve_input(value, label=label, roots=roots, kind=kind)


def _time_limit(value: str | None) -> str:
    """Return a validated HH:MM:SS time limit."""
    text = value or "00:03:00"
    if TIME_LIMIT_RE.fullmatch(text) is None:
        raise ConsoleValidationError("time_limit must use HH:MM:SS with zero-padded fields")
    return text


def _append_common_int(argv: list[str], flag: str, value: int | None) -> None:
    """Append an optional integer flag."""
    if value is not None:
        argv.extend([flag, str(value)])


def _append_common_float(argv: list[str], flag: str, value: float | None) -> None:
    """Append an optional float flag."""
    if value is not None:
        argv.extend([flag, str(value)])


def build_console_argv(
    request: ConsoleJobRequest,
    job_dir: Path,
    config: ConsoleConfig,
) -> list[str]:
    """Build an allowlisted argv array for one validated request.

    Parameters
    ----------
    request : ConsoleJobRequest
        The typed request.
    job_dir : Path
        Server-owned scratch directory for outputs.
    config : ConsoleConfig
        Instance paths, roots, and defaults.

    Returns
    -------
    list of str
        The executable argv, without a shell.

    Raises
    ------
    ConsoleValidationError
        When a required field is missing, a field is not valid for this command, or a
        value is outside its range or allowed roots.
    """
    command = request.command
    supplied = set(request.model_fields_set) - {"command"}
    unexpected = supplied - COMMAND_FIELDS[command]
    if unexpected:
        raise ConsoleValidationError(
            f"{command.value} does not accept: {', '.join(sorted(unexpected))}"
        )

    roots = config.roots
    argv = [sys.executable, "-m", "ws4.cli", command.value]
    dataset = config.dataset
    if not dataset.is_dir():
        raise ConsoleValidationError("the mounted dataset directory is unavailable")

    def targets_path() -> Path:
        """Return the requested or configured targets file."""
        if request.targets is not None:
            return _resolve_input(request.targets, label="targets", roots=roots)
        if config.targets is not None and config.targets.is_file():
            return config.targets
        raise ConsoleValidationError("targets is required for this command")

    if command is ConsoleCommand.simulate:
        schedule = _resolve_input(request.schedule or "", label="schedule", roots=roots)
        argv.extend(["--dataset", str(dataset), "--schedule", str(schedule), "--out", str(job_dir)])
        _append_common_int(argv, "--years", _bounded_int("years", request.years, 1, 1000))
    elif command is ConsoleCommand.optimize:
        targets = targets_path()
        argv.extend(["--dataset", str(dataset), "--targets", str(targets), "--out", str(job_dir)])
        initial = _resolve_optional(request.initial_schedule, label="initial schedule", roots=roots)
        if initial is not None:
            argv.extend(["--initial-schedule", str(initial)])
        argv.extend(["--time-limit", _time_limit(request.time_limit)])
        _append_common_int(argv, "--years", _bounded_int("years", request.years, 1, 1000))
        _append_common_int(
            argv, "--iterations", _bounded_int("iterations", request.iterations, 1, 1_000_000_000)
        )
        _append_common_int(argv, "--seed", _bounded_int("seed", request.seed, 0, 2_147_483_647))
        _append_common_int(argv, "--islands", _bounded_int("islands", request.islands, 0, 64))
        if request.engine is not None:
            engine = request.engine.strip()
            if engine not in {"sa", "tabu", "ils", "threshold"}:
                raise ConsoleValidationError("engine must be sa, tabu, ils, or threshold")
            argv.extend(["--engine", engine])
        _append_common_float(
            argv, "--lns-weight", _bounded_float("lns_weight", request.lns_weight, 0.0, 1.0)
        )
        _append_common_float(
            argv, "--lns-destroy", _bounded_float("lns_destroy", request.lns_destroy, 0.0, 1.0)
        )
        _append_common_int(
            argv,
            "--lns-max-destroy",
            _bounded_int("lns_max_destroy", request.lns_max_destroy, 1, 1_000_000),
        )
    elif command is ConsoleCommand.state_watch:
        targets = targets_path()
        argv.extend(["--dataset", str(dataset), "--targets", str(targets), "--plain"])
        candidate_index = _resolve_optional(
            request.candidate_index, label="candidate index", roots=roots
        )
        candidate_cache = _resolve_optional(
            request.candidate_cache, label="candidate cache", roots=roots
        )
        if (candidate_index is None) == (candidate_cache is None):
            raise ConsoleValidationError(
                "state-watch needs exactly one of candidate_index or candidate_cache"
            )
        if candidate_index is not None:
            argv.extend(["--candidate-index", str(candidate_index)])
        else:
            assert candidate_cache is not None
            argv.extend(["--candidate-cache", str(candidate_cache)])
        initial = _resolve_optional(request.initial_schedule, label="initial schedule", roots=roots)
        if initial is not None:
            argv.extend(["--initial-schedule", str(initial)])
        seed_state = _resolve_optional(request.seed_state, label="seed state", roots=roots)
        if seed_state is not None:
            argv.extend(["--seed-state", str(seed_state)])
        argv.extend(["--schedule-out", str(job_dir / "schedule.csv")])
        argv.extend(["--summary-out", str(job_dir / "state-watch.json")])
        _append_common_int(argv, "--years", _bounded_int("years", request.years, 1, 1000))
        _append_common_int(
            argv, "--iterations", _bounded_int("iterations", request.iterations, 1, 1_000_000_000)
        )
        _append_common_int(
            argv, "--period-width", _bounded_int("period_width", request.period_width, 1, 100)
        )
        if request.accounts is not None:
            accounts = request.accounts.replace(" ", "")
            if accounts and ACCOUNTS_RE.fullmatch(accounts) is None:
                raise ConsoleValidationError("accounts contains invalid characters")
            if accounts:
                argv.extend(["--accounts", accounts])
        _append_common_float(
            argv, "--lns-weight", _bounded_float("lns_weight", request.lns_weight, 0.0, 1.0)
        )
        _append_common_float(
            argv, "--lns-destroy", _bounded_float("lns_destroy", request.lns_destroy, 0.0, 1.0)
        )
        _append_common_int(
            argv,
            "--lns-max-destroy",
            _bounded_int("lns_max_destroy", request.lns_max_destroy, 1, 1_000_000),
        )
    elif command is ConsoleCommand.gpu_run:
        targets = targets_path()
        seed_schedule = _resolve_input(
            request.seed_schedule or "", label="seed schedule", roots=roots
        )
        table = _resolve_input(request.table or "", label="effect table", roots=roots)
        cache_dir = _resolve_input(
            request.cache_dir or "", label="cache directory", roots=roots, kind="dir"
        )
        argv.extend(
            [
                "--dataset",
                str(dataset),
                "--targets",
                str(targets),
                "--seed-schedule",
                str(seed_schedule),
                "--table",
                str(table),
                "--cache-dir",
                str(cache_dir),
                "--out-dir",
                str(job_dir),
                "--json-out",
                str(job_dir / "gpu-run.json"),
            ]
        )
        seeds = (request.seeds or "7").strip()
        if SEEDS_RE.fullmatch(seeds) is None:
            raise ConsoleValidationError("seeds must be a comma-separated list of integers")
        argv.extend(["--seeds", seeds])
        _append_common_int(argv, "--years", _bounded_int("years", request.years, 1, 1000))
        _append_common_int(
            argv, "--population", _bounded_int("population", request.population, 1, 1024)
        )
        _append_common_int(
            argv,
            "--generations",
            _bounded_int("generations", request.generations, 0, 1_000_000),
        )
        device = (request.device or "cuda").strip()
        if device not in {"cpu", "cuda"}:
            raise ConsoleValidationError("device must be cpu or cuda")
        argv.extend(["--device", device])
    elif command is ConsoleCommand.report:
        run = _resolve_input(request.run or "", label="run", roots=roots, kind="dir")
        argv.extend(["--run", str(run), "--out", str(job_dir)])
        report_targets = _resolve_optional(request.targets, label="targets", roots=roots)
        if report_targets is not None:
            argv.extend(["--targets", str(report_targets)])
    else:  # pragma: no cover - the enum makes this unreachable
        raise ConsoleValidationError(f"unknown command: {command}")
    return argv


@dataclass
class ConsoleJob:
    """One console job and its mutable execution state.

    Parameters
    ----------
    id : str
        Short job identifier.
    command : str
        Allowlisted command name.
    argv : list of str
        Server-built command line.
    directory : Path
        Job scratch directory.
    workspace : str
        Workspace label for the audit record.
    dataset_fingerprint : str
        Short dataset fingerprint.
    status : str, optional
        ``queued``, ``running``, ``completed``, ``failed``, or ``cancelled``.
    started : float, optional
        Wall-clock start timestamp.
    finished : float or None, optional
        Wall-clock finish timestamp.
    exit_code : int or None, optional
        Child exit status.
    output_bytes : int, optional
        Captured output bytes.
    truncated : bool, optional
        Whether the output cap was hit.
    timed_out : bool, optional
        Whether the wall clock cap was hit.
    cancelled : bool, optional
        Whether the job was cancelled.
    error : str or None, optional
        Final error message.
    process : subprocess.Popen or None, optional
        Running child process.
    pump_thread : threading.Thread or None, optional
        Output pump thread.
    """

    id: str
    command: str
    argv: list[str]
    directory: Path
    workspace: str
    dataset_fingerprint: str
    status: str = "queued"
    started: float = field(default_factory=time.time)
    finished: float | None = None
    exit_code: int | None = None
    output_bytes: int = 0
    truncated: bool = False
    timed_out: bool = False
    cancelled: bool = False
    error: str | None = None
    process: subprocess.Popen[bytes] | None = None
    pump_thread: threading.Thread | None = None

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe job snapshot.

        Returns
        -------
        dict
            Job metadata, status, and artifact names.
        """
        return {
            "id": self.id,
            "command": self.command,
            "workspace": self.workspace,
            "status": self.status,
            "started": self.started,
            "finished": self.finished,
            "exit_code": self.exit_code,
            "output_bytes": self.output_bytes,
            "truncated": self.truncated,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "error": self.error,
            "directory": str(self.directory),
            "artifacts": [item["name"] for item in _artifact_entries(self.directory)],
        }


def _artifact_entries(directory: Path) -> list[dict[str, Any]]:
    """Return regular files under a job directory, relative and sorted."""
    entries: list[dict[str, Any]] = []
    if not directory.is_dir():
        return entries
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            entries.append({"name": str(path.relative_to(directory)), "bytes": path.stat().st_size})
    return entries


def _dataset_fingerprint(dataset: Path) -> str:
    """Return a short fingerprint of the dataset manifest and fragments file."""
    digest = hashlib.sha256()
    for name in ("manifest.json", "fragments.parquet"):
        path = dataset / name
        if path.is_file():
            stat = path.stat()
            digest.update(name.encode())
            digest.update(str(stat.st_size).encode())
            digest.update(str(stat.st_mtime_ns).encode())
    return digest.hexdigest()[:16]


class ConsoleManager:
    """Own the allowlisted jobs, quotas, cancellation, and audit trail.

    Parameters
    ----------
    config : ConsoleConfig
        Paths, token, and quota settings.
    command_builder : callable or None, optional
        Internal argv builder override for tests. Production always uses
        :func:`build_console_argv`.
    """

    def __init__(
        self,
        config: ConsoleConfig,
        *,
        command_builder: Callable[[ConsoleJobRequest, Path, ConsoleConfig], list[str]]
        | None = None,
    ) -> None:
        self.config = config
        self._builder = command_builder or build_console_argv
        self._jobs: dict[str, ConsoleJob] = {}
        self._active: str | None = None
        self._lock = threading.Lock()
        self._audit_lock = threading.Lock()
        self._recent: deque[float] = deque()
        self._fingerprint = _dataset_fingerprint(config.dataset)
        config.runs.mkdir(parents=True, exist_ok=True)

    def authorize(self, authorization: str | None) -> None:
        """Require the configured bearer token.

        Parameters
        ----------
        authorization : str or None
            Value of the request's Authorization header.

        Raises
        ------
        ConsoleAuthError
            When the header is missing or the token does not match.
        """
        if authorization is None or not authorization.lower().startswith("bearer "):
            raise ConsoleAuthError("console authentication required")
        if not secrets.compare_digest(authorization[7:].strip(), self.config.token):
            raise ConsoleAuthError("console token is invalid")

    def schema(self) -> dict[str, Any]:
        """Return the command and field catalog used by the browser.

        Returns
        -------
        dict
            Enabled state, workspace label, command specs, and quota limits.
        """
        commands: list[dict[str, Any]] = []
        for spec in COMMAND_SPECS:
            fields: list[dict[str, Any]] = []
            for field_spec in spec["fields"]:
                item = dict(field_spec)
                if "default" not in item:
                    item["default"] = self._default_for(str(item["name"]))
                fields.append(item)
            commands.append({**spec, "fields": fields})
        return {
            "enabled": True,
            "workspace": self.config.workspace,
            "commands": commands,
            "limits": {
                "timeout_seconds": self.config.timeout_seconds,
                "max_output_bytes": self.config.max_output_bytes,
                "max_jobs_per_minute": self.config.max_jobs_per_minute,
                "max_concurrent": 1,
            },
        }

    def _default_for(self, name: str) -> str | int | float | None:
        """Return a schema default for a field name."""
        if name == "targets":
            return str(self.config.targets) if self.config.targets is not None else ""
        if name == "initial_schedule":
            return (
                str(self.config.initial_schedule)
                if self.config.initial_schedule is not None
                else ""
            )
        if name == "run":
            recent = _newest_run(self.config.runs)
            return str(recent) if recent is not None else ""
        return ""

    def start(self, request: ConsoleJobRequest) -> dict[str, Any]:
        """Validate and launch one job, or raise a typed console error.

        Parameters
        ----------
        request : ConsoleJobRequest
            Typed command request.

        Returns
        -------
        dict
            The initial job snapshot.
        """
        now = time.monotonic()
        with self._lock:
            if self._active is not None:
                active = self._jobs.get(self._active)
                if active is not None and active.status in {"queued", "running"}:
                    raise ConsoleBusyError("another console job is already running")
                self._active = None
            while self._recent and now - self._recent[0] >= 60.0:
                self._recent.popleft()
            if len(self._recent) >= self.config.max_jobs_per_minute:
                raise ConsoleRateLimitError("console job rate limit reached")
            self._recent.append(now)

        job_id = uuid.uuid4().hex[:8]
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        directory = self.config.runs / f"console-{stamp}-{job_id}"
        directory.mkdir(parents=True, exist_ok=False)
        try:
            argv = self._builder(request, directory, self.config)
        except Exception:
            directory.rmdir()
            raise
        job = ConsoleJob(
            id=job_id,
            command=request.command.value,
            argv=argv,
            directory=directory,
            workspace=self.config.workspace,
            dataset_fingerprint=self._fingerprint,
        )
        request_data = request.model_dump(mode="json", exclude_none=True)
        (directory / "request.json").write_text(
            json.dumps(request_data, indent=2) + "\n", encoding="utf-8"
        )
        self._write_job(job)
        with self._lock:
            self._jobs[job.id] = job
            self._active = job.id
        try:
            process = subprocess.Popen(
                argv,
                cwd=directory,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=self._environment(),
            )
        except OSError as error:
            with self._lock:
                job.status = "failed"
                job.error = f"could not start the command: {error}"
                job.finished = time.time()
                self._active = None
            self._write_job(job)
            self._audit(job)
            raise ConsoleValidationError(job.error) from error
        job.process = process
        job.status = "running"
        job.started = time.time()
        self._write_job(job)
        job.pump_thread = threading.Thread(
            target=self._pump, args=(job,), name=f"console-pump-{job.id}", daemon=True
        )
        job.pump_thread.start()
        threading.Thread(
            target=self._monitor,
            args=(job,),
            name=f"console-monitor-{job.id}",
            daemon=True,
        ).start()
        return job.snapshot()

    def list_jobs(self) -> list[dict[str, Any]]:
        """Return recent job snapshots in start order.

        Returns
        -------
        list of dict
            Snapshots for jobs held by this manager.
        """
        with self._lock:
            return [job.snapshot() for job in self._jobs.values()]

    def snapshot(self, job_id: str) -> dict[str, Any]:
        """Return one job snapshot or raise a not-found error.

        Parameters
        ----------
        job_id : str
            Job identifier.

        Returns
        -------
        dict
            The current job snapshot.
        """
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ConsoleValidationError(f"console job {job_id!r} was not found")
        return job.snapshot()

    def cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel one running job and its process group.

        Parameters
        ----------
        job_id : str
            Job identifier.

        Returns
        -------
        dict
            The current job snapshot.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ConsoleValidationError(f"console job {job_id!r} was not found")
            job.cancelled = True
        self._terminate(job)
        return job.snapshot()

    def output(self, job_id: str, offset: int = 0) -> dict[str, Any]:
        """Return captured output from an offset, plus the next offset.

        Parameters
        ----------
        job_id : str
            Job identifier.
        offset : int, optional
            Byte offset to read from. Defaults to zero.

        Returns
        -------
        dict
            Output text, next offset, and job status.
        """
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ConsoleValidationError(f"console job {job_id!r} was not found")
        path = job.directory / "console.log"
        start = max(0, int(offset))
        chunk = b""
        if path.is_file():
            with path.open("rb") as stream:
                stream.seek(start)
                chunk = stream.read(65_536)
        return {
            "id": job_id,
            "offset": start,
            "next_offset": start + len(chunk),
            "text": chunk.decode("utf-8", errors="replace"),
            "status": job.status,
        }

    def artifacts(self, job_id: str) -> list[dict[str, Any]]:
        """Return the job's regular files.

        Parameters
        ----------
        job_id : str
            Job identifier.

        Returns
        -------
        list of dict
            Relative artifact names and sizes.
        """
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ConsoleValidationError(f"console job {job_id!r} was not found")
        return _artifact_entries(job.directory)

    def artifact_path(self, job_id: str, name: str) -> Path:
        """Resolve an artifact path inside the job scratch directory.

        Parameters
        ----------
        job_id : str
            Job identifier.
        name : str
            Relative artifact path.

        Returns
        -------
        Path
            A regular file inside the job directory.
        """
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ConsoleValidationError(f"console job {job_id!r} was not found")
        candidate = (job.directory / name).resolve()
        if job.directory not in candidate.parents or not candidate.is_file():
            raise ConsoleValidationError("artifact was not found")
        return candidate

    def _environment(self) -> dict[str, str]:
        """Return a bounded environment for the child process."""
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.config.runs / ".console-home"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "NO_COLOR": "1",
            "TERM": "dumb",
        }
        repo_root = Path(__file__).resolve().parents[2]
        python_path = str(repo_root)
        inherited = os.environ.get("PYTHONPATH")
        if inherited:
            python_path = f"{python_path}{os.pathsep}{inherited}"
        env["PYTHONPATH"] = python_path
        return env

    def _pump(self, job: ConsoleJob) -> None:
        """Copy child output into a bounded log file."""
        process = job.process
        if process is None or process.stdout is None:
            return
        stream = process.stdout
        path = job.directory / "console.log"
        with path.open("wb") as output:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                with self._lock:
                    remaining = max(0, self.config.max_output_bytes - job.output_bytes)
                    if remaining == 0:
                        job.truncated = True
                    else:
                        accepted = chunk[:remaining]
                        output.write(accepted)
                        job.output_bytes += len(accepted)
                        if len(accepted) < len(chunk):
                            job.truncated = True
                if job.truncated:
                    output.write(b"\n[console output limit reached; job terminated]\n")
                    self._terminate(job)
                    break
            output.flush()

    def _monitor(self, job: ConsoleJob) -> None:
        """Wait for the process, enforce the wall-clock limit, and finalize the job."""
        process = job.process
        if process is None:
            return
        deadline = time.monotonic() + self.config.timeout_seconds
        while process.poll() is None:
            if time.monotonic() >= deadline:
                job.timed_out = True
                self._terminate(job)
                break
            time.sleep(0.05)
        try:
            job.exit_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - kill should prevent this
            self._terminate(job)
            job.exit_code = process.wait()
        if job.pump_thread is not None:
            job.pump_thread.join(timeout=5)
        if job.cancelled:
            job.status = "cancelled"
        elif job.timed_out:
            job.status = "failed"
            job.error = "console job exceeded its wall-clock limit"
        elif job.truncated:
            job.status = "failed"
            job.error = "console job exceeded its output limit"
        elif job.exit_code == 0:
            job.status = "completed"
        else:
            job.status = "failed"
            job.error = f"command exited with status {job.exit_code}"
        job.finished = time.time()
        self._write_job(job)
        self._audit(job)
        with self._lock:
            if self._active == job.id:
                self._active = None

    def _terminate(self, job: ConsoleJob) -> None:
        """Terminate the job's process group."""
        process = job.process
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            with contextlib.suppress(ProcessLookupError):
                process.kill()

    def _write_job(self, job: ConsoleJob) -> None:
        """Write the current job metadata beside its outputs."""
        payload = {
            **job.snapshot(),
            "argv": job.argv,
            "dataset_fingerprint": job.dataset_fingerprint,
        }
        with contextlib.suppress(OSError):
            (job.directory / "job.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )

    def _audit(self, job: ConsoleJob) -> None:
        """Append one final audit record for a job."""
        record = {
            **job.snapshot(),
            "argv": job.argv,
            "dataset_fingerprint": job.dataset_fingerprint,
            "recorded_utc": datetime.now(UTC).isoformat(),
        }
        with (
            self._audit_lock,
            (self.config.runs / "console-audit.jsonl").open("a", encoding="utf-8") as stream,
        ):
            stream.write(json.dumps(record, sort_keys=True) + "\n")


def _newest_run(runs: Path) -> Path | None:
    """Return the most recently modified run directory, if any."""
    if not runs.is_dir():
        return None
    candidates = [
        path
        for path in runs.iterdir()
        if path.is_dir()
        and not path.name.startswith("console-")
        and ((path / "summary.json").is_file() or (path / "account_values.csv").is_file())
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def create_console_router(manager: ConsoleManager) -> APIRouter:
    """Create the authenticated console API router.

    Parameters
    ----------
    manager : ConsoleManager
        Job manager shared by the router endpoints.

    Returns
    -------
    APIRouter
        Router mounted under ``/api/console``.
    """
    router = APIRouter(prefix="/api/console", tags=["console"])

    def http_error(error: ConsoleError) -> HTTPException:
        """Convert a console error to an HTTP error."""
        headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
        return HTTPException(status_code=error.status_code, detail=str(error), headers=headers)

    def auth(request: Request) -> None:
        """Authorize one console request."""
        try:
            manager.authorize(request.headers.get("authorization"))
        except ConsoleError as error:
            raise http_error(error) from error

    @router.get("")
    def schema(request: Request) -> dict[str, Any]:
        """Return the authenticated command catalog."""
        auth(request)
        return manager.schema()

    @router.get("/jobs")
    def jobs(request: Request) -> list[dict[str, Any]]:
        """Return the manager's recent job snapshots."""
        auth(request)
        return manager.list_jobs()

    @router.post("/jobs")
    def start(request: Request, body: ConsoleJobRequest) -> dict[str, Any]:
        """Validate and start one allowlisted job."""
        auth(request)
        try:
            return manager.start(body)
        except ConsoleError as error:
            raise http_error(error) from error

    @router.get("/jobs/{job_id}")
    def status(request: Request, job_id: str) -> dict[str, Any]:
        """Return one job's state."""
        auth(request)
        try:
            return manager.snapshot(job_id)
        except ConsoleError as error:
            raise http_error(error) from error

    @router.get("/jobs/{job_id}/output")
    def output(request: Request, job_id: str, offset: int = 0) -> dict[str, Any]:
        """Return a chunk of captured output."""
        auth(request)
        try:
            return manager.output(job_id, offset=offset)
        except ConsoleError as error:
            raise http_error(error) from error

    @router.post("/jobs/{job_id}/cancel")
    def cancel(request: Request, job_id: str) -> dict[str, Any]:
        """Cancel a running job."""
        auth(request)
        try:
            return manager.cancel(job_id)
        except ConsoleError as error:
            raise http_error(error) from error

    @router.get("/jobs/{job_id}/artifacts")
    def artifacts(request: Request, job_id: str) -> list[dict[str, Any]]:
        """List the job's scratch files."""
        auth(request)
        try:
            return manager.artifacts(job_id)
        except ConsoleError as error:
            raise http_error(error) from error

    @router.get("/jobs/{job_id}/artifacts/{name:path}")
    def artifact(request: Request, job_id: str, name: str) -> FileResponse:
        """Download one artifact from the job scratch directory."""
        auth(request)
        try:
            return FileResponse(manager.artifact_path(job_id, name))
        except ConsoleError as error:
            raise http_error(error) from error

    return router
