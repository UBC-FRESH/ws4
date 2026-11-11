"""Tests for the daily CFSDS breadth corpus."""

from __future__ import annotations

import pytest
from ws4.fire.daily_corpus import (
    DAILY_MINIMUM,
    DailyCase,
    _quantile_indices,
    daily_corpus_gate,
    daily_manifest,
)
from ws4.fire.fuel import FireFuelError


def _case(
    case_id: str,
    year: int,
    ecozone: int,
    area: float,
    status: str = "ready",
) -> DailyCase:
    """Build a small test case."""
    return DailyCase(
        case_id=case_id,
        year=year,
        days=3,
        final_area_ha=area,
        raster_area_ha=area,
        area_relative_error=0.0,
        ecozone=ecozone,
        lon=-115.0,
        lat=60.0,
        fuel_code=1,
        elevation_m=300.0,
        status=status,
    )


def test_daily_case_and_manifest() -> None:
    """A ready case serializes and contributes to the manifest."""
    case = _case("2023_1", 2023, 14, 1000.0)
    assert case.ready
    assert case.to_dict()["ready"] is True
    data = daily_manifest((case,), 3, 2)
    assert data["model_skill"] is False
    assert data["case_count"] == 1
    gate = data["gate"]
    assert isinstance(gate, dict)
    assert gate["status"] == "blocked"
    assert data["candidate_count"] == 3
    assert data["rejected_count"] == 2


def test_gate_requires_cases_years_and_ecozones() -> None:
    """The gate checks count, years, and ecozones together."""
    cases = tuple(
        _case(f"case_{index}", 2003 + index % 3, 14 + index % 2, 1000.0 + index)
        for index in range(DAILY_MINIMUM)
    )
    assert daily_corpus_gate(cases).status == "pass"
    assert daily_corpus_gate(cases[:-1]).status == "blocked"
    two_ecozones = tuple(
        _case(f"case_{index}", 2003 + index % 2, 14 + index % 2, 1000.0 + index)
        for index in range(DAILY_MINIMUM)
    )
    assert daily_corpus_gate(two_ecozones).status == "pass"
    one_ecozone = tuple(
        _case(f"case_{index}", 2003 + index % 2, 14, 1000.0 + index)
        for index in range(DAILY_MINIMUM)
    )
    assert daily_corpus_gate(one_ecozone).status == "blocked"


def test_quantile_indices_are_deterministic_and_end_inclusive() -> None:
    """Area quantiles cover the smallest and largest cases."""
    assert _quantile_indices(10, 3) == [0, 4, 9]
    assert _quantile_indices(3, 5) == [0, 1, 2]
    assert _quantile_indices(0, 3) == []


def test_rejected_case_is_not_ready() -> None:
    """Rejected cases do not count toward the gate."""
    case = _case("bad", 2023, 14, 1000.0, status="rejected")
    assert not case.ready
    assert daily_corpus_gate((case,)).ready_cases == 0


def test_invalid_status_is_rejected() -> None:
    """Unknown statuses fail validation."""
    with pytest.raises(FireFuelError, match="status"):
        _case("bad", 2023, 14, 1000.0, status="unknown")
