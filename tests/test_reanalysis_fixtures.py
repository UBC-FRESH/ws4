"""Tests for the P167 reanalysis fixture set."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.fire.observed import load_cfsds_reanalysis_case

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fire"
CASES = (
    "cfsds_2003_526",
    "cfsds_2003_706",
    "cfsds_2009_147",
    "cfsds_2009_79",
    "cfsds_2023_19",
    "cfsds_2023_786",
)


@pytest.mark.parametrize("name", CASES)
def test_each_reanalysis_fixture_loads(name: str) -> None:
    """Every P167 fixture satisfies the observed-fire contract."""
    fire = load_cfsds_reanalysis_case(FIXTURES / name)
    assert fire.fire_id == name.removeprefix("cfsds_")
    assert len(fire.perimeters) == 2
    assert fire.event_start < fire.event_end
    assert not fire.weather.empty
