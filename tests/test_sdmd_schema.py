"""Contract tests for the stand density management schema."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest
from pandas.api import types as ptypes
from ws4.sdmd.schema import (
    AU_CONSTRAINTS,
    PLOTS,
    REGIMES,
    SDMD_POINTS,
    SDMD_SCHEMA_VERSION,
    SDMD_TABLE_NAMES,
    STANDS,
    TREES,
    Problem,
    Table,
    coerce_to_schema,
    table_schema,
    validate_dataset,
    validate_frame,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"


def _frames() -> dict[str, pd.DataFrame]:
    """Load the two-AU fixture and coerce every table.

    Returns
    -------
    dict of str to pandas.DataFrame
        The six fixture tables, keyed by table name.
    """
    return {
        name: coerce_to_schema(pd.read_csv(FIXTURE / f"{name}.csv"), table_schema(name))
        for name in SDMD_TABLE_NAMES
    }


def _codes(problems: Sequence[Problem]) -> set[str]:
    """Return the finding codes in a list of problems.

    Parameters
    ----------
    problems : sequence of Problem
        The findings.

    Returns
    -------
    set of str
        The distinct codes.
    """
    return {problem.code for problem in problems}


def _valid_plots() -> pd.DataFrame:
    """Return a small valid plots frame.

    Returns
    -------
    pandas.DataFrame
        Three columns are filled, and the remaining required columns are present.
    """
    frame = coerce_to_schema(pd.read_csv(FIXTURE / "plots.csv"), PLOTS)
    return frame.iloc[[0, 1]].copy()


def test_fixture_has_two_aus_and_ten_plots() -> None:
    """The fixture is the two-AU, ten-plot contract that later tasks reuse."""
    frames = _frames()
    assert len(frames["plots"]) == 10
    assert set(frames["plots"]["au_id"]) == {"AU-IDFdk3-FDI", "AU-IDFdk3-PLI"}


def test_valid_fixture_has_no_problems() -> None:
    """The shipped fixture satisfies every structural, domain, and reference check."""
    frames = _frames()
    assert validate_dataset(frames, required=SDMD_TABLE_NAMES) == []


def test_schema_version_is_explicit() -> None:
    """The contract carries a version so a stored dataset can be identified."""
    assert SDMD_SCHEMA_VERSION == "ws4.sdmd.v1"


def test_table_schema_returns_the_named_table() -> None:
    """A known name resolves to its contract."""
    assert table_schema("regimes") is REGIMES


def test_table_schema_rejects_an_unknown_table() -> None:
    """An unknown name fails with the known names in the message."""
    with pytest.raises(KeyError, match="plots, trees, stands"):
        table_schema("yield_curves")


def test_coerce_adds_missing_columns_and_nullable_kinds() -> None:
    """Coercion adds absent columns and uses nullable pandas dtypes."""
    frame = pd.DataFrame({"au_id": ["AU-1"], "regime_id": ["REG-1"]})
    result = coerce_to_schema(frame, AU_CONSTRAINTS)
    assert ptypes.is_string_dtype(result["regime_id"])
    assert ptypes.is_bool_dtype(result["allowed"])
    assert ptypes.is_integer_dtype(result["max_entries"])
    assert ptypes.is_numeric_dtype(result["max_removal_fraction"])
    assert "review_status" in result.columns


def test_validate_frame_reports_a_missing_column() -> None:
    """A table without its required columns cannot pass."""
    problems = validate_frame(PLOTS, pd.DataFrame({"plot_id": ["P1"]}))
    assert "SDMD-MISSING-COLUMN" in _codes(problems)
    assert {problem.where for problem in problems} >= {"plots"}


def test_validate_frame_reports_a_wrong_kind() -> None:
    """A text year is a kind error, not a range error."""
    frame = _valid_plots().astype({"visit_year": "string"})
    problems = validate_frame(PLOTS, frame)
    assert "SDMD-COLUMN-KIND" in _codes(problems)
    assert "plots.visit_year" in {problem.where for problem in problems}


def test_validate_frame_reports_a_null_required_value() -> None:
    """A required value may not be missing."""
    frame = _valid_plots()
    frame.loc[0, "region"] = pd.NA
    assert "SDMD-NULL-VALUE" in _codes(validate_frame(PLOTS, frame))


def test_validate_frame_reports_blank_required_text() -> None:
    """A blank string is not a source and cannot stand in for one."""
    frame = _valid_plots()
    frame.loc[0, "sources"] = "   "
    assert "SDMD-EMPTY-VALUE" in _codes(validate_frame(PLOTS, frame))


def test_validate_frame_allows_a_nullable_text_column() -> None:
    """An empty optional field is allowed."""
    frame = _valid_plots()
    frame.loc[0, "bec_variant"] = pd.NA
    assert "SDMD-NULL-VALUE" not in _codes(validate_frame(PLOTS, frame))


def test_validate_frame_reports_a_duplicate_primary_key() -> None:
    """A plot visit is identified by plot id and visit year."""
    frame = _valid_plots()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    assert "SDMD-DUPLICATE-KEY" in _codes(validate_frame(PLOTS, frame))


def test_validate_dataset_reports_an_unknown_table() -> None:
    """Only the six declared tables belong to this contract."""
    frames = _frames()
    frames["yield_curves"] = pd.DataFrame({"au_id": ["AU-1"]})
    assert "SDMD-UNKNOWN-TABLE" in _codes(validate_dataset(frames))


def test_validate_dataset_reports_a_missing_required_table() -> None:
    """A caller can require a table that the input omits."""
    frames = _frames()
    del frames["regimes"]
    problems = validate_dataset(frames, required=SDMD_TABLE_NAMES)
    assert "SDMD-MISSING-TABLE" in _codes(problems)
    assert "regimes" in {problem.where for problem in problems}


def test_validate_dataset_accepts_a_single_table() -> None:
    """A partial dataset validates what it has and skips absent references."""
    frames = {"plots": _frames()["plots"]}
    assert validate_dataset(frames) == []


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        (PLOTS, "stand_age", -1),
        (PLOTS, "site_index", 0),
        (PLOTS, "aspect", 361),
        (PLOTS, "plot_area_ha", 0),
        (TREES, "dbh_cm", 0),
        (TREES, "crown_ratio", 1.5),
        (STANDS, "crown_cover_pct", 101),
        (STANDS, "volume_m3_ha", -0.1),
        (SDMD_POINTS, "qmd_cm", 0),
        (REGIMES, "removal_fraction", 1.5),
        (AU_CONSTRAINTS, "max_entries", -1),
    ],
)
def test_validate_dataset_reports_a_range_violation(
    table: Table, column: str, value: float
) -> None:
    """Every table enforces its numeric domain."""
    name = table.name
    frames = _frames()
    frames[name].loc[frames[name].index[0], column] = value
    problems = validate_dataset(frames)
    assert "SDMD-RANGE" in _codes(problems)
    assert f"{name}.{column}" in {problem.where for problem in problems}


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        (PLOTS, "review_status", "pending"),
        (SDMD_POINTS, "zone", "unknown"),
        (REGIMES, "entry_type", "seedtree"),
        (AU_CONSTRAINTS, "required_sdmd_zone", "unknown"),
        (AU_CONSTRAINTS, "review_status", "pending"),
    ],
)
def test_validate_dataset_reports_an_unknown_enumeration(
    table: Table, column: str, value: str
) -> None:
    """Unknown review statuses, zones, and entry types are refused."""
    name = table.name
    frames = _frames()
    frames[name].loc[frames[name].index[0], column] = value
    problems = validate_dataset(frames)
    assert "SDMD-ENUM" in _codes(problems)
    assert f"{name}.{column}" in {problem.where for problem in problems}


def test_validate_dataset_reports_an_inverted_entry_window() -> None:
    """A minimum entry age above the maximum is contradictory."""
    frames = _frames()
    frames["au_constraints"].loc[0, "min_entry_age"] = 120
    frames["au_constraints"].loc[0, "max_entry_age"] = 60
    problems = validate_dataset(frames)
    assert "SDMD-ENTRY-WINDOW" in _codes(problems)


def test_validate_dataset_reports_an_unknown_plot() -> None:
    """A tree list may only name plots in the plot table."""
    frames = _frames()
    tree = frames["trees"].iloc[[0]].copy()
    tree.loc[:, "plot_id"] = "PLOT-MISSING"
    frames["trees"] = pd.concat([frames["trees"], tree], ignore_index=True)
    problems = validate_dataset(frames)
    assert "SDMD-UNKNOWN-PLOT" in _codes(problems)
    assert "trees.plot_id" in {problem.where for problem in problems}


def test_validate_dataset_reports_an_unknown_stand_plot() -> None:
    """A stand summary may only name plots in the plot table."""
    frames = _frames()
    stand = frames["stands"].iloc[[0]].copy()
    stand.loc[:, "plot_id"] = "PLOT-MISSING"
    frames["stands"] = pd.concat([frames["stands"], stand], ignore_index=True)
    assert "SDMD-UNKNOWN-PLOT" in _codes(validate_dataset(frames))


def test_validate_dataset_reports_an_unknown_regime() -> None:
    """A constraint may only name a declared regime."""
    frames = _frames()
    frames["au_constraints"].loc[0, "regime_id"] = "REG-MISSING"
    problems = validate_dataset(frames)
    assert "SDMD-UNKNOWN-REGIME" in _codes(problems)


def test_validate_dataset_reports_a_regime_from_another_au() -> None:
    """A constraint's AU must own its regime."""
    frames = _frames()
    row = frames["au_constraints"].index[0]
    owner = frames["au_constraints"].loc[row, "au_id"]
    other = "AU-IDFdk3-PLI" if owner == "AU-IDFdk3-FDI" else "AU-IDFdk3-FDI"
    frames["au_constraints"].loc[row, "au_id"] = other
    assert "SDMD-REGIME-AU" in _codes(validate_dataset(frames))


def test_validate_dataset_reports_an_unknown_au() -> None:
    """An SDMD point may only name a known AU."""
    frames = _frames()
    frames["sdmd_points"].loc[0, "au_id"] = "AU-MISSING"
    assert "SDMD-UNKNOWN-AU" in _codes(validate_dataset(frames))


def test_validate_dataset_is_pure() -> None:
    """Validation does not mutate the caller's frames."""
    frames = _frames()
    before = copy.deepcopy(frames)
    validate_dataset(frames, required=SDMD_TABLE_NAMES)
    for name, frame in frames.items():
        pd.testing.assert_frame_equal(frame, before[name])
