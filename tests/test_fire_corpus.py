"""Tests for the public fire-corpus registry and admission gate."""

from __future__ import annotations

from dataclasses import replace

import pytest
from ws4.fire.corpus import (
    BREADTH_MINIMUM,
    CASES,
    DEPTH_MINIMUM,
    CorpusInputs,
    CorpusStatus,
    CorpusTier,
    FireCase,
    corpus_gate,
    manifest,
    validate_registry,
)
from ws4.fire.fuel import FireFuelError


def test_registry_is_internally_consistent() -> None:
    """The default registry has unique identifiers and valid statuses."""
    validate_registry()
    assert len({case.case_id for case in CASES}) == len(CASES)
    assert all(case.source and case.licence and case.notes for case in CASES)


def test_ready_and_limited_cases_report_missing_inputs() -> None:
    """Ready-with-limit cases remain usable but expose missing required inputs."""
    dogrib = next(case for case in CASES if case.case_id == "dogrib-2b")
    hay = next(case for case in CASES if case.case_id == "hay-river-2023-320")
    candidate = next(case for case in CASES if case.case_id == "cfsds-2023-321-daily")

    assert dogrib.ready
    assert dogrib.status is CorpusStatus.READY_WITH_LIMIT
    assert dogrib.missing_inputs == ("licence_documented",)
    assert hay.ready
    assert hay.missing_inputs == ()
    assert not candidate.ready
    assert candidate.status is CorpusStatus.CANDIDATE
    assert candidate.missing_inputs == ()


def test_duplicate_event_is_not_independent() -> None:
    """A duplicate of Hay River is rejected and excluded from the gate."""
    duplicate = next(case for case in CASES if case.case_id == "cfsds-2023-320-daily")
    assert duplicate.duplicate_of == "hay-river-2023-320"
    assert duplicate.status is CorpusStatus.REJECTED
    assert not duplicate.independent
    assert not duplicate.ready


def test_corpus_gate_is_blocked_at_two_depth_cases() -> None:
    """Two depth cases and no breadth cases do not pass the corpus gate."""
    gate = corpus_gate()
    assert gate.depth_ready == 0
    assert gate.depth_ready_with_limit == 2
    assert gate.breadth_ready == 0
    assert gate.breadth_ready_with_limit == 0
    assert gate.status == "blocked"
    assert gate.depth_ready < DEPTH_MINIMUM
    assert gate.breadth_ready < BREADTH_MINIMUM
    assert "Need 3 fully ready depth cases" in str(gate.to_dict()["reason"])


def test_manifest_counts_tiers_statuses_and_gaps() -> None:
    """The manifest records counts and does not merge model-only evidence."""
    data = manifest()
    assert data["case_count"] == len(CASES)
    assert data["independent_case_count"] == len(CASES) - 1
    assert data["tier_counts"] == {
        "daily_cfsds": 2,
        "hourly_fbp": 3,
        "model_only": 2,
    }
    assert data["status_counts"] == {
        "blocked": 1,
        "candidate": 1,
        "model_only": 2,
        "ready_with_limit": 2,
        "rejected": 1,
    }
    gate = data["gate"]
    assert isinstance(gate, dict)
    assert gate["status"] == "blocked"
    gaps = data["gaps"]
    assert isinstance(gaps, dict)
    assert "candidate" in gaps


def test_ready_case_with_missing_inputs_is_rejected() -> None:
    """A fully ready case may not hide missing required inputs."""
    hay = next(case for case in CASES if case.case_id == "hay-river-2023-320")
    broken = replace(
        hay,
        status=CorpusStatus.READY,
        inputs=replace(hay.inputs, hourly_weather=False),
    )
    with pytest.raises(FireFuelError, match="missing"):
        validate_registry((broken,))


def test_model_only_metadata_is_consistent() -> None:
    """Model-only tier and status must agree."""
    with pytest.raises(FireFuelError, match="model-only tier"):
        FireCase(
            case_id="bad",
            name="bad",
            region="bad",
            year=2023,
            tier=CorpusTier.MODEL_ONLY,
            status=CorpusStatus.READY,
            source="x",
            licence="x",
            inputs=CorpusInputs(),
            notes="x",
        )
