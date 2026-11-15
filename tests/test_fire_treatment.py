"""Tests for the published treatment-effect evidence contract."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from ws4.fire.observed import load_cfsds_reanalysis_case

MODULE = "ws4.fire.treatment"


def test_evidence_registry_and_position() -> None:
    module: Any = importlib.import_module(MODULE)
    item = module.evidence_for("thinning_plus_prescribed_fire")
    assert item.low == 0.62
    assert item.high == 0.72
    assert item.position(0.61) == "below"
    assert item.position(0.67) == "within"
    assert item.position(0.73) == "above"
    assert item.to_dict()["metric"] == "severity_reduction_fraction"
    assert len(module.TREATMENT_EVIDENCE) == 5


def test_reduction_fraction_and_classification() -> None:
    module: Any = importlib.import_module(MODULE)
    assert module.reduction_fraction(100.0, 30.0) == pytest.approx(0.70)
    result = module.classify_effect(
        baseline=100.0,
        treated=30.0,
        treatment="thinning_plus_prescribed_fire",
    )
    assert result["position"] == "within"
    assert result["reduction_fraction"] == pytest.approx(0.70)
    assert result["published_low"] == 0.62
    assert result["published_high"] == 0.72


def test_invalid_evidence_and_inputs() -> None:
    module: Any = importlib.import_module(MODULE)
    with pytest.raises(KeyError, match="no treatment evidence"):
        module.evidence_for("unknown")
    with pytest.raises(ValueError, match="baseline"):
        module.reduction_fraction(0.0, 1.0)
    with pytest.raises(ValueError, match="treated"):
        module.reduction_fraction(1.0, -1.0)
    with pytest.raises(ValueError, match="bounds"):
        module.TreatmentEvidence("x", "m", 0.8, 0.2, "s", "b")


def test_apply_fuel_treatment_changes_only_masked_cells() -> None:
    module: Any = importlib.import_module(MODULE)
    fire = load_cfsds_reanalysis_case(
        Path(__file__).resolve().parent / "fixtures" / "fire" / "fine_2003_96"
    )
    fuel_grid = fire.fbp_fuel_grid()
    row, col = np.argwhere(np.array([[value is not None for value in row] for row in fuel_grid]))[0]
    mask = np.zeros_like(fire.fuel_codes, dtype=bool)
    mask[row, col] = True
    before = fire.fuel_type_at(int(row), int(col))
    treated = module.apply_fuel_treatment(fire, mask=mask, replacement="D1")
    assert treated.fuel_type_at(int(row), int(col)) == "D1"
    assert fire.fuel_type_at(int(row), int(col)) == before
    assert treated.fuel_codes.shape == fire.fuel_codes.shape


def test_apply_fuel_treatment_rejects_bad_masks_and_codes() -> None:
    module: Any = importlib.import_module(MODULE)
    fire = load_cfsds_reanalysis_case(
        Path(__file__).resolve().parent / "fixtures" / "fire" / "fine_2003_96"
    )
    with pytest.raises(ValueError, match="shape"):
        module.apply_fuel_treatment(
            fire,
            mask=np.zeros((1, 1), dtype=bool),
            replacement="D1",
        )
    empty = np.zeros_like(fire.fuel_codes, dtype=bool)
    with pytest.raises(ValueError, match="at least one"):
        module.apply_fuel_treatment(fire, mask=empty, replacement="D1")
    used = next(iter(fire.fuel_lookup))
    mask = np.zeros_like(fire.fuel_codes, dtype=bool)
    mask[0, 0] = True
    with pytest.raises(ValueError, match="already in use"):
        module.apply_fuel_treatment(fire, mask=mask, replacement="D1", code=used)
    non_fuel = np.array(
        [[value is None for value in row] for row in fire.fbp_fuel_grid()],
        dtype=bool,
    )
    if non_fuel.any():
        with pytest.raises(ValueError, match="non-fuel"):
            module.apply_fuel_treatment(fire, mask=non_fuel, replacement="D1")
