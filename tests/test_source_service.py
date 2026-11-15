"""Tests for the P225 source service calculator."""

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


def test_one_source_4000_is_oversubscribed_by_service_time() -> None:
    module: Any = importlib.import_module("source_service")
    case = module.SourceService(
        aircraft=3,
        cycle_min=4.25,
        payload_l=6000.0,
        refill_l_min=4000.0,
        sources=1,
    )
    assert case.service_min == 1.5
    assert case.utilization == pytest.approx(18.0 / 17.0)
    assert case.feasible is False
    assert module.minimum_refill_l_min(
        aircraft=3, cycle_min=4.25, payload_l=6000.0, sources=1
    ) == pytest.approx(4235.294117647059)


def test_one_source_5000_and_two_sources_2000() -> None:
    module: Any = importlib.import_module("source_service")
    strong = module.SourceService(
        aircraft=3,
        cycle_min=4.25,
        payload_l=6000.0,
        refill_l_min=5000.0,
        sources=1,
    )
    two = module.SourceService(
        aircraft=3,
        cycle_min=4.25,
        payload_l=6000.0,
        refill_l_min=2000.0,
        sources=2,
    )
    assert strong.feasible is True
    assert two.feasible is False


def test_dict_and_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module: Any = importlib.import_module("source_service")
    case = module.SourceService(
        aircraft=3,
        cycle_min=4.25,
        payload_l=6000.0,
        refill_l_min=5000.0,
        sources=1,
    )
    assert case.to_dict()["feasible"] is True
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "source_service.py",
            "--sources",
            "1",
            "--refill-l-min",
            "5000",
        ],
    )
    module.main()
    output = json.loads(capsys.readouterr().out)
    assert output["cases"][0]["feasible"] is True
