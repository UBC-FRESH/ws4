"""Tests for the elite archive and Pareto filter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ws4.opt.archive import (
    Elite,
    EliteArchive,
    dominates,
    metrics_from_records,
    pareto_front,
    write_schedule,
)

DIRECTIONS = {"volume": "max", "cost": "min"}


def _elite(volume: float, cost: float, objective: float = 1.0, source: str = "a") -> Elite:
    """Build a small candidate with a two-metric vector."""
    return Elite(
        objective=objective,
        metrics={"volume": volume, "cost": cost},
        schedule={1: (("CC", 0),)},
        source=source,
    )


def test_dominates_respects_the_direction() -> None:
    """A candidate must be no worse everywhere and better somewhere."""
    strong = _elite(100.0, 10.0)
    weak = _elite(90.0, 12.0)
    assert dominates(strong, weak, DIRECTIONS)
    assert not dominates(weak, strong, DIRECTIONS)
    assert not dominates(strong, _elite(100.0, 10.0), DIRECTIONS)


def test_pareto_front_drops_dominated_and_tied_members() -> None:
    """Dominated points and exact ties do not both survive."""
    a = _elite(80.0, 10.0, objective=5.0, source="a")
    b = _elite(100.0, 15.0, objective=4.0, source="b")
    c = _elite(120.0, 20.0, objective=3.0, source="c")
    dominated = _elite(90.0, 30.0, objective=2.0, source="d")
    tie = _elite(80.0, 10.0, objective=6.0, source="e")
    front = pareto_front([a, b, c, dominated, tie], DIRECTIONS)
    assert [item.source for item in front] == ["c", "b", "a"]
    assert all(item.source != "d" for item in front)


def test_pareto_front_rejects_a_missing_direction() -> None:
    """Every metric needs an explicit direction."""
    with pytest.raises(ValueError, match="direction"):
        pareto_front([_elite(1.0, 2.0)], {"volume": "max"})


def test_archive_replaces_dominated_members_and_caps_the_size() -> None:
    """A stronger candidate removes the member it dominates; capacity trims the worst."""
    archive = EliteArchive(capacity=2, directions=DIRECTIONS)
    assert archive.add(_elite(80.0, 10.0, objective=1.0, source="a"))
    assert archive.add(_elite(100.0, 20.0, objective=2.0, source="b"))
    archive.add(_elite(120.0, 30.0, objective=3.0, source="c"))
    assert len(archive.elites) == 2
    assert [elite.source for elite in archive.elites] == ["a", "b"]
    archive.add(_elite(140.0, 40.0, objective=0.5, source="d"))
    assert len(archive.elites) == 2
    assert [elite.source for elite in archive.elites] == ["d", "a"]


def test_archive_removes_members_that_a_new_candidate_dominates() -> None:
    """A candidate that dominates retained members replaces them."""
    archive = EliteArchive(capacity=4, directions=DIRECTIONS)
    archive.add(_elite(80.0, 10.0, source="a"))
    archive.add(_elite(100.0, 20.0, source="b"))
    assert archive.add(_elite(120.0, 10.0, source="c"))
    assert [elite.source for elite in archive.elites] == ["c"]
    assert archive.add(_elite(130.0, 25.0, source="d"))
    assert [elite.source for elite in archive.elites] == ["c", "d"]


def test_archive_rejects_a_dominated_candidate() -> None:
    """A candidate worse on every metric is not retained."""
    archive = EliteArchive(capacity=4, directions=DIRECTIONS)
    archive.add(_elite(100.0, 10.0, source="a"))
    assert not archive.add(_elite(90.0, 20.0, source="b"))
    assert [elite.source for elite in archive.elites] == ["a"]


def test_archive_writes_the_manifest_and_schedules(tmp_path: Path) -> None:
    """The export contains one CSV per elite and a JSON manifest."""
    archive = EliteArchive(capacity=2, directions=DIRECTIONS)
    archive.add(_elite(100.0, 10.0, source="a"))
    paths = archive.write(tmp_path)
    manifest = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert manifest["directions"] == DIRECTIONS
    assert manifest["elites"][0]["schedule"] == "elite-000.csv"
    assert paths["manifest"] == tmp_path / "archive.json"
    assert (
        (tmp_path / "elite-000.csv")
        .read_text(encoding="utf-8")
        .startswith("block_id,treatment,offset")
    )


def test_write_schedule_orders_blocks_and_events(tmp_path: Path) -> None:
    """The schedule CSV is sorted by block and keeps the event order."""
    path = tmp_path / "schedule.csv"
    write_schedule(path, {2: (("CT", 5),), 1: (("CC", 0), ("CT", 10))})
    assert path.read_text(encoding="utf-8").splitlines() == [
        "block_id,treatment,offset",
        "1,CC,0",
        "1,CT,10",
        "2,CT,5",
    ]


def test_metrics_from_records_accepts_account_and_period_names() -> None:
    """A metric name can select an account or one account period."""
    records = [
        {"account": "product.volume", "period": 1, "value": 10.0},
        {"account": "product.volume", "period": 2, "value": 20.0},
        {"account": "feature.old", "value": 3.0},
    ]
    values = metrics_from_records(records, ["product.volume@2", "feature.old"])
    assert values == {"product.volume@2": 20.0, "feature.old": 3.0}
    with pytest.raises(ValueError, match="not found"):
        metrics_from_records(records, ["feature.missing"])
