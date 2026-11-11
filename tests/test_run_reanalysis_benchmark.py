"""Tests for the P167 reanalysis benchmark runner."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fire"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_benchmark_writes_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner writes per-case rows and a systematic-bias summary."""
    module: Any = importlib.import_module("run_reanalysis_benchmark")
    output = tmp_path / "benchmark.json"
    csv = tmp_path / "benchmark.csv"
    fixtures = [FIXTURES / "cfsds_2003_526", FIXTURES / "cfsds_2009_147"]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_reanalysis_benchmark.py",
            "--fixtures",
            *[str(fixture) for fixture in fixtures],
            "--output",
            str(output),
            "--csv",
            str(csv),
        ],
    )

    module.main()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["case_count"] == 2
    assert payload["summary"]["systematic_overprediction"] is True
    assert payload["summary"]["overpredicted_cases"] == 2
    assert len(pd.read_csv(csv)) == 2
