"""Tests for the surrogate-corpus builder wiring."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module = importlib.import_module("build_fire_surrogate_corpus")


def test_main_passes_the_requested_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script passes its explicit options to the corpus builder."""
    import ws4.fire.surrogate as surrogate_module

    calls: dict[str, object] = {}

    def fake_generate(**kwargs: object) -> object:
        calls.update(kwargs)
        return object()

    def fake_save(corpus: object, directory: Path) -> Path:
        calls["output"] = directory
        return directory / "manifest.json"

    monkeypatch.setattr(surrogate_module, "generate_corpus", fake_generate)
    monkeypatch.setattr(surrogate_module, "save_corpus", fake_save)
    output = tmp_path / "corpus"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_fire_surrogate_corpus.py",
            "--output",
            str(output),
            "--count",
            "12",
            "--seed",
            "7",
            "--rows",
            "20",
            "--cols",
            "21",
            "--duration",
            "45",
        ],
    )

    module.main()

    assert calls["count"] == 12
    assert calls["seed"] == 7
    assert calls["rows"] == 20
    assert calls["cols"] == 21
    assert calls["duration_min"] == 45.0
    assert calls["output"] == output
