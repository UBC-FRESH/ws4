"""Tests for the P222 gap-only queue simulation."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_three_aircraft_sustain_gap_rewetting() -> None:
    module: Any = importlib.import_module("dispatch_queue")
    result = module.simulate_queue(aircraft=3)
    assert result["feasible"] is True
    assert result["max_cell_gap_min"] == 10.75
    assert result["max_end_lateness_min"] == -2.25


def test_two_aircraft_accumulate_lateness() -> None:
    module: Any = importlib.import_module("dispatch_queue")
    result = module.simulate_queue(aircraft=2)
    assert result["feasible"] is False
    assert result["max_end_lateness_min"] > 0.0
