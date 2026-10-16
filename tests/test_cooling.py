"""Tests for the simulated-annealing temperature schedules."""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.cooling import AdaptiveCooling, TemperatureSchedule
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target
from ws4.opt.solvers import solve_sa_delta

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_initial_temperature_uses_the_mean_uphill_move() -> None:
    """The initial temperature sets the average uphill move to the target acceptance."""
    rule = AdaptiveCooling(initial_acceptance=0.8)
    expected = 3.0 / math.log(1.0 / 0.8)  # the positives 2 and 4 average 3; -1 is ignored
    assert rule.initial_temperature([2.0, 4.0, -1.0]) == pytest.approx(expected)


def test_initial_temperature_is_zero_without_an_uphill_move() -> None:
    """A sample of non-uphill moves gives a zero (frozen) start."""
    assert AdaptiveCooling().initial_temperature([-1.0, 0.0]) == 0.0


def test_cool_follows_the_decrement_rule() -> None:
    """The decrement is c / (1 + c ln(1 + delta) / (3 sigma)) and lowers the temperature."""
    rule = AdaptiveCooling(delta=0.1)
    expected = 10.0 / (1.0 + 10.0 * math.log1p(0.1) / (3.0 * 2.0))
    assert rule.cool(10.0, 2.0) == pytest.approx(expected)
    assert rule.cool(10.0, 2.0) < 10.0


def test_cool_leaves_the_temperature_for_a_zero_spread() -> None:
    """A non-positive spread leaves the temperature unchanged."""
    assert AdaptiveCooling().cool(10.0, 0.0) == 10.0


def test_adaptive_cooling_rejects_bad_parameters() -> None:
    """The acceptance ratio and delta are bounds-checked."""
    with pytest.raises(ValueError, match="initial_acceptance"):
        AdaptiveCooling(initial_acceptance=1.5)
    with pytest.raises(ValueError, match="delta"):
        AdaptiveCooling(delta=0.0)


def test_geometric_schedule_multiplies_the_temperature() -> None:
    """The geometric schedule reproduces temperature *= cooling."""
    schedule = TemperatureSchedule(initial=100.0, cooling=0.5, adaptive=False, window=4)
    assert schedule.temperature == 100.0
    schedule.observe(1.0, 0.0)
    schedule.observe(1.0, 0.0)
    assert schedule.temperature == pytest.approx(25.0)


def test_adaptive_schedule_warms_up_then_cools() -> None:
    """The first window sets the initial temperature; the next window lowers it."""
    schedule = TemperatureSchedule(initial=1.0, cooling=1.0, adaptive=True, window=3)
    assert math.isinf(schedule.temperature)
    for increase in (2.0, 4.0, -1.0):
        schedule.observe(increase, 0.0)
    warmed = 3.0 / math.log(1.0 / 0.9)
    assert schedule.temperature == pytest.approx(warmed)
    for objective in (1.0, 2.0, 3.0):
        schedule.observe(0.0, objective)
    assert schedule.temperature < warmed


def test_effective_window_is_capped_at_half_the_budget() -> None:
    """The warm-up and at least one cooling step both need a window."""
    assert TemperatureSchedule.effective_window(1000, 64) == 64
    assert TemperatureSchedule.effective_window(10, 64) == 5
    assert TemperatureSchedule.effective_window(1, 64) == 1


def test_schedule_rejects_a_non_positive_window() -> None:
    """The window must hold at least one iteration."""
    with pytest.raises(ValueError, match="window"):
        TemperatureSchedule(initial=1.0, cooling=0.9, adaptive=True, window=0)


def test_config_rejects_an_unknown_cooling_mode() -> None:
    """An unknown schedule name fails before the search starts."""
    with pytest.raises(ValueError, match="cooling_mode"):
        OptimizeConfig(cooling_mode="quench")


def test_adaptive_delta_solver_matches_a_fresh_evaluation(tmp_path: Path) -> None:
    """The adaptive schedule drives the delta solver to a verifiable objective."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "c"
    )
    optimizer = Optimizer.from_dataset(
        dataset, OptimizeConfig(years=3, iterations=40, seed=1, cooling_mode="adaptive")
    )
    targets = [Target("product.Volume", 0, minimum=300.0, maximum=400.0)]
    evaluator = IncrementalObjective(optimizer, targets)
    candidates = optimizer.candidates()
    initial = {block: options[0] for block, options in candidates.items() if options}
    best, objective = solve_sa_delta(
        evaluator,
        random.Random(5),
        iterations=40,
        temperature=1000.0,
        cooling=0.99,
        candidates=candidates,
        registry=optimizer.registry,
        initial=initial,
        adaptive=True,
        cooling_window=10,
    )
    assert objective == pytest.approx(optimizer._evaluate(best, targets))
