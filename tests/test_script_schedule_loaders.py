"""Unit tests for the measurement scripts' schedule CSV loaders."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import benchmark_route_events
import profile_route


def test_both_measurement_loaders_group_and_sort_treatment_chains(tmp_path: Path) -> None:
    """Both scripts read a run schedule into the same ordered block -> chain mapping."""
    path = tmp_path / "schedule.csv"
    pd.DataFrame(
        {
            "block_id": [2, 1, 1],
            "treatment": ["CC", "CC", "TH"],
            "offset": [5, 10, 0],
        }
    ).to_csv(path, index=False)
    expected = {
        1: (("TH", 0), ("CC", 10)),
        2: (("CC", 5),),
    }
    assert benchmark_route_events.load_schedule(path) == expected
    assert profile_route.load_schedule(path) == expected
