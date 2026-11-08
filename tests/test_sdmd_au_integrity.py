"""Tests for the AU label and BEC/TSA integrity check."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.sdmd.au_integrity import (
    default_official_bec_labels,
    default_retired_bec_versions,
    default_tsa_bec_counts,
    load_tsa_bec_counts,
    normalize_bec_label,
    normalize_tsa,
    parse_au_label,
    validate_au_integrity,
    validate_au_metadata,
)

DATA = Path(__file__).resolve().parents[1] / "ws4" / "sdmd" / "data" / "sdmd"


def _known() -> set[str]:
    frame = pd.read_csv(DATA / "bec_variants.csv", dtype=str).fillna("")
    return set((frame["zone"] + frame["subzone"] + frame["variant"]).astype(str))


def test_parse_au_label() -> None:
    """The label decodes BEC, optional TSA, and species."""
    parts = parse_au_label("AU-IDFdk3-TSA23-FDI")
    assert parts.bec == "IDFdk3"
    assert parts.tsa == "23"
    assert parts.species == "FDI"
    assert parse_au_label("AU-IDFdk3-FDI").tsa is None


def test_valid_tsa_23_idfdk3_passes() -> None:
    """A real BEC/TSA pair has no findings."""
    findings = validate_au_integrity(
        "AU-IDFdk3-TSA23-FDI",
        known_bec=_known(),
        tsa_bec_counts=load_tsa_bec_counts(DATA / "tsa_bec_counts.csv"),
    )
    assert findings == ()


def test_tsa_24_idfdk3_fails() -> None:
    """TSA 24 has no IDFdk3 PSP support."""
    findings = validate_au_integrity(
        "AU-IDFdk3-TSA24-FDI",
        known_bec=_known(),
        tsa_bec_counts=load_tsa_bec_counts(DATA / "tsa_bec_counts.csv"),
    )
    assert [item.code for item in findings] == ["SDMD-AU-TSA-BEC"]


def test_unknown_bec_and_malformed_label_fail() -> None:
    """Unknown BEC labels and malformed labels are refused."""
    counts = load_tsa_bec_counts(DATA / "tsa_bec_counts.csv")
    unknown = validate_au_integrity("AU-XYZ99-TSA23-FDI", known_bec=_known(), tsa_bec_counts=counts)
    assert {item.code for item in unknown} == {"SDMD-AU-BEC", "SDMD-AU-TSA-BEC"}
    malformed = validate_au_integrity("bad-label", known_bec=_known(), tsa_bec_counts=counts)
    assert [item.code for item in malformed] == ["SDMD-AU-LABEL"]


def test_current_bec_without_sdmd_coverage_is_named() -> None:
    """A current BEC label absent from WS4 is a coverage gap, not unknown."""
    findings = validate_au_integrity(
        "AU-CWHvh3-FDI",
        known_bec=_known(),
        tsa_bec_counts=load_tsa_bec_counts(DATA / "tsa_bec_counts.csv"),
        official_bec=default_official_bec_labels(),
        retired_bec=default_retired_bec_versions(),
    )
    assert [item.code for item in findings] == ["SDMD-AU-BEC-NO-COVERAGE"]


def test_retired_bec_label_is_refused() -> None:
    """A WS4 label retired by BECdb is refused with its retirement version."""
    findings = validate_au_integrity(
        "AU-CWHxm1-FDI",
        known_bec=_known(),
        tsa_bec_counts=load_tsa_bec_counts(DATA / "tsa_bec_counts.csv"),
        official_bec=default_official_bec_labels(),
        retired_bec=default_retired_bec_versions(),
    )
    assert [item.code for item in findings] == ["SDMD-AU-BEC-RETIRED"]
    assert "version 13" in findings[0].message


def test_retired_label_outside_ws4_is_still_retired() -> None:
    """A retired BEC label is named as retired even when WS4 never carried it."""
    findings = validate_au_integrity(
        "AU-PPxh1a-FDI",
        known_bec=_known(),
        tsa_bec_counts=load_tsa_bec_counts(DATA / "tsa_bec_counts.csv"),
        official_bec=default_official_bec_labels(),
        retired_bec=default_retired_bec_versions(),
    )
    assert [item.code for item in findings] == ["SDMD-AU-BEC-RETIRED"]
    assert "version 10" in findings[0].message


def test_metadata_mismatch_fails_closed() -> None:
    """A plot row must agree with the BEC and TSA in its AU label."""
    findings = validate_au_metadata(
        "AU-IDFdk3-TSA23-FDI",
        bec_labels=["IDFdk2"],
        tsa_labels=["TSA-24"],
    )
    assert [item.code for item in findings] == [
        "SDMD-AU-BEC-MISMATCH",
        "SDMD-AU-TSA-MISMATCH",
    ]


def test_metadata_matching_label_passes() -> None:
    """A matching plot BEC/TSA pair has no metadata findings."""
    assert (
        validate_au_metadata(
            "AU-IDFdk3-TSA23-FDI",
            bec_labels=["IDFdk3"],
            tsa_labels=["TSA-23"],
        )
        == ()
    )


def test_phase_alias_resolves_for_au_lookup() -> None:
    """BECdb phase aliases resolve to the base BEC instead of unknown."""
    assert normalize_bec_label("ICHmc1a") == "ICHmc1"
    assert normalize_bec_label("SBSwk3a") == "SBSwk3"
    assert normalize_tsa("TSA-24") == "24"
    assert normalize_tsa("24") == "24"
    known = _known()
    for label in ("AU-ICHmc1a-FDI", "AU-ICHxwa-FDI", "AU-SBSwk3a-FDI"):
        assert (
            validate_au_integrity(label, known_bec=known, tsa_bec_counts=default_tsa_bec_counts())
            == ()
        )


def test_ichmw5_alias_reaches_the_support_table() -> None:
    """The PSP alias ICHmw5 is normalized to the official ICHwm5 label."""
    counts = default_tsa_bec_counts()
    assert counts[("1", "ICHwm5")] == 14
    assert ("1", "ICHmw5") not in counts
    findings = validate_au_integrity(
        "AU-ICHwm5-TSA1-FDI", known_bec=_known(), tsa_bec_counts=counts
    )
    assert [item.code for item in findings] == ["SDMD-AU-BEC-NO-COVERAGE"]


def test_validator_defaults_refuse_a_retired_label() -> None:
    """Omitting the optional mappings no longer fails open."""
    findings = validate_au_integrity(
        "AU-CWHxm1-FDI", known_bec=_known(), tsa_bec_counts=default_tsa_bec_counts()
    )
    assert [item.code for item in findings] == ["SDMD-AU-BEC-RETIRED"]
