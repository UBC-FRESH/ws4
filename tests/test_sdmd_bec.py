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
    assert counts == {
        "same": 183,
        "not_in_ws4": 22,
        "not_in_cciss": 19,
        "cciss_split": 16,
        "ws4_split": 7,
    }
    assert len(frame) == 247


def test_crosswalk_classifies_prefix_splits() -> None:
    """A strict prefix is a split; no prefix is unresolved."""
    rows = classify_crosswalk({"BWBSdk1", "XYZ"}, {"BWBSdk", "ABC"})
    mapping = {(row.ws4_bec, row.cciss_bec): row.relationship for row in rows}
    assert mapping[("BWBSdk1", "BWBSdk")] == "ws4_split"
    assert mapping[("XYZ", None)] == "not_in_cciss"
    assert mapping[(None, "ABC")] == "not_in_ws4"


def test_crosswalk_marks_exact_matches() -> None:
    """An identical label is an exact match."""
    rows = classify_crosswalk({"IDFdk3"}, {"IDFdk3"})
    assert len(rows) == 1
    assert rows[0].relationship == "same"


def test_official_crosswalk_counts_are_stable() -> None:
    """The BECdb crosswalk has the expected relationship mix."""
    ours = pd.read_csv(DATA / "bec_variants.csv", dtype=str).fillna("")
    official = pd.read_csv(DATA / "bec_official.csv", dtype=str).fillna("")
    retired = pd.read_csv(DATA / "bec_retired.csv", dtype=str).fillna("")
    rows = classify_official(
        set((ours["zone"] + ours["subzone"] + ours["variant"]).astype(str)),
        set(official["bec"].astype(str)),
        dict(zip(retired["bec"], retired["retired_version"], strict=True)),
        dict(zip(official["bec"], official["notes"], strict=True)),
    )
    counts = pd.Series([row.relationship for row in rows]).value_counts().to_dict()
    assert counts == {
        "official_exact": 165,
        "not_in_ws4": 54,
        "retired": 48,
    }
    assert len(rows) == 267


def test_official_crosswalk_names_retirement_and_successor() -> None:
    """A retired WS4 label carries its BEC version and recorded successor."""
    ours = pd.read_csv(DATA / "bec_variants.csv", dtype=str).fillna("")
    official = pd.read_csv(DATA / "bec_official.csv", dtype=str).fillna("")
    retired = pd.read_csv(DATA / "bec_retired.csv", dtype=str).fillna("")
    rows = classify_official(
        set((ours["zone"] + ours["subzone"] + ours["variant"]).astype(str)),
        set(official["bec"].astype(str)),
        dict(zip(retired["bec"], retired["retired_version"], strict=True)),
        dict(zip(official["bec"], official["notes"], strict=True)),
    )
    status = {(row.ws4_bec, row.cciss_bec): row for row in rows}
    assert status[("CWHxm1", None)].relationship == "retired"
    assert status[("CWHxm1", None)].retired_version == "13"
    assert status[("CWHxm1", None)].replaced_by == "CWHdm1"
    assert status[(None, "CWHvh3")].relationship == "not_in_ws4"


def test_every_ws4_label_absent_from_current_bec_is_retired() -> None:
    """No WS4 label is left outside both the current and retired BECdb tables."""
    ours = pd.read_csv(DATA / "bec_variants.csv", dtype=str).fillna("")
    official = pd.read_csv(DATA / "bec_official.csv", dtype=str).fillna("")
    retired = pd.read_csv(DATA / "bec_retired.csv", dtype=str).fillna("")
    ws4 = set((ours["zone"] + ours["subzone"] + ours["variant"]).astype(str))
    current = set(official["bec"].astype(str))
    retired_labels = set(retired["bec"].astype(str))
    assert not (ws4 - current - retired_labels)
