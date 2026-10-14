"""Compile a ForestModelXML recipe and a fragment inventory into the matrix dataset."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from ..io.forest_model_xml import Recipe, Select, Term, Treatment, parse_recipe
from ..model.schema import MANIFEST_NAME, SCHEMA_VERSION, TABLES, coerce_to_schema
from ..model.types import CanonicalDatasetManifest

_FRAGMENT_COLUMNS = ("fragment_id", "block_id", "area_ha", "age", "track_id")


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


def _matches(terms: tuple[Term, ...], row: Mapping[str, object], constants: dict[str, str]) -> bool:
    """Return whether a select statement's terms match a row.

    A term the parser could not evaluate (``op == '?'``) is skipped, so matching is
    best-effort for statements that use the full expression language.
    """
    for term in terms:
        if term.op == "?":
            continue
        if term.field not in row:
            return False
        actual = str(row[term.field])
        expected = constants.get(term.value, term.value) if term.op == "in" else term.value
        if term.op in ("eq", "in"):
            if actual != expected:
                return False
        elif term.op == "ne":
            if actual == expected:
                return False
        else:
            try:
                left, right = float(actual), float(expected)
            except ValueError:
                return False
            if (term.op == "lt" and not left < right) or (term.op == "le" and not left <= right):
                return False
            if (term.op == "gt" and not left > right) or (term.op == "ge" and not left >= right):
                return False
    return True


def _track_for(
    row: Mapping[str, object], selects: tuple[Select, ...], constants: dict[str, str]
) -> int:
    """Return the one-based track id of the first matching select, or 0."""
    for index, select in enumerate(selects, start=1):
        if _matches(select.terms, row, constants):
            return index
    return 0


def _target_track(
    select: Select, treatment: Treatment, selects: tuple[Select, ...], constants: dict[str, str]
) -> int:
    """Return the one-based track id a treatment transitions to, or 0 for none."""
    state: dict[str, object] = {
        term.field: constants.get(term.value, term.value) if term.op == "in" else term.value
        for term in select.terms
        if term.op in ("eq", "in")
    }
    state.update(treatment.transition)
    for index, candidate in enumerate(selects, start=1):
        if _matches(candidate.terms, state, constants):
            return index
    return 0


def _curve_ids(recipe: Recipe) -> dict[str, int]:
    """Assign a stable integer id to every curve, in recipe order."""
    return {name: index for index, name in enumerate(recipe.curves, start=1)}


def build_canonical_dataset(xml_path: Path, fragments_path: Path, out_dir: Path) -> Path:
    """Compile a ForestModelXML recipe and a fragment inventory into a matrix dataset.

    Parameters
    ----------
    xml_path : Path
        Path to the ForestModelXML recipe.
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
    recipe = parse_recipe(xml_path)
    raw = _read_fragments(fragments_path)
    curve_ids = _curve_ids(recipe)

    fragments = pd.DataFrame(
        {
            "fragment_id": range(1, len(raw) + 1),
            "block_id": raw[recipe.input_block].astype("int64"),
            "area_ha": raw[recipe.input_area].astype("float64"),
            "age": raw[recipe.input_age].astype("int64"),
            "track_id": [
                _track_for(
                    {str(key): value for key, value in record.items()},
                    recipe.selects,
                    recipe.constants,
                )
                for record in raw.to_dict("records")
            ],
        },
        columns=list(_FRAGMENT_COLUMNS),
    )

    tracks = pd.DataFrame(
        [
            {"track_id": index, "name": select.statement}
            for index, select in enumerate(recipe.selects, start=1)
        ],
        columns=["track_id", "name"],
    )
    strata = pd.DataFrame(
        [
            {"track_id": index, "offset": 0, "next_age": recipe.horizon, "cycle": 0}
            for index in range(1, len(recipe.selects) + 1)
        ],
        columns=["track_id", "offset", "next_age", "cycle"],
    )
    curves = pd.DataFrame(
        [
            {"curve_id": curve_ids[name], "x": x, "y": y}
            for name, points in recipe.curves.items()
            for x, y in points
        ],
        columns=["curve_id", "x", "y"],
    )

    feature_rows: list[dict[str, object]] = []
    product_rows: list[dict[str, object]] = []
    treatment_rows: list[dict[str, object]] = []
    account_rows: list[dict[str, object]] = []
    for index, select in enumerate(recipe.selects, start=1):
        for attribute in select.features:
            if attribute.curve is None:
                continue
            feature_rows.append(
                {
                    "track_id": index,
                    "label": attribute.label,
                    "curve_id": curve_ids[attribute.curve],
                }
            )
            account_rows.append(
                {"group": "forest", "attribute": attribute.label, "account": attribute.label}
            )
        for attribute in select.products:
            if attribute.curve is None:
                continue
            product_rows.append(
                {
                    "track_id": index,
                    "label": attribute.label,
                    "curve_id": curve_ids[attribute.curve],
                }
            )
        for treatment in select.treatments:
            treatment_rows.append(
                {
                    "track_id": index,
                    "begin": treatment.min_age,
                    "end": treatment.max_age,
                    "treatment": treatment.label,
                    "new_track": _target_track(select, treatment, recipe.selects, recipe.constants),
                    "offset": 0,
                    "retain": 0,
                }
            )

    blocks = fragments.groupby("block_id", as_index=False).agg(
        track_id=("track_id", "first"), area_ha=("area_ha", "sum")
    )
    blocks["offset"] = 0

    tables: dict[str, pd.DataFrame] = {
        "fragments": fragments,
        "blocks": blocks[["block_id", "track_id", "offset", "area_ha"]],
        "tracks": tracks,
        "strata": strata,
        "treatments": pd.DataFrame(
            treatment_rows,
            columns=["track_id", "begin", "end", "treatment", "new_track", "offset", "retain"],
        ),
        "curves": curves,
        "features": pd.DataFrame(feature_rows, columns=["track_id", "label", "curve_id"]),
        "products": pd.DataFrame(
            product_rows, columns=["track_id", "treatment", "label", "curve_id"]
        ),
        "accounts": pd.DataFrame(account_rows, columns=["group", "attribute", "account"]),
        "groups": pd.DataFrame({"block_id": blocks["block_id"], "group": "forest"}),
        "messages": pd.DataFrame(
            {
                "severity": ["info"],
                "message": [
                    f"compiled {len(fragments)} fragments into {len(blocks)} blocks, "
                    f"{len(recipe.selects)} tracks"
                ],
            }
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        coerce_to_schema(tables[table.name], table).to_parquet(out_dir / table.file, index=False)

    manifest = CanonicalDatasetManifest(
        schema_version=SCHEMA_VERSION,
        tables={table.name: table.file for table in TABLES},
        sources=[
            {"path": xml_path.name, "sha256": _sha256(xml_path)},
            {"path": fragments_path.name, "sha256": _sha256(fragments_path)},
        ],
        options={"period_length": 1, "recipe": "ForestModelXML"},
    )
    (out_dir / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return out_dir
