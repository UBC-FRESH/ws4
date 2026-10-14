"""Compile a ForestModelXML recipe and a fragment inventory into the matrix dataset.

The matrix is a Model II model: the builder enumerates the reachable strata (unique
state-variable combinations) and expands each into a track, then connects treatments to
the target stratum's track (see ``notes/design/ws4-matrix-builder-and-interop.md``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from ..io.forest_model_xml import Recipe, parse_recipe
from ..model.schema import MANIFEST_NAME, SCHEMA_VERSION, TABLES, coerce_to_schema
from ..model.types import CanonicalDatasetManifest
from .expansion import expand_strata, state_of, state_variables, transition_key

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


def _curve_ids(recipe: Recipe) -> dict[str, int]:
    """Assign a stable integer id to every curve, in recipe order."""
    return {name: index for index, name in enumerate(recipe.curves, start=1)}


def _strata_expr(variables: Sequence[str], key: tuple[str, ...]) -> str:
    """Render a stratum as a strata expression such as ``status(C)+oper(Operable)``."""
    return "+".join(f"{name}({value})" for name, value in zip(variables, key, strict=True))


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
    variables = state_variables(recipe)

    records: list[dict[str, object]] = [
        {str(key): value for key, value in record.items()} for record in raw.to_dict("records")
    ]
    fragment_keys = [state_of(record, variables, recipe) for record in records]
    strata = expand_strata(fragment_keys, recipe)
    track_of: dict[tuple[str, ...], int] = {s.key: s.track_id for s in strata}

    fragments = pd.DataFrame(
        {
            "fragment_id": range(1, len(records) + 1),
            "block_id": raw[recipe.input_block].astype("int64"),
            "area_ha": raw[recipe.input_area].astype("float64"),
            "age": raw[recipe.input_age].astype("int64"),
            "track_id": [track_of.get(key, 0) for key in fragment_keys],
        },
        columns=list(_FRAGMENT_COLUMNS),
    )

    tracks = pd.DataFrame(
        [
            {"track_id": stratum.track_id, "name": _strata_expr(variables, stratum.key)}
            for stratum in strata
        ],
        columns=["track_id", "name"],
    )
    strata_table = pd.DataFrame(
        [
            {"track_id": stratum.track_id, "offset": 0, "next_age": recipe.horizon, "cycle": 0}
            for stratum in strata
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
    for stratum in strata:
        for select_index in stratum.select_indices:
            select = recipe.selects[select_index - 1]
            for attribute in select.features:
                if attribute.curve is None:
                    continue
                feature_rows.append(
                    {
                        "track_id": stratum.track_id,
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
                        "track_id": stratum.track_id,
                        "label": attribute.label,
                        "curve_id": curve_ids[attribute.curve],
                    }
                )
            for treatment in select.treatments:
                treatment_rows.append(
                    {
                        "track_id": stratum.track_id,
                        "begin": treatment.min_age,
                        "end": treatment.max_age,
                        "treatment": treatment.label,
                        "new_track": track_of.get(
                            transition_key(stratum.key, variables, treatment, recipe.constants), 0
                        ),
                        "offset": 0,
                        "retain": 0,
                    }
                )

    blocks = (
        fragments.groupby(["block_id", "track_id"], as_index=False)
        .agg(offset=("age", "min"), area_ha=("area_ha", "sum"))
        .loc[:, ["block_id", "track_id", "offset", "area_ha"]]
    )

    tables: dict[str, pd.DataFrame] = {
        "fragments": fragments,
        "blocks": blocks,
        "tracks": tracks,
        "strata": strata_table,
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
                    f"compiled {len(fragments)} fragments into {len(blocks)} block portions, "
                    f"{len(strata)} strata"
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
        options={"period_length": 1, "recipe": "ForestModelXML", "model": "II"},
    )
    (out_dir / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return out_dir
