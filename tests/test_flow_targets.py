"""Tests for the flow targets (even flow and non-declining yield)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target, flow_term, objective

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_an_even_flow_term_sums_the_distance_from_the_mean() -> None:
    """Even flow is the sum of |period - mean| over the periods."""
    index = {(0, "a"): 10.0, (1, "a"): 20.0, (2, "a"): 30.0}
    target = Target("a", 0, period_width=1, flow="even")
    assert flow_term(index, target, 3) == pytest.approx(20.0)  # mean 20, +-10 each side


def test_an_ndy_term_sums_the_declines() -> None:
    """Non-declining yield sums how much each period falls below the one before it."""
    rising = {(0, "a"): 10.0, (1, "a"): 20.0, (2, "a"): 30.0}
    falling = {(0, "a"): 30.0, (1, "a"): 20.0, (2, "a"): 10.0}
    target = Target("a", 0, period_width=1, flow="ndy")
    assert flow_term(rising, target, 3) == 0.0
    assert flow_term(falling, target, 3) == pytest.approx(20.0)


def test_a_flow_term_aggregates_by_period_width_and_window() -> None:
    """The period width groups the years and the window clips them."""
    index = {(year, "a"): float(year + 1) for year in range(10)}
    one_period = Target("a", 0, period_width=6, flow="even", flow_start=0, flow_end=6)
    assert flow_term(index, one_period, 10) == 0.0  # a single period is trivially even
    two_periods = Target("a", 0, period_width=3, flow="ndy", flow_start=0, flow_end=6)
    assert flow_term(index, two_periods, 10) == 0.0  # 6 then 15: rising, no decline
    declining = Target("a", 0, period_width=3, flow="ndy", flow_start=0, flow_end=6)
    falling = {(year, "a"): float(10 - year) for year in range(6)}
    assert flow_term(falling, declining, 10) == pytest.approx(9.0)  # 27 then 18


def test_a_flow_target_is_rejected_for_unknown_keys() -> None:
    """The flow type and window are validated."""
    with pytest.raises(ValueError, match="flow type"):
        Target("a", 0, flow="bogus")
    with pytest.raises(ValueError, match="flow_end"):
        Target("a", 0, flow="ndy", flow_start=10, flow_end=10)


def test_objective_prices_a_flow_target_from_a_frame() -> None:
    """The pure objective applies a flow target at zero with its weight."""
    values = pd.DataFrame(
        [
            {"year": 0, "account": "a", "value": 10.0},
            {"year": 1, "account": "a", "value": 30.0},
        ]
    )
    target = Target(
        "a",
        0,
        period_width=1,
        flow="even",
        minimum=0.0,
        maximum=0.0,
        min_weight=2.0,
        max_weight=2.0,
    )
    assert objective(values, [target]) == pytest.approx(2.0 * 20.0)  # mean 20, +-10 each side


def test_the_move_delta_matches_a_fresh_evaluation_for_a_flow_target(tmp_path: Path) -> None:
    """The move-based delta includes a flow term, so it equals a fresh evaluation."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=3, iterations=1, seed=1))
    target = Target("product.Volume", 0, period_width=1, flow="even")
    candidates = optimizer.candidates()
    schedule = {block: options[0] for block, options in candidates.items() if options}
    evaluator = IncrementalObjective(optimizer, [target], ())
    evaluator.reset(schedule)
    block = next(iter(schedule))
    reduced = dict(schedule)
    del reduced[block]
    fresh = IncrementalObjective(optimizer, [target], ())
    fresh.reset(reduced)
    assert evaluator.objective + evaluator.delta([block], reduced) == pytest.approx(fresh.objective)
