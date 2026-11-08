"""Integration tests: run the command-line tools in subprocesses.

These tests exercise the same entry points that CI and the pre-commit hooks call, so a
broken import or a broken exit status shows up here even when the unit tests pass. The
first half drives the framework scripts in ``scripts/``; the second half drives the
``ws4`` command itself.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[1]
SCRIPTS: Path = ROOT / "scripts"


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one script from ``scripts/`` in a subprocess.

    Parameters
    ----------
    name : str
        File name of the script, such as ``check_workflow.py``.
    *args : str
        Arguments passed to the script.

    Returns
    -------
    subprocess.CompletedProcess of str
        The finished process, with its captured output.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validator_passes_on_this_repository() -> None:
    """The validator, run as CI runs it, passes on this repository."""
    result = run_script("check_workflow.py", str(ROOT))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 error(s)" in result.stdout


def test_validator_fails_a_defective_body_file(tmp_path: Path) -> None:
    """The validator, run on one body file, fails it when a form feed is present."""
    body = tmp_path / "body.md"
    body.write_text(f"Branch: eature{chr(12)}/p0\n", encoding="utf-8")
    result = run_script("check_workflow.py", "--files", str(body))
    assert result.returncode == 1
    assert "CONTROL-CHAR" in result.stdout


def test_validator_help_documents_the_files_option() -> None:
    """The help text names the file mode, so that people can find the check."""
    result = run_script("check_workflow.py", "--help")
    assert result.returncode == 0
    assert "--files" in result.stdout


def test_dashboard_help_documents_the_outputs() -> None:
    """The dashboard help text names its Markdown and JSON outputs."""
    result = run_script("dashboard.py", "--help")
    assert result.returncode == 0
    assert "--markdown" in result.stdout
    assert "--json" in result.stdout


def test_serve_help_documents_the_console() -> None:
    """The serve help names the opt-in console flag and token option."""
    result = run_ws4("serve", "--help", env={**os.environ, "COLUMNS": "160"})
    assert result.returncode == 0
    assert "--allow-console" in result.stdout
    assert "--console-token" in result.stdout


def test_dashboard_rejects_an_unknown_option() -> None:
    """The dashboard exits with status 2 on an option it does not know."""
    result = run_script("dashboard.py", "--bogus")
    assert result.returncode == 2


def run_ws4(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the ``ws4`` command line in a subprocess.

    Parameters
    ----------
    *args : str
        Arguments passed to the command.
    env : dict of str to str or None, optional
        Environment override; None inherits the test environment.

    Returns
    -------
    subprocess.CompletedProcess of str
        The finished process, with its captured output.
    """
    return subprocess.run(
        [sys.executable, "-m", "ws4.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def build_example(tmp_path: Path) -> Path:
    """Compile the synthetic example into a scratch directory.

    Parameters
    ----------
    tmp_path : Path
        The scratch directory.

    Returns
    -------
    Path
        The compiled dataset directory.
    """
    out = tmp_path / "compiled"
    result = run_ws4(
        "build",
        "--xml",
        "examples/synthetic/recipe.xml",
        "--fragments",
        "examples/synthetic/fragments.csv",
        "--out",
        str(out),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out


def test_optimize_runs_without_a_weights_file(tmp_path: Path) -> None:
    """The weights file is optional: the weights that apply are each target's own."""
    dataset = build_example(tmp_path)
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n- account: feature.Volume\n  period: 1\n  minimum: 700\n  period_width: 1\n"
    )
    out = tmp_path / "run"
    result = run_ws4(
        "optimize",
        "--dataset",
        str(dataset),
        "--targets",
        str(targets),
        "--years",
        "5",
        "--time-limit",
        "00:00:05",
        "--threads",
        "1",
        "--out",
        str(out),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out / "summary.json").is_file()
    assert (out / "schedule.csv").is_file()


def test_optimize_honours_the_iteration_budget(tmp_path: Path) -> None:
    """``--iterations`` sets the search budget, as it does for watch and calibrate."""
    dataset = build_example(tmp_path)
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n- account: feature.Volume\n  period: 1\n  minimum: 700\n  period_width: 1\n"
    )
    out = tmp_path / "run"
    result = run_ws4(
        "optimize",
        "--dataset",
        str(dataset),
        "--targets",
        str(targets),
        "--years",
        "5",
        "--iterations",
        "7",
        "--threads",
        "1",
        "--out",
        str(out),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["iterations"] == 7


def test_optimize_still_accepts_a_weights_file(tmp_path: Path) -> None:
    """A weights file passed for compatibility is accepted and ignored."""
    dataset = build_example(tmp_path)
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n- account: feature.Volume\n  period: 1\n  minimum: 700\n  period_width: 1\n"
    )
    weights = tmp_path / "weights.yaml"
    weights.write_text("weights: {}\n")
    out = tmp_path / "run"
    result = run_ws4(
        "optimize",
        "--dataset",
        str(dataset),
        "--targets",
        str(targets),
        "--weights",
        str(weights),
        "--years",
        "5",
        "--iterations",
        "5",
        "--threads",
        "1",
        "--out",
        str(out),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_serve_refuses_patch_accounts_without_topology(tmp_path: Path) -> None:
    """The service names the missing topology instead of starting doomed runs."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    runs = tmp_path / "runs"
    runs.mkdir()
    patches = tmp_path / "patches.yaml"
    patches.write_text("accounts: []\n", encoding="utf-8")
    result = run_ws4(
        "serve",
        "--dataset",
        str(dataset),
        "--runs",
        str(runs),
        "--patch-accounts",
        str(patches),
        "--port",
        "0",
    )
    assert result.returncode != 0
    combined = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
    assert "patch-accounts" in combined
    assert "topology" in combined


def test_disturbance_reports_a_fire_event() -> None:
    """The disturbance command reads a FEMIC consumer row and reports its year and type."""
    result = run_ws4("disturbance", "--events", "tests/fixtures/disturbance/fire.json")
    combined = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
    assert result.returncode == 0, combined
    assert "fire-2023-001" in combined
    assert "2023" in combined
    assert "fire" in combined


def test_disturbance_json_is_machine_readable() -> None:
    """The ``--json`` output is a stable summary object."""
    result = run_ws4(
        "disturbance",
        "--events",
        "tests/fixtures/disturbance/fire.json",
        "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["event_count"] == 1
    assert payload["event_types"] == ["fire"]
    assert payload["affected_blocks"] == [101]


def test_disturbance_filters_by_block() -> None:
    """A block filter selects only events that name the block."""
    result = run_ws4(
        "disturbance",
        "--events",
        "tests/fixtures/disturbance/nsr.json",
        "--block-id",
        "201",
        "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["event_count"] == 1
    assert payload["affected_blocks"] == [201]


def test_disturbance_rejects_a_malformed_event(tmp_path: Path) -> None:
    """A missing required field fails with a clear message."""
    target = tmp_path / "bad.json"
    target.write_text('{"event_id": "x", "year": 2020}', encoding="utf-8")
    result = run_ws4("disturbance", "--events", str(target))
    combined = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
    assert result.returncode != 0
    assert "missing disturbance fields" in combined


def test_price_paths_writes_the_comparison_and_provenance(tmp_path: Path) -> None:
    """The price-paths command compares the fixture and writes its three artifacts."""
    out = tmp_path / "prices"
    result = run_ws4(
        "price-paths",
        "--table",
        "tests/fixtures/prices/paths.json",
        "--out",
        str(out),
    )
    combined = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)

    assert result.returncode == 0, combined
    assert "policy_shock" in combined
    assert "not a forecast" in combined.casefold()
    for name in (
        "price_path_comparison.csv",
        "price_path_report.md",
        "price_path_provenance.json",
    ):
        assert (out / name).is_file()
    provenance = json.loads((out / "price_path_provenance.json").read_text(encoding="utf-8"))
    assert provenance["baseline_path"] == "base"
    assert provenance["row_count"] == 24


def test_price_paths_rejects_a_table_without_the_caveat(tmp_path: Path) -> None:
    """A table that does not say it is not a forecast fails cleanly."""
    payload = json.loads((ROOT / "tests/fixtures/prices/paths.json").read_text(encoding="utf-8"))
    payload.pop("not_a_forecast")
    table = tmp_path / "paths.json"
    table.write_text(json.dumps(payload), encoding="utf-8")

    result = run_ws4("price-paths", "--table", str(table), "--out", str(tmp_path / "out"))
    combined = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)

    assert result.returncode != 0
    assert "not_a_forecast" in combined


def test_gpu_run_help_documents_the_cache_and_table_inputs() -> None:
    """The GPU command exposes its persistent cache and effect-table inputs."""
    result = run_ws4("gpu-run", "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    combined = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
    assert "--cache-dir" in combined
    assert "--table" in combined
    assert "--seeds" in combined


def test_gpu_watch_help_documents_the_factorized_archive() -> None:
    """The watcher can read display cells from a persisted factorized archive."""
    result = run_ws4("gpu-watch", "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    combined = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
    assert "--factorized" in combined
    assert "--factorized-cache" in combined


def test_optimize_accepts_an_sdmd_store(tmp_path: Path) -> None:
    """``--sdmd-dir`` enables the per-AU guard and reports it in the summary."""
    dataset = build_example(tmp_path)
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n- account: feature.Volume\n  period: 1\n  minimum: 700\n  period_width: 1\n"
    )
    sdmd = tmp_path / "sdmd"
    sdmd.mkdir()
    (sdmd / "regimes.csv").write_text(
        "regime_id,au_id,name,entry_age,entry_type,residual_ba_m2_ha,"
        "removal_fraction,cycle_length,repeat_count,post_treatment_track,"
        "eligibility_expr,operability_expr,constraint_ids,review_status\n"
        "REG-1-CC,1,clearcut,40,clearcut,0,1,0,0,,,,,reviewed\n",
        encoding="utf-8",
    )
    (sdmd / "au_constraints.csv").write_text(
        "au_id,regime_id,allowed,min_entry_age,max_entry_age,max_entries,"
        "min_interval_years,max_removal_fraction,required_sdmd_zone,source,"
        "review_status\n"
        "1,REG-1-CC,True,0,120,1,0,1.0,,test,reviewed\n",
        encoding="utf-8",
    )
    out = tmp_path / "run"
    result = run_ws4(
        "optimize",
        "--dataset",
        str(dataset),
        "--targets",
        str(targets),
        "--sdmd-dir",
        str(sdmd),
        "--years",
        "5",
        "--iterations",
        "2",
        "--threads",
        "1",
        "--out",
        str(out),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((out / "summary.json").read_text())
    stats = summary["constraint_stats"]
    assert isinstance(stats, dict)
    assert stats["sdmd_guard"] is True
