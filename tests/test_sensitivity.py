"""Tests for the advisory target sensitivity report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from sensitivity import _slack, main, render_markdown, run_sensitivity


def _write_run(tmp_path: Path) -> tuple[Path, Path]:
    """Write a run report and the target file it came from."""
    run = tmp_path / "run"
    run.mkdir()
    pd.DataFrame(
        [
            {
                "account": "a",
                "period": 1,
                "value": 7.0,
                "minimum": 10.0,
                "maximum": None,
                "penalty": 6.0,
                "status": "below",
            },
            {
                "account": "b",
                "period": 1,
                "value": 12.0,
                "minimum": None,
                "maximum": 10.0,
                "penalty": 6.0,
                "status": "above",
            },
            {
                "account": "c",
                "period": 1,
                "value": 10.0,
                "minimum": 5.0,
                "maximum": 15.0,
                "penalty": 0.0,
                "status": "met",
            },
            {
                "account": "d",
                "period": 1,
                "value": 5.0,
                "minimum": 5.0,
                "maximum": 15.0,
                "penalty": 0.0,
                "status": "met",
            },
        ]
    ).to_csv(run / "report_targets.csv", index=False)
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n"
        "  - account: a\n    period: 1\n    minimum: 10\n    min_weight: 2\n"
        "  - account: b\n    period: 1\n    maximum: 10\n    max_weight: 3\n"
        "  - account: c\n    period: 1\n    minimum: 5\n    maximum: 15\n"
        "  - account: d\n    period: 1\n    minimum: 5\n    maximum: 15\n",
        encoding="utf-8",
    )
    return run, targets


def test_slack_is_the_distance_to_the_nearest_bound() -> None:
    """Slack is zero outside the band and the nearest distance inside it."""
    assert _slack(10.0, 5.0, 15.0) == 5.0
    assert _slack(7.0, 5.0, 15.0) == 2.0
    assert _slack(20.0, 5.0, 15.0) == 0.0
    assert _slack(10.0, None, None) == 0.0


def test_sensitivity_reports_shortfall_excess_and_marginal(tmp_path: Path) -> None:
    """A missed bound carries its weight; an inside target has zero marginal."""
    run, targets = _write_run(tmp_path)
    report = run_sensitivity(run, targets)
    records = report["records"]
    assert isinstance(records, list)
    by_account = {record["account"]: record for record in records}
    assert by_account["a"]["shortfall"] == 3.0
    assert by_account["a"]["marginal_relaxation"] == 2.0
    assert by_account["b"]["excess"] == 2.0
    assert by_account["b"]["marginal_relaxation"] == 3.0
    assert by_account["c"]["slack"] == 5.0
    assert by_account["c"]["marginal_relaxation"] == 0.0
    assert by_account["d"]["binding"] is True
    assert report["binding_count"] == 1
    assert report["missed_count"] == 2


def test_sensitivity_markdown_names_every_target(tmp_path: Path) -> None:
    """The Markdown table has a row per target."""
    run, targets = _write_run(tmp_path)
    markdown = render_markdown(run_sensitivity(run, targets))
    assert "| Account | Period |" in markdown
    for account in ("a", "b", "c", "d"):
        assert f"| {account} |" in markdown


def test_sensitivity_main_writes_json_and_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI writes both files and prints the table."""
    run, targets = _write_run(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sensitivity.py",
            "--run",
            str(run),
            "--targets",
            str(targets),
            "--out",
            str(out),
        ],
    )
    assert main() == 0
    assert (out / "sensitivity.md").is_file()
    document = json.loads((out / "sensitivity.json").read_text(encoding="utf-8"))
    assert document["missed_count"] == 2
