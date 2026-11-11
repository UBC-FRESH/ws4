"""Tests for the containment-boundary input."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ws4.fire.comparison import ComparisonError, DogribCase, observed_mask, run_observed_case
from ws4.fire.observed import load_cfsds_reanalysis_case

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fire" / "cfsds_2009_147"


def _run(mask: np.ndarray | None = None) -> DogribCase:
    fire = load_cfsds_reanalysis_case(FIXTURE)
    metadata = json.loads((FIXTURE / "metadata.json").read_text(encoding="utf-8"))
    return run_observed_case(
        fire,
        scenario="containment",
        ffmc=float(metadata["ffmc"]),
        bui=float(metadata["bui"]),
        duration_min=float(metadata["duration_min"]),
        initial_mask=observed_mask(fire, 0),
        containment_mask=mask,
    )


def test_containment_mask_reduces_burnable_area() -> None:
    """A containment block is excluded from the simulation."""
    baseline = _run()
    rows = int(baseline.growth.grid.rows)
    cols = int(baseline.growth.grid.cols)
    mask = np.zeros((rows, cols), dtype=bool)
    mask[:, -10:] = True
    contained = _run(mask)
    assert contained.metrics.area_sim_ha < baseline.metrics.area_sim_ha
    assert np.isinf(contained.growth.ignition_time_min[mask]).all()


def test_containment_mask_validation() -> None:
    """Bad shapes and fully contained grids fail clearly."""
    baseline = _run()
    with pytest.raises(ComparisonError, match="shape"):
        _run(np.zeros((1, 1), dtype=bool))
    rows = int(baseline.growth.grid.rows)
    cols = int(baseline.growth.grid.cols)
    with pytest.raises(ComparisonError, match="no burnable"):
        _run(np.ones((rows, cols), dtype=bool))
