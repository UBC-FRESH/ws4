"""Tests for the P166 reanalysis runner."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fire" / "cfsds_2003_526"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_runner_writes_uncalibrated_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner writes the expected poor, uncalibrated result."""
    module: Any = importlib.import_module("run_cfsds_reanalysis_case")
    output = tmp_path / "metrics.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_cfsds_reanalysis_case.py", "--fixture", str(FIXTURE), "--output", str(output)],
    )

    module.main()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["case"] == "2003_526"
    assert payload["result"]["metrics"]["iou"] < 0.2
    assert payload["result"]["metrics"]["area_bias"] > 1.0
