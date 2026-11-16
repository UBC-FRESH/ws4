"""Tests for the FFS treatment-effect extractor."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

KEYS = ["SITE_CODE", "UNIT_CODE", "TREATMENT_NAME", "SAMPLE_YEAR_CODE"]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SITE_CODE": [1, 1, 1, 1, 2, 2],
            "UNIT_CODE": [10, 10, 11, 11, 12, 12],
            "TREATMENT_NAME": ["thin", "thin", "burn", "burn", "thin", "thin"],
            "SAMPLE_YEAR_CODE": [-1, 1, -1, 1, -1, 1],
            "VALUE": [100.0, 50.0, 100.0, 20.0, 10.0, 9.0],
        }
    )


def test_pair_and_summary() -> None:
    module: Any = importlib.import_module("ws4.fire.treatment_effects")
    paired = module.pair_pre_post(_frame(), "VALUE")
    assert len(paired) == 3
    assert set(paired["pct_change"]) == {-50.0, -80.0, -10.0}
    summary = module.summarize_effects(paired).set_index("TREATMENT_NAME")
    assert summary.loc["thin", "n"] == 2
    assert summary.loc["thin", "median"] == pytest.approx(-30.0)
    assert summary.loc["burn", "median"] == pytest.approx(-80.0)


def test_surface_fuel_and_invalid_inputs() -> None:
    module: Any = importlib.import_module("ws4.fire.treatment_effects")
    fuels = pd.DataFrame(
        {
            "SITE_CODE": [1, 1],
            "UNIT_CODE": [10, 10],
            "TREATMENT_NAME": ["thin", "thin"],
            "SAMPLE_YEAR_CODE": [-1, 1],
            "ONE_HOUR_FUELS": [1.0, 2.0],
            "TEN_HOUR_FUELS": [2.0, 1.0],
            "HUNDRED_HOUR_FUELS": [3.0, 1.0],
            "SOUND_1000_HOUR_FUELS": [4.0, 1.0],
            "ROTTEN_1000_HOUR_FUELS": [5.0, 1.0],
        }
    )
    fuels["TOTAL"] = module.surface_fuel_total(fuels)
    paired = module.pair_pre_post(fuels, "TOTAL")
    assert float(paired["pct_change"].iloc[0]) == pytest.approx(-60.0)
    with pytest.raises(ValueError, match="missing columns"):
        module.pair_pre_post(pd.DataFrame({"x": [1]}), "x")
    with pytest.raises(ValueError, match="missing fuel"):
        module.surface_fuel_total(pd.DataFrame({"x": [1]}))
    with pytest.raises(ValueError, match="pre and post"):
        module.pair_pre_post(_frame().assign(SAMPLE_YEAR_CODE=1), "VALUE")


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module: Any = importlib.import_module("ffs_treatment_effects")
    vegetation = tmp_path / "vegetation.csv"
    trees = tmp_path / "trees.csv"
    fuels = tmp_path / "fuels.csv"
    base = _frame().rename(columns={"VALUE": "CANOPY_COVER_VERT_PROJECTION"})
    base.to_csv(vegetation, index=False)
    _frame().rename(columns={"VALUE": "LIVE_TREE_BASAL_AREA"}).to_csv(trees, index=False)
    fuel = _frame().rename(columns={"VALUE": "ONE_HOUR_FUELS"})
    for name in (
        "TEN_HOUR_FUELS",
        "HUNDRED_HOUR_FUELS",
        "SOUND_1000_HOUR_FUELS",
        "ROTTEN_1000_HOUR_FUELS",
    ):
        fuel[name] = 0.0
    fuel.to_csv(fuels, index=False)
    output = tmp_path / "out.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ffs_treatment_effects.py",
            "--vegetation",
            str(vegetation),
            "--trees",
            str(trees),
            "--fuels",
            str(fuels),
            "--output",
            str(output),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["dataset"].startswith("National Fire and Fire Surrogate")
    assert len(payload["metrics"]["surface_fuel_pct_change"]) == 2
