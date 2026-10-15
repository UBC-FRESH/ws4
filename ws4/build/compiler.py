"""Compile a ForestModelXML recipe and a fragment inventory into the matrix dataset.

The matrix is a Model II model: the builder enumerates the reachable strata (unique
state-variable combinations) and expands each into a track, then connects treatments to
the target stratum's track (see ``notes/design/ws4-matrix-builder-and-interop.md``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict

import pandas as pd

from ..io.expressions import ExpressionError, evaluate_value
from ..io.forest_model_xml import Attribute, Recipe, Retention, parse_recipe
from ..io.fragments import read_fragments
from ..model.schema import MANIFEST_NAME, SCHEMA_VERSION, TABLES, coerce_to_schema
from ..model.types import CanonicalDatasetManifest
from .expansion import (
    expand_strata,
    matching_selects,
    resolve_value,
    state_of,
    state_variables,
    transition_key,
)

_FRAGMENT_COLUMNS = ("fragment_id", "block_id", "area_ha", "age", "track_id")


class _Portion(TypedDict):
    """An area portion of a fragment, with its stratum key."""

    block_id: int
    area_ha: float
    age: int
    key: tuple[str, ...]


def _read_fragments(path: Path) -> pd.DataFrame:
    """Read a fragment inventory from a shapefile, CSV, or Parquet."""
    return read_fragments(path)


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _curve_ids(recipe: Recipe) -> dict[str, int]:
    """Assign a stable integer id to every curve, in recipe order."""
    return {name: index for index, name in enumerate(recipe.curves, start=1)}


def _strata_expr(variables: Sequence[str], key: tuple[str, ...]) -> str:
    """Render a stratum as a strata expression such as ``status(C)+oper(Operable)``."""
    return "+".join(f"{name}({value})" for name, value in zip(variables, key, strict=True))


def _input_value(
    expression: str, record: Mapping[str, object], constants: dict[str, str]
) -> object:
    """Resolve an ``<input>`` expression against a fragment row.

    A plain column name is read directly; an expression such as ``Int(RES_KEY)`` or
    ``Shape_Area/10000`` is evaluated against the row.
    """
    if expression in record:
        return record[expression]
    try:
        return evaluate_value(expression, record, constants)
    except ExpressionError:
        return record.get(expression)


def _managed_value(row: Mapping[str, object], constants: dict[str, str]) -> str:
    """Return the managed/unmanaged value for a stratum.

    A model may carry an ``IFM`` field; otherwise the value is derived from the status
    field and the ``managed`` constant.
    """
    if "IFM" in row:
        return str(row["IFM"])
    managed = constants.get("managed", "C")
    return "managed" if str(row.get("status", "")) == managed else "unmanaged"


def _expand_tokens(
    text: str, row: Mapping[str, object], kind: str, constants: dict[str, str]
) -> str:
    """Replace a label or expression's ``%f``, ``%m``, ``%au``, and ``%s`` tokens.

    ``%f`` becomes the attribute's kind (``feature`` or ``product``), ``%m`` the
    managed/unmanaged value, and ``%au`` / ``%s`` the analysis unit and species.
    """
    return (
        text.replace("%f", kind)
        .replace("%m", _managed_value(row, constants))
        .replace("%au", str(row.get("au", "")))
        .replace("%s", str(row.get("species", "")))
    )


def _expand_label(
    label: str, row: Mapping[str, object], kind: str, constants: dict[str, str]
) -> str:
    """Expand a label's ``%f`` and ``%m`` tokens, and evaluate a label expression.

    A label that is an expression (for example ``'%f.area.%m.state.'+if(...)`` or
    ``'product.area.managed.state.'+statecode``) is evaluated against the row.
    """
    text = _expand_tokens(label, row, kind, constants)
    if "+" in text or "if(" in text:
        try:
            return str(evaluate_value(text, row, constants))
        except ExpressionError:
            return text
    return text


def _factor_value(attribute: object, row: Mapping[str, object], constants: dict[str, str]) -> float:
    """Evaluate an attribute's factor expression, defaulting to 1.0."""
    factor = getattr(attribute, "factor", None)
    if factor is None:
        return 1.0
    try:
        return float(str(evaluate_value(factor, row, constants)))
    except (ExpressionError, ValueError):
        return 1.0


