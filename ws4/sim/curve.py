"""Curve evaluation for the simulator."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def curve_value(curves: pd.DataFrame, curve_id: int, x: float) -> float:
    """Evaluate a long-format curve at ``x`` by linear interpolation.

    Values below the first point and above the last point are clamped to the
    endpoint values, matching the model's interpolation contract.

    Parameters
    ----------
    curves : pandas.DataFrame
        The ``curves`` table, with ``curve_id``, ``x``, and ``y`` columns.
    curve_id : int
        The curve to evaluate.
    x : float
        The domain value (for example, an offset age).

    Returns
    -------
    float
        The interpolated value, or ``0.0`` when the curve has no points.
    """
    points = curves[curves["curve_id"] == curve_id].sort_values("x")
    if points.empty:
        return 0.0
    xs = points["x"].to_numpy(dtype=float)
    ys = points["y"].to_numpy(dtype=float)
    return float(np.interp(x, xs, ys))


@dataclass
class CurveTable:
    """Curve values precomputed at every integer age, for gather-based evaluation.

    Every offset that reaches curve evaluation is an integer age, and curve breakpoints
    are integers, so a table ``table[row, age] = curve(age)`` is exact and evaluation is a
    2-D gather rather than a per-curve interpolation. Ages above ``age_max`` clamp to the
    last column (matching ``numpy.interp``).

    Attributes
    ----------
    table : numpy.ndarray
        ``(n_curves, age_max + 1)`` float64 values.
    row_of : dict of int to int
        Curve id to table row.
    age_max : int
        The largest age the table covers.
    """

    table: np.ndarray
    row_of: dict[int, int]
    age_max: int

    @classmethod
    def from_curves(cls, curves: pd.DataFrame) -> CurveTable:
        """Build the table from a long-format curves table.

        Parameters
        ----------
        curves : pandas.DataFrame
            The ``curves`` table, with ``curve_id``, ``x``, and ``y`` columns.

        Returns
        -------
        CurveTable
            The table. Empty when the curves table is empty.
        """
        if curves.empty:
            return cls(table=np.zeros((0, 1)), row_of={}, age_max=0)
        frame = curves.sort_values(["curve_id", "x"])
        identifiers = frame["curve_id"].to_numpy()
        xs_all = frame["x"].to_numpy(dtype=float)
        ys_all = frame["y"].to_numpy(dtype=float)
        age_max = int(np.max(xs_all))
        boundaries = np.flatnonzero(np.diff(identifiers)) + 1
        group_ids = identifiers[np.concatenate([[0], boundaries])]
        segments = np.split(np.arange(identifiers.size), boundaries)
        table = np.zeros((len(group_ids), age_max + 1), dtype=float)
        row_of: dict[int, int] = {}
        grid = np.arange(age_max + 1, dtype=float)
        for row, (curve_id, segment) in enumerate(zip(group_ids, segments, strict=True)):
            table[row] = np.interp(grid, xs_all[segment], ys_all[segment])
            row_of[int(curve_id)] = row
        return cls(table=table, row_of=row_of, age_max=age_max)

    def row(self, curve_id: int) -> int | None:
        """Return a curve's table row, or None when the curve is absent.

        Parameters
        ----------
        curve_id : int
            The curve identifier.

        Returns
        -------
        int or None
            The row in :attr:`table`, or None when the curve is not in the table.
        """
        return self.row_of.get(int(curve_id))

    def at(self, curve_id: int, x: float) -> float | None:
        """Return a curve's value at an integer age, or None for a non-integer/absent curve.

        Parameters
        ----------
        curve_id : int
            The curve.
        x : float
            The age. A non-integer age returns None so the caller can fall back to
            interpolation.

        Returns
        -------
        float or None
            The value, or None when the curve is absent or the age is not an integer.
        """
        row = self.row_of.get(int(curve_id))
        if row is None or x != int(x):
            return None
        age = min(max(int(x), 0), self.age_max)
        return float(self.table[row, age])

    def value(self, curve_id: int, x: float) -> float:
        """Return a curve's value at any age.

        Integer ages are exact; a non-integer age interpolates the two bracketing integer
        columns (the curve is linear between integer breakpoints). Ages at or beyond the
        ends clamp, and an absent curve is ``0.0``.

        Parameters
        ----------
        curve_id : int
            The curve.
        x : float
            The age.

        Returns
        -------
        float
            The value.
        """
        row = self.row_of.get(int(curve_id))
        if row is None:
            return 0.0
        if x >= self.age_max:
            return float(self.table[row, self.age_max])
        if x <= 0:
            return float(self.table[row, 0])
        low = int(x)
        fraction = x - low
        if fraction == 0.0:
            return float(self.table[row, low])
        lower = float(self.table[row, low])
        upper = float(self.table[row, low + 1])
        return lower + fraction * (upper - lower)

    def gather(self, rows: np.ndarray, ages: np.ndarray) -> np.ndarray:
        """Return the values for precomputed curve rows at integer ages.

        The table is addressed flat — ``row * (age_max + 1) + age`` into the table's own buffer —
        rather than through numpy's two-array indexing, which computes the same addresses with a
        per-element bounds check and stride fold. Measured on a real C5 call of 205,942 queries over
        a ``(1801, 843)`` table: 877 us against 1,150 us, for identical values.

        Parameters
        ----------
        rows : numpy.ndarray
            The table row per query (from :meth:`row`).
        ages : numpy.ndarray
            The integer age per query; clipped to ``[0, age_max]``.

        Returns
        -------
        numpy.ndarray
            The curve value per query.
        """
        clipped = np.clip(ages, 0, self.age_max).astype(np.int64)
        return np.asarray(self.table.ravel()[rows * (self.age_max + 1) + clipped])
