"""Tests for explicit VRI stand treatment prescriptions."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _feature() -> dict[str, object]:
    return {
        "type": "Feature",
        "properties": {
            "FEATURE_ID": 42,
            "BCLCS_LEVEL_1": "V",
            "SPECIES_CD_1": "HW",
            "SPECIES_PCT_1": 60,
            "CROWN_CLOSURE": 70,
            "PROJ_HEIGHT_1": 21.7,
            "PROJ_AGE_1": 95,
        },
    }


def test_explicit_prescription_preview() -> None:
    module: Any = importlib.import_module("ws4.fire.prescription")
    stand = module.stand_from_vri_feature(_feature())
    assert stand is not None
    prescription = module.prescription_from_ffs("thin-burn", fuel_type="C2")
    preview = module.apply_stand_prescription(stand, prescription)
    assert preview.pre_fuel_type == "C2"
    assert preview.post_fuel_type == "C2"
    assert preview.post_crown_closure_pct == pytest.approx(53.97)
    assert preview.post_assignment.rule_id == "explicit-fbp"
    assert preview.basal_area_pct == pytest.approx(-29.0)
    assert preview.to_dict()["prescription"]["fuel_type"] == "C2"


def test_prescription_rejects_unknowns_and_features() -> None:
    module: Any = importlib.import_module("ws4.fire.prescription")
    with pytest.raises(KeyError, match="unknown FFS"):
        module.prescription_from_ffs("unknown", fuel_type="C2")
    with pytest.raises(ValueError, match="fuel_type"):
        module.prescription_from_ffs("thin-burn", fuel_type="ZZ")
    with pytest.raises(ValueError, match="name"):
        module.TreatmentPrescription("", "C2", 0.0, 0.0, 0.0, "source")
    assert module.stand_from_vri_feature({"properties": {"BCLCS_LEVEL_1": "N"}}) is None
    assert module.stand_from_vri_feature({"properties": {"BCLCS_LEVEL_1": "V"}}) is None


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module: Any = importlib.import_module("vri_treatment_preview")
    source = tmp_path / "vri.geojson"
    source.write_text(json.dumps({"type": "FeatureCollection", "features": [_feature()]}))
    output = tmp_path / "preview.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vri_treatment_preview.py",
            "--input",
            str(source),
            "--treatment",
            "thin-burn",
            "--fuel-type",
            "C7",
            "--output",
            str(output),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["stand_count"] == 1
    assert payload["stands"][0]["post_fuel_type"] == "C7"
