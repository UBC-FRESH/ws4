"""Tests for the reproducible BEC coverage builder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _builder() -> Any:  # noqa: ANN401 - test-only dynamic module loader
    """Load the builder script without making ``scripts`` a package."""
    spec = importlib.util.spec_from_file_location(
        "build_bec_coverage_test", ROOT / "scripts" / "build_bec_coverage.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_builder_emits_all_current_labels() -> None:
    """The builder produces the 219-row registry with the expected statuses."""
    frame = _builder().build_coverage()
    assert len(frame) == 219
    assert frame["coverage_status"].value_counts().to_dict() == {
        "mixed_zone": 209,
        "no_diagram": 4,
        "reviewed_variant": 1,
        "reviewed_zone": 5,
    }
    assert set(frame["bec"]) == set(frame["bec"].unique())


def test_builder_emits_the_provisional_review_queue() -> None:
    """The builder names the eight provisional diagrams and their labels."""
    queue = _builder().build_review_queue()
    assert len(queue) == 8
    assert set(queue["status"]) == {"provisional"}
    labels: set[str] = set()
    for value in queue["bec_labels"]:
        labels.update(item for item in str(value).split(";") if item)
    assert len(labels) == 210


def test_builder_reads_all_atlas_reviews() -> None:
    """The builder finds the reviewed and provisional Atlas diagrams."""
    reviews = _builder()._diagram_reviews()
    assert reviews["fdin"] == "reviewed"
    assert reviews["pln"] == "reviewed"
    assert reviews["fdcn"] == "reviewed"


def test_builder_main_writes_the_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The builder entry point writes the CSV to its configured data path."""
    builder = _builder()
    frame = builder.build_coverage()
    monkeypatch.setattr(builder, "DATA", tmp_path)
    monkeypatch.setattr(builder, "build_coverage", lambda: frame)
    monkeypatch.setattr(builder, "build_review_queue", lambda: pd.DataFrame())
    assert builder.main() == 0
    assert (tmp_path / "bec_coverage.csv").is_file()
    assert (tmp_path / "bec_review_queue.csv").is_file()
