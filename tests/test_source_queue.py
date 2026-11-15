"""Tests for the P226 source queue simulation."""

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


def test_two_sources_and_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module: Any = importlib.import_module("source_queue")
    two = module.simulate(refill_l_min=2000.0, sources=2)
    assert two.to_dict()["sources"] == 2
    assert two.feasible is True
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "source_queue.py",
            "--refill-l-min",
            "4235.294",
            "--sources",
            "1,2",
            "--applications",
            "1",
        ],
    )
    module.main()
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 2
    assert data[0]["feasible"] is True