def _expression_curve(
    recipe: Recipe,
    variables: Sequence[str],
    key: tuple[str, ...],
    expression: str,
    kind: str,
    attributes: dict[str, str] | None = None,
    treatment: str = "",
) -> str | None:
    """Evaluate an attribute's curve expression to a curve name or a number string.

    ``%f`` / ``%m`` / ``%au`` / ``%s`` tokens are expanded first, and
    ``attribute('label')`` resolves against ``attributes`` (the labels already emitted
    for this stratum). The result is a curve name, a number, or None when the
    expression cannot be evaluated.
    """
    row = dict(zip(variables, key, strict=True))
    if treatment:
        row["treatment"] = treatment
    text = _expand_tokens(expression, row, kind, recipe.constants)
    try:
        return str(evaluate_value(text, row, recipe.constants, attributes))
    except ExpressionError:
        return None


def _retained_key(
    key: tuple[str, ...],
    variables: Sequence[str],
    retention: Retention,
    constants: dict[str, str],
) -> tuple[str, ...]:
    """Return the state key a retention rule moves its area to."""
    state = dict(zip(variables, key, strict=True))
    for name, value in retention.assigns.items():
        state[name] = resolve_value(value, state, constants)
    return tuple(state.get(name, "") for name in variables)


def _account_group(states: set[str]) -> str:
    """Return the account group for a label's producing selects.

    A label produced only by managed selects belongs to ``_MANAGED_``, only by unmanaged
    selects to ``_UNMANAGED_``, and otherwise to ``_ALL_``.
    """
    if states == {"managed"}:
        return "_MANAGED_"
    if states == {"unmanaged"}:
        return "_UNMANAGED_"
    return "_ALL_"


def _as_float(value: object) -> float:
    """Convert a value to a float, or 0.0 when it is not numeric."""
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _retention_factor(
    expression: str, record: Mapping[str, object], constants: dict[str, str]
) -> float:
    """Evaluate a retention factor to a value in ``[0, 1]``.

    The factor is a literal number (for example ``0.1``), a fragment column, or an
    expression. A factor that cannot be evaluated is treated as zero.
    """
    value: object
    if expression in record:
        value = record[expression]
    else:
        try:
            value = evaluate_value(expression, record, constants)
        except ExpressionError:
            value = 0.0
    return min(max(_as_float(value), 0.0), 1.0)


def _retention_split(
    record: Mapping[str, object], key: tuple[str, ...], variables: Sequence[str], recipe: Recipe
) -> tuple[float, tuple[str, ...]] | None:
    """Return the retention factor and the retained state key, or None."""
    for index in matching_selects(key, variables, recipe.selects, recipe.constants):
        retention = recipe.selects[index - 1].retention
        if retention is None:
            continue
        factor = (
            _retention_factor(retention.factor, record, recipe.constants)
            if retention.factor
            else 0.0
        )
        state = dict(zip(variables, key, strict=True))
        for name, value in retention.assigns.items():
            state[name] = resolve_value(value, state, recipe.constants)
        return factor, tuple(state.get(name, "") for name in variables)
    return None


