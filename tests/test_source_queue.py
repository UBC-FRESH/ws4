"""Tests for the P226 source queue simulation."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_threshold_source_is_feasible_with_queue() -> None:
    module: Any = importlib.import_module("source_queue")
    result = module.simulate(refill_l_min=4235.294)
    assert result.feasible is True
    assert result.max_source_wait_min > 0.0
    assert result.max_cell_gap_min <= 15.0


def test_stronger_source_reduces_wait_and_weak_source_fails() -> None:
    module: Any = importlib.import_module("source_queue")
    strong = module.simulate(refill_l_min=6000.0)
    weak = module.simulate(refill_l_min=3000.0)
    assert strong.max_source_wait_min < 2.83
    assert weak.feasible is False
    assert weak.max_end_lateness_min > 0.0
