"""Tests for target normalization and priority tiers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.opt.calibrate import write_targets
from ws4.opt.objective import (
    PRIORITY_SCALE,
    Target,
    load_targets,
    normalization_scale,
    objective,
    penalty,
    priority_total,
    raw_penalty,
)
from ws4.report import target_status


def test_auto_normalization_divides_the_weighted_penalty() -> None:
    """A target's scale is its larger absolute bound, floored at one."""
    target = Target("a", period=1, minimum=100.0, min_weight=2.0, normalization="auto")
    assert normalization_scale(target) == 100.0
    assert raw_penalty(50.0, target) == 100.0
    assert penalty(50.0, target) == 1.0
    assert normalization_scale(Target("a", period=1, minimum=0.5, normalization="auto")) == 1.0
    assert normalization_scale(Target("a", period=1, minimum=100.0)) == 1.0


def test_priority_tiers_weight_higher_priority_more_strongly() -> None:
    """A different tier gets the priority multiplier; one tier stays additive."""
    first = Target("a", period=1, maximum=1.0, priority=1)
    second = Target("b", period=1, maximum=1.0, priority=2)
    assert priority_total([first, second], [0.0, 0.0]) == 0.0
    assert priority_total([first, second], [1.0, 0.0]) == PRIORITY_SCALE
    assert priority_total([first, second], [0.0, 2.0]) == 2.0
    assert priority_total([first, first], [1.0, 2.0]) == 3.0


def test_priority_and_normalization_round_trip_through_yaml(tmp_path: Path) -> None:
    """The new fields survive write/load and defaults stay off the file."""
    target = Target("a", period=1, minimum=10.0, normalization="auto", priority=2)
    path = write_targets(tmp_path / "targets.yaml", [target])
    loaded = load_targets(path)
    assert loaded[0].normalization == "auto"
    assert loaded[0].priority == 2
    plain = write_targets(tmp_path / "plain.yaml", [Target("b", period=1, minimum=1.0)])
    text = plain.read_text(encoding="utf-8")
    assert "normalization" not in text
    assert "priority" not in text


def test_invalid_normalization_and_priority_are_rejected() -> None:
    """Unknown normalization and a non-positive priority fail at construction."""
    with pytest.raises(ValueError, match="normalization"):
        Target("a", period=1, normalization="percent")
    with pytest.raises(ValueError, match="priority"):
        Target("a", period=1, priority=0)


def test_report_has_raw_and_normalized_penalties() -> None:
    """The target report carries raw penalty, normalized penalty, scale, and priority."""
    values = pd.DataFrame({"offset": [0], "account": ["a"], "value": [50.0]})
    target = Target("a", period=1, minimum=100.0, min_weight=2.0, normalization="auto", priority=2)
    row = target_status(values, [target]).iloc[0]
    assert row["raw_penalty"] == 100.0
    assert row["penalty"] == 1.0
    assert row["scale"] == 100.0
    assert row["normalization"] == "auto"
    assert row["priority"] == 2


def test_objective_uses_normalization_and_priority() -> None:
    """The full objective matches the normalized priority total."""
    values = pd.DataFrame(
        [
            {"offset": 0, "account": "a", "value": 50.0},
            {"offset": 0, "account": "b", "value": 50.0},
        ]
    )
    targets = [
        Target("a", period=1, minimum=100.0, normalization="auto", priority=1),
        Target("b", period=1, minimum=50.0, normalization="auto", priority=2),
    ]
    expected = priority_total(targets, [0.5, 0.0])
    assert objective(values, targets) == pytest.approx(expected)
