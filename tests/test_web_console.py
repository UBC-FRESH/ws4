"""Contract and security tests for the allowlisted WS4 web console."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from ws4.web.app import create_app
from ws4.web.console import (
    ConsoleBusyError,
    ConsoleCommand,
    ConsoleConfig,
    ConsoleJobRequest,
    ConsoleManager,
    ConsoleRateLimitError,
    ConsoleValidationError,
    build_console_argv,
)

TOKEN = "test-console-token"


def _app(
    tmp_path: Path,
    *,
    enabled: bool = True,
    timeout: float = 15.0,
    output_bytes: int = 1_000_000,
    rate: int = 6,
) -> tuple[TestClient, Path, Path]:
    """Create a dataset, a reportable run, and a console-enabled client."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    runs = tmp_path / "runs"
    run = runs / "run1"
    run.mkdir(parents=True)
    (run / "account_values.csv").write_text(
        "offset,account,value\n0,feature.Volume,10.0\n1,feature.Volume,11.0\n",
        encoding="utf-8",
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    period: 1\n    minimum: 0\n",
        encoding="utf-8",
    )
    app = create_app(
        dataset=dataset,
        runs=runs,
        targets=targets,
        allow_console=enabled,
        console_token=TOKEN if enabled else None,
        console_roots=[tmp_path],
        console_timeout=timeout,
        console_output_bytes=output_bytes,
        console_rate_limit=rate,
        console_workspace="test",
    )
    return TestClient(app), run, targets


def _headers() -> dict[str, str]:
    """Return the valid bearer header."""
    return {"Authorization": f"Bearer {TOKEN}"}


