"""The schedule time-key contract.

WS4 runs on two clocks, and they must not be confused:

- the **simulation clock** is the year. Year 1 is the first one-year step,
  immediately after the zero-length accounting period 0. A schedule carries the
  number of years after the start of the simulation that a treatment happens:
  the ``offset``. Offset 0 is year 1.
- the **accounting clock** is the period. Period 0 is the instantaneous
  pre-simulation snapshot; periods 1 and later are the accounting intervals
  that targets are set on.

A schedule therefore carries an ``offset`` column, not a ``period`` column. The
old ``period`` column name is rejected because it collides with the accounting
clock and allowed the nonsensical "treatment in period 0".
"""

from __future__ import annotations

import pandas as pd

SCHEDULE_OFFSET_COLUMN = "offset"
SCHEDULE_PERIOD_ALIAS = "period"


def schedule_offset_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a schedule frame keyed by the canonical ``offset`` column.

    Parameters
    ----------
    frame : pandas.DataFrame
        A schedule frame. It must carry ``offset``.

    Returns
    -------
    pandas.DataFrame
        A copy with an integer ``offset`` column.

    Raises
    ------
    ValueError
        When ``offset`` is missing, when the legacy ``period`` column is used,
        or when an offset is negative.
    """
    if SCHEDULE_PERIOD_ALIAS in frame.columns and SCHEDULE_OFFSET_COLUMN not in frame.columns:
        raise ValueError(
            "schedule uses the accounting column 'period'; schedules are keyed by "
            "'offset', the number of years after the start of the simulation, where "
            "offset 0 is year 1. Period 0 is the zero-length pre-simulation snapshot "
            "and is not a treatment slot."
        )
    if SCHEDULE_OFFSET_COLUMN not in frame.columns:
        raise ValueError("schedule is missing the required 'offset' column")
    result = frame.copy()
    result[SCHEDULE_OFFSET_COLUMN] = pd.to_numeric(
        result[SCHEDULE_OFFSET_COLUMN], errors="raise"
    ).astype(int)
    if (result[SCHEDULE_OFFSET_COLUMN] < 0).any():
        raise ValueError("schedule offsets must be non-negative")
    return result
