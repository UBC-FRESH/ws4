"""Tests for the search tuner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ws4.opt.engine import OptimizeConfig
from ws4.opt.tune import candidates, run_tuning, validate_space


class _FakeRunner:
    """Rank temperature and cooling by their distance from a target."""

    def __init__(self, config: OptimizeConfig) -> None:
        self.config = config

    def run(self, out_dir: Path) -> dict[str, Any]:
        """Write a summary whose objective prefers temperature 500 and cooling 0.95."""
        out_dir.mkdir(parents=True, exist_ok=True)
        objective = abs(self.config.temperature - 500.0) + abs(self.config.cooling - 0.95) * 1000
        summary = {"incumbent_objective": objective, "status": "ok"}
        (out_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return summary


def test_validate_space_rejects_unknown_excluded_and_bad_values() -> None:
    """Configuration names and scalar types are checked before any run."""
    with pytest.raises(ValueError, match="unknown"):
        validate_space({"nope": [1]})
    with pytest.raises(ValueError, match="not tunable"):
        validate_space({"targets_path": ["x.yaml"]})
    with pytest.raises(ValueError, match="integer"):
        validate_space({"iterations": [1.5]})
    with pytest.raises(ValueError, match="unknown value"):
        validate_space({"metaheuristic": ["anneal"]})
    with pytest.raises(ValueError, match="empty"):
        validate_space({})


def test_candidates_grid_and_random_are_deterministic() -> None:
    """The grid is the product and the random sample is reproducible."""
    space = {"temperature": [100.0, 500.0], "cooling": [0.9, 0.99]}
    grid = candidates(space)
    assert len(grid) == 4
    assert grid[0] == {"temperature": 100.0, "cooling": 0.9}
    first = candidates(space, mode="random", budget=2, seed=7)
    second = candidates(space, mode="random", budget=2, seed=7)
    assert first == second
    assert len(first) == 2
    with pytest.raises(ValueError, match="over"):
        candidates(space, max_candidates=3)


def test_run_tuning_ranks_the_best_candidate(tmp_path: Path) -> None:
    """The winning candidate has the lowest best and median objective."""
    targets = tmp_path / "targets.yaml"
    targets.write_text("targets: []\n", encoding="utf-8")
    report = run_tuning(
        dataset=tmp_path / "dataset",
        targets=targets,
        out_dir=tmp_path / "tuning",
        space={"temperature": [100.0, 500.0, 1000.0], "cooling": [0.95]},
        seeds=(1, 2),
        iterations=2,
        years=2,
        runner_factory=lambda _dataset, config: _FakeRunner(config),
    )
    winner = report["winner"]
    assert isinstance(winner, dict)
    assert winner["parameters"] == {"temperature": 500.0, "cooling": 0.95}
    assert winner["best"] == 0.0
    assert (tmp_path / "tuning" / "tuning.json").is_file()
    assert (tmp_path / "tuning" / "tuning.md").is_file()
    assert (tmp_path / "tuning" / "best.json").is_file()


def test_run_tuning_records_failures(tmp_path: Path) -> None:
    """A failing candidate is named instead of aborting the sweep."""
    targets = tmp_path / "targets.yaml"
    targets.write_text("targets: []\n", encoding="utf-8")

    class _Broken:
        def __init__(self, config: OptimizeConfig) -> None:
            self.config = config

        def run(self, out_dir: Path) -> dict[str, Any]:
            raise RuntimeError("boom")

    report = run_tuning(
        dataset=tmp_path / "dataset",
        targets=targets,
        out_dir=tmp_path / "tuning",
        space={"temperature": [100.0]},
        seeds=(1,),
        runner_factory=lambda _dataset, config: _Broken(config),
    )
    assert report["winner"] is None
    assert report["failures"] == 1
    assert "boom" in str(report["markdown"])
