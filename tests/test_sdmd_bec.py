"""Tests for the BEC crosswalk classifier."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.sdmd.bec import classify_crosswalk

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"


def test_crosswalk_counts_are_stable() -> None:
    """The 247-row union has the expected relationship mix."""
    frame = pd.read_csv(DATA / "bec_crosswalk_review.csv", dtype=str)
    counts = frame["relationship"].value_counts().to_dict()
    assert counts == {"same": 183, "unresolved": 45, "cciss_split": 12, "ws4_split": 7}
    assert len(frame) == 247


def test_crosswalk_classifies_prefix_splits() -> None:
    """A strict prefix is a split; no prefix is unresolved."""
    rows = classify_crosswalk({"BWBSdk1", "XYZ"}, {"BWBSdk", "ABC"})
    mapping = {(row.ws4_bec, row.cciss_bec): row.relationship for row in rows}
    assert mapping[("BWBSdk1", "BWBSdk")] == "ws4_split"
    assert mapping[("XYZ", None)] == "unresolved"
    assert mapping[(None, "ABC")] == "unresolved"


def test_crosswalk_marks_exact_matches() -> None:
    """An identical label is an exact match."""
    rows = classify_crosswalk({"IDFdk3"}, {"IDFdk3"})
    assert len(rows) == 1
    assert rows[0].relationship == "same"