def _wait(client: TestClient, job_id: str, *, timeout: float = 20.0) -> dict[str, Any]:
    """Poll an API job until it reaches a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/console/jobs/{job_id}", headers=_headers())
        assert response.status_code == 200, response.text
        snapshot = cast(dict[str, Any], response.json())
        if snapshot["status"] in {"completed", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish")


def _wait_manager(manager: ConsoleManager, job_id: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """Poll a manager job until it reaches a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = manager.snapshot(job_id)
        if snapshot["status"] in {"completed", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def _manager(
    tmp_path: Path,
    builder: Callable[[ConsoleJobRequest, Path, ConsoleConfig], list[str]],
    *,
    timeout: float = 10.0,
    output: int = 1_000_000,
    rate: int = 10,
) -> tuple[ConsoleManager, Path]:
    """Create a manager with an injected argv builder for quota tests."""
    dataset = tmp_path / "dataset"
    dataset.mkdir(exist_ok=True)
    (dataset / "manifest.json").write_text("{}", encoding="utf-8")
    runs = tmp_path / "runs"
    run = runs / "run1"
    run.mkdir(parents=True, exist_ok=True)
    (run / "account_values.csv").write_text(
        "offset,account,value\n0,feature.Volume,1.0\n", encoding="utf-8"
    )
    config = ConsoleConfig(
        dataset=dataset,
        runs=runs,
        roots=(tmp_path.resolve(),),
        token=TOKEN,
        workspace="test",
        timeout_seconds=timeout,
        max_output_bytes=output,
        max_jobs_per_minute=rate,
    )
    return ConsoleManager(config, command_builder=builder), run


def test_console_is_absent_when_disabled(tmp_path: Path) -> None:
    """A read-only service does not expose the console API or capability."""
    client, _run, _targets = _app(tmp_path, enabled=False)
    summary = client.get("/api/summary").json()
    assert summary["capabilities"]["console"] is False
    assert client.get("/api/console").status_code == 404


def test_console_requires_the_configured_bearer_token(tmp_path: Path) -> None:
    """The catalog and jobs reject missing or wrong credentials."""
    client, _run, _targets = _app(tmp_path)
    assert client.get("/api/console").status_code == 401
    assert client.get("/api/console", headers={"Authorization": "Bearer wrong"}).status_code == 401
    response = client.get("/api/console", headers=_headers())
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    names = {item["name"] for item in response.json()["commands"]}
    assert names == {"simulate", "optimize", "state-watch", "gpu-run", "report"}


def test_console_rejects_unknown_commands_fields_and_paths(tmp_path: Path) -> None:
    """Validation happens before a process is launched."""
    client, run, _targets = _app(tmp_path)
    cases = [
        {"command": "serve"},
        {"command": "simulate", "schedule": str(run / "account_values.csv"), "shell": "bash"},
        {"command": "simulate", "schedule": "../../etc/passwd"},
        {"command": "simulate", "schedule": "/tmp/schedule.csv; touch /tmp/pwned"},
        {"command": "report", "run": str(run), "out": "/tmp/elsewhere"},
        {"command": "report", "run": str(tmp_path / "missing-run")},
    ]
    for body in cases:
        response = client.post("/api/console/jobs", headers=_headers(), json=body)
        assert response.status_code == 422, (body, response.text)


def test_console_report_job_runs_in_scratch_and_writes_audit(tmp_path: Path) -> None:
    """An allowed report job completes, exposes artifacts, and leaves an audit line."""
    client, run, _targets = _app(tmp_path)
    response = client.post(
        "/api/console/jobs",
        headers=_headers(),
        json={"command": "report", "run": str(run)},
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["status"] in {"running", "completed"}
    finished = _wait(client, job["id"])
    assert finished["status"] == "completed", finished
    assert finished["exit_code"] == 0
    output = client.get(
        f"/api/console/jobs/{job['id']}/output",
        headers=_headers(),
    ).json()
    assert "Report written" in output["text"]
    artifacts = client.get(
        f"/api/console/jobs/{job['id']}/artifacts",
        headers=_headers(),
    ).json()
    names = {item["name"] for item in artifacts}
    assert any(name.endswith(".csv") for name in names)
    artifact = client.get(
        f"/api/console/jobs/{job['id']}/artifacts/{sorted(names)[0]}",
        headers=_headers(),
    )
    assert artifact.status_code == 200
    audit = (tmp_path / "runs" / "console-audit.jsonl").read_text(encoding="utf-8")
    record = json.loads(audit.splitlines()[-1])
    assert record["command"] == "report"
    assert record["dataset_fingerprint"]
    assert record["argv"][1:3] == ["-m", "ws4.cli"]
    assert record["exit_code"] == 0


def test_builders_cover_each_allowlisted_command(tmp_path: Path) -> None:
    """Each allowlisted family builds an argv with server-owned outputs."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text("{}", encoding="utf-8")
    runs = tmp_path / "runs"
    run = runs / "run1"
    run.mkdir(parents=True)
    (run / "account_values.csv").write_text(
        "offset,account,value\n0,feature.Volume,1\n", encoding="utf-8"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text("targets: []\n", encoding="utf-8")
    schedule = tmp_path / "schedule.csv"
    schedule.write_text("block_id,treatment,offset\n", encoding="utf-8")
    candidate = tmp_path / "candidates.npz"
    candidate.write_bytes(b"npz")
    seed_state = tmp_path / "seed.npz"
    seed_state.write_bytes(b"npz")
    table = tmp_path / "effects.pt"
    table.write_bytes(b"pt")
    cache = tmp_path / "cache"
    cache.mkdir()
    config = ConsoleConfig(
        dataset=dataset.resolve(),
        runs=runs.resolve(),
        roots=(tmp_path.resolve(),),
        token=TOKEN,
        workspace="test",
        targets=targets.resolve(),
    )
    job = tmp_path / "job"
    cases = [
        (ConsoleJobRequest(command=ConsoleCommand.simulate, schedule=str(schedule)), "--schedule"),
        (ConsoleJobRequest(command=ConsoleCommand.optimize, targets=str(targets)), "--targets"),
        (
            ConsoleJobRequest(
                command=ConsoleCommand.state_watch,
                targets=str(targets),
                candidate_index=str(candidate),
                seed_state=str(seed_state),
            ),
            "--candidate-index",
        ),
        (
            ConsoleJobRequest(
                command=ConsoleCommand.gpu_run,
                targets=str(targets),
                seed_schedule=str(schedule),
                table=str(table),
                cache_dir=str(cache),
            ),
            "--seed-schedule",
        ),
        (ConsoleJobRequest(command=ConsoleCommand.report, run=str(run)), "--run"),
    ]
    for request, flag in cases:
        argv = build_console_argv(request, job, config)
        assert argv[1:3] == ["-m", "ws4.cli"]
        assert flag in argv
        assert any(
            name in argv for name in ("--out", "--out-dir", "--schedule-out", "--summary-out")
        )
        assert any(part.startswith(str(job)) for part in argv)


def test_builder_rejects_a_path_outside_readonly_roots(tmp_path: Path) -> None:
    """The argv builder confines every input path."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    runs = tmp_path / "runs"
    runs.mkdir()
    config = ConsoleConfig(
        dataset=dataset.resolve(),
        runs=runs.resolve(),
        roots=(tmp_path.resolve(),),
        token=TOKEN,
        workspace="test",
    )
    request = ConsoleJobRequest(command=ConsoleCommand.simulate, schedule="../../etc/passwd")
    with pytest.raises(ConsoleValidationError, match="does not exist"):
        build_console_argv(request, tmp_path / "job", config)


def _sleep_builder(_request: ConsoleJobRequest, _job: Path, _config: ConsoleConfig) -> list[str]:
    """Return a process that outlives the test quota."""
    return [sys.executable, "-c", "import time; time.sleep(5)"]


def _print_builder(_request: ConsoleJobRequest, _job: Path, _config: ConsoleConfig) -> list[str]:
    """Return a process that floods stdout."""
    return [sys.executable, "-c", "print('x' * 10000)"]


def _ok_builder(_request: ConsoleJobRequest, _job: Path, _config: ConsoleConfig) -> list[str]:
    """Return a process that prints and exits."""
    return [sys.executable, "-c", "print('ok')"]


def test_manager_timeout_terminates_the_process_group(tmp_path: Path) -> None:
    """A job that exceeds its wall-clock limit is failed and marked timed out."""
    manager, run = _manager(tmp_path, _sleep_builder, timeout=0.4)
    job = manager.start(ConsoleJobRequest(command=ConsoleCommand.report, run=str(run)))
    finished = _wait_manager(manager, job["id"])
    assert finished["status"] == "failed"
    assert finished["timed_out"] is True
    assert finished["error"] == "console job exceeded its wall-clock limit"


def test_manager_cancel_terminates_the_process_group(tmp_path: Path) -> None:
    """Cancellation marks the job and kills its process group."""
    manager, run = _manager(tmp_path, _sleep_builder, timeout=10.0)
    job = manager.start(ConsoleJobRequest(command=ConsoleCommand.report, run=str(run)))
    manager.cancel(job["id"])
    finished = _wait_manager(manager, job["id"])
    assert finished["status"] == "cancelled"
    assert finished["cancelled"] is True


def test_manager_output_limit_fails_and_truncates(tmp_path: Path) -> None:
    """An output flood is terminated and marked failed."""
    manager, run = _manager(tmp_path, _print_builder, output=64)
    job = manager.start(ConsoleJobRequest(command=ConsoleCommand.report, run=str(run)))
    finished = _wait_manager(manager, job["id"])
    assert finished["status"] == "failed"
    assert finished["truncated"] is True
    assert int(finished["output_bytes"]) <= 64
    output = manager.output(job["id"])
    assert "output limit" in str(output["text"])


def test_manager_rejects_a_second_concurrent_job(tmp_path: Path) -> None:
    """The default concurrency limit is one active job."""
    manager, run = _manager(tmp_path, _sleep_builder, timeout=10.0)
    job = manager.start(ConsoleJobRequest(command=ConsoleCommand.report, run=str(run)))
    with pytest.raises(ConsoleBusyError):
        manager.start(ConsoleJobRequest(command=ConsoleCommand.report, run=str(run)))
    manager.cancel(job["id"])


def test_manager_rate_limit_rejects_a_sixth_job(tmp_path: Path) -> None:
    """The sliding-window rate limit is enforced after jobs finish."""
    manager, run = _manager(tmp_path, _ok_builder, rate=1)
    job = manager.start(ConsoleJobRequest(command=ConsoleCommand.report, run=str(run)))
    _wait_manager(manager, job["id"])
    with pytest.raises(ConsoleRateLimitError):
        manager.start(ConsoleJobRequest(command=ConsoleCommand.report, run=str(run)))
