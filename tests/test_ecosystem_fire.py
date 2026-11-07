"""Tests for the fire process, its salvage source, and the end-to-end run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.disturbance import DisturbanceEvent
from ws4.ecosystem import (
    CohortState,
    Event,
    FireConfig,
    FireEdge,
    FireError,
    FireProcess,
    FireRun,
    RandomTape,
    SalvageSource,
    load_ecosystem_package,
    run_fire_demo,
    synthetic_grid,
)
from ws4.ecosystem.log import EventLog

COLUMNS = [
    "fragment_id",
    "cohort_id",
    "species",
    "age",
    "area_fraction",
    "biomass_t_ha",
    "fuel_t_ha",
    "snag_t_ha",
    "attributes_json",
]


def ignition(fragment: int = 1, *, time: float = 0.0, year: int = 0) -> Event:
    """Build one ignition event for a direct spread test."""
    return Event(
        event_id=f"ign-{fragment}-{year}",
        process_id="fire",
        event_type="fire_ignition",
        time=time,
        year=year,
        phase="ignition",
        source="test",
        scenario_id="s",
        fragment_ids=(fragment,),
        confidence=1.0,
    )


def fire_event(
    *,
    fragment: int = 1,
    year: int = 0,
    severity: float = 0.8,
    mortality: float = 0.8,
    area: float = 10.0,
) -> Event:
    """Build one fire event for a direct effect test."""
    return Event(
        event_id=f"fire-{fragment}-{year}",
        process_id="fire",
        event_type="fire",
        time=0.1,
        year=year,
        phase="propagation",
        source="ws4.ecosystem.fire",
        scenario_id="s",
        fragment_ids=(fragment,),
        severity_class="high",
        severity_value=severity,
        magnitude=mortality,
        area_ha=area,
        confidence=1.0,
    )


def test_poisson_ignition_rate_is_in_the_expected_range() -> None:
    _, state, edges = synthetic_grid(1, 1)
    config = FireConfig(ignition_rate_per_fragment_year=0.05, base_spread_probability=0.0)
    process = FireProcess(config, edges, RandomTape(123), "s")

    count = sum(len(process.ignitions(state, year)) for year in range(1000))

    assert count == pytest.approx(50, abs=15)


def test_one_dimensional_chain_has_a_geometric_burn_length() -> None:
    _, state, edges = synthetic_grid(1, 50)
    config = FireConfig(
        ignition_rate_per_fragment_year=0.0,
        base_spread_probability=0.5,
        distance_scale_m=1e9,
    )
    lengths: list[int] = []
    for seed in range(200):
        process = FireProcess(config, edges, RandomTape(seed), "s")
        lengths.append(len(process.spread(state, ignition())))

    assert sum(lengths) / len(lengths) == pytest.approx(2.0, abs=0.2)
    assert min(lengths) == 1


def test_zero_fuel_barrier_stops_the_fire() -> None:
    schema, state, _ = synthetic_grid(3, 3)
    cohorts = state.cohorts.copy()
    cohorts.loc[cohorts["fragment_id"].isin((2, 5, 8)), "fuel_t_ha"] = 0.0
    barred = CohortState(
        cohorts=cohorts,
        schema=schema,
        fragment_areas=state.fragment_areas,
    )
    config = FireConfig(
        ignition_rate_per_fragment_year=0.0,
        base_spread_probability=1.0,
        distance_scale_m=1e9,
    )
    _, _, edges = synthetic_grid(3, 3)
    process = FireProcess(config, edges, RandomTape(4), "s")

    events = process.spread(barred, ignition())

    assert {event.fragment_ids[0] for event in events} == {1, 4, 7}


def test_wind_favours_the_downwind_edge() -> None:
    _, state, edges = synthetic_grid(1, 2)
    config = FireConfig(
        ignition_rate_per_fragment_year=0.0,
        base_spread_probability=0.5,
        distance_scale_m=1e9,
        wind_direction_deg=90.0,
        wind_strength=1.0,
    )
    downwind = FireProcess(config, edges, RandomTape(1), "s").spread(state, ignition(1))
    upwind = FireProcess(config, edges, RandomTape(1), "s").spread(state, ignition(2))

    assert {event.fragment_ids[0] for event in downwind} == {1, 2}
    assert {event.fragment_ids[0] for event in upwind} == {2}


def test_fire_effect_preserves_area_and_creates_snags() -> None:
    _, state, edges = synthetic_grid(1, 1)
    config = FireConfig(mortality_factor=1.0, snag_fraction=0.1)
    process = FireProcess(config, edges, RandomTape(1), "s")

    updated = process.apply(state, fire_event(severity=0.8, mortality=0.8))

    assert updated.cohorts["area_fraction"].sum() == pytest.approx(1.0)
    dead = updated.cohorts[updated.cohorts["cohort_id"] == 2].iloc[0]
    assert dead["age"] == 0
    assert dead["area_fraction"] == pytest.approx(0.8)
    assert dead["biomass_t_ha"] == pytest.approx(0.0)
    assert dead["snag_t_ha"] == pytest.approx(10.0)
    updated.check_area_conservation()


def test_salvage_removes_snags_and_records_a_volume() -> None:
    _, state, edges = synthetic_grid(1, 1)
    config = FireConfig(mortality_factor=1.0, snag_fraction=0.1, salvage_delay_years=1)
    fire = fire_event(severity=0.8, mortality=0.8)
    burned = FireProcess(config, edges, RandomTape(1), "s").apply(state, fire)
    source = SalvageSource(config, "s")

    events = source.events(burned, 1, (fire,))

    assert len(events) == 1
    assert events[0].event_type == "salvage"
    assert events[0].parent_event_id == fire.event_id
    assert events[0].magnitude == pytest.approx(84.0)
    salvaged = source.apply(burned, events[0])
    assert float(salvaged.cohorts["snag_t_ha"].sum()) == pytest.approx(0.0)
    assert source.events(salvaged, 2, (fire,)) == ()


def test_replay_is_exact_and_seed_sensitive() -> None:
    first = run_fire_demo(rows=4, cols=4, years=10, seed=11)
    second = run_fire_demo(rows=4, cols=4, years=10, seed=11)
    different = run_fire_demo(rows=4, cols=4, years=10, seed=12)

    assert first.log == second.log
    assert first.log.replay_token == second.log.replay_token
    assert first.accounts.equals(second.accounts)
    assert first.log.replay_token != different.log.replay_token


def test_fire_events_are_disturbance_compatible() -> None:
    result = run_fire_demo(rows=3, cols=3, years=5, seed=3)

    for event in result.fires:
        parsed = DisturbanceEvent.from_dict(event.to_disturbance_dict(result.start_year))
        assert parsed.event_id == event.event_id
        assert parsed.year == result.start_year + event.year
        assert parsed.event_type == "fire"
        assert parsed.source_id == "ws4.ecosystem.fire"


def test_result_writes_every_output(tmp_path: Path) -> None:
    result = run_fire_demo(rows=3, cols=3, years=5, seed=3)

    result.write(tmp_path)

    assert (tmp_path / "events.json").is_file()
    assert (tmp_path / "accounts.csv").is_file()
    assert (tmp_path / "disturbances.json").is_file()
    assert (tmp_path / "cohorts.csv").is_file()
    assert (tmp_path / "summary.json").is_file()
    assert EventLog.read(tmp_path / "events.json") == result.log
    disturbances = json.loads((tmp_path / "disturbances.json").read_text(encoding="utf-8"))
    assert len(disturbances) == len(result.fires)


def write_fire_package(root: Path) -> Path:
    """Write a minimal two-by-two ecosystem package for the dataset integration test."""
    root.mkdir(parents=True, exist_ok=True)
    state = pd.DataFrame(
        [
            ["species", "string", "cohort", "", "", "Species"],
            ["age", "int", "cohort", "years", "", "Age"],
            ["area_fraction", "float", "cohort", "", "", "Share"],
            ["biomass_t_ha", "float", "cohort", "t/ha", "0.0", "Biomass"],
            ["fuel_t_ha", "float", "cohort", "t/ha", "0.0", "Fuel"],
            ["snag_t_ha", "float", "cohort", "t/ha", "0.0", "Snags"],
        ],
        columns=["name", "dtype", "scope", "unit", "default", "description"],
    )
    cohorts = pd.DataFrame(
        [
            ["1", "1", "PL", "60", "1.0", "100.0", "20.0", "2.0", "{}"],
            ["2", "1", "PL", "60", "1.0", "100.0", "20.0", "2.0", "{}"],
            ["3", "1", "PL", "60", "1.0", "100.0", "20.0", "2.0", "{}"],
            ["4", "1", "PL", "60", "1.0", "100.0", "20.0", "2.0", "{}"],
        ],
        columns=COLUMNS,
    )
    bridges = pd.DataFrame(
        [["null", "null", "{}", "", ""]],
        columns=["bridge_id", "type", "params_json", "state_reads", "state_writes"],
    )
    state.to_csv(root / "state_variables.csv", index=False)
    cohorts.to_csv(root / "cohorts.csv", index=False)
    bridges.to_csv(root / "bridges.csv", index=False)
    manifest = {
        "schema_version": "ws4.ecosystem.v1",
        "package_id": "fire",
        "created_utc": "2026-11-07T00:00:00Z",
        "producer": {"name": "test", "version": "1"},
        "sources": [],
        "table_hashes": {
            name: hashlib.sha256((root / f"{name}.csv").read_bytes()).hexdigest()
            for name in ("state_variables", "cohorts", "bridges")
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_fire_run_reads_a_package_and_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    pd.DataFrame({"fragment_id": [1, 2, 3, 4], "area_ha": [10.0] * 4}).to_parquet(
        dataset / "fragments.parquet", index=False
    )
    package = load_ecosystem_package(write_fire_package(dataset / "ecosystem"))
    state = package.cohort_state(dataset)
    _, _, edges = synthetic_grid(2, 2)
    config = FireConfig(ignition_rate_per_fragment_year=0.05, base_spread_probability=0.6)

    result = FireRun(
        state,
        edges,
        config,
        scenario_id="package",
        seed=5,
        package_hashes=(("ecosystem", package.fingerprint),),
    ).run(10)

    assert result.log.metadata.package_hashes == (("ecosystem", package.fingerprint),)
    result.state.check_area_conservation()
    assert not result.accounts.empty


def test_invalid_fire_configuration_is_rejected() -> None:
    with pytest.raises(FireError, match="ignition_rate"):
        FireConfig(ignition_rate_per_fragment_year=-1.0)
    with pytest.raises(FireError, match="base_spread_probability"):
        FireConfig(base_spread_probability=1.5)
    with pytest.raises(FireError, match="severity_min"):
        FireConfig(severity_min=0.8, severity_max=0.2)
    with pytest.raises(FireError, match="distance_scale_m"):
        FireConfig(distance_scale_m=0.0)
    with pytest.raises(FireError, match="salvage_delay_years"):
        FireConfig(salvage_delay_years=-1)
    with pytest.raises(FireError, match="max_spread_steps"):
        FireConfig(max_spread_steps=0)


def test_invalid_fire_edge_is_rejected() -> None:
    with pytest.raises(FireError, match="source"):
        FireEdge(0, 1)
    with pytest.raises(FireError, match="source and target"):
        FireEdge(1, 1)
    with pytest.raises(FireError, match="distance_m"):
        FireEdge(1, 2, -1.0)


def test_negative_horizon_is_rejected() -> None:
    _, state, edges = synthetic_grid(1, 1)

    with pytest.raises(FireError, match="years"):
        FireRun(state, edges, FireConfig()).run(-1)


def test_biomass_mass_balance_closes_after_fire_and_salvage() -> None:
    _, state, edges = synthetic_grid(3, 3)
    initial = float(
        (
            state.cohorts["biomass_t_ha"]
            * state.cohorts["area_fraction"]
            * state.cohorts["fragment_id"].map(state.fragment_areas)
        ).sum()
    )
    config = FireConfig(ignition_rate_per_fragment_year=0.05, base_spread_probability=0.6)

    result = FireRun(state, edges, config, seed=4).run(10)

    accounts = result.accounts
    killed = float(accounts.loc[accounts["account"] == "fire.killed_biomass_t", "value"].sum())
    snag_created = float(accounts.loc[accounts["account"] == "fire.snag_created_t", "value"].sum())
    emitted = float(accounts.loc[accounts["account"] == "fire.emitted_biomass_t", "value"].sum())
    final_biomass = float(accounts.loc[accounts["account"] == "state.biomass_t", "value"].iloc[-1])

    assert killed == pytest.approx(snag_created + emitted)
    assert initial == pytest.approx(final_biomass + killed)
