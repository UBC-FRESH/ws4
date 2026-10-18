"""Tests for legacy matrix ingestion."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.legacy import ingest_legacy_matrix
from ws4.model.schema import validate_dataset

_LEGACY: dict[str, pd.DataFrame] = {
    "blocks.csv": pd.DataFrame({"BLOCK": [1], "TRACK": [1], "OFFSET": [0], "AREA": [5.0]}),
    "tracknames.csv": pd.DataFrame({"TRACK": [1], "STRATA": ["all"]}),
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
        {
            "GROUP": ["forest"],
            "ATTRIBUTE": ["feature.Volume"],
            "ACCOUNT": ["feature.Volume"],
            "SUM": [1.0],
        }
    ),
    "protoaccounts.csv": pd.DataFrame(
        {
            "GROUP": ["forest"],
            "ATTRIBUTE": ["feature.Volume"],
            "ACCOUNT": ["feature.Volume"],
            "SUM": [1.0],
        }
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


def _write_split_matrix(root: Path) -> tuple[Path, Path, Path]:
    """Write a matrix that splits one block across two tracks, with and without a track column.

    Parameters
    ----------
    root : Path
        A scratch directory.

    Returns
    -------
    tuple of (Path, Path, Path)
        The matrix, a fragments file carrying the row's own track, and one that does not.
    """
    matrix = root / "matrix"
    matrix.mkdir()
    for name, frame in _LEGACY.items():
        frame.to_csv(matrix / name, index=False)
    # one block, two portions: 5 ha unmanaged on track 1, 3 ha managed on track 2, both at age 10
    pd.DataFrame(
        {
            "BLOCK": [1, 1],
            "TYPE": ["unmanaged", "managed"],
            "TRACK": [1, 2],
            "OFFSET": [10, 10],
            "AREA": [5.0, 3.0],
        }
    ).to_csv(matrix / "blocks.csv", index=False)
    with_track = root / "fragments_with_track.csv"
    pd.DataFrame(
        {"BLOCK": [1, 1], "AREA_HA": [5.0, 3.0], "F_AGE": [10, 10], "TRACK": [1, 2]}
    ).to_csv(with_track, index=False)
    without_track = root / "fragments_without_track.csv"
    pd.DataFrame({"BLOCK": [1, 1], "AREA_HA": [5.0, 3.0], "F_AGE": [10, 10]}).to_csv(
        without_track, index=False
    )
    return matrix, with_track, without_track


def test_a_split_block_keeps_the_track_of_its_own_row(tmp_path: Path) -> None:
    """Each portion of a split block keeps its own track, so its features are its own."""
    matrix, with_track, _without_track = _write_split_matrix(tmp_path)
    dataset = ingest_legacy_matrix(matrix, with_track, tmp_path / "compiled")
    fragments = pd.read_parquet(dataset / "fragments.parquet")
    assert list(fragments["track_id"]) == [1, 2]
    assert list(fragments["area_ha"]) == [5.0, 3.0]


def test_a_split_block_without_a_track_column_is_refused(tmp_path: Path) -> None:
    """An inventory that cannot name the track is refused rather than guessed at."""
    matrix, _with_track, without_track = _write_split_matrix(tmp_path)
    with pytest.raises(ValueError, match="needs a TRACK column"):
        ingest_legacy_matrix(matrix, without_track, tmp_path / "compiled")
