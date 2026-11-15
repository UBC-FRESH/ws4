"""Tests for the P218 capacity calculator."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_capacity_calculates_gap_and_full_line() -> None:
    module: Any = importlib.import_module("rewetting_capacity")
    gap = module.Capacity(
        line_cells=5,
        drops_per_cell=2,
        interval_min=15.0,
        cycle_min=4.25,
        payload_l=6000.0,
    )
    assert gap.sorties_per_application == 10
    assert gap.sorties_per_hour == 40.0
    assert gap.aircraft_lower_bound == 3
    assert gap.water_l_per_hour == 240000.0
    full = module.Capacity(
        line_cells=75,
        drops_per_cell=2,
        interval_min=15.0,
        cycle_min=4.25,
        payload_l=6000.0,
    )
    assert full.sorties_per_application == 150
    assert full.sorties_per_hour == 600.0
    assert full.aircraft_lower_bound == 43
    assert full.water_l_per_hour == 3600000.0
