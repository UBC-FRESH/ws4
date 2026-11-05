"""BC-wide SDMD coverage registry.

The registry answers one question for every current BEC label: which digitized
diagrams apply, whether they are reviewed, and whether an AU store exists. It is
not an AU and does not invent evidence.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

__all__ = ["COVERAGE_PATH", "coverage_frame", "coverage_payload", "coverage_row"]

COVERAGE_PATH = Path(__file__).resolve().parent / "data" / "sdmd" / "bec_coverage.csv"
COVERAGE_SCHEMA_VERSION = "ws4.sdmd.coverage.v1"


@lru_cache(maxsize=1)
def coverage_frame() -> pd.DataFrame:
    """Return the packaged BEC coverage registry.

    Returns
    -------
    pandas.DataFrame
        One row per current BEC label.
    """
    return pd.read_csv(COVERAGE_PATH, dtype=str).fillna("")


def coverage_payload(
    *,
    zone: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Return the coverage registry, optionally filtered.

    Parameters
    ----------
    zone : str or None, optional
        BEC zone filter.
    status : str or None, optional
        ``reviewed``, ``provisional``, or ``no-diagram`` filter.

    Returns
    -------
    dict
        Schema version, total count, status counts, and matching rows.
    """
    frame = coverage_frame()
    if zone:
        frame = frame[frame["zone"] == zone]
    if status:
        frame = frame[frame["coverage_status"] == status]
    counts = coverage_frame()["coverage_status"].value_counts().to_dict()
    return {
        "schema_version": COVERAGE_SCHEMA_VERSION,
        "count": len(frame),
        "counts": {str(key): int(value) for key, value in counts.items()},
        "rows": frame.to_dict(orient="records"),
    }


def coverage_row(bec: str) -> dict[str, Any] | None:
    """Return one BEC coverage row, or None.

    Parameters
    ----------
    bec : str
        Compact BEC label such as ``IDFdk3``.

    Returns
    -------
    dict or None
        The row, or None when the label is not a current BEC.
    """
    frame = coverage_frame()
    match = frame[frame["bec"] == bec]
    if match.empty:
        return None
    row = match.iloc[0].to_dict()
    return {str(key): value for key, value in row.items()}
