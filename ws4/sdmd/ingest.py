"""Ingest adapters for the SDMD layer.

The adapters accept public sample-plot, VRI, and LiDAR evidence and produce the
tables defined in :mod:`ws4.sdmd.schema`. They do not read a proprietary file format
and do not fetch data: the caller supplies a frame, and this module normalizes names,
checks the contract, and refuses evidence that would make the layer dishonest.

Two refusals are deliberate. An unlabelled ``nemora`` gap-fill row is refused, so a
synthetic plot cannot enter as an observation. A canopy-only LiDAR TPH is refused as
total density, because canopy cover is not stand density.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from .schema import (
    PLOTS,
    REVIEW_STATUSES,
    TREES,
    Problem,
    coerce_to_schema,
    validate_dataset,
)

SDMD_INGEST_SCHEMA_VERSION = "ws4.sdmd.ingest.v1"
SYNTHETIC_PREFIX = "synthetic:"
LIDAR_TPH_BASES: tuple[str, ...] = ("total", "canopy_only")

PLOT_ALIASES: dict[str, str] = {
    "plot": "plot_id",
    "year": "visit_year",
    "age": "stand_age",
    "si": "site_index",
    "au": "au_id",
    "zone": "bec_zone",
    "subzone": "bec_subzone",
    "variant": "bec_variant",
}

TREE_ALIASES: dict[str, str] = {
    "tree": "tree_id",
    "dbh": "dbh_cm",
    "height": "height_m",
    "crown": "crown_ratio",
    "expansion": "tph",
}

AU_ALIASES: dict[str, str] = {
    "au": "au_id",
    "zone": "bec_zone",
    "subzone": "bec_subzone",
    "variant": "bec_variant",
    "species": "species_group",
    "age_min": "min_age",
    "age_max": "max_age",
    "si_min": "min_site_index",
    "si_max": "max_site_index",
}

LIDAR_ALIASES: dict[str, str] = {
    "au": "au_id",
    "plot": "plot_id",
    "piece_size": "piece_size_m3",
    "clump": "clump_fraction",
    "cover": "canopy_cover_pct",
    "basis": "tph_basis",
}

AU_COLUMNS: tuple[str, ...] = (
    "au_id",
    "region",
    "bec_zone",
    "bec_subzone",
    "bec_variant",
    "tsa",
    "species_group",
    "min_age",
    "max_age",
    "min_site_index",
    "max_site_index",
)

AU_REQUIRED_COLUMNS: tuple[str, ...] = (
    "au_id",
    "region",
    "bec_zone",
    "bec_subzone",
    "tsa",
    "species_group",
)

LIDAR_COLUMNS: tuple[str, ...] = (
    "au_id",
    "plot_id",
    "piece_size_m3",
    "clump_fraction",
    "canopy_cover_pct",
    "tph",
    "tph_basis",
    "source",
    "review_status",
)

LIDAR_METRIC_COLUMNS: tuple[str, ...] = (
    "piece_size_m3",
    "clump_fraction",
    "canopy_cover_pct",
    "tph",
)


class SdmdIngestError(ValueError):
    """Raised when SDMD evidence cannot be normalized or is not admissible."""


@dataclass(frozen=True)
class AuMatchResult:
    """The outcome of matching sample plots to VRI analysis units.

    Attributes
    ----------
    matched : pandas.DataFrame
        The plots that received an AU, with the ``au_id`` column set.
    unmatched : pandas.DataFrame
        The plots that did not, with a ``match_reason`` column. Ambiguous and
        absent matches are reported rather than guessed.
    """

    matched: pd.DataFrame
    unmatched: pd.DataFrame


@dataclass(frozen=True)
class _AuRule:
    """One normalized AU matching rule."""

    au_id: str
    region: str
    bec_zone: str
    bec_subzone: str
    bec_variant: str | None
    tsa: str
    species_group: str
    min_age: float | None
    max_age: float | None
    min_site_index: float | None
    max_site_index: float | None


def read_psp_plots(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate a PSP plot table.

    Parameters
    ----------
    frame : pandas.DataFrame
        Raw plots. Canonical column names are preferred; the short aliases in
        :data:`PLOT_ALIASES` are also accepted.

    Returns
    -------
    pandas.DataFrame
        A schema-valid ``plots`` frame with nullable pandas dtypes.

    Raises
    ------
    SdmdIngestError
        If a required column is missing, a value is outside the contract, or an
        unlabelled ``nemora`` row would enter as an observation.
    """
    normalized = _normalize(frame, PLOT_ALIASES)
    _require_columns(normalized, PLOTS.required_columns, "plots")
    result = coerce_to_schema(normalized, PLOTS)
    _raise_for_problems(validate_dataset({"plots": result}))
    _check_synthetic_labels(result)
    return result


