"""Tests for the compiled-dataset schema and validator."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from ws4.model.schema import MANIFEST_NAME, TABLES, validate_dataset
from ws4.model.types import CanonicalDatasetManifest

_EMPTY: dict[str, pd.DataFrame] = {
    "fragments": pd.DataFrame(
        {
            "fragment_id": [1, 2],
            "block_id": [1, 1],
            "area_ha": [3.0, 2.0],
            "age": [40, 60],
            "track_id": [1, 1],
        }
    ),
    "blocks": pd.DataFrame({"block_id": [1], "track_id": [1], "offset": [0], "area_ha": [5.0]}),
    "tracks": pd.DataFrame({"track_id": [1], "name": ["natural"]}),
    "strata": pd.DataFrame({"track_id": [1], "offset": [0], "next_age": [0], "cycle": [0]}),
    "treatments": pd.DataFrame(
        {
            "track_id": [1],
            "begin": [40],
            "end": [80],
            "treatment": ["CC"],
            "new_track": [1],
            "offset": [0],
            "retain": [0],
        }
    ),
    "curves": pd.DataFrame({"curve_id": [1, 1], "x": [0.0, 10.0], "y": [0.0, 1.0]}),
    "features": pd.DataFrame({"track_id": [1], "label": ["feature.Area"], "curve_id": [1]}),
    "products": pd.DataFrame(
        {"track_id": [1], "treatment": ["CC"], "label": ["product.Volume"], "curve_id": [1]}
    ),
    "protoaccounts": pd.DataFrame(
        {
            "group": ["all"],
            "attribute": ["feature.Area"],
            "account": ["feature.Area"],
            "sum": [1.0],
        }
    ),
    "accounts": pd.DataFrame(
        {
            "group": ["all"],
            "attribute": ["feature.Area"],
            "account": ["feature.Area"],
            "sum": [1.0],
        }
    ),
    "groups": pd.DataFrame({"block_id": [1], "group": ["forest"]}),
    "messages": pd.DataFrame({"severity": ["info"], "message": ["ok"]}),
}


def _write_dataset(root: Path, tables: dict[str, pd.DataFrame] | None = None) -> Path:
    """Write a dataset directory with a manifest and the given tables."""
    dataset = root / "compiled"
    dataset.mkdir()
    chosen = tables if tables is not None else _EMPTY
    for table in TABLES:
        frame = chosen[table.name]
        frame.to_parquet(dataset / table.file, index=False)
    manifest = CanonicalDatasetManifest(tables={t.name: t.file for t in TABLES})
    (dataset / MANIFEST_NAME).write_text(manifest.model_dump_json(), encoding="utf-8")
    return dataset


def test_valid_dataset_has_no_problems(tmp_path: Path) -> None:
    """A well-formed dataset validates cleanly."""
    assert validate_dataset(_write_dataset(tmp_path)) == []


def test_missing_manifest_is_reported(tmp_path: Path) -> None:
    """A dataset without a manifest is rejected."""
    dataset = _write_dataset(tmp_path)
    (dataset / MANIFEST_NAME).unlink()
    codes = {problem.code for problem in validate_dataset(dataset)}
    assert "DATASET-MISSING-MANIFEST" in codes


def test_wrong_schema_version_is_reported(tmp_path: Path) -> None:
    """A manifest with a different schema version is rejected."""
    dataset = _write_dataset(tmp_path)
    payload = json.loads((dataset / MANIFEST_NAME).read_text(encoding="utf-8"))
    payload["schema_version"] = "9.9"
    (dataset / MANIFEST_NAME).write_text(json.dumps(payload), encoding="utf-8")
    codes = {problem.code for problem in validate_dataset(dataset)}
    assert "DATASET-SCHEMA-VERSION" in codes


def test_missing_column_is_reported(tmp_path: Path) -> None:
    """A table missing a required column is rejected."""
    broken = dict(_EMPTY)
    broken["fragments"] = _EMPTY["fragments"].drop(columns=["age"])
    codes = {problem.code for problem in validate_dataset(_write_dataset(tmp_path, broken))}
    assert "DATASET-MISSING-COLUMN" in codes


def test_negative_area_is_reported(tmp_path: Path) -> None:
    """A negative fragment area is rejected."""
    broken = dict(_EMPTY)
    broken["fragments"] = _EMPTY["fragments"].assign(area_ha=[-1.0, 2.0])
    codes = {problem.code for problem in validate_dataset(_write_dataset(tmp_path, broken))}
    assert "DATASET-NEGATIVE-AREA" in codes


def test_unknown_block_is_reported(tmp_path: Path) -> None:
    """A fragment that references an unknown block is rejected."""
    broken = dict(_EMPTY)
    broken["fragments"] = _EMPTY["fragments"].assign(block_id=[1, 99])
    codes = {problem.code for problem in validate_dataset(_write_dataset(tmp_path, broken))}
    assert "DATASET-UNKNOWN-BLOCK" in codes


def test_non_monotonic_curve_is_reported(tmp_path: Path) -> None:
    """A curve whose x values are not strictly increasing is rejected."""
    broken = dict(_EMPTY)
    broken["curves"] = pd.DataFrame({"curve_id": [1, 1], "x": [10.0, 0.0], "y": [1.0, 0.0]})
    codes = {problem.code for problem in validate_dataset(_write_dataset(tmp_path, broken))}
    assert "DATASET-CURVE-DOMAIN" in codes
