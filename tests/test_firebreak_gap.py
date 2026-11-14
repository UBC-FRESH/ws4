"""Tests for the P201 firebreak-gap diagnostic."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_closed_barrier_is_full_height_and_single_column() -> None:
    module: Any = importlib.import_module("run_firebreak_gap_2003_96")
    mask = module.build_gap_barrier(rows=6, cols=8, barrier_col=3, gap_center_row=2, gap_cells=0)
    assert mask.shape == (6, 8)
    assert mask[:, 3].all()
    assert mask.sum() == 6


def test_barrier_gap_opens_only_the_requested_rows() -> None:
    module: Any = importlib.import_module("run_firebreak_gap_2003_96")
    mask = module.build_gap_barrier(rows=7, cols=8, barrier_col=3, gap_center_row=3, gap_cells=3)
    assert np.flatnonzero(mask[:, 3]).tolist() == [0, 1, 5, 6]
    assert not mask[2:5, 3].any()


def test_oracle_barrier_falls_between_start_and_eastern_extent() -> None:
    module: Any = importlib.import_module("run_firebreak_gap_2003_96")
    start = np.zeros((5, 10), dtype=bool)
    start[2, 1] = True
    observed = np.zeros((5, 10), dtype=bool)
    observed[2, 9] = True
    assert module._oracle_barrier_column(start, observed) == 6


def test_gap_artifact_shows_geometry_control_over_weather() -> None:
    payload = json.loads(
        (ROOT / "notes/reports/p201-firebreak-gap.json").read_text(encoding="utf-8")
    )
    by_gap: dict[int, set[float]] = {}
    for row in payload["rows"]:
        by_gap.setdefault(int(row["gap_cells"]), set()).add(float(row["area_sim_ha"]))
    assert by_gap == {0: {98025.0}, 5: {158025.0}, 10: {158150.0}}
    assert all(
        row["east_of_barrier_burned_cells"] == 0 for row in payload["rows"] if row["gap_cells"] == 0
    )
