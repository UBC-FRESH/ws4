"""Tests for the BEC crosswalk classifier."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.sdmd.bec import classify_crosswalk, classify_official

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"


def test_crosswalk_counts_are_stable() -> None:
    """The 247-row union has the expected relationship mix."""
    frame = pd.read_csv(DATA / "bec_crosswalk_review.csv", dtype=str)
    counts = frame["relationship"].value_counts().to_dict()
    assert counts == {"same": 183, "unresolved": 41, "cciss_split": 16, "ws4_split": 7}
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


def test_official_crosswalk_counts_are_stable() -> None:
    """The official BEC 13.1 crosswalk has the expected relationship mix."""
    ours = pd.read_csv(DATA / "bec_variants.csv", dtype=str).fillna("")
    official = pd.read_csv(DATA / "bec_official.csv", dtype=str).fillna("")
    rows = classify_official(
        set((ours["zone"] + ours["subzone"] + ours["variant"]).astype(str)),
        set(official["bec"].astype(str)),
    )
    counts = pd.Series([row.relationship for row in rows]).value_counts().to_dict()
    assert counts == {
        "official_exact": 165,
        "not_in_ws4": 37,
        "not_in_official": 26,
        "official_finer": 17,
        "ws4_finer": 12,
    }
    assert len(rows) == 257


def test_official_crosswalk_names_an_absent_label() -> None:
    """A WS4 label absent from BEC 13.1 is named, not unresolved."""
    ours = pd.read_csv(DATA / "bec_variants.csv", dtype=str).fillna("")
    official = pd.read_csv(DATA / "bec_official.csv", dtype=str).fillna("")
    rows = classify_official(
        set((ours["zone"] + ours["subzone"] + ours["variant"]).astype(str)),
        set(official["bec"].astype(str)),
    )
    status = {(row.ws4_bec, row.cciss_bec): row.relationship for row in rows}
    assert status[("CWHxm1", None)] == "not_in_official"
    assert status[(None, "CWHvh3")] == "not_in_ws4"
