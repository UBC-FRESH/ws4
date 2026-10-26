"""Tests for the WS4 fertilization growth and emissions bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.carbon.fertilization import (
    FertilizationApplication,
    FertilizationConfig,
    block_areas_from_dataset,
    fertilization_accounts,
    load_fertilization_config,
    with_fertilization_curves,
    with_fertilization_disturbances,
)

from test_carbon_sit import _schedule, _write_dataset, _write_package


def _config(*, multiplier: float = 1.5) -> FertilizationConfig:
    """Return the public thesis/TIPSY assumptions for a test."""
    return FertilizationConfig(
        dose_kg_n_ha=200.0,
        response_years=10,
        growth_multiplier=multiplier,
        co2_kg_ha=17.13779467,
        ch4_kg_ha=0.055734646,
        n2o_kg_ha={
            "f1": 20.00206748,
            "f2": 40.00206748,
            "f3": 60.00206748,
        },
        gwp_ch4=27.9,
        gwp_n2o=273.0,
        source={"name": "test"},
    )


def _write_config(root: Path, *, multiplier: float | None = None) -> Path:
    """Write a FEMIC-compatible fertilization YAML."""
    lines = [
        'schema_version: "0.1"',
        "dose_kg_n_ha: 200",
        "response_years: 10",
        "factors_kg_ha:",
        "  co2: 17.13779467",
        "  ch4: 0.055734646",
        "  n2o_once: 20.00206748",
        "  n2o_twice: 40.00206748",
        "  n2o_thrice: 60.00206748",
        "gwp100:",
        "  ch4: 27.9",
        "  n2o: 273.0",
        "growth_response:",
        "  method: tipsy_mof_response",
        "  response_years: 10",
    ]
    if multiplier is not None:
        lines.append(f"  growth_multiplier: {multiplier}")
    path = root / "fertilization.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_load_fertilization_config_accepts_the_femic_file(tmp_path: Path) -> None:
    """The FEMIC assumptions load directly, with a public default multiplier."""
    config = load_fertilization_config(_write_config(tmp_path, multiplier=1.25))

    assert config.dose_kg_n_ha == pytest.approx(200.0)
    assert config.response_years == 10
    assert config.growth_multiplier == pytest.approx(1.25)
    assert config.n2o_kg_ha["f3"] == pytest.approx(60.00206748)
    assert config.gwp_n2o == pytest.approx(273.0)
    assert config.path == _write_config(tmp_path, multiplier=1.25)

    default_config = load_fertilization_config(_write_config(tmp_path))
    assert default_config.growth_multiplier == pytest.approx(1.10)


def test_with_fertilization_adds_the_three_disturbances(tmp_path: Path) -> None:
    """The in-memory package gains f1/f2/f3 without changing the original."""
    package = _write_package(tmp_path / "package")
    original = package.table("disturbance_types").copy()

    augmented = with_fertilization_disturbances(package, _config())

    assert set(augmented.table("disturbance_types")["user_dist_type"]) == {
        "CC",
        "fire",
        "f1",
        "f2",
        "f3",
    }
    assert package.table("disturbance_types").equals(original)


def test_fertilization_accounts_use_block_area_and_n2o_tier(tmp_path: Path) -> None:
    """The emissions audit uses the scheduled block area and the f1/f2/f3 tier."""
    dataset = _write_dataset(tmp_path / "dataset")
    schedule = pd.DataFrame(
        {
            "block_id": [1, 2, 2],
            "treatment": ["f1", "f1", "f2"],
            "offset": [0, 1, 1],
        }
    )

    accounts = fertilization_accounts(
        schedule,
        block_areas_from_dataset(dataset),
        _config(),
    )
    by_name = accounts.set_index(["offset", "account"])["value"]

    assert by_name.loc[(0, "fertilization.area_ha")] == pytest.approx(3.0)
    assert by_name.loc[(0, "fertilization.dose_kg_n")] == pytest.approx(600.0)
    assert by_name.loc[(1, "fertilization.area_ha")] == pytest.approx(4.0)
    assert by_name.loc[(1, "fertilization.n2o_t")] == pytest.approx(
        (2 * 20.00206748 + 2 * 40.00206748) / 1000.0
    )
    assert by_name.loc[(1, "fertilization.co2e_t")] > by_name.loc[(1, "fertilization.co2_t")]


def test_fertilization_growth_response_and_written_accounts(tmp_path: Path) -> None:
    """A fertilizer event raises growing pools and adds audited accounts."""
    pytest.importorskip("libcbm")
    from ws4.carbon.libcbm import (
        cbm_defaults_reference,
        run_libcbm,
        write_carbon_run,
    )
    from ws4.carbon.sit import build_sit_tables

    package = _write_package(tmp_path / "package")
    package.manifest.cbm_defaults.sha256 = cbm_defaults_reference().sha256
    dataset = _write_dataset(tmp_path / "dataset")
    config = _config(multiplier=2.0)
    augmented = with_fertilization_disturbances(package, config)
    schedule = pd.DataFrame({"block_id": [2], "treatment": ["f1"], "offset": [0]})
    tables = build_sit_tables(augmented, dataset, schedule)

    baseline = run_libcbm(augmented, tables, n_steps=12)
    fertilized = run_libcbm(
        augmented,
        tables,
        n_steps=12,
        fertilization=config,
    )
    baseline_hw = float(baseline.pools.groupby("timestep")["HardwoodMerch"].sum().iloc[-1])
    fertilized_hw = float(fertilized.pools.groupby("timestep")["HardwoodMerch"].sum().iloc[-1])
    assert fertilized_hw > baseline_hw

    emissions = fertilization_accounts(
        schedule,
        block_areas_from_dataset(dataset),
        config,
    )
    result = write_carbon_run(
        fertilized,
        tmp_path / "run",
        package=augmented,
        dataset_dir=dataset,
        schedule=schedule,
        n_steps=12,
        extra_accounts=emissions,
        extra_manifest=config.manifest(),
    )
    accounts = pd.read_csv(result.accounts_path)
    assert "fertilization.co2e_t" in set(accounts["account"])
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["fertilization"]["growth_multiplier"] == pytest.approx(2.0)
    assert manifest["fertilization"]["total_co2e_t"] > 0


def test_application_loader_resolves_the_materialized_curve(tmp_path: Path) -> None:
    """An application names a source track and a relative curve artifact."""
    curve = tmp_path / "track2-f1.csv"
    pd.DataFrame(
        {
            "track_name": ["track2"] * 4,
            "age": [0, 10, 20, 30],
            "volume_m3_ha": [0.0, 60.0, 140.0, 200.0],
        }
    ).to_csv(curve, index=False)
    path = _write_config(tmp_path, multiplier=1.0)
    path.write_text(
        path.read_text(encoding="utf-8")
        + "applications:\n"
        + "  - treatment: f1\n"
        + "    source_track: track2\n"
        + "    curve: track2-f1.csv\n",
        encoding="utf-8",
    )

    config = load_fertilization_config(path)

    assert config.uses_curves
    assert config.applications[0].source_track == "track2"
    assert config.applications[0].target_track == "track2+F1"
    assert config.applications[0].curve == curve


def test_materialized_curve_transition_preserves_age(tmp_path: Path) -> None:
    """The curve path transitions to a fertilized track without resetting age."""
    pytest.importorskip("libcbm")
    from ws4.carbon.libcbm import (
        cbm_defaults_reference,
        run_libcbm,
    )
    from ws4.carbon.sit import build_sit_tables_from_tables

    package = _write_package(tmp_path / "package")
    package.manifest.cbm_defaults.sha256 = cbm_defaults_reference().sha256
    dataset = _write_dataset(tmp_path / "dataset")
    curve = tmp_path / "track2-f1.csv"
    pd.DataFrame(
        {
            "track_name": ["track2"] * 4,
            "age": [0, 10, 20, 30],
            "volume_m3_ha": [0.0, 60.0, 140.0, 200.0],
        }
    ).to_csv(curve, index=False)
    config = FertilizationConfig(
        dose_kg_n_ha=200.0,
        response_years=10,
        growth_multiplier=1.0,
        co2_kg_ha=17.13779467,
        ch4_kg_ha=0.055734646,
        n2o_kg_ha={"f1": 20.00206748, "f2": 40.00206748, "f3": 60.00206748},
        gwp_ch4=27.9,
        gwp_n2o=273.0,
        source={},
        applications=(
            FertilizationApplication(
                treatment="f1",
                source_track="track2",
                curve=curve,
                target_track="track2+F1",
            ),
        ),
    )
    fragments = pd.read_parquet(dataset / "fragments.parquet")
    tracks = pd.read_parquet(dataset / "tracks.parquet")
    treatments = pd.read_parquet(dataset / "treatments.parquet")
    base_tracks = tracks.copy()
    base_treatments = treatments.copy()
    augmented, tracks, treatments = with_fertilization_curves(
        package,
        tracks,
        treatments,
        config,
    )
    schedule = pd.DataFrame({"block_id": [2], "treatment": ["f1"], "offset": [0]})
    tables = build_sit_tables_from_tables(
        augmented,
        fragments,
        tracks,
        treatments,
        schedule,
    )
    fertilized = run_libcbm(augmented, tables, n_steps=3)
    baseline_tables = build_sit_tables_from_tables(
        package,
        fragments,
        base_tracks,
        base_treatments,
        pd.DataFrame({"block_id": [], "treatment": [], "offset": []}),
    )
    baseline = run_libcbm(package, baseline_tables, n_steps=3)

    assert "track2+F1" in set(fertilized.classifiers["track"])
    assert 21 in set(fertilized.state.loc[fertilized.state["timestep"] == 1, "age"])
    assert (
        fertilized.pools.groupby("timestep")["HardwoodMerch"].sum().iloc[-1]
        > baseline.pools.groupby("timestep")["HardwoodMerch"].sum().iloc[-1]
    )


def test_ledger_prices_materialized_curve_mode(tmp_path: Path) -> None:
    """The ledger also prices a materialized curve transition."""
    pytest.importorskip("libcbm")
    from ws4.carbon.ledger import CarbonLedger
    from ws4.carbon.libcbm import cbm_defaults_reference

    package = _write_package(tmp_path / "package")
    package.manifest.cbm_defaults.sha256 = cbm_defaults_reference().sha256
    dataset = _write_dataset(tmp_path / "dataset")
    curve = tmp_path / "track2-f1.csv"
    pd.DataFrame(
        {
            "track_name": ["track2"] * 4,
            "age": [0, 10, 20, 30],
            "volume_m3_ha": [0.0, 60.0, 140.0, 200.0],
        }
    ).to_csv(curve, index=False)
    config = FertilizationConfig(
        dose_kg_n_ha=200.0,
        response_years=10,
        growth_multiplier=1.0,
        co2_kg_ha=17.13779467,
        ch4_kg_ha=0.055734646,
        n2o_kg_ha={"f1": 20.00206748, "f2": 40.00206748, "f3": 60.00206748},
        gwp_ch4=27.9,
        gwp_n2o=273.0,
        source={},
        applications=(
            FertilizationApplication(
                treatment="f1",
                source_track="track2",
                curve=curve,
                target_track="track2+F1",
            ),
        ),
    )
    ledger = CarbonLedger(dataset, package, years=3, fertilization=config)

    delta = ledger.contribution(2, (("f1", 0),))

    assert delta[(0, "fertilization.co2e_t")] > 0
    assert delta[(1, "carbon.ecosystem.total")] > 0


def test_ledger_prices_fertilization_growth_and_emissions(tmp_path: Path) -> None:
    """The optimizer ledger includes both the growth delta and the emissions."""
    pytest.importorskip("libcbm")
    from ws4.carbon.ledger import CarbonLedger
    from ws4.carbon.libcbm import cbm_defaults_reference

    package = _write_package(tmp_path / "package")
    package.manifest.cbm_defaults.sha256 = cbm_defaults_reference().sha256
    dataset = _write_dataset(tmp_path / "dataset")
    config = _config(multiplier=2.0)
    ledger = CarbonLedger(dataset, package, years=12, fertilization=config)

    delta = ledger.contribution(2, (("f1", 0),))

    assert delta[(0, "fertilization.area_ha")] == pytest.approx(2.0)
    assert delta[(0, "fertilization.co2e_t")] == pytest.approx(
        (2.0 * 17.13779467 / 1000.0)
        + (2.0 * 0.055734646 / 1000.0) * 27.9
        + (2.0 * 20.00206748 / 1000.0) * 273.0
    )
    assert (11, "carbon.ecosystem.total") in delta


def test_schedule_without_fertilization_is_unchanged(tmp_path: Path) -> None:
    """A normal schedule keeps the original two-event compiler path."""
    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset")

    from ws4.carbon.sit import build_sit_tables

    tables = build_sit_tables(package, dataset, _schedule())
    assert "f1" not in set(tables.disturbance_types["id"])
