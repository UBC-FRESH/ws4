"""Ingest a legacy matrix dataset into the WS4 schema.

A legacy dataset is a compiled matrix directory plus a fragments table. Its columns use
the established matrix names; this module maps them to the WS4 schema and records the
mapping in the manifest.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from ..model.schema import MANIFEST_NAME, SCHEMA_VERSION, TABLES, coerce_to_schema
from ..model.types import CanonicalDatasetManifest

LEGACY_MAPPING: dict[str, dict[str, str]] = {
    "blocks": {"BLOCK": "block_id", "TRACK": "track_id", "OFFSET": "offset", "AREA": "area_ha"},
    "tracks": {"TRACK": "track_id", "STRATA": "name"},
    "strata": {"TRACK": "track_id", "OFFSET": "offset", "NEXTAGE": "next_age", "CYCLE": "cycle"},
    "treatments": {
        "TRACK": "track_id",
        "BEGIN": "begin",
        "END": "end",
        "TREATMENT": "treatment",
        "NEWTRACK": "new_track",
        "OFFSET": "offset",
        "RETAIN": "retain",
    },
    "curves": {"CURVE": "curve_id", "X": "x", "Y": "y"},
    "features": {"TRACK": "track_id", "LABEL": "label", "CURVE": "curve_id"},
    "products": {
        "TRACK": "track_id",
        "TREATMENT": "treatment",
        "LABEL": "label",
        "CURVE": "curve_id",
    },
    "accounts": {"GROUP": "group", "ATTRIBUTE": "attribute", "ACCOUNT": "account"},
    "groups": {"BLOCK": "block_id", "GROUP": "group"},
    "messages": {"SEVERITY": "severity", "MESSAGE": "message"},
}

# The track table is usually ``tracknames.csv``; the rest share their table name.
LEGACY_FILES: dict[str, str] = {
    **{name: f"{name}.csv" for name in LEGACY_MAPPING},
    "tracks": "tracknames.csv",
}


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_mapped(path: Path, mapping: dict[str, str]) -> pd.DataFrame:
    """Read a legacy CSV and rename its columns to the schema names."""
    frame = pd.read_csv(path)
    present = {source: target for source, target in mapping.items() if source in frame.columns}
    return frame.rename(columns=present)[list(present.values())]


def ingest_legacy_matrix(matrix_dir: Path, fragments_path: Path, out_dir: Path) -> Path:
    """Ingest a legacy matrix dataset into the WS4 schema.

    Parameters
    ----------
    matrix_dir : Path
        Directory holding the legacy matrix CSV files.
    fragments_path : Path
        Path to the fragment inventory (CSV or Parquet), with the block, area, and age
        columns.
    out_dir : Path
        Directory to write the ingested dataset into.

    Returns
    -------
    Path
        The dataset directory.
    """
    matrix_dir = Path(matrix_dir)
    fragments_path = Path(fragments_path)
    out_dir = Path(out_dir)

    tables: dict[str, pd.DataFrame] = {}
    for name, filename in LEGACY_FILES.items():
        path = matrix_dir / filename
        if path.is_file():
            tables[name] = _read_mapped(path, LEGACY_MAPPING[name])

    blocks = tables["blocks"]
    if fragments_path.suffix.lower() in {".csv", ".txt"}:
        raw = pd.read_csv(fragments_path)
    else:
        raw = pd.read_parquet(fragments_path)
    block_track = dict(zip(blocks["block_id"].tolist(), blocks["track_id"].tolist(), strict=False))
    fragments = pd.DataFrame(
        {
            "fragment_id": range(1, len(raw) + 1),
            "block_id": raw["BLOCK"].astype(int),
            "area_ha": raw["AREA_HA"].astype(float),
            "age": raw["F_AGE"].astype(int),
            "track_id": [block_track.get(int(b), 0) for b in raw["BLOCK"]],
        }
    )
    tables["fragments"] = fragments

    out_dir.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        frame = tables.get(table.name, pd.DataFrame(columns=table.required_columns))
        coerce_to_schema(frame, table).to_parquet(out_dir / table.file, index=False)

    manifest = CanonicalDatasetManifest(
        schema_version=SCHEMA_VERSION,
        tables={table.name: table.file for table in TABLES},
        sources=[
            {"path": matrix_dir.name, "sha256": _sha256(matrix_dir / LEGACY_FILES["blocks"])},
            {"path": fragments_path.name, "sha256": _sha256(fragments_path)},
        ],
        options={"period_length": 1, "ingest": "legacy-matrix", "mapping": LEGACY_MAPPING},
    )
    (out_dir / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return out_dir
