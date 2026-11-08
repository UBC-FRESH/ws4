"""Tests for the provisional-diagram review queue."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"


def test_review_queue_is_empty_after_all_reviews() -> None:
    """The queue is a work list, not an approval."""
    queue = pd.read_csv(DATA / "bec_review_queue.csv", dtype=str).fillna("")
    assert len(queue) == 0
    assert set(queue["status"]) == set()
    assert set(queue["diagram_id"]) == set()