def read_psp_trees(frame: pd.DataFrame, *, plots: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate a PSP tree list against its plot table.

    Parameters
    ----------
    frame : pandas.DataFrame
        Raw tree list. Canonical column names are preferred; the short aliases in
        :data:`TREE_ALIASES` are also accepted.
    plots : pandas.DataFrame
        The plot table that the tree list references.

    Returns
    -------
    pandas.DataFrame
        A schema-valid ``trees`` frame with nullable pandas dtypes.

    Raises
    ------
    SdmdIngestError
        If a required column is missing, a value is outside the contract, or a tree
        names an unknown plot.
    """
    normalized = _normalize(frame, TREE_ALIASES)
    _require_columns(normalized, TREES.required_columns, "trees")
    result = coerce_to_schema(normalized, TREES)
    _raise_for_problems(validate_dataset({"trees": result}))
    if "plot_id" in plots.columns:
        known = {str(value) for value in plots["plot_id"].dropna()}
        unknown = {str(value) for value in result["plot_id"].dropna()} - known
        if unknown:
            sample = ", ".join(sorted(unknown)[:5])
            message = f"trees name unknown plot_id values: {sample}"
            raise SdmdIngestError(message)
    return result


def read_vri_aus(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate a VRI analysis-unit assignment table.

    Parameters
    ----------
    frame : pandas.DataFrame
        Raw AU descriptions. Canonical column names are preferred; the short aliases
        in :data:`AU_ALIASES` are also accepted.

    Returns
    -------
    pandas.DataFrame
        AU descriptions with text and numeric bounds typed, ready for matching.

    Raises
    ------
    SdmdIngestError
        If a required column is missing, an AU id repeats, a BEC or TSA value is
        empty, or an age or site-index window is inverted.
    """
    normalized = _normalize(frame, AU_ALIASES)
    _require_columns(normalized, AU_REQUIRED_COLUMNS, "aus")
    result = pd.DataFrame(
        {
            column: normalized[column]
            if column in normalized.columns
            else pd.Series([pd.NA] * len(normalized), dtype="object")
            for column in AU_COLUMNS
        }
    )
    for column in (
        "au_id",
        "region",
        "bec_zone",
        "bec_subzone",
        "bec_variant",
        "tsa",
        "species_group",
    ):
        result[column] = result[column].astype("string").str.strip()
    for column in ("min_age", "max_age", "min_site_index", "max_site_index"):
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("Float64")
    _raise_for_blank(
        result, ("au_id", "region", "bec_zone", "bec_subzone", "tsa", "species_group"), "aus"
    )
    if bool(result["au_id"].duplicated().any()):
        repeated = sorted(set(result.loc[result["au_id"].duplicated(), "au_id"].astype(str)))
        message = f"aus repeat au_id values: {', '.join(repeated[:5])}"
        raise SdmdIngestError(message)
    _check_window(result, "min_age", "max_age", "aus")
    _check_window(result, "min_site_index", "max_site_index", "aus")
    return result


def leading_species(trees: pd.DataFrame) -> pd.DataFrame:
    """Return each plot's leading species group by total TPH.

    A tie is broken by the species code in ascending order, so the result is
    deterministic.

    Parameters
    ----------
    trees : pandas.DataFrame
        A tree list with ``plot_id``, ``species``, and ``tph``.

    Returns
    -------
    pandas.DataFrame
        Two columns: ``plot_id`` and ``species_group``.

    Raises
    ------
    SdmdIngestError
        If a required column is missing.
    """
    _require_columns(trees, ("plot_id", "species", "tph"), "trees")
    totals = trees.groupby(["plot_id", "species"], observed=True)[["tph"]].sum().reset_index()
    ordered = totals.sort_values(["plot_id", "tph", "species"], ascending=[True, False, True])
    first = ordered.drop_duplicates(subset=["plot_id"], keep="first")
    result: pd.DataFrame = first.rename(columns={"species": "species_group"})[
        ["plot_id", "species_group"]
    ]
    return result


def match_plots_to_aus(
    plots: pd.DataFrame,
    aus: pd.DataFrame,
    *,
    leading_species: pd.DataFrame | None = None,
) -> AuMatchResult:
    """Match plots to analysis units by BEC, TSA, species, age, and site index.

    A preassigned ``au_id`` is kept only when the AU exists in the AU table. A blank
    ``au_id`` is filled only when exactly one AU matches. No match and more than one
    match are reported in ``unmatched`` rather than guessed.

    Parameters
    ----------
    plots : pandas.DataFrame
        The plot table, with or without an ``au_id`` column.
    aus : pandas.DataFrame
        The AU table from :func:`read_vri_aus`, or a frame that function accepts.
    leading_species : pandas.DataFrame, optional
        A ``plot_id`` and ``species_group`` table, usually from
        :func:`leading_species`. When omitted, species is not used in matching.

    Returns
    -------
    AuMatchResult
        The matched plots with ``au_id`` set, and the rest with a ``match_reason``.
    """
    normalized_aus = read_vri_aus(aus)
    rules = [
        _AuRule(
            au_id=_text(row.au_id),
            region=_text(row.region),
            bec_zone=_text(row.bec_zone),
            bec_subzone=_text(row.bec_subzone),
            bec_variant=_text(row.bec_variant) or None,
            tsa=_text(row.tsa),
            species_group=_text(row.species_group),
            min_age=_optional_float(row.min_age),
            max_age=_optional_float(row.max_age),
            min_site_index=_optional_float(row.min_site_index),
            max_site_index=_optional_float(row.max_site_index),
        )
        for row in normalized_aus.itertuples(index=False)
    ]
    rules_by_key: dict[tuple[str, str, str, str], list[_AuRule]] = {}
    for rule in rules:
        key = (rule.region, rule.bec_zone, rule.bec_subzone, rule.tsa)
        rules_by_key.setdefault(key, []).append(rule)
    species_by_plot: dict[str, str] = {}
    if leading_species is not None:
        _require_columns(leading_species, ("plot_id", "species_group"), "leading_species")
        species_by_plot = {
            str(row.plot_id): str(row.species_group)
            for row in leading_species.itertuples(index=False)
        }
    _require_columns(
        plots,
        ("plot_id", "region", "bec_zone", "bec_subzone", "tsa", "stand_age", "site_index"),
        "plots",
    )
    assigned: list[str] = []
    matched_positions: list[int] = []
    unmatched_positions: list[int] = []
    reasons: list[str] = []
    for position in range(len(plots)):
        row = plots.iloc[position]
        au_id = _text(row.get("au_id"))
        if au_id:
            if au_id in {rule.au_id for rule in rules}:
                assigned.append(au_id)
                matched_positions.append(position)
            else:
                unmatched_positions.append(position)
                reasons.append(f"preassigned AU not in VRI table: {au_id}")
            continue
        key = (
            _text(row["region"]),
            _text(row["bec_zone"]),
            _text(row["bec_subzone"]),
            _text(row["tsa"]),
        )
        species = species_by_plot.get(_text(row["plot_id"]))
        candidates = [
            rule
            for rule in rules_by_key.get(key, [])
            if _matches(
                rule, row.get("bec_variant"), row.get("stand_age"), row.get("site_index"), species
            )
        ]
        if len(candidates) == 1:
            assigned.append(candidates[0].au_id)
            matched_positions.append(position)
        elif not candidates:
            unmatched_positions.append(position)
            reasons.append("no AU matched BEC, TSA, species, age, and site index")
        else:
            unmatched_positions.append(position)
            ids = ", ".join(sorted(rule.au_id for rule in candidates))
            reasons.append(f"ambiguous match: {ids}")
    matched = plots.iloc[matched_positions].copy()
    matched["au_id"] = assigned
    unmatched = plots.iloc[unmatched_positions].copy()
    unmatched["match_reason"] = reasons
    return AuMatchResult(matched=matched, unmatched=unmatched)


def label_synthetic(plots: pd.DataFrame, *, source: str = "nemora") -> pd.DataFrame:
    """Label gap-fill plots as synthetic and set them to provisional review.

    Parameters
    ----------
    plots : pandas.DataFrame
        A normalized plot table with a ``sources`` and a ``review_status`` column.
    source : str
        The gap-fill source name. Defaults to ``nemora``.

    Returns
    -------
    pandas.DataFrame
        A copy whose ``sources`` carry the ``synthetic:`` prefix and whose review
        status is ``provisional``.

    Raises
    ------
    SdmdIngestError
        If the plot table lacks the provenance columns.
    """
    _require_columns(plots, ("sources", "review_status"), "plots")
    result = plots.copy()
    label = source if source.startswith(SYNTHETIC_PREFIX) else f"{SYNTHETIC_PREFIX}{source}"
    result["sources"] = label
    result["review_status"] = "provisional"
    return result


def read_lidar_evidence(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate LiDAR structure and density evidence.

    A row may carry piece size, clump fraction, canopy cover, or a total TPH. A
    ``canopy_only`` row may not carry a TPH, because canopy-derived density is not
    total stand density.

    Parameters
    ----------
    frame : pandas.DataFrame
        Raw evidence. Canonical column names are preferred; the short aliases in
        :data:`LIDAR_ALIASES` are also accepted.

    Returns
    -------
    pandas.DataFrame
        Evidence with text and numeric columns typed.

    Raises
    ------
    SdmdIngestError
        If a required column is missing, a basis is unknown, a canopy-only row
        carries a TPH, a value is out of range, or a row carries no evidence.
    """
    normalized = _normalize(frame, LIDAR_ALIASES)
    _require_columns(
        normalized,
        ("au_id", "tph_basis", "source", "review_status"),
        "lidar_evidence",
    )
    result = pd.DataFrame(
        {
            column: normalized[column]
            if column in normalized.columns
            else pd.Series([pd.NA] * len(normalized), dtype="object")
            for column in LIDAR_COLUMNS
        }
    )
    for column in ("au_id", "plot_id", "tph_basis", "source", "review_status"):
        result[column] = result[column].astype("string").str.strip()
    for column in LIDAR_METRIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("Float64")
    _raise_for_blank(result, ("au_id", "tph_basis", "source", "review_status"), "lidar_evidence")
    unknown_basis = sorted(set(result["tph_basis"].dropna()) - set(LIDAR_TPH_BASES))
    if unknown_basis:
        message = f"lidar_evidence has unknown tph_basis values: {', '.join(unknown_basis)}"
        raise SdmdIngestError(message)
    unknown_review = sorted(set(result["review_status"].dropna()) - set(REVIEW_STATUSES))
    if unknown_review:
        message = "lidar_evidence has unknown review_status values: " + ", ".join(unknown_review)
        raise SdmdIngestError(message)
    canopy_only = result["tph_basis"] == "canopy_only"
    if bool((canopy_only & result["tph"].notna()).any()):
        message = "canopy-only LiDAR TPH is not total stand density"
        raise SdmdIngestError(message)
    if bool((result["piece_size_m3"].notna() & (result["piece_size_m3"] <= 0)).any()):
        message = "lidar_evidence piece_size_m3 must be greater than zero"
        raise SdmdIngestError(message)
    _raise_for_range(result, "clump_fraction", minimum=0.0, maximum=1.0, table="lidar_evidence")
    _raise_for_range(result, "canopy_cover_pct", minimum=0.0, maximum=100.0, table="lidar_evidence")
    _raise_for_range(result, "tph", minimum=0.0, table="lidar_evidence")
    if bool(result[list(LIDAR_METRIC_COLUMNS)].isna().all(axis=1).any()):
        message = "lidar_evidence row carries no piece size, clump, cover, or TPH"
        raise SdmdIngestError(message)
    return result


def _normalize(frame: pd.DataFrame, aliases: Mapping[str, str]) -> pd.DataFrame:
    """Rename known short aliases to canonical column names.

    Parameters
    ----------
    frame : pandas.DataFrame
        The raw frame.
    aliases : mapping of str to str
        Alias to canonical-name mapping.

    Returns
    -------
    pandas.DataFrame
        A copy with aliases renamed.
    """
    renamed = {alias: canonical for alias, canonical in aliases.items() if alias in frame.columns}
    return frame.rename(columns=renamed).copy()


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], table: str) -> None:
    """Refuse a frame that lacks a required column.

    Parameters
    ----------
    frame : pandas.DataFrame
        The frame.
    columns : sequence of str
        The required columns.
    table : str
        The table name, used in the message.

    Raises
    ------
    SdmdIngestError
        When a required column is absent.
    """
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        message = f"{table} is missing required column(s): {', '.join(missing)}"
        raise SdmdIngestError(message)


def _raise_for_problems(problems: Sequence[Problem]) -> None:
    """Raise one ingest error that names every schema finding.

    Parameters
    ----------
    problems : sequence of Problem
        The schema findings.

    Raises
    ------
    SdmdIngestError
        Whenever a finding is present.
    """
    if not problems:
        return
    detail = "; ".join(f"{item.code} {item.where}: {item.message}" for item in problems)
    raise SdmdIngestError(detail)


def _check_synthetic_labels(plots: pd.DataFrame) -> None:
    """Refuse an unlabelled gap-fill row.

    Parameters
    ----------
    plots : pandas.DataFrame
        A schema-valid plot table.

    Raises
    ------
    SdmdIngestError
        When a row names ``nemora`` without a ``synthetic:`` label.
    """
    for row in plots.itertuples(index=False):
        tokens = {token.strip().lower() for token in str(row.sources).split(",")}
        if "nemora" in tokens and not any(token.startswith("synthetic") for token in tokens):
            message = (
                f"plot {row.plot_id} uses an unlabelled nemora gap-fill; "
                "call label_synthetic before ingesting it"
            )
            raise SdmdIngestError(message)


def _raise_for_blank(frame: pd.DataFrame, columns: Sequence[str], table: str) -> None:
    """Refuse blank required text in a normalized input frame.

    Parameters
    ----------
    frame : pandas.DataFrame
        The normalized frame.
    columns : sequence of str
        The required text columns.
    table : str
        The table name, used in the message.

    Raises
    ------
    SdmdIngestError
        When a required text value is missing or blank.
    """
    for column in columns:
        series = frame[column]
        blank = series.isna() | (series.astype("string").str.strip() == "")
        if bool(blank.any()):
            message = f"{table} has a blank {column}"
            raise SdmdIngestError(message)


def _check_window(frame: pd.DataFrame, low: str, high: str, table: str) -> None:
    """Refuse an inverted numeric window.

    Parameters
    ----------
    frame : pandas.DataFrame
        The normalized frame.
    low : str
        The lower-bound column.
    high : str
        The upper-bound column.
    table : str
        The table name, used in the message.

    Raises
    ------
    SdmdIngestError
        When a lower bound exceeds its upper bound.
    """
    if bool((frame[low] > frame[high]).any()):
        message = f"{table} has a {low} above its {high}"
        raise SdmdIngestError(message)


def _raise_for_range(
    frame: pd.DataFrame,
    column: str,
    *,
    minimum: float,
    maximum: float | None = None,
    table: str,
) -> None:
    """Refuse a numeric value outside a range.

    Parameters
    ----------
    frame : pandas.DataFrame
        The normalized frame.
    column : str
        The numeric column.
    minimum : float
        The inclusive lower bound.
    maximum : float, optional
        The inclusive upper bound.
    table : str
        The table name, used in the message.

    Raises
    ------
    SdmdIngestError
        When a value is outside the range.
    """
    values = frame[column]
    outside = values.notna() & (values < minimum)
    if maximum is not None:
        outside = outside | (values.notna() & (values > maximum))
    if bool(outside.any()):
        message = f"{table} {column} is outside its allowed range"
        raise SdmdIngestError(message)


def _text(value: object) -> str:
    """Return a trimmed string, or an empty string for a missing value.

    Parameters
    ----------
    value : object
        A cell value.

    Returns
    -------
    str
        The trimmed text.
    """
    if _is_missing(value):
        return ""
    return str(value).strip()


def _optional_float(value: object) -> float | None:
    """Return a float, or ``None`` for a missing value.

    Parameters
    ----------
    value : object
        A cell value.

    Returns
    -------
    float or None
        The value, or ``None`` when it is missing.
    """
    if _is_missing(value):
        return None
    return float(str(value))


def _is_missing(value: object) -> bool:
    """Return whether a cell is missing.

    Parameters
    ----------
    value : object
        A cell value.

    Returns
    -------
    bool
        ``True`` for ``None``, pandas ``NA``, and a NaN float.
    """
    if value is None or value is pd.NA:
        return True
    return isinstance(value, float) and math.isnan(value)


def _matches(
    rule: _AuRule,
    variant: object,
    age: object,
    site_index: object,
    species: str | None,
) -> bool:
    """Test one plot against one AU rule.

    Parameters
    ----------
    rule : _AuRule
        The AU rule.
    variant : object
        The plot's BEC variant.
    age : object
        The plot's stand age.
    site_index : object
        The plot's site index.
    species : str or None
        The plot's leading species group.

    Returns
    -------
    bool
        Whether the plot's BEC/TSA key, variant, species, age, and site index all
        fit the rule. A blank rule bound is a wildcard.
    """
    plot_variant = _text(variant)
    if rule.bec_variant is not None and plot_variant and rule.bec_variant != plot_variant:
        return False
    if species is not None and rule.species_group and species != rule.species_group:
        return False
    return _within(age, rule.min_age, rule.max_age) and _within(
        site_index, rule.min_site_index, rule.max_site_index
    )


def _within(value: object, low: float | None, high: float | None) -> bool:
    """Test a value against an optional window.

    Parameters
    ----------
    value : object
        The plot value.
    low : float, optional
        The inclusive lower bound.
    high : float, optional
        The inclusive upper bound.

    Returns
    -------
    bool
        ``True`` when the value is inside the window, or when it is missing or the
        bound is a wildcard.
    """
    number = _optional_float(value)
    if number is None:
        return True
    if low is not None and number < low:
        return False
    return not (high is not None and number > high)
