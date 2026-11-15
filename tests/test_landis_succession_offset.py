"""Five-year succession comparison and offset convention."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.ecosystem.bridge import VolumeBridgeConfig, age_volume_curves_from_frame
from ws4.ecosystem.evaluation import evaluate_process_schedule
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.ecosystem.landis import LandisSuccessionProcess
from ws4.ecosystem.regeneration import RegenerationConfig
from ws4.ecosystem.state import CohortState
from ws4.opt.account_compare import compare_accounts
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _state() -> CohortState:
    """Build the two-fragment state at ages 40 and 60."""
    _schema, base, _edges = synthetic_grid(1, 2)
    rows = [
        {
            "fragment_id": fragment,
            "cohort_id": 1,
            "species": "PL",
            "age": 40 if fragment == 1 else 60,
            "area_fraction": 1.0,
            "biomass_t_ha": 120.0 if fragment == 1 else 170.0,
            "fuel_t_ha": 0.0,
            "snag_t_ha": 0.0,
            "attributes_json": "{}",
        }
        for fragment in (1, 2)
    ]
    return CohortState(
        cohorts=pd.DataFrame(rows, columns=base.cohorts.columns),
        schema=base.schema,
        fragment_areas={1: 3.0, 2: 2.0},
    )


def _run_process(curves: dict[str, dict[int, float]], horizon: int, tmp_path: Path) -> object:
    """Run LANDIS succession with no schedule for the requested horizon."""
    del tmp_path
    return evaluate_process_schedule(
        _state(),
        (),
        {},
        {},
        horizon_years=horizon,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        bridge=VolumeBridgeConfig(
            default_volume_m3_per_t=0.0,
            merchantable_fraction=1.0,
            age_volume_curves=curves,
        ),
        succession_process=LandisSuccessionProcess(),
        seed=1,
    )


def test_four_transitions_match_the_five_year_estate_offset(tmp_path: Path) -> None:
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "dataset"
    )
    schedule = tmp_path / "empty.csv"
    pd.DataFrame(columns=["block_id", "treatment", "offset"]).to_csv(schedule, index=False)
    estate = Simulator.from_dataset(dataset).simulate(pd.read_csv(schedule), years=5)
    curves = age_volume_curves_from_frame(pd.read_parquet(dataset / "curves.parquet"), {"PL": 2})

    four = _run_process(curves, 4, tmp_path)
    five = _run_process(curves, 5, tmp_path)
    from ws4.ecosystem.evaluation import ProcessScheduleEvaluation

    assert isinstance(four, ProcessScheduleEvaluation)
    assert isinstance(five, ProcessScheduleEvaluation)
    four_row = compare_accounts(
        four.accounts, estate, {"bridge.volume_m3": "feature.Volume"}
    ).rows.iloc[0]
    five_row = compare_accounts(
        five.accounts, estate, {"bridge.volume_m3": "feature.Volume"}
    ).rows.iloc[0]

    assert four_row["process_value"] == pytest.approx(750.0)
    assert four_row["absolute_difference"] == pytest.approx(0.0)
    assert five_row["process_value"] == pytest.approx(762.5)
    assert five_row["absolute_difference"] == pytest.approx(12.5)
    assert five_row["relative_difference"] == pytest.approx(12.5 / 750.0)
