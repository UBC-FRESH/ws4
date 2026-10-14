"""Tests for the objective and the optimizer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target, load_targets, objective, penalty

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


def test_optimizer_improves_the_objective(tmp_path: Path) -> None:
    """The optimizer finds a schedule that lowers the penalty."""
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
        OptimizeConfig(targets_path=str(targets), seed=1, years=1, iterations=60),
    )
    summary = optimizer.run(tmp_path / "run")
    assert summary["incumbent_objective"] < 200.0
    assert (tmp_path / "run" / "schedule.csv").is_file()
