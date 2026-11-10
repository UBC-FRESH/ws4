"""Tests for the surrogate evaluation entry point."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module = importlib.import_module("evaluate_fire_surrogate")


def test_main_writes_synthetic_and_ood_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The evaluation writes both synthetic and Dogrib rows."""
    from ws4.fire.surrogate import generate_corpus
    from ws4.fire.surrogate_model import SurrogateModel

    corpus = generate_corpus(count=5, seed=3, rows=8, cols=8, duration_min=20.0)
    model = SurrogateModel.fit(corpus, hidden_units=4, epochs=2, seed=3)
    model_dir = tmp_path / "model"
    model.save(model_dir)
    output = tmp_path / "evaluation.csv"
    summary = tmp_path / "evaluation.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_fire_surrogate.py",
            "--model",
            str(model_dir),
            "--count",
            "5",
            "--seed",
            "3",
            "--rows",
            "8",
            "--cols",
            "8",
            "--duration",
            "20",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ],
    )

    module.main()

    assert output.is_file()
    assert summary.is_file()
    text = output.read_text(encoding="utf-8")
    assert "synthetic-holdout" in text
    assert "dogrib-ood" in text
