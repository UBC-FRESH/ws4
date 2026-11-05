"""Tests for the Pareto solution-space read model."""

from __future__ import annotations

from typing import Any

import pytest
from ws4.opt.solution_space import build_solution_space


def _member(
    label: str,
    seed: int,
    volume: float,
    old: float,
    *,
    objective: float | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    """Build one portfolio member with two outcome metrics."""
    return {
        "label": label,
        "seed": seed,
        "objective": objective if objective is not None else -volume,
        "metrics": {
            "volume": volume,
            "old": old,
            "objective": objective if objective is not None else -volume,
        },
        "factors": {"product.volume": 1.0},
        "status": status,
        "schedule": f"{label}/seed-{seed:03d}/schedule.csv",
    }


def _payload(*members: dict[str, Any], directions: dict[str, str] | None = None) -> dict[str, Any]:
    """Wrap members in a portfolio-style report."""
    return {
        "metrics": ["volume", "old"],
        "directions": directions or {"volume": "max", "old": "max", "objective": "min"},
        "members": list(members),
    }


def test_solution_space_recomputes_the_exact_front_from_all_members() -> None:
    """A bounded archive cannot hide an outcome trade-off from the explorer."""
    space = build_solution_space(
        _payload(
            _member("member-000", 1, 100.0, 10.0),
            _member("member-001", 1, 90.0, 20.0),
            _member("member-002", 1, 80.0, 30.0),
            _member("member-003", 1, 70.0, 5.0),
        )
    )
    assert space["front"] == ["member-000:001", "member-001:001", "member-002:001"]
    assert space["front_size"] == 3
    assert space["points"][0]["normalized"]["volume"] == 1.0
    assert space["points"][2]["normalized"]["old"] == 1.0
    assert space["points"][3]["front"] is False


def test_solution_space_respects_min_and_max_directions() -> None:
    """The normalized box always puts the best value at one."""
    space = build_solution_space(
        _payload(
            _member("member-000", 1, 100.0, 10.0),
            _member("member-001", 1, 90.0, 20.0),
        ),
        near_front_epsilon=0.0,
    )
    assert space["directions"]["volume"] == "max"
    assert space["directions"]["old"] == "max"
    space = build_solution_space(
        {
            "metrics": ["cost"],
            "directions": {"cost": "min"},
            "members": [
                {"label": "a", "seed": 1, "objective": 2.0, "metrics": {"cost": 10.0}},
                {"label": "b", "seed": 1, "objective": 1.0, "metrics": {"cost": 20.0}},
            ],
        }
    )
    by_key = {point["key"]: point for point in space["points"]}
    assert by_key["a:001"]["normalized"]["cost"] == 1.0
    assert by_key["b:001"]["normalized"]["cost"] == 0.0
    assert space["front"] == ["a:001"]


def test_solution_space_near_front_is_labelled_and_not_pareto() -> None:
    """A near-front point keeps its larger sample but is not called nondominated."""
    payload = _payload(
        _member("member-000", 1, 100.0, 10.0),
        _member("member-001", 1, 90.0, 20.0),
        _member("member-002", 1, 80.0, 30.0),
        _member("member-003", 1, 70.0, 5.0),
    )
    exact = build_solution_space(payload, near_front_epsilon=0.0)
    near = build_solution_space(payload, near_front_epsilon=0.7)
    dominated = next(point for point in exact["points"] if point["key"] == "member-003:001")
    assert dominated["front"] is False
    assert dominated["near_front"] is False
    assert "member-003:001" in near["near_front"]
    assert "member-003:001" not in near["front"]


def test_solution_space_skips_failed_and_incomplete_members() -> None:
    """A failed run or a missing metric cannot become a zero-valued point."""
    payload = _payload(
        _member("member-000", 1, 100.0, 10.0),
        _member("member-001", 1, 90.0, 20.0, status="failed"),
        {"label": "member-002", "seed": 1, "objective": 1.0, "metrics": {"volume": 9.0}},
    )
    space = build_solution_space(payload)
    assert [point["key"] for point in space["points"]] == ["member-000:001"]
    assert space["failed"] == 1


def test_solution_space_requires_metrics() -> None:
    """An artifact without declared outcomes cannot define a point cloud."""
    with pytest.raises(ValueError, match="no declared metrics"):
        build_solution_space({"members": []})
    with pytest.raises(ValueError, match="unknown direction"):
        build_solution_space(
            {
                "metrics": ["a"],
                "directions": {"a": "sideways"},
                "members": [],
            }
        )
