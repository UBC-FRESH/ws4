"""The schedule snapshot is a diff: the analyst watches the movement, not a static map."""

from __future__ import annotations

import json
from pathlib import Path

from ws4.opt.telemetry import RunLogger


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_schedule_snapshots_carry_only_the_changed_blocks(tmp_path: Path) -> None:
    """A block that did not move is not resent; a removed block is sent with an empty chain."""
    path = tmp_path / "telemetry.jsonl"
    with RunLogger(path, "r1", {"seed": 1}) as logger:
        logger.schedule(0, {1: (("CC", 10),), 2: (("CT", 20),)})
        logger.schedule(20, {1: (("CC", 10),), 2: (("CT", 30),), 3: (("CC", 40),)})
        logger.schedule(40, {3: (("CC", 40),)})
    records = [record for record in _records(path) if record["type"] == "schedule"]
    assert records[0]["changed"] == [[1, [["CC", 10]]], [2, [["CT", 20]]]]
    assert records[1]["changed"] == [[2, [["CT", 30]]], [3, [["CC", 40]]]]
    assert records[2]["changed"] == [[1, []], [2, []]]
