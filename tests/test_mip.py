"""Tests for the mixed-integer bound."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.mip import bound_for
from ws4.opt.objective import Target, objective
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
_EMPTY = pd.DataFrame([], columns=["block_id", "treatment", "period"])


def _setup(tmp_path: Path) -> tuple[Path, list[Target]]:
    """Compile the synthetic fixture and return a target that CC improves."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    # The empty schedule gives 700; treating both blocks drops the value.
    return dataset, [Target("feature.Volume", 0, maximum=500.0)]


def test_mip_bound_is_no_worse_than_the_empty_schedule(tmp_path: Path) -> None:
    """The bound is at or below the empty-schedule penalty."""
    dataset, targets = _setup(tmp_path)
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=1)).candidates()
    result = bound_for(dataset, targets, candidates, 1)
    empty = objective(Simulator.from_dataset(dataset).simulate(_EMPTY, 1), targets)
    assert result.status == "optimal"
    assert result.objective <= empty


def test_mip_bound_is_achieved_by_its_schedule(tmp_path: Path) -> None:
    """The chosen schedule's real penalty equals the bound (a tight small problem)."""
    dataset, targets = _setup(tmp_path)
    candidates = Optimizer.from_dataset(dataset, OptimizeConfig(years=1)).candidates()
    result = bound_for(dataset, targets, candidates, 1)
    schedule = pd.DataFrame(
        [
            {"block_id": block, "treatment": treatment, "period": year}
            for block, (treatment, year) in result.schedule.items()
        ]
    )
    achieved = objective(Simulator.from_dataset(dataset).simulate(schedule, 1), targets)
    assert achieved == result.objective
    assert result.objective == 0.0  # both blocks can be treated
