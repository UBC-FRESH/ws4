"""Tests for the scenario comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.opt.scenarios import compare_scenarios, parse_metric, parse_run_spec

import compare_scenarios as scenario_script


def _run(
    path: Path, *, objective: float, volume: float, cost: float, include_constraint: bool = True
) -> Path:
    """Write a minimal completed run."""
    path.mkdir(parents=True)
    (path / "summary.json").write_text(
        json.dumps(
            {
                "incumbent_objective": objective,
                "blocks_scheduled": 2,
                "iterations": 10,
                "seed": 1,
                "metaheuristic": "sa",
                "status": "ok",
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "account": "feature.Volume",
                "period": 1,
                "value": volume,
                "status": "met",
                "raw_penalty": 0.0,
                "penalty": 0.0,
                "scale": 500.0,
                "normalization": "auto",
                "priority": 2,
            },
            {
                "account": "feature.Old",
                "period": 1,
                "value": cost,
                "status": "met",
                "raw_penalty": 0.0,
                "penalty": 0.0,
                "scale": 1.0,
                "normalization": "none",
                "priority": 1,
            },
        ]
    ).to_csv(path / "report_targets.csv", index=False)
    pd.DataFrame(
        [
            {"offset": 0, "account": "feature.Volume", "value": volume},
            {"offset": 0, "account": "feature.Old", "value": cost},
        ]
    ).to_csv(path / "account_values.csv", index=False)
    pd.DataFrame([{"block_id": 1, "treatment": "CC", "offset": 0}]).to_csv(
        path / "schedule.csv", index=False
    )
    if include_constraint:
        (path / "constraint_report.json").write_text(
            json.dumps({"feasible": True, "violations": []}), encoding="utf-8"
        )
    return path


def test_parse_run_and_metric() -> None:
    """Run labels and metric directions parse with useful defaults."""
    assert parse_run_spec("base=runs/a") == ("base", Path("runs/a"))
    assert parse_run_spec("runs/a")[0] == "a"
    assert parse_metric("feature.Volume") == ("feature.Volume", "max")
    assert parse_metric("feature.Old:min") == ("feature.Old", "min")
    with pytest.raises(ValueError, match="min"):
        parse_metric("x:sideways")


def test_compare_writes_tables_and_a_front(tmp_path: Path) -> None:
    """Two trade-off runs are compared and both survive the requested front."""
    first = _run(tmp_path / "runs" / "a", objective=2.0, volume=10.0, cost=5.0)
    second = _run(tmp_path / "runs" / "b", objective=1.0, volume=20.0, cost=10.0)
    report = compare_scenarios(
        [("base", first), ("dense", second)],
        tmp_path / "compare",
        metrics={"feature.Volume": "max", "feature.Old": "min"},
    )
    assert [record["label"] for record in report["runs"]] == ["base", "dense"]
    assert set(report["front"]) == {"base", "dense"}
    assert (tmp_path / "compare" / "scenarios.json").is_file()
    assert (tmp_path / "compare" / "scenario_runs.csv").is_file()
    assert (tmp_path / "compare" / "scenario_targets.csv").is_file()
    assert (tmp_path / "compare" / "scenario_accounts.csv").is_file()
    targets = pd.read_csv(tmp_path / "compare" / "scenario_targets.csv")
    assert {"raw_penalty", "penalty", "scale", "normalization", "priority"} <= set(targets.columns)
    assert "Scenario comparison" in str(report["markdown"])


def test_compare_reports_missing_artefacts_without_failing(tmp_path: Path) -> None:
    """A run without a constraint report stays in the table as not reported."""
    first = _run(tmp_path / "runs" / "a", objective=2.0, volume=10.0, cost=5.0)
    second = _run(
        tmp_path / "runs" / "b",
        objective=1.0,
        volume=20.0,
        cost=10.0,
        include_constraint=False,
    )
    report = compare_scenarios([("a", first), ("b", second)], tmp_path / "compare")
    records = {record["label"]: record for record in report["runs"]}
    assert records["a"]["constraint_feasible"] is True
    assert records["b"]["constraint_feasible"] is None
    assert report["front"] == []


def test_duplicate_labels_are_rejected(tmp_path: Path) -> None:
    """The report needs distinct labels."""
    run = _run(tmp_path / "run", objective=1.0, volume=1.0, cost=1.0)
    with pytest.raises(ValueError, match="unique"):
        compare_scenarios([("same", run), ("same", run)], tmp_path / "compare")


def test_cli_writes_the_report(tmp_path: Path) -> None:
    """The command wires repeated run and metric arguments."""
    first = _run(tmp_path / "runs" / "a", objective=2.0, volume=10.0, cost=5.0)
    second = _run(tmp_path / "runs" / "b", objective=1.0, volume=20.0, cost=10.0)
    code = scenario_script.main(
        [
            "--run",
            f"base={first}",
            "--run",
            f"dense={second}",
            "--metric",
            "feature.Volume:max",
            "--out",
            str(tmp_path / "cli"),
        ]
    )
    assert code == 0
    assert (tmp_path / "cli" / "scenarios.md").is_file()
