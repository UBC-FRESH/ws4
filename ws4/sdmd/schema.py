"""Schema and validation for the WS4 stand density management layer.

The stand density management diagram (SDMD) is a diagnostic and constraint layer, not a
growth model (see ``notes/adr/0013-sdmd-as-constraint-layer.md``). This module is the
stable contract between that layer's ingestion, compilation, API, web tab, and solver
integration. It defines six tables, a coercion helper, and validators that can fail.

Later tasks add ingestion, digitization, the API, the web tab, and solver constraints.
They read these tables; they do not widen them silently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import pandas as pd
from pandas.api import types as ptypes

SDMD_SCHEMA_VERSION = "ws4.sdmd.v1"

Kind = Literal["integer", "number", "string", "boolean"]

REVIEW_STATUSES: tuple[str, ...] = ("unreviewed", "provisional", "reviewed", "rejected")

REGIME_ENTRY_TYPES: tuple[str, ...] = (
    "untreated",
    "clearcut",
    "ct60",
    "fuel50",
    "selection80",
    "shelterwood40",
    "vr20",
)

SDMD_ZONES: tuple[str, ...] = (
    "understocked",
    "density-management",
    "competition",
    "self-thinning",
    "outside",
)


@dataclass(frozen=True)
class Column:
    """One column of an SDMD table.

    Attributes
    ----------
    name : str
        Column name.
    kind : {"integer", "number", "string", "boolean"}
        Expected value kind.
    nullable : bool
        Whether a missing value is allowed. Defaults to ``False``.
    """

    name: str
    kind: Kind
    nullable: bool = False


@dataclass(frozen=True)
class Table:
    """One SDMD table contract.

    Attributes
    ----------
    name : str
        Logical table name, as used by the API and the fixtures.
    description : str
        One sentence that says what a row means.
    columns : tuple of Column
        The required columns.
    primary_key : tuple of str
        The columns that identify one row.
    """

    name: str
    description: str
    columns: tuple[Column, ...]
    primary_key: tuple[str, ...]

    @property
    def required_columns(self) -> tuple[str, ...]:
        """Return the column names.

        Returns
        -------
        tuple of str
            Every column name in schema order.
        """
        return tuple(column.name for column in self.columns)


PLOTS = Table(
    name="plots",
    description="One PSP or synthetic sample plot, with its AU assignment and visit.",
    columns=(
        Column("plot_id", "string"),
        Column("region", "string"),
        Column("bec_zone", "string"),
        Column("bec_subzone", "string"),
        Column("bec_variant", "string", nullable=True),
        Column("tsa", "string"),
        Column("au_id", "string"),
        Column("visit_year", "integer"),
        Column("stand_age", "integer"),
        Column("site_index", "number"),
        Column("slope", "number"),
        Column("aspect", "number"),
        Column("elevation", "number"),
        Column("plot_area_ha", "number"),
        Column("sources", "string"),
        Column("review_status", "string"),
    ),
    primary_key=("plot_id", "visit_year"),
)

TREES = Table(
    name="trees",
    description="One measured tree in a plot's tree list.",
    columns=(
        Column("plot_id", "string"),
        Column("tree_id", "string"),
        Column("species", "string"),
        Column("dbh_cm", "number"),
        Column("height_m", "number"),
        Column("crown_ratio", "number"),
        Column("tph", "number"),
        Column("live", "boolean"),
        Column("damage", "string", nullable=True),
        Column("source", "string"),
    ),
    primary_key=("plot_id", "tree_id"),
)

STANDS = Table(
    name="stands",
    description="One stand summary for a plot visit.",
    columns=(
        Column("plot_id", "string"),
        Column("visit_year", "integer"),
        Column("age", "integer"),
        Column("tph", "number"),
        Column("ba_m2_ha", "number"),
        Column("qmd_cm", "number"),
        Column("top_height_m", "number"),
        Column("mean_height_m", "number"),
        Column("volume_m3_ha", "number"),
        Column("crown_cover_pct", "number"),
        Column("source", "string"),
        Column("review_status", "string"),
    ),
    primary_key=("plot_id", "visit_year"),
)

SDMD_POINTS = Table(
    name="sdmd_points",
    description="One AU-level observation or compiled point on the density diagram.",
    columns=(
        Column("sdmd_id", "string"),
        Column("au_id", "string"),
        Column("region", "string"),
        Column("species_group", "string"),
        Column("site_index", "number"),
        Column("age", "integer"),
        Column("top_height_m", "number"),
        Column("qmd_cm", "number"),
        Column("tph", "number"),
        Column("ba_m2_ha", "number"),
        Column("mean_tree_volume_m3", "number"),
        Column("rd", "number"),
        Column("sdi", "number"),
        Column("sdi_max", "number"),
        Column("zone", "string"),
        Column("source", "string"),
        Column("review_status", "string"),
    ),
    primary_key=("sdmd_id",),
)

REGIMES = Table(
    name="regimes",
    description="One silviculture regime as an ordered sequence of entries.",
    columns=(
        Column("regime_id", "string"),
        Column("au_id", "string"),
        Column("name", "string"),
        Column("entry_age", "integer"),
        Column("entry_type", "string"),
        Column("residual_ba_m2_ha", "number"),
        Column("removal_fraction", "number"),
        Column("cycle_length", "integer"),
        Column("repeat_count", "integer"),
        Column("post_treatment_track", "string", nullable=True),
        Column("eligibility_expr", "string", nullable=True),
        Column("operability_expr", "string", nullable=True),
        Column("constraint_ids", "string", nullable=True),
        Column("review_status", "string"),
    ),
    primary_key=("regime_id",),
)

AU_CONSTRAINTS = Table(
    name="au_constraints",
    description="One allowed or denied regime for one AU, with its operating limits.",
    columns=(
        Column("au_id", "string"),
        Column("regime_id", "string"),
        Column("allowed", "boolean"),
        Column("min_entry_age", "integer"),
        Column("max_entry_age", "integer"),
        Column("max_entries", "integer"),
        Column("min_interval_years", "integer"),
        Column("max_removal_fraction", "number"),
        Column("required_sdmd_zone", "string", nullable=True),
        Column("source", "string"),
        Column("review_status", "string"),
    ),
    primary_key=("au_id", "regime_id"),
)

SDMD_TABLES: tuple[Table, ...] = (PLOTS, TREES, STANDS, SDMD_POINTS, REGIMES, AU_CONSTRAINTS)

SDMD_TABLES_BY_NAME: dict[str, Table] = {table.name: table for table in SDMD_TABLES}

SDMD_TABLE_NAMES: tuple[str, ...] = tuple(table.name for table in SDMD_TABLES)

_KIND_CHECKS = {
    "integer": ptypes.is_integer_dtype,
    "number": ptypes.is_numeric_dtype,
    "string": ptypes.is_string_dtype,
    "boolean": ptypes.is_bool_dtype,
}


@dataclass(frozen=True)
class Problem:
    """One validation finding.

    Attributes
    ----------
    code : str
        Stable finding code, such as ``SDMD-MISSING-COLUMN``.
    where : str
        The table or table field the finding applies to.
    message : str
        A human-readable description.
    """

    code: str
    where: str
    message: str


def table_schema(name: str) -> Table:
    """Return the table contract for a table name.

    Parameters
    ----------
    name : str
        Logical table name, such as ``plots``.

    Returns
    -------
    Table
        The table contract.

    Raises
    ------
    KeyError
        When the name is not part of the SDMD schema.
    """
    try:
        return SDMD_TABLES_BY_NAME[name]
    except KeyError:
        known = ", ".join(SDMD_TABLE_NAMES)
        message = f"unknown SDMD table '{name}'; known tables: {known}"
        raise KeyError(message) from None


def coerce_to_schema(frame: pd.DataFrame, table: Table) -> pd.DataFrame:
    """Coerce a frame's columns to the table's kinds.

    A missing column is added empty so that :func:`validate_frame` can report it as
    missing rather than failing the coercion.

    Parameters
    ----------
    frame : pandas.DataFrame
        The frame to coerce.
    table : Table
        The target table contract.

    Returns
    -------
    pandas.DataFrame
        A copy with the table's columns typed with nullable pandas dtypes.
    """
    result = frame.copy()
    for column in table.columns:
        series = (
            result[column.name] if column.name in result.columns else pd.Series(dtype="float64")
        )
        if column.kind == "string":
            result[column.name] = series.astype("string")
        elif column.kind == "boolean":
            result[column.name] = series.astype("boolean")
        elif column.kind == "integer":
            result[column.name] = pd.to_numeric(series, errors="raise").astype("Int64")
        else:
            result[column.name] = pd.to_numeric(series, errors="raise").astype("Float64")
    return result


def validate_frame(table: Table, frame: pd.DataFrame) -> list[Problem]:
    """Validate one frame against its table contract.

    The checks are structural: required columns, value kinds, non-null required
    values, non-empty required text, and a unique primary key. Value domains and
    cross-table references belong to :func:`validate_dataset`.

    Parameters
    ----------
    table : Table
        The table contract.
    frame : pandas.DataFrame
        The frame to validate.

    Returns
    -------
    list of Problem
        The findings for this frame. The list is empty when the frame is valid.
    """
    problems: list[Problem] = []
    for column in table.columns:
        if column.name not in frame.columns:
            problems.append(
                Problem("SDMD-MISSING-COLUMN", table.name, f"missing column {column.name}")
            )
            continue
        series = frame[column.name]
        if not _KIND_CHECKS[column.kind](series):
            problems.append(
                Problem(
                    "SDMD-COLUMN-KIND",
                    f"{table.name}.{column.name}",
                    f"expected a {column.kind} column",
                )
            )
            continue
        if column.nullable:
            continue
        if bool(series.isna().any()):
            problems.append(
                Problem(
                    "SDMD-NULL-VALUE",
                    f"{table.name}.{column.name}",
                    "required value is missing",
                )
            )
        if column.kind == "string" and bool((series.fillna("").str.strip() == "").any()):
            problems.append(
                Problem(
                    "SDMD-EMPTY-VALUE",
                    f"{table.name}.{column.name}",
                    "required text is empty",
                )
            )
    if all(name in frame.columns for name in table.primary_key):
        duplicated = frame.duplicated(subset=list(table.primary_key), keep=False)
        if bool(duplicated.any()):
            key = ", ".join(table.primary_key)
            problems.append(
                Problem(
                    "SDMD-DUPLICATE-KEY",
                    table.name,
                    f"primary key ({key}) is not unique",
                )
            )
    return problems


def validate_dataset(
    frames: Mapping[str, pd.DataFrame],
    *,
    required: Sequence[str] = (),
) -> list[Problem]:
    """Validate a set of SDMD tables, their value domains, and their references.

    Parameters
    ----------
    frames : mapping of str to pandas.DataFrame
        The tables to validate, keyed by logical table name.
    required : sequence of str, optional
        Table names that must be present. Defaults to an empty sequence.

    Returns
    -------
    list of Problem
        Every finding, in table order. The list is empty when the dataset is valid.
    """
    problems: list[Problem] = []
    for name in frames:
        if name not in SDMD_TABLES_BY_NAME:
            problems.append(
                Problem("SDMD-UNKNOWN-TABLE", name, "table is not part of the SDMD schema")
            )
    for name in required:
        if name not in frames:
            problems.append(Problem("SDMD-MISSING-TABLE", name, "required table is missing"))
    for table in SDMD_TABLES:
        if table.name in frames:
            problems.extend(validate_frame(table, frames[table.name]))
    problems.extend(_check_values(frames))
    problems.extend(_check_references(frames))
    return problems


def _check_values(frames: Mapping[str, pd.DataFrame]) -> list[Problem]:
    """Check the value domains of the tables that are present.

    Parameters
    ----------
    frames : mapping of str to pandas.DataFrame
        The tables to check.

    Returns
    -------
    list of Problem
        The domain findings.
    """
    problems: list[Problem] = []
    for name in ("plots", "stands", "sdmd_points", "regimes", "au_constraints"):
        frame = frames.get(name)
        if frame is None:
            continue
        problems.extend(_check_review_status(name, frame))
    plots = frames.get("plots")
    if plots is not None:
        problems.extend(_range(plots, "plots", "visit_year", minimum=1800))
        problems.extend(_range(plots, "plots", "stand_age", minimum=0))
        problems.extend(_range(plots, "plots", "site_index", minimum=0, exclusive=True))
        problems.extend(_range(plots, "plots", "slope", minimum=0, maximum=100))
        problems.extend(_range(plots, "plots", "aspect", minimum=0, maximum=360))
        problems.extend(_range(plots, "plots", "elevation", minimum=-500, maximum=5000))
        problems.extend(_range(plots, "plots", "plot_area_ha", minimum=0, exclusive=True))
    trees = frames.get("trees")
    if trees is not None:
        problems.extend(_range(trees, "trees", "dbh_cm", minimum=0, exclusive=True))
        problems.extend(_range(trees, "trees", "height_m", minimum=0))
        problems.extend(_range(trees, "trees", "crown_ratio", minimum=0, maximum=1))
        problems.extend(_range(trees, "trees", "tph", minimum=0))
    stands = frames.get("stands")
    if stands is not None:
        problems.extend(_range(stands, "stands", "visit_year", minimum=1800))
        problems.extend(_range(stands, "stands", "age", minimum=0))
        for column in ("tph", "ba_m2_ha", "qmd_cm", "top_height_m", "mean_height_m"):
            problems.extend(_range(stands, "stands", column, minimum=0))
        problems.extend(_range(stands, "stands", "volume_m3_ha", minimum=0))
        problems.extend(_range(stands, "stands", "crown_cover_pct", minimum=0, maximum=100))
    sdmd_points = frames.get("sdmd_points")
    if sdmd_points is not None:
        problems.extend(_range(sdmd_points, "sdmd_points", "site_index", minimum=0, exclusive=True))
        problems.extend(_range(sdmd_points, "sdmd_points", "age", minimum=0))
        for column in ("top_height_m", "qmd_cm", "mean_tree_volume_m3", "rd", "sdi", "sdi_max"):
            problems.extend(_range(sdmd_points, "sdmd_points", column, minimum=0, exclusive=True))
        for column in ("tph", "ba_m2_ha"):
            problems.extend(_range(sdmd_points, "sdmd_points", column, minimum=0))
        problems.extend(_enum(sdmd_points, "sdmd_points", "zone", SDMD_ZONES))
    regimes = frames.get("regimes")
    if regimes is not None:
        problems.extend(_range(regimes, "regimes", "entry_age", minimum=0))
        problems.extend(_range(regimes, "regimes", "residual_ba_m2_ha", minimum=0))
        problems.extend(_range(regimes, "regimes", "removal_fraction", minimum=0, maximum=1))
        problems.extend(_range(regimes, "regimes", "cycle_length", minimum=0))
        problems.extend(_range(regimes, "regimes", "repeat_count", minimum=0))
        problems.extend(_enum(regimes, "regimes", "entry_type", REGIME_ENTRY_TYPES))
    constraints = frames.get("au_constraints")
    if constraints is not None:
        problems.extend(_range(constraints, "au_constraints", "min_entry_age", minimum=0))
        problems.extend(_range(constraints, "au_constraints", "max_entry_age", minimum=0))
        problems.extend(_range(constraints, "au_constraints", "max_entries", minimum=0))
        problems.extend(_range(constraints, "au_constraints", "min_interval_years", minimum=0))
        problems.extend(
            _range(constraints, "au_constraints", "max_removal_fraction", minimum=0, maximum=1)
        )
        problems.extend(_enum(constraints, "au_constraints", "required_sdmd_zone", SDMD_ZONES))
        problems.extend(_check_entry_window(constraints))
    return problems


def _check_review_status(name: str, frame: pd.DataFrame) -> list[Problem]:
    """Check the review-status enumeration of one table.

    Parameters
    ----------
    name : str
        The table name.
    frame : pandas.DataFrame
        The table.

    Returns
    -------
    list of Problem
        The enumeration findings.
    """
    return _enum(frame, name, "review_status", REVIEW_STATUSES)


def _check_entry_window(frame: pd.DataFrame) -> list[Problem]:
    """Check that every constraint's minimum entry age does not exceed its maximum.

    Parameters
    ----------
    frame : pandas.DataFrame
        The ``au_constraints`` table.

    Returns
    -------
    list of Problem
        The findings. Rows with a missing value are left to the kind and null checks.
    """
    if not {"min_entry_age", "max_entry_age"}.issubset(frame.columns):
        return []
    minimum = pd.to_numeric(frame["min_entry_age"], errors="coerce")
    maximum = pd.to_numeric(frame["max_entry_age"], errors="coerce")
    if not bool((minimum > maximum).any()):
        return []
    return [
        Problem(
            "SDMD-ENTRY-WINDOW",
            "au_constraints",
            "min_entry_age exceeds max_entry_age",
        )
    ]


def _range(
    frame: pd.DataFrame,
    table: str,
    column: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    exclusive: bool = False,
) -> list[Problem]:
    """Check that a numeric column stays inside a range.

    Parameters
    ----------
    frame : pandas.DataFrame
        The table.
    table : str
        The table name, used in the finding.
    column : str
        The numeric column.
    minimum : float, optional
        The lower bound.
    maximum : float, optional
        The upper bound.
    exclusive : bool
        When ``True``, the lower bound is exclusive. Defaults to ``False``.

    Returns
    -------
    list of Problem
        One finding when any value is outside the range, otherwise an empty list.
    """
    if column not in frame.columns or not ptypes.is_numeric_dtype(frame[column]):
        return []
    values = pd.to_numeric(frame[column], errors="coerce")
    outside = pd.Series(False, index=frame.index)
    if minimum is not None:
        outside = outside | (values <= minimum if exclusive else values < minimum)
    if maximum is not None:
        outside = outside | (values > maximum)
    if not bool(outside.any()):
        return []
    bound = _describe_bounds(minimum, maximum, exclusive)
    return [Problem("SDMD-RANGE", f"{table}.{column}", f"value outside {bound}")]


def _describe_bounds(minimum: float | None, maximum: float | None, exclusive: bool) -> str:
    """Describe a range for a finding message.

    Parameters
    ----------
    minimum : float, optional
        The lower bound.
    maximum : float, optional
        The upper bound.
    exclusive : bool
        Whether the lower bound is exclusive.

    Returns
    -------
    str
        A short human-readable range.
    """
    parts: list[str] = []
    if minimum is not None:
        parts.append(f"{'>' if exclusive else '>='} {minimum:g}")
    if maximum is not None:
        parts.append(f"<= {maximum:g}")
    return " and ".join(parts) if parts else "the allowed range"


def _enum(
    frame: pd.DataFrame,
    table: str,
    column: str,
    allowed: Sequence[str],
) -> list[Problem]:
    """Check that a text column uses only allowed values.

    Parameters
    ----------
    frame : pandas.DataFrame
        The table.
    table : str
        The table name, used in the finding.
    column : str
        The text column.
    allowed : sequence of str
        The allowed values.

    Returns
    -------
    list of Problem
        One finding when any value is unknown, otherwise an empty list.
    """
    if column not in frame.columns or not ptypes.is_string_dtype(frame[column]):
        return []
    values = frame[column].dropna().astype("string").str.strip()
    unknown = sorted(set(values) - set(allowed))
    if not unknown:
        return []
    sample = ", ".join(unknown[:5])
    return [Problem("SDMD-ENUM", f"{table}.{column}", f"unknown value(s): {sample}")]


def _check_references(frames: Mapping[str, pd.DataFrame]) -> list[Problem]:
    """Check the cross-table references that the schema guarantees.

    Parameters
    ----------
    frames : mapping of str to pandas.DataFrame
        The tables to check.

    Returns
    -------
    list of Problem
        The referential findings.
    """
    problems: list[Problem] = []
    plots = frames.get("plots")
    plot_ids = _values(plots, "plot_id") if plots is not None else set()
    if plots is not None:
        for name in ("trees", "stands"):
            frame = frames.get(name)
            if frame is None or "plot_id" not in frame.columns:
                continue
            unknown = _values(frame, "plot_id") - plot_ids
            if unknown:
                problems.append(_unknown("SDMD-UNKNOWN-PLOT", name, "plot_id", unknown))
    regimes = frames.get("regimes")
    constraints = frames.get("au_constraints")
    if regimes is not None and constraints is not None:
        regime_ids = _values(regimes, "regime_id")
        if "regime_id" in constraints.columns:
            unknown = _values(constraints, "regime_id") - regime_ids
            if unknown:
                problems.append(
                    _unknown("SDMD-UNKNOWN-REGIME", "au_constraints", "regime_id", unknown)
                )
        if {"au_id", "regime_id"}.issubset(regimes.columns) and {
            "au_id",
            "regime_id",
        }.issubset(constraints.columns):
            regime_series = regimes["regime_id"].astype("string")
            au_series = regimes["au_id"].astype("string")
            owners = dict(zip(regime_series, au_series, strict=True))
            mismatched = [
                str(row.regime_id)
                for row in constraints.itertuples(index=False)
                if owners.get(str(row.regime_id)) not in {None, str(row.au_id)}
            ]
            if mismatched:
                problems.append(
                    Problem(
                        "SDMD-REGIME-AU",
                        "au_constraints",
                        "regime belongs to a different AU: " + ", ".join(sorted(mismatched)[:5]),
                    )
                )
    known_aus: set[str] = set()
    for name in ("plots", "regimes", "au_constraints"):
        frame = frames.get(name)
        if frame is not None:
            known_aus |= _values(frame, "au_id")
    points = frames.get("sdmd_points")
    if points is not None and known_aus:
        unknown = _values(points, "au_id") - known_aus
        if unknown:
            problems.append(_unknown("SDMD-UNKNOWN-AU", "sdmd_points", "au_id", unknown))
    return problems


def _values(frame: pd.DataFrame, column: str) -> set[str]:
    """Return the non-null string values of a column.

    Parameters
    ----------
    frame : pandas.DataFrame
        The table.
    column : str
        The column name.

    Returns
    -------
    set of str
        The distinct non-null values, converted to text.
    """
    if column not in frame.columns:
        return set()
    return {str(value) for value in frame[column].dropna()}


def _unknown(code: str, table: str, column: str, values: set[str]) -> Problem:
    """Build a finding for unknown reference values.

    Parameters
    ----------
    code : str
        The stable finding code.
    table : str
        The table that holds the reference.
    column : str
        The column that holds the reference.
    values : set of str
        The unknown values.

    Returns
    -------
    Problem
        The finding, with at most five values in its message.
    """
    sample = ", ".join(sorted(values)[:5])
    return Problem(code, f"{table}.{column}", f"unknown reference(s): {sample}")
