"""End-to-end prototype test: build, validate, and simulate the synthetic landscape."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.model.schema import validate_dataset
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
_RECIPE = _FIXTURE / "recipe.xml"
_FRAGMENTS = _FIXTURE / "fragments.csv"


def _build(tmp_path: Path) -> Path:
    """Compile the synthetic fixture into a dataset."""
    return build_canonical_dataset(_RECIPE, _FRAGMENTS, tmp_path / "compiled")


def _simulate(dataset: Path, schedule: Path, tmp_path: Path, years: int) -> pd.DataFrame:
    """Simulate a schedule and return the account values."""
    out = tmp_path / f"sim-{schedule.stem}-{years}"
    Simulator.from_dataset(dataset).run(schedule, years=years, out_dir=out)
    return pd.read_csv(out / "account_values.csv")


def _write_schedule(tmp_path: Path, name: str, rows: list[tuple[int, str, int]]) -> Path:
    """Write a schedule CSV."""
    path = tmp_path / name
    pd.DataFrame(rows, columns=["block_id", "treatment", "offset"]).to_csv(path, index=False)
    return path


def test_build_produces_a_valid_dataset(tmp_path: Path) -> None:
    """The compiled synthetic dataset validates cleanly."""
    assert validate_dataset(_build(tmp_path)) == []


def test_simulate_grows_the_feature_account(tmp_path: Path) -> None:
    """With no schedule, the feature account follows the curve as fragments age."""
    dataset = _build(tmp_path)
    schedule = _write_schedule(tmp_path, "empty.csv", [])
    values = _simulate(dataset, schedule, tmp_path, years=2)
    volume = values[values["account"] == "feature.Volume"].set_index("offset")["value"]
    assert volume.loc[0] == pytest.approx(700.0)
    assert volume.loc[1] == pytest.approx(712.5)


def test_treatment_resets_offset_and_switches_track(tmp_path: Path) -> None:
    """A scheduled treatment resets the offset and moves the fragment off the track."""
    dataset = _build(tmp_path)
    schedule = _write_schedule(tmp_path, "cc.csv", [(1, "CC", 0)])
    values = _simulate(dataset, schedule, tmp_path, years=1)
    volume = values[values["account"] == "feature.Volume"].set_index("offset")["value"]
    assert volume.loc[0] == pytest.approx(340.0)
