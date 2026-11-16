"""Tests for decision quality under scenario uncertainty."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _matrix() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "decision": ["A", "A", "A", "B", "B", "B", "C", "C", "C"],
            "scenario": ["s1", "s2", "s3"] * 3,
            "outcome": [1.0, 2.0, 3.0, 2.0, 2.0, 2.0, 3.0, 1.0, 1.0],
        }
    )


def test_decision_metrics() -> None:
    module: Any = importlib.import_module("ws4.opt.decision_quality")
    report = module.evaluate_decisions(
        _matrix(), decision="decision", scenario="scenario", outcome="outcome"
    )
    assert report.deterministic_choice == "C"
    assert report.robust_choice == "B"
    assert report.minimax_regret_choice == "B"
    assert report.metrics.loc["A", "expected_outcome"] == pytest.approx(2.0)
    assert report.metrics.loc["C", "expected_regret"] == pytest.approx(2.0 / 3.0)
    assert report.metrics.loc["A", "rank_stability"] == pytest.approx(0.0)
    assert report.metrics.loc["B", "rank_stability"] == pytest.approx(1.0)
    assert report.summary()["schema_version"] == "ws4.decision-quality.v1"


def test_constraints_weights_and_invalid_inputs(tmp_path: Path) -> None:
    module: Any = importlib.import_module("ws4.opt.decision_quality")
    frame = _matrix()
    frame["feasible"] = [1, 1, 1, 1, 1, 0, 1, 1, 1]
    report = module.evaluate_decisions(
        frame,
        decision="decision",
        scenario="scenario",
        outcome="outcome",
        feasible="feasible",
        weights={"s1": 2.0, "s2": 1.0, "s3": 1.0},
    )
    assert report.weights["s1"] == 0.5
    assert report.metrics.loc["B", "constraint_satisfaction"] == pytest.approx(0.75)
    with pytest.raises(ValueError, match="unique"):
        module.evaluate_decisions(
            pd.concat([frame, frame.iloc[[0]]], ignore_index=True),
            decision="decision",
            scenario="scenario",
            outcome="outcome",
        )
    with pytest.raises(ValueError, match="missing columns"):
        module.evaluate_decisions(frame, decision="nope", scenario="scenario", outcome="outcome")
    with pytest.raises(ValueError, match="weights"):
        module.evaluate_decisions(
            frame,
            decision="decision",
            scenario="scenario",
            outcome="outcome",
            weights={"s1": 1.0},
        )
    with pytest.raises(ValueError, match="two decisions"):
        module.evaluate_decisions(
            frame[frame.decision == "A"],
            decision="decision",
            scenario="scenario",
            outcome="outcome",
        )
    report.write(tmp_path / "out")
    assert (tmp_path / "out" / "decision_quality.json").is_file()


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = tmp_path / "matrix.csv"
    _matrix().to_csv(input_path, index=False)
    output = tmp_path / "out"
    module: Any = importlib.import_module("decision_quality")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "decision_quality.py",
            "--input",
            str(input_path),
            "--output",
            str(output),
        ],
    )
    module.main()
    payload = json.loads((output / "decision_quality.json").read_text(encoding="utf-8"))
    assert payload["deterministic_choice"] == "C"
    assert payload["robust_choice"] == "B"
