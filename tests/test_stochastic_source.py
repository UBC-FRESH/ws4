"""Tests for the P227 source variability envelope."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_seeded_sample_and_threshold() -> None:
    module: Any = importlib.import_module("stochastic_source_queue")
    first = module.simulate_sample(refill_l_min=4235.294, seed=7)
    second = module.simulate_sample(refill_l_min=4235.294, seed=7)
    assert first == second
    assert first.feasible is True
    weak = module.simulate_sample(refill_l_min=3500.0, seed=7)
    assert weak.feasible is False
    assert module.percentile([10.0, 20.0, 30.0], 0.95) == 30.0
