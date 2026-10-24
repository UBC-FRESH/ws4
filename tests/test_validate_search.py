"""Tests for the multi-seed and multi-engine validation harness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from ws4.opt.engine import OptimizeConfig

import validate_search
from validate_search import _parse_csv, _stats, main, render_markdown, run_validation


class _FakeRunner:
    """A runner that returns a deterministic objective for an engine and seed."""

    def __init__(self, engine: str, seed: int) -> None:
        self.engine = engine
        self.seed = seed

    def run(self, out_dir: Path) -> dict[str, object]:
        out_dir.mkdir(parents=True, exist_ok=True)
        return {"incumbent_objective": float(self.seed), "bound": 0.0, "gap": float(self.seed)}


def _fake_factory(dataset: Path, config: OptimizeConfig) -> _FakeRunner:
    return _FakeRunner(config.metaheuristic, config.seed)


def test_parse_csv_rejects_empty_and_unknown_values() -> None:
    """The parser returns clean values and names an invalid one."""
    assert _parse_csv(" sa, tabu ") == ["sa", "tabu"]
    with pytest.raises(ValueError, match="at least one"):
        _parse_csv(" , ")
    with pytest.raises(ValueError, match="unknown"):
        _parse_csv("sa,nope", allowed=("sa", "tabu"))


def test_stats_reports_the_distribution() -> None:
    """The summary reports the best, mean, median, worst, and population stdev."""
    stats = _stats([3.0, 1.0, 2.0])
    assert stats == {
        "runs": 3,
        "best": 1.0,
        "mean": 2.0,
        "median": 2.0,
        "worst": 3.0,
        "stdev": 0.816497,
    }
    assert _stats([]) == {"runs": 0}


def test_run_validation_runs_each_engine_and_seed(tmp_path: Path) -> None:
    """Two engines and two seeds produce four records and one summary per engine."""
    report = run_validation(
        dataset=tmp_path / "dataset",
        targets=tmp_path / "targets.yaml",
        engines=("sa", "tabu"),
        seeds=(1, 2),
        iterations=3,
        years=1,
        workdir=tmp_path / "runs",
        runner_factory=_fake_factory,
        mip_bound=True,
    )
    records = report["records"]
    assert isinstance(records, list)
    assert len(records) == 4
    assert {record["engine"] for record in records} == {"sa", "tabu"}
    assert all("gap" in record for record in records)
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert summary["sa"]["runs"] == 2


def test_run_validation_rejects_an_unknown_engine(tmp_path: Path) -> None:
    """An unknown engine is named before any run starts."""
    with pytest.raises(ValueError, match="unknown"):
        run_validation(
            dataset=tmp_path / "dataset",
            targets=tmp_path / "targets.yaml",
            engines=("nope",),
            seeds=(1,),
            runner_factory=_fake_factory,
        )


def test_render_markdown_has_one_row_per_engine(tmp_path: Path) -> None:
    """The Markdown report names every engine and its distribution."""
    report = run_validation(
        dataset=tmp_path / "dataset",
        targets=tmp_path / "targets.yaml",
        engines=("sa", "tabu"),
        seeds=(1,),
        workdir=tmp_path / "runs",
        runner_factory=_fake_factory,
    )
    markdown = render_markdown(report)
    assert "| Engine | Runs |" in markdown
    assert "| sa |" in markdown
    assert "| tabu |" in markdown


def test_main_writes_the_json_and_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI writes both report files and prints the Markdown."""
    report = {
        "dataset": "d",
        "targets": "t",
        "iterations": 1,
        "years": 1,
        "mip_bound": False,
        "summary": {"sa": {"runs": 1, "best": 0.0}},
        "markdown": "# Validation sweep",
    }
    monkeypatch.setattr(validate_search, "run_validation", lambda **kwargs: report)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_search.py",
            "--dataset",
            str(tmp_path / "dataset"),
            "--targets",
            str(tmp_path / "targets.yaml"),
            "--engines",
            "sa",
            "--seeds",
            "1",
            "--out",
            str(tmp_path / "out"),
        ],
    )
    assert main() == 0
    out = tmp_path / "out"
    assert out.joinpath("validation.md").is_file()
    document = json.loads(out.joinpath("validation.json").read_text(encoding="utf-8"))
    assert document["summary"]["sa"]["runs"] == 1
