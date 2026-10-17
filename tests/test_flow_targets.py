"""Tests for the flow targets (even flow and non-declining yield)."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target, flow_penalty, flow_values, objective, objective_terms

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_even_flow_values_are_measured_against_the_reference_period() -> None:
    """Even flow is the percent difference from the reference period, the final one by default."""
    index = {(0, "a"): 10.0, (1, "a"): 20.0, (2, "a"): 30.0}
    target = Target("a", 0, period_width=1, flow="even")
    assert flow_values(index, target, 3) == pytest.approx([-200 / 3, -100 / 3])
    first = Target("a", 0, period_width=1, flow="even", flow_reference=0)
    assert flow_values(index, first, 3) == pytest.approx([100.0, 200.0])


def test_even_flow_values_are_infinite_while_the_reference_is_empty() -> None:
    """A zero reference balance leaves every other period undefined: the term is infinite."""
    index = {(0, "a"): 5.0, (1, "a"): 0.0}
    target = Target("a", 0, period_width=1, flow="even")
    assert flow_values(index, target, 2) == [math.inf]


def test_a_flow_band_prices_only_what_falls_outside_it() -> None:
    """The band applies per period, so one percent either way is free and the rest is charged."""
    index = {(0, "a"): 98.0, (1, "a"): 100.5, (2, "a"): 103.0, (3, "a"): 100.0}
    target = Target(
        "a",
        0,
        period_width=1,
        flow="even",
        minimum=-1.0,
        maximum=1.0,
        min_weight=10_000.0,
        max_weight=10_000.0,
        shape="non_linear",
    )
    assert flow_values(index, target, 4) == pytest.approx([-2.0, 0.5, 3.0])
    # -2% is 1 outside the band, +0.5% is inside it, +3% is 2 outside; squared, times 10000
    assert flow_penalty(index, target, 4) == pytest.approx(10_000.0 * (1.0 + 0.0 + 4.0))


def test_ndy_values_are_the_change_between_consecutive_periods() -> None:
    """Non-declining yield is the percent change from each period to the next."""
    rising = {(0, "a"): 10.0, (1, "a"): 20.0, (2, "a"): 30.0}
    falling = {(0, "a"): 30.0, (1, "a"): 20.0, (2, "a"): 10.0}
    target = Target("a", 0, period_width=1, flow="ndy")
    assert flow_values(rising, target, 3) == pytest.approx([100.0, 50.0])
    assert flow_values(falling, target, 3) == pytest.approx([-100 / 3, -50.0])
    non_declining = Target("a", 0, period_width=1, flow="ndy", minimum=0.0, min_weight=1.0)
    assert flow_penalty(rising, non_declining, 3) == 0.0
    assert flow_penalty(falling, non_declining, 3) == pytest.approx(100 / 3 + 50.0)


def test_a_flow_term_groups_and_clips_its_window() -> None:
    """The period width groups the years and the window clips them."""
    index = {(year, "a"): float(year + 1) for year in range(10)}
    one_period = Target("a", 0, period_width=6, flow="even", flow_start=0, flow_end=6)
    assert flow_values(index, one_period, 10) == []  # fewer than two periods: nothing to compare
    rising = Target("a", 0, period_width=3, flow="ndy", flow_start=0, flow_end=6)
    assert flow_values(index, rising, 10) == pytest.approx([150.0])  # 6 then 15
    falling = {(year, "a"): float(10 - year) for year in range(6)}
    declining = Target("a", 0, period_width=3, flow="ndy", flow_start=0, flow_end=6)
    assert flow_values(falling, declining, 10) == pytest.approx([-100 / 3])  # 27 then 18


def test_a_flow_target_is_rejected_for_unknown_keys() -> None:
    """The flow type and window are validated."""
    with pytest.raises(ValueError, match="flow type"):
        Target("a", 0, flow="bogus")
    with pytest.raises(ValueError, match="flow_end"):
        Target("a", 0, flow="ndy", flow_start=10, flow_end=10)


def test_objective_prices_a_flow_target_from_a_frame() -> None:
    """The pure objective applies a flow target's band to each period."""
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
        minimum=-1.0,
        maximum=1.0,
        min_weight=2.0,
        max_weight=2.0,
    )
    # the reference is the final period (30); the other is 66.67% below it, 65.67 outside the band
    assert objective(values, [target]) == pytest.approx(2.0 * (200.0 / 3.0 - 1.0))


def test_objective_terms_prices_a_flow_target_per_period() -> None:
    """The per-target breakdown the watcher shows uses the flow pricing, not the additive one."""
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
        minimum=-1.0,
        maximum=1.0,
        min_weight=2.0,
        max_weight=2.0,
    )
    assert objective_terms(values, [target]) == pytest.approx([2.0 * (200.0 / 3.0 - 1.0)])


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
