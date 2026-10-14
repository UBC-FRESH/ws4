"""Tests for the programmatic model API."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.model.api import Model
from ws4.model.schema import TABLES, validate_dataset

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _dataset(tmp_path: Path) -> Path:
    """Compile the synthetic fixture."""
    return build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )


def test_round_trip_preserves_the_model(tmp_path: Path) -> None:
    """Loading a dataset and writing it back yields the same valid model."""
    dataset = _dataset(tmp_path)
    out = Model.from_dataset(dataset).write(tmp_path / "round")
    assert validate_dataset(out) == []
    for table in TABLES:
        original = pd.read_parquet(dataset / table.file)
        rewritten = pd.read_parquet(out / table.file)
        assert len(original) == len(rewritten), table.name


def test_empty_model_writes_a_valid_dataset(tmp_path: Path) -> None:
    """An empty model writes a dataset that validates (every table is present)."""
    out = Model.empty().write(tmp_path / "empty")
    assert validate_dataset(out) == []


def test_append_and_replace(tmp_path: Path) -> None:
    """Rows can be appended and replaced programmatically."""
    model = Model.empty()
    model.append("tracks", {"track_id": 1, "name": "natural"})
    model.append("tracks", {"track_id": 2, "name": "managed"})
    assert len(model.table("tracks")) == 2
    model.replace(
        "tracks", model.table("tracks")["track_id"] == 2, {"track_id": 2, "name": "thinned"}
    )
    tracks = model.table("tracks").set_index("track_id")
    assert tracks.loc[2, "name"] == "thinned"
    assert len(model.table("tracks")) == 2
