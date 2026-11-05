"""Tests for the BC-wide SDMD coverage registry."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.sdmd.coverage import coverage_frame, coverage_payload, coverage_row

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"


def test_coverage_has_every_current_bec_and_named_statuses() -> None:
    """The registry covers 219 labels and distinguishes reviewed, provisional, and gaps."""
    frame = coverage_frame()
    assert len(frame) == 219
    assert frame["bec"].nunique() == 219
    counts = frame["coverage_status"].value_counts().to_dict()
    assert counts == {
        "mixed_zone": 209,
        "no_diagram": 4,
        "reviewed_variant": 1,
        "reviewed_zone": 5,
    }


def test_reviewed_variant_has_au_evidence_and_diagrams() -> None:
    """IDFdk3 is the reviewed variant and names its two pilot AUs."""
    row = coverage_row("IDFdk3")
    assert row is not None
    assert row["coverage_status"] == "reviewed_variant"
    assert "variant" in row["match_level"]
    assert {"fdin", "fdip", "pln", "plp"} <= set(str(row["diagram_ids"]).split(";"))
    assert row["au_ids"] == "AU-IDFdk3-TSA23-FDI;AU-IDFdk3-TSA23-PLI"


def test_provisional_and_no_diagram_rows_are_explicit() -> None:
    """Zone-level and missing coverage are not silently treated as reviewed."""
    provisional = coverage_row("CWHvm1")
    assert provisional is not None
    assert provisional["coverage_status"] == "mixed_zone"
    assert "zone" in provisional["match_level"]
    assert "fdcn" in str(provisional["diagram_ids"])
    missing = coverage_row("BAFAun")
    assert missing is not None
    assert missing["coverage_status"] == "no_diagram"
    assert missing["diagram_ids"] == ""
    assert missing["au_ids"] == ""
    assert missing["gap_reason"] == "no_atlas_zone"
    assert missing["gap_action"]


def test_coverage_filters_and_unknown_label() -> None:
    """Zone/status filters and unknown labels are explicit."""
    payload = coverage_payload(zone="CWH", status="mixed_zone")
    assert payload["count"] > 0
    assert all(row["zone"] == "CWH" for row in payload["rows"])
    assert all(row["coverage_status"] == "mixed_zone" for row in payload["rows"])
    assert coverage_row("XYZ99") is None


def test_coverage_csv_is_reproducible() -> None:
    """The committed CSV matches the builder's row/column contract."""
    frame = pd.read_csv(DATA / "bec_coverage.csv", dtype=str).fillna("")
    assert list(frame.columns) == [
        "bec",
        "zone",
        "subzone",
        "variant",
        "zone_name",
        "subzone_name",
        "variant_name",
        "coverage_status",
        "match_level",
        "diagram_ids",
        "species",
        "origins",
        "reviewed_count",
        "provisional_count",
        "au_ids",
        "evidence_status",
        "gap_reason",
        "gap_action",
        "note",
    ]
    assert not frame.duplicated(["bec"]).any()
    assert set(frame["coverage_status"]) <= {
        "reviewed_variant",
        "reviewed_zone",
        "mixed_zone",
        "no_diagram",
    }
    assert set(frame["evidence_status"]) <= {"pilot", "none"}


def test_gap_triage_distinguishes_atlas_and_non_atlas_zones() -> None:
    """Every no-diagram row says whether its zone has an Atlas diagram."""
    frame = coverage_frame()
    gap = frame[frame["coverage_status"] == "no_diagram"]
    assert gap["gap_reason"].value_counts().to_dict() == {"no_atlas_zone": 4}
    assert set(gap["gap_action"]) == {
        "No diagram in the 14-public Atlas for this zone; add source evidence before coverage.",
    }
