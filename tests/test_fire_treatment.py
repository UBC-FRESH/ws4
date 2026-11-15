"""Tests for the published treatment-effect evidence contract."""

from __future__ import annotations

import importlib
from typing import Any

import pytest

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
