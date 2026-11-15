"""Five-year harvest comparison and the missing track-change state."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.ecosystem.bridge import VolumeBridgeConfig, track_age_volume_curves_from_frame
from ws4.ecosystem.evaluation import ProcessScheduleEvaluation, evaluate_process_schedule
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.ecosystem.landis import LandisSuccessionProcess
from ws4.ecosystem.regeneration import RegenerationConfig
from ws4.ecosystem.state import CohortState
from ws4.opt.account_compare import compare_accounts
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _state() -> CohortState:
    """Build the two-fragment initial state."""
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
            "track_id": 1,
        }
        for fragment in (1, 2)
    ]
    return CohortState(
        cohorts=pd.DataFrame(rows, columns=[*base.cohorts.columns, "track_id"]),
        schema=base.schema,
        fragment_areas={1: 3.0, 2: 2.0},
    )


def _process(
    curves: dict[int, dict[int, float]],
    transitions: dict[tuple[int, str], int],
    horizon: int,
    *,
    schedule: dict[int, tuple[tuple[str, int], ...]],
) -> ProcessScheduleEvaluation:
    """Run LANDIS succession with the timed CC schedule."""
    return evaluate_process_schedule(
        _state(),
        (),
        schedule,
        {1: (1,), 2: (2,)},
        horizon_years=horizon,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        bridge=VolumeBridgeConfig(
            default_volume_m3_per_t=0.0,
            merchantable_fraction=1.0,
            track_age_volume_curves=curves,
        ),
        succession_process=LandisSuccessionProcess(),
        track_transitions=transitions,
        seed=1,
    )


def test_timed_harvest_follows_the_managed_track(tmp_path: Path) -> None:
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "dataset"
    )
    schedule_path = tmp_path / "schedule.csv"
    pd.DataFrame({"block_id": [1], "treatment": ["CC"], "offset": [2]}).to_csv(
        schedule_path, index=False
    )
    estate = Simulator.from_dataset(dataset).simulate(pd.read_csv(schedule_path), years=5)
    features = pd.read_parquet(dataset / "features.parquet")
    volume_features = features.loc[features["label"] == "feature.Volume"]
    curves = track_age_volume_curves_from_frame(
        pd.read_parquet(dataset / "curves.parquet"),
        {
            int(str(row.track_id)): int(str(row.curve_id))
            for row in volume_features.itertuples(index=False)
        },
    )
    treatments = pd.read_parquet(dataset / "treatments.parquet")
    transitions = {
        (int(str(row.track_id)), str(row.treatment)): int(str(row.new_track))
        for row in treatments.itertuples(index=False)
    }

    four = _process(curves, transitions, 4, schedule={1: (("CC", 2),)})
    five = _process(curves, transitions, 5, schedule={1: (("CC", 2),)})
    four_row = compare_accounts(
        four.accounts, estate, {"bridge.volume_m3": "feature.Volume"}
    ).rows.iloc[0]
    five_row = compare_accounts(
        five.accounts, estate, {"bridge.volume_m3": "feature.Volume"}
    ).rows.iloc[0]

    assert four_row["estate_value"] == pytest.approx(390.0)
    assert four_row["process_value"] == pytest.approx(390.0)
    assert four_row["absolute_difference"] == pytest.approx(0.0)
    assert five_row["process_value"] == pytest.approx(410.0)
    assert five_row["absolute_difference"] == pytest.approx(20.0)
