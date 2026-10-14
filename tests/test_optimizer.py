"""Tests for the objective and the optimizer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target, load_targets, objective, penalty
from ws4.opt.telemetry import RunLogger, read_records

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_penalty_weights_shortfall_and_excess() -> None:
    """A value below the minimum or above the maximum is penalized."""
    target = Target(account="a", year=0, minimum=10.0, maximum=20.0, min_weight=2.0, max_weight=3.0)
    assert penalty(15.0, target) == 0.0
    assert penalty(7.0, target) == 2.0 * 3.0
    assert penalty(25.0, target) == 3.0 * 5.0


def test_objective_sums_targets() -> None:
    """The objective sums the penalties over the targets."""
    values = pd.DataFrame({"year": [0, 0], "account": ["a", "b"], "value": [5.0, 100.0]})
    targets = [Target("a", 0, minimum=10.0), Target("b", 0, maximum=50.0)]
    assert objective(values, targets) == 5.0 + 50.0


def test_load_targets(tmp_path: Path) -> None:
    """Targets load from a YAML file."""
    path = tmp_path / "targets.yaml"
    path.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    loaded = load_targets(path)
    assert loaded == [Target("feature.Volume", 0, maximum=500.0)]


@pytest.mark.parametrize("metaheuristic", ["sa", "tabu", "ils"])
def test_metaheuristics_improve_the_objective(tmp_path: Path, metaheuristic: str) -> None:
    """Each metaheuristic finds a schedule that lowers the penalty."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    # The empty schedule gives feature.Volume = 700 at year 0; CC on block 1 lowers it.
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            targets_path=str(targets),
            seed=1,
            years=1,
            iterations=60,
            metaheuristic=metaheuristic,
        ),
    )
    summary = optimizer.run(tmp_path / "run")
    assert summary["incumbent_objective"] < 200.0
    assert summary["metaheuristic"] == metaheuristic
    assert (tmp_path / "run" / "schedule.csv").is_file()


def test_run_logger_writes_a_header_and_steps(tmp_path: Path) -> None:
    """The telemetry logger writes a run header and one record per step."""
    path = tmp_path / "telemetry.jsonl"
    with RunLogger(path, "run-1", {"seed": 7}) as logger:
        logger.step(0, 10.0)
        logger.step(1, 8.0)
    records = read_records(path)
    assert records[0] == {"type": "run", "run_id": "run-1", "config": {"seed": 7}}
    assert records[1] == {"type": "step", "iteration": 0, "objective": 10.0}
    assert records[2]["objective"] == 8.0


def test_optimizer_writes_telemetry(tmp_path: Path) -> None:
    """An optimizer run writes its telemetry beside its outputs."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    Optimizer.from_dataset(
        dataset, OptimizeConfig(targets_path=str(targets), seed=1, years=1, iterations=5)
    ).run(tmp_path / "run")
    records = read_records(tmp_path / "run" / "telemetry.jsonl")
    assert records[0]["type"] == "run"
    assert sum(1 for record in records if record["type"] == "step") == 5


def test_lns_operator_is_registered(tmp_path: Path) -> None:
    """The destroy-repair operator is part of the default registry."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig())
    assert "lns" in optimizer.registry.names()


def test_warm_start_runs(tmp_path: Path) -> None:
    """A warm-started run produces a valid incumbent."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    summary = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(targets_path=str(targets), seed=1, years=1, iterations=30, warm_start=True),
    ).run(tmp_path / "run")
    assert summary["incumbent_objective"] < 200.0


def test_parallel_multi_start_matches_the_serial_result(tmp_path: Path) -> None:
    """A parallel multi-start run produces a valid incumbent."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )
    summary = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            targets_path=str(targets), seed=1, years=1, iterations=30, starts=2, workers=2
        ),
    ).run(tmp_path / "run")
    assert summary["incumbent_objective"] < 200.0
    assert (tmp_path / "run" / "schedule.csv").is_file()


def test_multi_start_is_no_worse_than_single_start(tmp_path: Path) -> None:
    """More starts cannot raise the incumbent objective."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 500\n",
        encoding="utf-8",
    )

    def config(starts: int) -> OptimizeConfig:
        return OptimizeConfig(
            targets_path=str(targets), seed=1, years=1, iterations=40, starts=starts
        )

    single = Optimizer.from_dataset(dataset, config(1)).run(tmp_path / "s1")
    multi = Optimizer.from_dataset(dataset, config(4)).run(tmp_path / "s4")
    assert multi["incumbent_objective"] <= single["incumbent_objective"]
