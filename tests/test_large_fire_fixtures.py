"""Tests for the large-fire reanalysis fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.fire.observed import load_cfsds_reanalysis_case

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fire"
CASES = ("large_2003_96", "large_2003_663", "large_2023_331", "large_2023_366")


@pytest.mark.parametrize("name", CASES)
def test_large_fixture_loads(name: str) -> None:
    """Each large fixture loads on the coarse grid."""
    fire = load_cfsds_reanalysis_case(FIXTURES / name)
    assert fire.grid.cell_size_m == 500.0
    assert len(fire.perimeters) == 2
    assert fire.grid.nrows > 50
    assert fire.grid.ncols > 50