def _portions(
    record: Mapping[str, object], variables: Sequence[str], recipe: Recipe
) -> list[_Portion]:
    """Split a fragment into area portions by its retention rule.

    The retained fraction moves to the state the retention rule assigns (for
    example, ``IFM = unmanaged``); the rest keeps the fragment's own state.
    """
    key = state_of(record, variables, recipe)
    block_id = int(_as_float(_input_value(recipe.input_block, record, recipe.constants)))
    area = _as_float(_input_value(recipe.input_area, record, recipe.constants))
    age = int(_as_float(_input_value(recipe.input_age, record, recipe.constants)))
    split = _retention_split(record, key, variables, recipe)
    if split is None:
        return [_Portion(block_id=block_id, area_ha=area, age=age, key=key)]
    factor, retained_key = split
    rows: list[_Portion] = []
    if factor < 1.0:
        rows.append(_Portion(block_id=block_id, area_ha=area * (1.0 - factor), age=age, key=key))
    if factor > 0.0:
        rows.append(_Portion(block_id=block_id, area_ha=area * factor, age=age, key=retained_key))
    return rows


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
    portions = [portion for record in records for portion in _portions(record, variables, recipe)]
    fragment_keys = [portion["key"] for portion in portions]
    strata = expand_strata(fragment_keys, recipe)
    track_of: dict[tuple[str, ...], int] = {s.key: s.track_id for s in strata}

    fragments = pd.DataFrame(
        {
            "fragment_id": range(1, len(portions) + 1),
            "block_id": [portion["block_id"] for portion in portions],
            "area_ha": [portion["area_ha"] for portion in portions],
            "age": [portion["age"] for portion in portions],
            "track_id": [track_of.get(portion["key"], 0) for portion in portions],
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
    curve_rows: list[dict[str, object]] = [
        {"curve_id": curve_ids[name], "x": x, "y": y}
        for name, points in recipe.curves.items()
        for x, y in points
    ]
    scaled_ids: dict[tuple[str, float], int] = {}
    constant_ids: dict[float, int] = {}
    next_curve = [len(curve_ids) + 1]

    def curve_for(base_name: str, factor: float) -> int:
        """Return a base curve's id, or a scaled copy when the factor is not 1."""
        if factor == 1.0:
            return curve_ids[base_name]
        key = (base_name, round(factor, 6))
        if key in scaled_ids:
            return scaled_ids[key]
        curve_id = next_curve[0]
        next_curve[0] += 1
        scaled_ids[key] = curve_id
        for x, y in recipe.curves[base_name]:
            curve_rows.append({"curve_id": curve_id, "x": x, "y": y * factor})
        return curve_id

    def constant_curve(value: float) -> int:
        """Return the id of a constant-valued curve, creating it on first use."""
        key = round(value, 9)
        if key in constant_ids:
            return constant_ids[key]
        curve_id = next_curve[0]
        next_curve[0] += 1
        constant_ids[key] = curve_id
        curve_rows.append({"curve_id": curve_id, "x": 0.0, "y": key})
        return curve_id

    def resolve_curve(
        attribute: Attribute,
        key: tuple[str, ...],
        kind: str,
        attributes: dict[str, str],
        treatment: str = "",
    ) -> tuple[int | None, str | None]:
        """Resolve an attribute to a curve id and, when it names one, its curve name.

        A ``<curve idref>`` resolves to that curve; an expression resolves to a curve
        name (an existing recipe curve) or, when it evaluates to a number, to a constant
        curve. The name is returned so a later ``attribute('label')`` can resolve to it.
        """
        row = dict(zip(variables, key, strict=True))
        if treatment:
            row["treatment"] = treatment
        factor = _factor_value(attribute, row, recipe.constants)
        if attribute.curve is not None:
            return curve_for(attribute.curve, factor), attribute.curve
        if attribute.expression is None:
            return None, None
        result = _expression_curve(
            recipe, variables, key, attribute.expression, kind, attributes, treatment
        )
        if result is None:
            return None, None
        if result in curve_ids:
            return curve_for(result, factor), result
        try:
            return constant_curve(float(result) * factor), None
        except ValueError:
            return None, None

    feature_rows: list[dict[str, object]] = []
    product_rows: list[dict[str, object]] = []
    treatment_rows: list[dict[str, object]] = []
    # A product select with no ``treatment eq`` context applies to every treatment its
    # track offers, so each product is tagged with each of those treatments.
    treatments_of_track: dict[int, list[str]] = {}
    for stratum in strata:
        labels: list[str] = []
        for select_index in stratum.select_indices:
            labels.extend(
                treatment.label for treatment in recipe.selects[select_index - 1].treatments
            )
        treatments_of_track[stratum.track_id] = labels
    # The Matrix Builder writes a simple summary account for every attribute, with the
    # account name identical to the attribute name (see the user guide, "Creating Summary
    # Accounts"). The user copies ``protoaccounts`` to ``accounts`` and edits it; a re-run
    # must not overwrite that edited copy. Each label records the managed state(s) of the
    # selects that produce it, which determines its account group.
    account_labels: dict[str, set[str]] = {}
    for stratum in strata:
        row = dict(zip(variables, stratum.key, strict=True))
        managed = _managed_value(row, recipe.constants)
        # The curve each feature label already resolved to for this stratum, so an
        # expression such as ``operable(attribute('feature.yield.managed.total'))`` can
        # resolve to the same curve the base attribute used.
        label_curves: dict[str, str] = {}
        for select_index in stratum.select_indices:
            select = recipe.selects[select_index - 1]
            for attribute in select.features:
                curve_id, curve_name = resolve_curve(
                    attribute, stratum.key, "feature", label_curves
                )
                if curve_id is None:
                    continue
                label = _expand_label(attribute.label, row, "feature", recipe.constants)
                if curve_name is not None:
                    label_curves[label] = curve_name
                feature_rows.append(
                    {"track_id": stratum.track_id, "label": label, "curve_id": curve_id}
                )
                account_labels.setdefault(label, set()).add(managed)
            # A retention rule's features describe the retained fraction, so they attach
            # to the stratum the rule moves the area to, not to the select's own stratum.
            if select.retention is not None:
                retained = _retained_key(stratum.key, variables, select.retention, recipe.constants)
                retained_track = track_of.get(retained)
                retained_row = dict(zip(variables, retained, strict=True))
                for attribute in select.retention_features:
                    curve_id, _ = resolve_curve(attribute, retained, "feature", label_curves)
                    if curve_id is None or retained_track is None:
                        continue
                    label = _expand_label(
                        attribute.label, retained_row, "feature", recipe.constants
                    )
                    feature_rows.append(
                        {"track_id": retained_track, "label": label, "curve_id": curve_id}
                    )
                    account_labels.setdefault(label, set()).add(managed)
            for attribute in select.products:
                if select.treatment_context:
                    contexts = [select.treatment_context]
                else:
                    contexts = treatments_of_track.get(stratum.track_id, [])
                for context in contexts:
                    # A product curve may depend on the treatment; try the treatment
                    # context first and fall back to the stratum-wide value.
                    curve_id, _ = resolve_curve(
                        attribute, stratum.key, "product", label_curves, treatment=context
                    )
                    if curve_id is None and context:
                        curve_id, _ = resolve_curve(attribute, stratum.key, "product", label_curves)
                    if curve_id is None:
                        continue
                    label_row = dict(row)
                    if context:
                        label_row["treatment"] = context
                    label = _expand_label(attribute.label, label_row, "product", recipe.constants)
                    product_rows.append(
                        {
                            "track_id": stratum.track_id,
                            "treatment": context,
                            "label": label,
                            "curve_id": curve_id,
                        }
                    )
                    account_labels.setdefault(label, set()).add(managed)
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

    protoaccount_rows = [
        {"group": _account_group(states), "attribute": label, "account": label, "sum": 1.0}
        for label, states in account_labels.items()
    ]

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
        "curves": pd.DataFrame(curve_rows, columns=["curve_id", "x", "y"]),
        "features": pd.DataFrame(feature_rows, columns=["track_id", "label", "curve_id"]),
        "products": pd.DataFrame(
            product_rows, columns=["track_id", "treatment", "label", "curve_id"]
        ),
        "protoaccounts": pd.DataFrame(
            protoaccount_rows, columns=["group", "attribute", "account", "sum"]
        ),
        "accounts": pd.DataFrame(
            protoaccount_rows, columns=["group", "attribute", "account", "sum"]
        ),
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
        # Preserve a user-curated accounts file: the builder only writes protoaccounts,
        # and re-running must not overwrite an edited accounts table.
        if table.name == "accounts" and (out_dir / table.file).is_file():
            continue
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
