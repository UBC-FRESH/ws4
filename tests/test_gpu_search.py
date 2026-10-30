"""Tests for the bounded batched LNS prototype.

The search must reproduce the incremental objective exactly and leave the CPU evaluator
as the reference.  These tests run on the CPU torch path when no device is present; the
same tensor code is used on CUDA.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.gpu_effects import EffectTable
from ws4.opt.gpu_search import BatchedLnsSearch
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target

torch = pytest.importorskip("torch")

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _optimizer(tmp_path: Path) -> tuple[Optimizer, IncrementalObjective]:
    """Build the synthetic optimizer and a target set with a feature period target."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=4, iterations=1, seed=1))
    targets = [
        Target("product.Volume", period=1, period_width=1, minimum=1000.0),
        Target("feature.Volume", period=3, period_width=1, minimum=1000.0),
    ]
    return optimizer, IncrementalObjective(optimizer, targets)


def _initial(optimizer: Optimizer) -> dict[int, tuple[tuple[str, int], ...]]:
    """Return a deliberately suboptimal schedule for the fixture."""
    return dict.fromkeys(optimizer.candidates(), (("CC", 1),))


def test_search_prices_a_batch_exactly_and_returns_a_verified_objective(
    tmp_path: Path,
) -> None:
    """Every checked proposal matches the exact evaluator and the result re-evaluates."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    search = BatchedLnsSearch(optimizer, evaluator, table, proposals=8, temperature=100.0, seed=4)
    result = search.run(_initial(optimizer), rounds=3, check=3)
    verifier = IncrementalObjective(optimizer, evaluator.targets)
    verifier.reset(result.schedule)
    assert result.objective == pytest.approx(verifier.objective, abs=1e-6)
    assert result.objective <= result.initial_objective
    assert result.proposals == 24
    assert result.seconds >= 0.0


def test_search_improves_a_suboptimal_schedule(tmp_path: Path) -> None:
    """The best-of-batch acceptance finds a better chain than the starting one."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    search = BatchedLnsSearch(optimizer, evaluator, table, proposals=16, temperature=10.0, seed=5)
    result = search.run(_initial(optimizer), rounds=10)
    assert result.objective_gain > 0.0
    assert set(result.schedule) == set(optimizer.candidates())


def test_zero_rounds_returns_the_initial_schedule(tmp_path: Path) -> None:
    """A zero-round run is a pure exact re-evaluation."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    initial = _initial(optimizer)
    result = BatchedLnsSearch(optimizer, evaluator, table).run(initial, rounds=0)
    assert result.schedule == initial
    assert result.objective == result.initial_objective
    assert result.accepted == 0


def test_mixed_priorities_are_rejected(tmp_path: Path) -> None:
    """The prototype refuses a target mix it cannot price exactly."""
    optimizer, _evaluator = _optimizer(tmp_path)
    evaluator = IncrementalObjective(
        optimizer,
        [
            Target("product.Volume", period=1, period_width=1, minimum=1.0, priority=1),
            Target("feature.Volume", period=3, period_width=1, minimum=1.0, priority=2),
        ],
    )
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    with pytest.raises(NotImplementedError):
        BatchedLnsSearch(optimizer, evaluator, table)


def test_empty_schedule_is_rejected(tmp_path: Path) -> None:
    """LNS needs at least one assigned block to destroy."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    with pytest.raises(ValueError, match="assigned block"):
        BatchedLnsSearch(optimizer, evaluator, table).run({}, rounds=1)
