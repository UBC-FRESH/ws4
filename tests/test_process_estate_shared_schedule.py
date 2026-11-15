"""One schedule through both the estate simulator and the process engine."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.ecosystem.bridge import VolumeBridgeConfig
from ws4.ecosystem.evaluation import evaluate_process_schedule
from ws4.ecosystem.events import Event
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.ecosystem.process import ProcessContext
from ws4.ecosystem.regeneration import RegenerationConfig
from ws4.ecosystem.state import CohortState
from ws4.opt.account_compare import compare_accounts
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


class _NoSuccession:
    """A process source that emits no events."""

    process_id = "no-succession"
    phases: tuple[str, ...] = ("growth",)
    state_reads: frozenset[str] = frozenset()
    state_writes: frozenset[str] = frozenset()

    def events(self, state: CohortState, context: ProcessContext) -> Sequence[Event]:
        """Return no events."""
        del state, context
        return ()

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Return the state unchanged."""
        del event
        return state


def _process_state() -> CohortState:
    """Build the two-fragment process state matching the synthetic fixture."""
    _schema, base, _edges = synthetic_grid(1, 2)
    rows = [
        {
            "fragment_id": fragment,
            "cohort_id": 1,
            "species": "PL",
            "age": 40 if fragment == 1 else 60,
            "area_fraction": 1.0,
            "biomass_t_ha": biomass,
            "fuel_t_ha": 0.0,
            "snag_t_ha": 0.0,
            "attributes_json": "{}",
        }
        for fragment, biomass in ((1, 120.0), (2, 170.0))
    ]
    return CohortState(
        cohorts=pd.DataFrame(rows, columns=base.cohorts.columns),
        schema=base.schema,
        fragment_areas={1: 3.0, 2: 2.0},
    )


def test_one_clearcut_matches_across_engines(tmp_path: Path) -> None:
    """The estate and process sides both report 340 m3 after the same CC schedule."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "dataset"
    )
    schedule_path = tmp_path / "schedule.csv"
    pd.DataFrame({"block_id": [1], "treatment": ["CC"], "offset": [0]}).to_csv(
        schedule_path, index=False
    )
    estate_values = Simulator.from_dataset(dataset).simulate(pd.read_csv(schedule_path), years=1)

    process = evaluate_process_schedule(
        _process_state(),
        (),
        {1: (("CC", 0),)},
        {1: (1,), 2: (2,)},
        horizon_years=1,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        bridge=VolumeBridgeConfig(
            default_volume_m3_per_t=0.0,
            merchantable_fraction=1.0,
            age_volume_curves={"PL": {0: 0.0, 40: 120.0, 60: 170.0}},
        ),
        succession_process=_NoSuccession(),
        seed=1,
    )

    comparison = compare_accounts(
        process.accounts,
        estate_values,
        {"bridge.volume_m3": "feature.Volume"},
    )
    row = comparison.rows.iloc[0]
    assert row["process_value"] == pytest.approx(340.0)
    assert row["estate_value"] == pytest.approx(340.0)
    assert row["absolute_difference"] == pytest.approx(0.0)
    comparison.write(tmp_path / "comparison")
    assert (tmp_path / "comparison" / "account_comparison.json").is_file()


def test_compiled_natural_curve_matches_the_estate(tmp_path: Path) -> None:
    """The compiled natural curve reproduces the estate volume after CC."""
    from ws4.ecosystem.bridge import age_volume_curves_from_frame

    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "dataset"
    )
    curve_frame = pd.read_parquet(dataset / "curves.parquet")
    curves = age_volume_curves_from_frame(curve_frame, {"PL": 2})
    schedule_path = tmp_path / "schedule.csv"
    pd.DataFrame({"block_id": [1], "treatment": ["CC"], "offset": [0]}).to_csv(
        schedule_path, index=False
    )
    estate_values = Simulator.from_dataset(dataset).simulate(pd.read_csv(schedule_path), years=1)
    process = evaluate_process_schedule(
        _process_state(),
        (),
        {1: (("CC", 0),)},
        {1: (1,), 2: (2,)},
        horizon_years=1,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        regeneration=RegenerationConfig(establishment_probability=0.0),
        bridge=VolumeBridgeConfig(
            default_volume_m3_per_t=0.0,
            merchantable_fraction=1.0,
            age_volume_curves=curves,
        ),
        succession_process=_NoSuccession(),
        seed=1,
    )

    comparison = compare_accounts(
        process.accounts,
        estate_values,
        {"bridge.volume_m3": "feature.Volume"},
    )
    row = comparison.rows.iloc[0]
    assert row["process_value"] == pytest.approx(340.0)
    assert row["estate_value"] == pytest.approx(340.0)
    assert row["absolute_difference"] == pytest.approx(0.0)
