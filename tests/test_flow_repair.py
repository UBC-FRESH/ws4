"""Tests for the bounded flow-directed repair pass."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.flow_repair import flow_penalty_total, repair_flow_gap
from ws4.opt.objective import Target, flow_penalty

_ESTATE = Path(__file__).resolve().parents[1] / "examples" / "estate"


def _estate_optimizer(tmp_path: Path) -> Optimizer:
    """Compile the sample estate and return an optimizer for it."""
    dataset = build_canonical_dataset(
        _ESTATE / "recipe.xml", _ESTATE / "fragments.csv", tmp_path / "compiled"
    )
    return Optimizer.from_dataset(dataset, OptimizeConfig(years=100, iterations=1, seed=1))


def _targets() -> tuple[Target, Target]:
    """Return a product floor and an even-flow band referenced to period 1."""
    level = Target("product.Harvested.CC", period=1, period_width=10, minimum=1000.0)
    flow = Target(
        "product.Harvested.CC",
        period=1,
        period_width=10,
        flow="even",
        flow_start_period=1,
        flow_end_period=10,
        flow_reference_period=1,
        minimum=-5.0,
        maximum=5.0,
        min_weight=10_000.0,
        max_weight=10_000.0,
    )
    return level, flow


def _random_schedule(optimizer: Optimizer) -> dict[int, tuple[tuple[str, int], ...]]:
    """Return a deterministic, uneven schedule so the flow target has a gap."""
    rng = random.Random(3)
    return {block: rng.choice(chains) for block, chains in optimizer.candidates().items() if chains}


def test_flow_repair_is_exact_and_reduces_the_flow_gap(tmp_path: Path) -> None:
    """The repair lowers both the objective and the flow penalty, exactly."""
    optimizer = _estate_optimizer(tmp_path)
    level, flow = _targets()
    targets = [level, flow]
    candidates = optimizer.candidates()
    schedule = _random_schedule(optimizer)
    evaluator = optimizer.delta_evaluator(targets)
    assert evaluator is not None
    evaluator.reset(schedule)
    before_objective = evaluator.objective
    before_flow = flow_penalty_total(targets, evaluator.totals, 100)

    result = repair_flow_gap(evaluator, candidates, max_trials=200, chains_per_block=4)

    # a move was available and every accepted move lowered both prices
    assert result.moves > 0
    assert result.objective < result.objective_before
    assert result.flow_penalty_after < result.flow_penalty_before
    # the example's uneven schedule has a positive high period and a deep low period; both
    # ends of the reported gap move toward zero here
    assert result.flow_after[flow.account][0] > result.flow_before[flow.account][0]
    assert result.flow_after[flow.account][1] < result.flow_before[flow.account][1]

    # the repaired state is exact against a fresh incremental evaluation and the optimizer's
    # whole-schedule evaluator
    fresh = optimizer.delta_evaluator(targets)
    assert fresh is not None
    fresh.reset(result.schedule)
    assert fresh.objective == pytest.approx(result.objective, abs=1e-6)
    assert optimizer._evaluate(result.schedule, targets) == pytest.approx(
        result.objective, abs=1e-6
    )
    assert result.objective_before == pytest.approx(before_objective)
    assert result.flow_penalty_before == pytest.approx(before_flow)
    assert result.flow_penalty_after == pytest.approx(flow_penalty(fresh.totals, flow, 100))


def test_flow_repair_leaves_a_run_without_flow_targets_alone(tmp_path: Path) -> None:
    """With no even-flow target the pass prices nothing and returns the same schedule."""
    optimizer = _estate_optimizer(tmp_path)
    level, _ = _targets()
    candidates = optimizer.candidates()
    schedule = _random_schedule(optimizer)
    evaluator = optimizer.delta_evaluator([level])
    assert evaluator is not None
    evaluator.reset(schedule)
    before = evaluator.objective

    result = repair_flow_gap(evaluator, candidates, max_trials=100)

    assert result.trials == 0
    assert result.moves == 0
    assert result.objective == pytest.approx(before)
    assert result.schedule == schedule


def test_flow_repair_rejects_non_positive_bounds(tmp_path: Path) -> None:
    """A zero trial budget or chain budget is a configuration error."""
    optimizer = _estate_optimizer(tmp_path)
    level, flow = _targets()
    evaluator = optimizer.delta_evaluator([level, flow])
    assert evaluator is not None
    evaluator.reset({})
    with pytest.raises(ValueError, match="max_trials"):
        repair_flow_gap(evaluator, {}, max_trials=0)
    with pytest.raises(ValueError, match="chains_per_block"):
        repair_flow_gap(evaluator, {}, chains_per_block=0)


def test_flow_repair_config_rejects_negative_values() -> None:
    """The optimizer configuration refuses a negative trial count or an empty chain count."""
    with pytest.raises(ValueError, match="flow_repair_trials"):
        OptimizeConfig(flow_repair_trials=-1)
    with pytest.raises(ValueError, match="flow_repair_chains"):
        OptimizeConfig(flow_repair_chains=0)
