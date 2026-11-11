"""Tests for the corpus manifest builder."""

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


def test_main_writes_manifest_and_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The builder writes a JSON manifest and a flat CSV inventory."""
    module: Any = importlib.import_module("build_fire_corpus_manifest")
    output = tmp_path / "manifest.json"
    csv = tmp_path / "inventory.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_fire_corpus_manifest.py", "--output", str(output), "--csv", str(csv)],
    )

    module.main()

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["case_count"] == 7
    assert data["gate"]["status"] == "blocked"
    frame = pd.read_csv(csv)
    assert len(frame) == 7
    assert set(frame["case_id"]) == {case["case_id"] for case in data["cases"]}
