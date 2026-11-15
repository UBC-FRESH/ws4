"""Tests for the P224 water-source capacity calculator."""

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


def test_one_source_threshold() -> None:
    module: Any = importlib.import_module("water_source_capacity")
    source = module.SourceCapacity(
        sorties_per_hour=40.0,
        payload_l=6000.0,
        refill_l_min=4000.0,
        sources=1,
    )
    assert source.required_l_per_hour == 240000.0
    assert source.feasible is True
    assert source.utilization == 1.0
    assert module.minimum_refill_l_min(sorties_per_hour=40.0, payload_l=6000.0, sources=1) == 4000.0


def test_two_source_threshold_and_failure() -> None:
    module: Any = importlib.import_module("water_source_capacity")
    two = module.SourceCapacity(
        sorties_per_hour=40.0,
        payload_l=6000.0,
        refill_l_min=2000.0,
        sources=2,
    )
    assert two.feasible is True
    weak = module.SourceCapacity(
        sorties_per_hour=40.0,
        payload_l=6000.0,
        refill_l_min=3000.0,
        sources=1,
    )
    assert weak.feasible is False
    assert weak.source_limited_sorties_per_hour == 30.0


def test_dict_and_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module: Any = importlib.import_module("water_source_capacity")
    source = module.SourceCapacity(
        sorties_per_hour=40.0,
        payload_l=6000.0,
        refill_l_min=4000.0,
        sources=1,
    )
    data = source.to_dict()
    assert data["required_l_per_hour"] == 240000.0
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "water_source_capacity.py",
            "--sources",
            "1",
            "--refill-l-min",
            "4000",
        ],
    )
    module.main()
    output = json.loads(capsys.readouterr().out)
    assert output["minimum_refill_l_min"] == {"1": 4000.0}
    assert output["cases"][0]["feasible"] is True
