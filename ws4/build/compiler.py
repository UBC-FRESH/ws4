"""Compile a recipe and a fragment inventory into the matrix dataset."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from ..io.forest_model_xml import ForestModelImporter
from ..model.schema import MANIFEST_NAME, SCHEMA_VERSION, TABLES
from ..model.types import CanonicalDatasetManifest

_FRAGMENT_COLUMNS = ("fragment_id", "block_id", "area_ha", "age", "track_id")

_RECIPE_COLUMNS: dict[str, tuple[str, ...]] = {
    "tracks": ("track_id", "name"),
    "strata": ("track_id", "offset", "next_age", "cycle"),
    "treatments": ("track_id", "begin", "end", "treatment", "new_track", "offset", "retain"),
    "curves": ("curve_id", "x", "y"),
    "features": ("track_id", "label", "curve_id"),
    "products": ("track_id", "treatment", "label", "curve_id"),
}


def _frame(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> pd.DataFrame:
    """Build a DataFrame with a fixed column set, even when there are no rows."""
    return pd.DataFrame(rows, columns=list(columns))


def _read_fragments(path: Path) -> pd.DataFrame:
    """Read a fragment inventory from CSV or Parquet."""
    if path.suffix.lower() in {".csv", ".txt"}:
        return pd.read_csv(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"unsupported fragment inventory format: {path.suffix}")


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_canonical_dataset(xml_path: Path, fragments_path: Path, out_dir: Path) -> Path:
    """Compile a canonical dataset from a recipe and a fragment inventory.

    Parameters
    ----------
    xml_path : Path
        Path to the forest-model XML recipe.
    fragments_path : Path
        Path to the fragment inventory, as CSV or Parquet.
    out_dir : Path
        Directory to write the compiled dataset into.

    Returns
    -------
    Path
        The dataset directory.
    """
    xml_path = Path(xml_path)
    fragments_path = Path(fragments_path)
    out_dir = Path(out_dir)

    recipe = ForestModelImporter(xml_path).parse()
    fragments = _read_fragments(fragments_path)[list(_FRAGMENT_COLUMNS)].copy()

    blocks = fragments.groupby("block_id", as_index=False).agg(
        track_id=("track_id", "first"), area_ha=("area_ha", "sum")
    )
    blocks["offset"] = 0

    features = _frame(recipe["features"], _RECIPE_COLUMNS["features"])
    tables: dict[str, pd.DataFrame] = {
        "fragments": fragments,
        "blocks": blocks[["block_id", "track_id", "offset", "area_ha"]],
        "tracks": _frame(recipe["tracks"], _RECIPE_COLUMNS["tracks"]),
        "strata": _frame(recipe["strata"], _RECIPE_COLUMNS["strata"]),
        "treatments": _frame(recipe["treatments"], _RECIPE_COLUMNS["treatments"]),
        "curves": _frame(recipe["curves"], _RECIPE_COLUMNS["curves"]),
        "features": features,
        "products": _frame(recipe["products"], _RECIPE_COLUMNS["products"]),
        "accounts": pd.DataFrame(
            {
                "group": ["forest"] * len(features),
                "attribute": features["label"].astype("string"),
                "account": features["label"].astype("string"),
            }
        ),
        "groups": pd.DataFrame({"block_id": blocks["block_id"], "group": "forest"}),
        "messages": pd.DataFrame(
            {
                "severity": ["info"],
                "message": [f"compiled {len(fragments)} fragments into {len(blocks)} blocks"],
            }
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        tables[table.name].to_parquet(out_dir / table.file, index=False)

    manifest = CanonicalDatasetManifest(
        schema_version=SCHEMA_VERSION,
        tables={table.name: table.file for table in TABLES},
        sources=[
            {"path": xml_path.name, "sha256": _sha256(xml_path)},
            {"path": fragments_path.name, "sha256": _sha256(fragments_path)},
        ],
        options={"period_length": 1},
    )
    (out_dir / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return out_dir
