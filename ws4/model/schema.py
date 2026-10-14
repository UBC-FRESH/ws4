"""Compiled-dataset schema and validation for WS4.

The compiled matrix dataset is the runtime contract (see ``notes/adr/0002`` and
``notes/adr/0006``). This module defines the tables, the manifest, and a validator
that checks a dataset against both.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from pandas.api import types as ptypes

from .types import CanonicalDatasetManifest

SCHEMA_VERSION = "0.1"
MANIFEST_NAME = "manifest.json"

Kind = Literal["integer", "number", "string", "boolean"]


@dataclass(frozen=True)
class Column:
    """One column of a matrix table.

    Attributes
    ----------
    name : str
        Column name.
    kind : {"integer", "number", "string", "boolean"}
        Expected value kind.
    """

    name: str
    kind: Kind


@dataclass(frozen=True)
class Table:
    """One table of the compiled matrix dataset.

    Attributes
    ----------
    name : str
        Logical table name, as used in the manifest.
    file : str
        File name inside the dataset directory.
    columns : tuple of Column
        The required columns.
    """

    name: str
    file: str
    columns: tuple[Column, ...]

    @property
    def required_columns(self) -> tuple[str, ...]:
        """Return the required column names."""
        return tuple(column.name for column in self.columns)


TABLES: tuple[Table, ...] = (
    Table(
        "fragments",
        "fragments.parquet",
        (
            Column("fragment_id", "integer"),
            Column("block_id", "integer"),
            Column("area_ha", "number"),
            Column("age", "integer"),
            Column("track_id", "integer"),
        ),
    ),
    Table(
        "blocks",
        "blocks.parquet",
        (
            Column("block_id", "integer"),
            Column("track_id", "integer"),
            Column("offset", "integer"),
            Column("area_ha", "number"),
        ),
    ),
    Table(
        "tracks",
        "tracks.parquet",
        (
            Column("track_id", "integer"),
            Column("name", "string"),
        ),
    ),
    Table(
        "strata",
        "strata.parquet",
        (
            Column("track_id", "integer"),
            Column("offset", "integer"),
            Column("next_age", "integer"),
            Column("cycle", "integer"),
        ),
    ),
    Table(
        "treatments",
        "treatments.parquet",
        (
            Column("track_id", "integer"),
            Column("begin", "integer"),
            Column("end", "integer"),
            Column("treatment", "string"),
            Column("new_track", "integer"),
            Column("offset", "integer"),
            Column("retain", "integer"),
        ),
    ),
    Table(
        "curves",
        "curves.parquet",
        (
            Column("curve_id", "integer"),
            Column("x", "number"),
            Column("y", "number"),
        ),
    ),
    Table(
        "features",
        "features.parquet",
        (
            Column("track_id", "integer"),
            Column("label", "string"),
            Column("curve_id", "integer"),
        ),
    ),
    Table(
        "products",
        "products.parquet",
        (
            Column("track_id", "integer"),
            Column("treatment", "string"),
            Column("label", "string"),
            Column("curve_id", "integer"),
        ),
    ),
    Table(
        "protoaccounts",
        "protoaccounts.parquet",
        (
            Column("group", "string"),
            Column("attribute", "string"),
            Column("account", "string"),
            Column("sum", "number"),
        ),
    ),
    Table(
        "accounts",
        "accounts.parquet",
        (
            Column("group", "string"),
            Column("attribute", "string"),
            Column("account", "string"),
            Column("sum", "number"),
        ),
    ),
    Table(
        "groups",
        "groups.parquet",
        (
            Column("block_id", "integer"),
            Column("group", "string"),
        ),
    ),
    Table(
        "messages",
        "messages.parquet",
        (
            Column("severity", "string"),
            Column("message", "string"),
        ),
    ),
)

TABLES_BY_NAME: dict[str, Table] = {table.name: table for table in TABLES}

_KIND_CHECKS = {
    "integer": ptypes.is_integer_dtype,
    "number": ptypes.is_numeric_dtype,
    "string": ptypes.is_string_dtype,
    "boolean": ptypes.is_bool_dtype,
}


def coerce_to_schema(frame: pd.DataFrame, table: Table) -> pd.DataFrame:
    """Coerce a frame's required columns to the schema kinds.

    Parameters
    ----------
    frame : pandas.DataFrame
        The frame to coerce. A missing required column is added empty.
    table : Table
        The table schema.

    Returns
    -------
    pandas.DataFrame
        The frame with its required columns typed.
    """
    result = frame.copy()
    for column in table.columns:
        series = (
            result[column.name] if column.name in result.columns else pd.Series(dtype="float64")
        )
        if column.kind == "string":
            result[column.name] = series.astype("string")
        elif column.kind == "boolean":
            result[column.name] = series.astype("bool")
        elif column.kind == "integer":
            result[column.name] = pd.to_numeric(series).astype("int64")
        else:
            result[column.name] = pd.to_numeric(series).astype("float64")
    return result


@dataclass(frozen=True)
class Problem:
    """One validation finding.

    Attributes
    ----------
    code : str
        Stable finding code, such as ``DATASET-MISSING-COLUMN``.
    where : str
        The file or field the finding applies to.
    message : str
        A human-readable description.
    """

    code: str
    where: str
    message: str


def load_manifest(dataset_dir: Path) -> CanonicalDatasetManifest:
    """Load and parse the manifest of a dataset.

    Parameters
    ----------
    dataset_dir : Path
        The dataset directory.

    Returns
    -------
    CanonicalDatasetManifest
        The parsed manifest.

    Raises
    ------
    FileNotFoundError
        When the manifest is missing.
    """
    manifest_path = dataset_dir / MANIFEST_NAME
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return CanonicalDatasetManifest.model_validate(raw)


def dataset_reference(dataset_dir: Path) -> dict[str, object]:
    """Return a reference to a compiled dataset, for a run record.

    A run directory records this so that the dataset that produced it can be identified and
    audited: the schema version, the source hashes, and the SHA-256 of the manifest file.

    Parameters
    ----------
    dataset_dir : Path
        The dataset directory.

    Returns
    -------
    dict of str to object
        The reference, or an empty mapping when the manifest is missing.
    """
    manifest_path = Path(dataset_dir) / MANIFEST_NAME
    if not manifest_path.is_file():
        return {}
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    return {
        "schema_version": manifest.get("schema_version"),
        "sources": manifest.get("sources", []),
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _check_table(table: Table, dataset_dir: Path) -> list[Problem]:
    """Check one table for presence, columns, and kinds.

    Parameters
    ----------
    table : Table
        The table schema.
    dataset_dir : Path
        The dataset directory.

    Returns
    -------
    list of Problem
        The findings for this table.
    """
    problems: list[Problem] = []
    path = dataset_dir / table.file
    if not path.is_file():
        problems.append(Problem("DATASET-MISSING-TABLE", table.name, f"missing file {table.file}"))
        return problems
    frame = pd.read_parquet(path)
    for column in table.columns:
        if column.name not in frame.columns:
            problems.append(
                Problem("DATASET-MISSING-COLUMN", table.name, f"missing column {column.name}")
            )
            continue
        check = _KIND_CHECKS[column.kind]
        if not check(frame[column.name]):
            problems.append(
                Problem(
                    "DATASET-COLUMN-KIND",
                    f"{table.name}.{column.name}",
                    f"expected a {column.kind} column",
                )
            )
    return problems


def _check_invariants(dataset_dir: Path) -> list[Problem]:
    """Check the cross-table and value invariants.

    Parameters
    ----------
    dataset_dir : Path
        The dataset directory.

    Returns
    -------
    list of Problem
        The invariant findings.
    """
    problems: list[Problem] = []
    frames = {
        name: pd.read_parquet(dataset_dir / f"{name}.parquet")
        for name in (
            "fragments",
            "blocks",
            "tracks",
            "strata",
            "treatments",
            "curves",
            "features",
            "products",
        )
    }
    fragments = frames["fragments"]
    blocks = frames["blocks"]
    tracks = frames["tracks"]
    curves = frames["curves"]

    if (fragments["area_ha"] < 0).any():
        problems.append(
            Problem("DATASET-NEGATIVE-AREA", "fragments", "area_ha must be non-negative")
        )
    if (fragments["age"] < 0).any():
        problems.append(Problem("DATASET-NEGATIVE-AGE", "fragments", "age must be non-negative"))
    if (blocks["area_ha"] < 0).any():
        problems.append(Problem("DATASET-NEGATIVE-AREA", "blocks", "area_ha must be non-negative"))

    unknown_blocks = set(fragments["block_id"]) - set(blocks["block_id"])
    if unknown_blocks:
        sample = sorted(unknown_blocks)[:5]
        problems.append(
            Problem("DATASET-UNKNOWN-BLOCK", "fragments", f"block_id not in blocks: {sample}")
        )

    # Every table that names a track must name a real one.
    track_ids = set(tracks["track_id"])
    for name in ("blocks", "strata", "treatments", "features", "products"):
        unknown = set(frames[name]["track_id"]) - track_ids
        if unknown:
            sample = sorted(unknown)[:5]
            problems.append(
                Problem("DATASET-UNKNOWN-TRACK", name, f"track_id not in tracks: {sample}")
            )
    # A treatment's target track is a real track, or 0 for no transition.
    unknown_new = set(frames["treatments"]["new_track"]) - track_ids - {0}
    if unknown_new:
        sample = sorted(unknown_new)[:5]
        problems.append(
            Problem("DATASET-UNKNOWN-TRACK", "treatments", f"new_track not in tracks: {sample}")
        )
    # Every feature and product curve must exist.
    curve_ids = set(curves["curve_id"])
    for name in ("features", "products"):
        unknown = set(frames[name]["curve_id"]) - curve_ids
        if unknown:
            sample = sorted(unknown)[:5]
            problems.append(
                Problem("DATASET-UNKNOWN-CURVE", name, f"curve_id not in curves: {sample}")
            )

    for curve_id, group in curves.groupby("curve_id", sort=True):
        if not group["x"].is_monotonic_increasing or group["x"].duplicated().any():
            problems.append(
                Problem(
                    "DATASET-CURVE-DOMAIN",
                    "curves",
                    f"curve {curve_id} x values must be strictly increasing",
                )
            )
    return problems


def validate_dataset(dataset_dir: Path) -> list[Problem]:
    """Validate a compiled dataset against its manifest and the schema.

    Parameters
    ----------
    dataset_dir : Path
        The dataset directory.

    Returns
    -------
    list of Problem
        Every finding. An empty list means the dataset is valid.
    """
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_dir():
        return [Problem("DATASET-MISSING", str(dataset_dir), "dataset directory not found")]
    try:
        manifest = load_manifest(dataset_dir)
    except FileNotFoundError:
        return [Problem("DATASET-MISSING-MANIFEST", str(dataset_dir), f"missing {MANIFEST_NAME}")]
    except ValueError as exc:  # pydantic validation error
        return [Problem("DATASET-BAD-MANIFEST", MANIFEST_NAME, str(exc))]

    problems: list[Problem] = []
    if manifest.schema_version != SCHEMA_VERSION:
        problems.append(
            Problem(
                "DATASET-SCHEMA-VERSION",
                MANIFEST_NAME,
                f"schema_version {manifest.schema_version} != {SCHEMA_VERSION}",
            )
        )
    for table in TABLES:
        if table.name not in manifest.tables:
            problems.append(
                Problem("DATASET-UNLISTED-TABLE", MANIFEST_NAME, f"{table.name} is not listed")
            )
        problems.extend(_check_table(table, dataset_dir))
    if not problems:
        problems.extend(_check_invariants(dataset_dir))
    return problems
