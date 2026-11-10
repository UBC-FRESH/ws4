"""Tests for the surrogate training entry point."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module = importlib.import_module("train_fire_surrogate")


def test_main_writes_model_and_training_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script writes a model, weights, and a training record."""
    corpus = tmp_path / "corpus"
    output = tmp_path / "model"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_fire_surrogate.py",
            "--corpus",
            str(corpus),
            "--output",
            str(output),
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
            "--hidden",
            "4",
            "--epochs",
            "2",
        ],
    )

    module.main()

    assert (output / "model.json").is_file()
    assert (output / "weights.npz").is_file()
    assert (output / "training.json").is_file()
    assert (corpus / "manifest.json").is_file()
    assert (corpus / "samples.npz").is_file()
