"""Tests for the hard-feasibility constraint strategies."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.constraints import ConstraintGuard
from ws4.opt.engine import OptimizeConfig, Optimizer

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


class _FakeOptimizer:
    """A three-block topology and area table for direct guard tests."""

    def __init__(self, strategy: str) -> None:
        self.cfg = SimpleNamespace(
            constraint_strategy=strategy,
            allow_spatial_override=False,
            topology_path="topology.csv",
            max_opening_ha=4.0,
            min_green_up_years=None,
            min_core_area_ha=None,
            core_buffer_m=None,
        )

    def _block_area(self) -> dict[int, float]:
        return {1: 3.0, 2: 2.0, 3: 2.0}

    def _graph(self) -> list[tuple[int, int, float]]:
        return [(1, 2, 100.0), (2, 3, 100.0)]

    def _edges_by_block(self) -> dict[int, list[tuple[int, int, float]]]:
        return {
            1: [(1, 2, 100.0)],
            2: [(1, 2, 100.0), (2, 3, 100.0)],
            3: [(2, 3, 100.0)],
        }


def _chain() -> tuple[tuple[str, int], ...]:
    """Return a one-event chain."""
    return (("CC", 0),)


def test_guard_rejects_an_opening_violation() -> None:
    """Reject returns None and counts the proposal without changing the schedule."""
    guard = ConstraintGuard(_FakeOptimizer("reject"))  # type: ignore[arg-type]
    before = {1: _chain()}
    proposed = {1: _chain(), 2: _chain()}
    assert guard.consider(before, proposed, [2]) is None
    assert guard.stats["proposed"] == 1
    assert guard.stats["rejected"] == 1
    assert guard.stats["repaired"] == 0


def test_guard_repairs_by_dropping_one_addition() -> None:
    """A swap that breaks the opening cap keeps the feasible single-block remainder."""
    guard = ConstraintGuard(_FakeOptimizer("repair"))  # type: ignore[arg-type]
    before = {2: _chain(), 3: _chain()}
    proposed = {1: _chain(), 2: _chain()}
    repaired = guard.consider(before, proposed, [1, 3])
    assert repaired == {2: _chain()}
    assert guard.stats["repaired"] == 1
    assert guard.stats["rejected"] == 0


def test_guard_prepare_removes_violating_blocks() -> None:
    """An infeasible seed is made feasible and the removal is counted."""
    guard = ConstraintGuard(_FakeOptimizer("repair"))  # type: ignore[arg-type]
    prepared = guard.prepare({1: _chain(), 2: _chain(), 3: _chain()})
    assert prepared == {}
    assert guard.initial_removed == 3
    assert guard.initial_repairs == 1
    assert guard.feasible(prepared)


def test_unknown_constraint_strategy_fails_before_the_search() -> None:
    """The configuration rejects a strategy outside the three supported values."""
    with pytest.raises(ValueError, match="constraint_strategy"):
        OptimizeConfig(constraint_strategy="ignore")


def _run(tmp_path: Path, strategy: str) -> dict[str, Any]:
    """Compile the fixture, run one constrained search, and return the summary."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    topology = tmp_path / "topology.csv"
    topology.write_text("BLOCK1,BLOCK2,DISTANCE,LENGTH\n1,2,10,100\n", encoding="utf-8")
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    period: 1\n    maximum: 500\n",
        encoding="utf-8",
    )
    cfg = OptimizeConfig(
        years=1,
        iterations=40,
        seed=1,
        threads=1,
        targets_path=str(targets),
        topology_path=str(topology),
        max_opening_ha=4.0,
        constraint_strategy=strategy,
    )
    return Optimizer.from_dataset(dataset, cfg).run(tmp_path / "run")


def test_reject_run_writes_a_feasible_constraint_report(tmp_path: Path) -> None:
    """A reject run leaves zero spatial violations and reports its move counts."""
    summary = _run(tmp_path, "reject")
    assert summary["constraint_strategy"] == "reject"
    stats = summary["constraint_stats"]
    assert isinstance(stats, dict)
    assert stats["enabled"] is True
    assert stats["proposed"] > 0
    assert summary["constraint_feasible"] is True
    report = json.loads((tmp_path / "run" / "constraint_report.json").read_text())
    assert report["feasible"] is True
    assert report["violations"] == []


def test_repair_run_writes_a_feasible_constraint_report(tmp_path: Path) -> None:
    """A repair run also leaves zero spatial violations."""
    summary = _run(tmp_path, "repair")
    assert summary["constraint_strategy"] == "repair"
    assert summary["constraint_feasible"] is True
    report = json.loads((tmp_path / "run" / "constraint_report.json").read_text())
    assert report["stats"]["strategy"] == "repair"
    assert report["violations"] == []


def test_penalize_run_keeps_the_default_guard_disabled(tmp_path: Path) -> None:
    """Penalize does not intercept moves; its final feasibility is still reported."""
    summary = _run(tmp_path, "penalize")
    assert summary["constraint_strategy"] == "penalize"
    stats = summary["constraint_stats"]
    assert isinstance(stats, dict)
    assert stats["enabled"] is False
    assert stats["proposed"] == 0
    assert isinstance(summary["constraint_feasible"], bool)
