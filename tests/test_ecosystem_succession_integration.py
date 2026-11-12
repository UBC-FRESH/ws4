"""Integration test for fire, succession, salvage, regeneration, and the bridge."""

from __future__ import annotations

from ws4.ecosystem.bridge import SpeciesVolumeBridge, VolumeBridgeConfig
from ws4.ecosystem.executor import Executor
from ws4.ecosystem.fire import (
    FireConfig,
    FireProcess,
    FireProcessSource,
    SalvageProcessSource,
    SalvageSource,
    synthetic_grid,
)
from ws4.ecosystem.log import EventLogMetadata
from ws4.ecosystem.regeneration import RegenerationConfig, RegenerationProcess
from ws4.ecosystem.succession import SuccessionProcess
from ws4.ecosystem.tape import RandomTape


def test_fire_succession_salvage_and_regeneration_share_one_run() -> None:
    _schema, state, edges = synthetic_grid(5, 5)
    config = FireConfig(
        ignition_rate_per_fragment_year=2.0,
        base_spread_probability=1.0,
        salvage_delay_years=0,
    )
    fire = FireProcess(config, edges, RandomTape(17), scenario_id="multi-test")
    salvage = SalvageSource(config, scenario_id="multi-test")
    regeneration = RegenerationProcess(
        RegenerationConfig(establishment_probability=1.0),
        RandomTape(17),
        scenario_id="multi-test",
    )
    sources = (
        FireProcessSource(fire),
        SuccessionProcess(),
        SalvageProcessSource(salvage),
        regeneration,
    )
    executor = Executor(
        state,
        sources,
        EventLogMetadata(scenario_id="multi-test", scenario_seed=17),
    )

    result = executor.run(2)

    event_types = {event.event_type for event in result.log.events}
    assert {"fire", "succession", "salvage", "regeneration"} <= event_types
    result.state.check_area_conservation()
    table = SpeciesVolumeBridge(
        VolumeBridgeConfig(volume_m3_per_t={"PL": 1.2}, default_volume_m3_per_t=1.0)
    ).table(result.state)
    assert len(table) == len(result.state.fragment_areas)
    assert (table["volume_m3"] >= 0.0).all()
    assert (table["volume_m3_ha"] >= 0.0).all()
