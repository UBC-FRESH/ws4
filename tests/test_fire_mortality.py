"""Tests for the FOFEM tree-mortality equation and FTM validator."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_mortality_probability_monotonicity() -> None:
    module: Any = importlib.import_module("ws4.fire.mortality")
    low = module.mortality_probability(
        dbh_cm=30.0,
        crown_volume_scorched_pct=20.0,
        bark_coefficient=0.028,
    )
    high = module.mortality_probability(
        dbh_cm=30.0,
        crown_volume_scorched_pct=80.0,
        bark_coefficient=0.028,
    )
    thick = module.mortality_probability(
        dbh_cm=30.0,
        crown_volume_scorched_pct=80.0,
        bark_coefficient=0.063,
    )
    assert 0.0 < low < high < 1.0
    assert thick < high
    assert module.species_mortality(
        species_code="PICO",
        dbh_cm=30.0,
        crown_volume_scorched_pct=80.0,
    ) == pytest.approx(high)


def test_metrics_and_invalid_inputs() -> None:
    module: Any = importlib.import_module("ws4.fire.mortality")
    observed = np.array([0.0, 0.0, 1.0, 1.0])
    predicted = np.array([0.1, 0.2, 0.8, 0.9])
    assert module.rank_auc(observed, predicted) == pytest.approx(1.0)
    assert module.brier_score(observed, predicted) == pytest.approx(0.025)
    with pytest.raises(ValueError, match="dbh_cm"):
        module.mortality_probability(
            dbh_cm=1.0, crown_volume_scorched_pct=50.0, bark_coefficient=0.028
        )
    with pytest.raises(ValueError, match="crown_volume"):
        module.mortality_probability(
            dbh_cm=30.0, crown_volume_scorched_pct=101.0, bark_coefficient=0.028
        )
    with pytest.raises(KeyError, match="no bark"):
        module.species_mortality(species_code="XXXX", dbh_cm=30.0, crown_volume_scorched_pct=50.0)
    with pytest.raises(ValueError, match="one-dimensional"):
        module.rank_auc(np.array([[0.0, 1.0]]), np.array([[0.1, 0.9]]))


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    trees = tmp_path / "trees.csv"
    trees.write_text(
        "Species,DBH_cm,CVS_percent,yr3status,Dataset,YrFireName\n"
        "PICO,30,80,1,A,f1\n"
        "PICO,10,0,0,B,f2\n"
        "PSME,40,100,1,C,f3\n"
        "PSME,5,10,0,D,f4\n"
        "PICO,25,40,0,E,f5\n",
        encoding="utf-8",
    )
    bark = tmp_path / "bark.csv"
    bark.write_text(
        "PLANTS_Species_Code,Genus_Species,BT_coef\n"
        "PICO,Pinus contorta,0.028\n"
        "PSME,Pseudotsuga menziesii,0.063\n",
        encoding="utf-8",
    )
    return trees, bark


def test_ftm_validator_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trees, bark = _write_fixture(tmp_path)
    output = tmp_path / "result.json"
    module: Any = importlib.import_module("validate_tree_mortality")
    frame = module.load_ftm(trees, bark)
    assert len(frame) == 5
    assert frame["observed"].sum() == 2
    train, validation = module.split_by_dataset(frame)
    assert len(train) + len(validation) == len(frame)
    with pytest.raises(ValueError, match="fraction"):
        module.split_by_dataset(frame, fraction=1.0)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_tree_mortality.py",
            "--trees",
            str(trees),
            "--bark",
            str(bark),
            "--output",
            str(output),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["sample"]["n"] == 5
    assert payload["dataset"].startswith("Fire and Tree Mortality")
