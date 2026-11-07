"""Tests for the provisional-diagram review queue."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"


def test_review_queue_names_eight_provisional_diagrams_and_210_labels() -> None:
    """The queue is a work list, not an approval."""
    queue = pd.read_csv(DATA / "bec_review_queue.csv", dtype=str).fillna("")
    assert len(queue) == 8
    assert set(queue["status"]) == {"provisional"}
    assert set(queue["diagram_id"]) == {
        "cwn",
        "cwp",
        "hwn",
        "hwp",
        "ssn",
        "ssp",
        "swn",
        "swp",
    }
    labels: set[str] = set()
    for value in queue["bec_labels"]:
        labels.update(item for item in str(value).split(";") if item)
    assert len(labels) == 210
    assert "IDFdk3" in labels
    assert all(str(url).startswith("https://") for url in queue["pdf_url"])
