"""Tests for first-perimeter seeding in the generic observed runner."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ws4.fire.comparison import ComparisonError, observed_mask, run_observed_case
from ws4.fire.observed import load_cfsds_reanalysis_case

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fire" / "cfsds_2009_147"


def test_first_perimeter_seeds_many_cells() -> None:
    """The first perimeter seeds more than one cell and runs."""
    fire = load_cfsds_reanalysis_case(FIXTURE)
    metadata = json.loads((FIXTURE / "metadata.json").read_text(encoding="utf-8"))
    start = observed_mask(fire, 0)
    result = run_observed_case(
        fire,
        scenario="test",
        ffmc=float(metadata["ffmc"]),
        bui=float(metadata["bui"]),
        duration_min=float(metadata["duration_min"]),
        initial_mask=start,
    )
    assert result.start_cells > 1
    assert result.metrics.area_sim_ha > 0


def test_bad_initial_mask_fails() -> None:
    """Wrong-shaped and empty masks fail clearly."""
    fire = load_cfsds_reanalysis_case(FIXTURE)
    metadata = json.loads((FIXTURE / "metadata.json").read_text(encoding="utf-8"))
    with pytest.raises(ComparisonError, match="shape"):
        run_observed_case(
            fire,
            scenario="test",
            ffmc=float(metadata["ffmc"]),
            bui=float(metadata["bui"]),
            duration_min=10.0,
            initial_mask=np.zeros((1, 1), dtype=bool),
        )
    with pytest.raises(ComparisonError, match="no burnable"):
        run_observed_case(
            fire,
            scenario="test",
            ffmc=float(metadata["ffmc"]),
            bui=float(metadata["bui"]),
            duration_min=10.0,
            initial_mask=np.zeros((fire.grid.nrows, fire.grid.ncols), dtype=bool),
        )
