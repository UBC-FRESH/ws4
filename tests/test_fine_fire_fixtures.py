"""Tests for the fine-grid large-fire fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.fire.observed import load_cfsds_reanalysis_case

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fire"
CASES = ("fine_2003_96", "fine_2003_663")


@pytest.mark.parametrize("name", CASES)
def test_fine_fixture_loads(name: str) -> None:
    """Each fine fixture loads at 100 m."""
    fire = load_cfsds_reanalysis_case(FIXTURES / name)
    assert fire.grid.cell_size_m == 100.0
    assert len(fire.perimeters) == 2
    assert fire.grid.nrows > 200
