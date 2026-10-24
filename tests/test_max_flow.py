"""Tests for the binary-search flow ceiling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.max_flow import flow_feasibility, high_bound, period_values, run_max_flow
from ws4.opt.objective import load_targets

import max_flow as max_flow_script

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_period_values_sum_products_and_read_levels() -> None:
    """A product account sums its period; a level account reads the period end."""
    frame = pd.DataFrame(
        [
            {"offset": 0, "account": "product.volume", "value": 10.0},
            {"offset": 1, "account": "product.volume", "value": 20.0},
            {"offset": 0, "account": "feature.old", "value": 5.0},
            {"offset": 1, "account": "feature.old", "value": 7.0},
        ]
    )
    assert period_values(frame, "product.volume", 2, 2) == {1: 30.0}
    assert period_values(frame, "feature.old", 2, 2) == {1: 7.0}


def test_period_values_reject_a_partial_period() -> None:
    """The horizon must divide into whole accounting periods."""
    with pytest.raises(ValueError, match="multiple"):
        period_values(pd.DataFrame(), "a", 5, 2)


def test_high_bound_is_positive_for_the_synthetic_estate(tmp_path: Path) -> None:
    """The additive envelope is a positive bound for a volume account."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=1))
    assert high_bound(optimizer, "feature.Volume", 1, 1) > 0.0


def test_max_flow_writes_a_probe_log_and_schedule(tmp_path: Path) -> None:
    """A real small search writes the report, probes, and a best schedule."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text("targets: []\n", encoding="utf-8")
    report = run_max_flow(
        dataset=dataset,
        targets=targets,
        account="feature.Volume",
        out_dir=tmp_path / "flow",
        years=1,
        period_width=1,
        iterations=10,
        probes=2,
        high=400.0,
    )
    assert report["ceiling"] >= 0.0
    assert len(report["probes"]) == 2
    assert (tmp_path / "flow" / "max_flow.json").is_file()
    assert (tmp_path / "flow" / "max_flow.md").is_file()
    assert (tmp_path / "flow" / "best-schedule.csv").is_file()
    assert (tmp_path / "flow" / "probe-config.json").is_file()
    assert "Advisory ceiling" in str(report["markdown"])


def test_max_flow_preserves_non_volume_targets(tmp_path: Path) -> None:
    """The probe target file keeps the other targets and adds one floor per period."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n"
        "  - account: feature.Old\n    period: 1\n    maximum: 10\n"
        "  - account: feature.Volume\n    period: 1\n    maximum: 500\n",
        encoding="utf-8",
    )
    report = run_max_flow(
        dataset=dataset,
        targets=targets,
        account="feature.Volume",
        out_dir=tmp_path / "flow",
        years=2,
        period_width=1,
        iterations=2,
        probes=1,
        high=100.0,
    )
    assert report["probes"]
    probe_targets = load_targets(tmp_path / "flow" / "probes" / "probe-000" / "targets.yaml")
    assert {target.account for target in probe_targets} == {"feature.Old", "feature.Volume"}
    assert sum(target.account == "feature.Volume" for target in probe_targets) == 2


def test_main_wires_the_arguments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI calls the search and reports a written result."""
    captured: dict[str, Any] = {}

    def fake(**kwargs: object) -> dict[str, Any]:
        captured.update(kwargs)
        return {"markdown": "# flow", "ceiling": 10.0, "feasible": True}

    monkeypatch.setattr(max_flow_script, "run_max_flow", fake)
    code = max_flow_script.main(
        [
            "--dataset",
            str(tmp_path / "dataset"),
            "--targets",
            str(tmp_path / "targets.yaml"),
            "--account",
            "product.volume",
            "--out",
            str(tmp_path / "flow"),
            "--high",
            "100",
            "--probes",
            "2",
        ]
    )
    assert code == 0
    assert captured["account"] == "product.volume"
    assert captured["high"] == 100.0
    assert captured["probes"] == 2


def test_zero_high_bound_writes_an_empty_schedule(tmp_path: Path) -> None:
    """A zero ceiling is a valid advisory result, not a crash."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text("targets: []\n", encoding="utf-8")
    report = run_max_flow(
        dataset=dataset,
        targets=targets,
        account="feature.Volume",
        out_dir=tmp_path / "flow",
        years=1,
        period_width=1,
        probes=1,
        high=0.0,
    )
    assert report["ceiling"] == 0.0
    assert report["probes"] == []
    assert report["feasible"] is False
    assert (tmp_path / "flow" / "best-schedule.csv").read_text(encoding="utf-8") == (
        "block_id,treatment,offset\n"
    )


def test_flow_feasibility_checks_ndy_and_even() -> None:
    """NDY allows growth and a bounded decline; even holds the reference band."""
    assert flow_feasibility({1: 10.0, 2: 11.0}, "ndy", 0.0)[0] is True
    assert flow_feasibility({1: 10.0, 2: 9.0}, "ndy", 0.0)[0] is False
    assert flow_feasibility({1: 10.0, 2: 9.9}, "ndy", 1.0)[0] is True
    assert flow_feasibility({1: 10.0, 2: 10.05}, "even", 1.0)[0] is True
    assert flow_feasibility({1: 10.0, 2: 11.0}, "even", 1.0)[0] is False


def test_max_flow_adds_the_requested_flow_target(tmp_path: Path) -> None:
    """An NDY probe writes the floors plus a flow target and reports both statuses."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text("targets: []\n", encoding="utf-8")
    report = run_max_flow(
        dataset=dataset,
        targets=targets,
        account="feature.Volume",
        out_dir=tmp_path / "flow",
        years=1,
        period_width=1,
        iterations=2,
        probes=1,
        high=100.0,
        flow="ndy",
    )
    assert report["flow"] == "ndy"
    probe_targets = load_targets(tmp_path / "flow" / "probes" / "probe-000" / "targets.yaml")
    assert any(target.flow == "ndy" for target in probe_targets)
    assert "floor_feasible" in report["probes"][0]
    assert "flow_feasible" in report["probes"][0]
