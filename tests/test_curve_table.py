"""Tests for the shared age-grid curve table."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from ws4.sim.curve import CurveTable, curve_value


def _tiny() -> pd.DataFrame:
    """Two curves: a triangle over ages 0..20, and a single-point constant."""
    return pd.DataFrame(
        {
            "curve_id": [1, 1, 1, 2],
            "x": [0.0, 10.0, 20.0, 0.0],
            "y": [0.0, 100.0, 0.0, 5.0],
        }
    )


def test_the_table_reproduces_integer_ages() -> None:
    """A curve's value at an integer age is exact."""
    table = CurveTable.from_curves(_tiny())
    assert table.age_max == 20
    assert table.at(1, 0) == 0.0
    assert table.at(1, 5) == 50.0
    assert table.at(1, 20) == 0.0


def test_the_table_clamps_out_of_range_ages() -> None:
    """Ages below zero and above the range clamp to the endpoints."""
    table = CurveTable.from_curves(_tiny())
    assert table.at(1, -4) == 0.0
    assert table.at(1, 100) == 0.0  # clamps to the age_max column


def test_a_single_point_curve_is_constant() -> None:
    """A one-point curve is that value everywhere."""
    table = CurveTable.from_curves(_tiny())
    assert table.at(2, 0) == 5.0
    assert table.at(2, 7) == 5.0
    assert table.at(2, 1000) == 5.0


def test_a_non_integer_age_is_not_served_by_the_table() -> None:
    """A non-integer age returns None so the caller falls back to interpolation."""
    assert CurveTable.from_curves(_tiny()).at(1, 2.5) is None


def test_an_absent_curve_returns_none() -> None:
    """An unknown curve id is not in the table."""
    assert CurveTable.from_curves(_tiny()).at(99, 3) is None


def test_gather_matches_at() -> None:
    """The vectorized gather returns the same values as the scalar lookup."""
    table = CurveTable.from_curves(_tiny())
    rows = np.array([table.row(1), table.row(2)], dtype=np.int64)
    values = table.gather(rows, np.array([5, 7]))
    assert list(values) == [50.0, 5.0]


def test_gather_clamps_at_both_ends() -> None:
    """The vectorized gather clamps an out-of-range age to the table's ends."""
    ramp = pd.DataFrame({"curve_id": [4, 4], "x": [0.0, 10.0], "y": [1.0, 21.0]})
    table = CurveTable.from_curves(ramp)
    rows = np.array([0, 0, 0, 0], dtype=np.int64)
    ages = np.array([-5.0, 0.0, 10.0, 99.0])
    assert table.gather(rows, ages).tolist() == [1.0, 1.0, 21.0, 21.0]


def test_gather_returns_values_independent_of_the_table() -> None:
    """The gather copies, so writing to the result cannot corrupt the table."""
    table = CurveTable.from_curves(_tiny())
    rows = np.array([0, 0], dtype=np.int64)
    values = table.gather(rows, np.array([5.0, 10.0]))
    values[:] = -1.0
    assert table.gather(rows, np.array([5.0, 10.0])).tolist() == [50.0, 100.0]


def test_the_table_matches_curve_value_on_a_real_dataset() -> None:
    """The table equals ``curve_value`` for integer ages on the fixture's curves."""
    curves = pd.DataFrame(
        {
            "curve_id": [1, 1, 1, 2, 2],
            "x": [0.0, 40.0, 80.0, 0.0, 100.0],
            "y": [0.0, 120.0, 220.0, 10.0, 30.0],
        }
    )
    table = CurveTable.from_curves(curves)
    for curve_id in (1, 2):
        for age in (0, 1, 17, 40, 80, 99, 200):
            assert table.at(curve_id, age) == pytest.approx(curve_value(curves, curve_id, age))


def test_an_empty_curves_table_builds_an_empty_table() -> None:
    """An empty curves table yields an empty table that serves nothing."""
    table = CurveTable.from_curves(pd.DataFrame({"curve_id": [], "x": [], "y": []}))
    assert table.row_of == {}
    assert table.at(1, 0) is None


def test_value_matches_curve_value_for_integer_and_fractional_ages() -> None:
    """``value`` is exact at integer ages and linear between them, and clamps."""
    table = CurveTable.from_curves(_tiny())
    for age in (0, 5, 10, 15, 20, 2.5, 7.25, -3, 100):
        assert table.value(1, age) == pytest.approx(curve_value(_tiny(), 1, age))
    # A single-point curve is constant, and an absent curve is zero.
    assert table.value(2, 7.5) == pytest.approx(curve_value(_tiny(), 2, 7.5))
    assert table.value(99, 3) == 0.0
