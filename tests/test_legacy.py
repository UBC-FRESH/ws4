"""Tests for legacy matrix ingestion."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.build.legacy import ingest_legacy_matrix
from ws4.model.schema import validate_dataset

_LEGACY: dict[str, pd.DataFrame] = {
    "blocks.csv": pd.DataFrame({"BLOCK": [1], "TRACK": [1], "OFFSET": [0], "AREA": [5.0]}),
    "tracks.csv": pd.DataFrame({"TRACK": [1], "STRATA": ["all"]}),
    "strata.csv": pd.DataFrame({"TRACK": [1], "OFFSET": [0], "NEXTAGE": [100], "CYCLE": [0]}),
    "treatments.csv": pd.DataFrame(
        {
            "TRACK": [1],
            "BEGIN": [0],
            "END": [100],
            "TREATMENT": ["CC"],
            "NEWTRACK": [1],
            "OFFSET": [0],
            "RETAIN": [0],
        }
    ),
    "curves.csv": pd.DataFrame({"CURVE": [1, 1], "X": [0.0, 10.0], "Y": [0.0, 100.0]}),
    "features.csv": pd.DataFrame({"TRACK": [1], "LABEL": ["feature.Volume"], "CURVE": [1]}),
    "products.csv": pd.DataFrame(
        {"TRACK": [1], "TREATMENT": ["CC"], "LABEL": ["product.Volume"], "CURVE": [1]}
    ),
    "accounts.csv": pd.DataFrame(
        {"GROUP": ["forest"], "ATTRIBUTE": ["feature.Volume"], "ACCOUNT": ["feature.Volume"]}
    ),
    "groups.csv": pd.DataFrame({"BLOCK": [1], "GROUP": ["forest"]}),
    "messages.csv": pd.DataFrame({"SEVERITY": ["info"], "MESSAGE": ["ok"]}),
}


def _write_legacy(root: Path) -> tuple[Path, Path]:
    """Write a legacy matrix directory and a fragments file."""
    matrix = root / "matrix"
    matrix.mkdir()
    for name, frame in _LEGACY.items():
        frame.to_csv(matrix / name, index=False)
    fragments = root / "fragments.csv"
    pd.DataFrame({"BLOCK": [1], "AREA_HA": [5.0], "F_AGE": [10]}).to_csv(fragments, index=False)
    return matrix, fragments


def test_legacy_ingest_produces_a_valid_dataset(tmp_path: Path) -> None:
    """A legacy matrix ingests into a dataset that validates."""
    matrix, fragments = _write_legacy(tmp_path)
    dataset = ingest_legacy_matrix(matrix, fragments, tmp_path / "compiled")
    assert validate_dataset(dataset) == []


def test_legacy_ingest_maps_the_columns(tmp_path: Path) -> None:
    """The ingested tables carry the schema names and values."""
    matrix, fragments = _write_legacy(tmp_path)
    dataset = ingest_legacy_matrix(matrix, fragments, tmp_path / "compiled")
    blocks = pd.read_parquet(dataset / "blocks.parquet")
    assert list(blocks.columns) == ["block_id", "track_id", "offset", "area_ha"]
    assert blocks["area_ha"].iloc[0] == 5.0
    frags = pd.read_parquet(dataset / "fragments.parquet")
    assert frags["track_id"].iloc[0] == 1
