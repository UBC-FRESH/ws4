"""Tests for the P227 source variability envelope."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

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


def test_aggregate_and_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module: Any = importlib.import_module("stochastic_source_queue")
    samples = [module.simulate_sample(refill_l_min=6000.0, seed=seed) for seed in range(3)]
    summary = module.aggregate(samples)
    assert summary["samples"] == 3
    assert summary["feasible_fraction"] == 1.0
    assert summary["p95_cell_gap_min"] > 0.0
    monkeypatch.setattr(
        sys, "argv", ["stochastic_source_queue.py", "--refill-l-min", "6000", "--samples", "2"]
    )
    module.main()
    data = json.loads(capsys.readouterr().out)
    assert data["6000.0"]["samples"] == 2
