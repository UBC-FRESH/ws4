"""Tests for the carbon account writer and the libcbm mapping configuration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.carbon.libcbm import (
    CarbonEngineError,
    CarbonRun,
    CbmDefaultsReference,
    build_sit_config,
    carbon_accounts,
    check_cbm_defaults,
    write_carbon_run,
)
from ws4.carbon.package import (
    CarbonBoundaries,
    CarbonManifest,
    CarbonMapping,
    CarbonPackage,
    CarbonProducer,
    CarbonUnits,
    CbmDefaults,
)


def _package() -> CarbonPackage:
    """Return a minimal package for mapping and writer tests."""
    manifest = CarbonManifest(
        schema_version="0.1",
        package_id="fixture",
        created_utc="2026-10-25T00:00:00Z",
        producer=CarbonProducer(name="femic", version="test"),
        cbm_defaults=CbmDefaults(version="1.2.9300.391", sha256="b" * 64, source="libcbm"),
        units=CarbonUnits(
            area="ha",
            volume="m3/ha",
            carbon="tC",
            carbon_density="tC/ha",
            co2e="tCO2e",
        ),
        boundaries=CarbonBoundaries(admin="British Columbia", eco="Montane Cordillera"),
        mapping=CarbonMapping(),
    )
    tables = {
        "classifiers": pd.DataFrame(
            {
                "classifier_id": ["1", "1", "2", "2"],
                "classifier": ["track", "track", "species", "species"],
                "value": ["track1", "track2", "softwood", "hardwood"],
            }
        ),
        "disturbance_types": pd.DataFrame(
            {
                "user_dist_type": ["cc", "fire"],
                "default_dist_type": [
                    "Clearcut harvesting without salvage",
                    "Wildfire",
                ],
            }
        ),
    }
    return CarbonPackage(
        path=Path("."),
        manifest=manifest,
        tables=tables,
        table_hashes={},
        fingerprint="f" * 64,
    )


def _run() -> CarbonRun:
    """Return a tiny synthetic CBM run."""
    pools = pd.DataFrame(
        {
            "timestep": [0, 1],
            "identifier": [1, 1],
            "SoftwoodMerch": [10.0, 11.0],
            "SoftwoodFoliage": [1.0, 1.0],
            "AboveGroundSlowSoil": [2.0, 2.0],
            "Products": [0.0, 1.0],
        }
    )
    flux = pd.DataFrame(
        {
            "timestep": [0, 1],
            "identifier": [1, 1],
            "DeltaBiomass_AG": [1.0, 1.0],
            "DeltaBiomass_BG": [0.5, 0.5],
            "DecaySlowAGToAir": [0.2, 0.2],
            "DisturbanceMerchToAir": [0.0, 0.5],
        }
    )
    return CarbonRun(
        pools=pools,
        flux=flux,
        classifiers=pd.DataFrame(),
        state=pd.DataFrame(),
        libcbm_version="2.10.2",
        defaults=CbmDefaultsReference(
            path=Path("cbm_defaults.db"), version="1.2.9300.391", sha256="b" * 64
        ),
    )


def test_build_sit_config_maps_species_and_disturbances() -> None:
    """The mapping config names the package species and disturbance defaults."""
    config = build_sit_config(_package())
    mapping = config["mapping_config"]
    assert isinstance(mapping, dict)
    species = mapping["species"]
    assert species["species_classifier"] == "species"
    assert species["species_mapping"] == [
        {"user_species": "hardwood", "default_species": "Hardwood forest type"},
        {"user_species": "softwood", "default_species": "Softwood forest type"},
    ]
    disturbances = mapping["disturbance_types"]["disturbance_type_mapping"]
    assert {
        "user_dist_type": "cc",
        "default_dist_type": "Clearcut harvesting without salvage",
    } in disturbances


def test_check_cbm_defaults_rejects_a_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A package/defaults mismatch is a hard failure unless explicitly allowed."""
    import ws4.carbon.libcbm as engine

    installed = CbmDefaultsReference(path=Path("cbm_defaults.db"), version="9.9.9", sha256="c" * 64)
    monkeypatch.setattr(engine, "cbm_defaults_reference", lambda: installed)
    with pytest.raises(CarbonEngineError):
        check_cbm_defaults(_package())
    assert check_cbm_defaults(_package(), allow_mismatch=True) is installed


def test_carbon_accounts_summarizes_pools_and_fluxes() -> None:
    """The account writer names the totals and converts to CO2e."""
    accounts = carbon_accounts(_run())
    by_name = accounts.set_index(["offset", "account"])["value"]
    assert by_name.loc[(0, "carbon.biomass.total")] == 11.0
    assert by_name.loc[(0, "carbon.dom.total")] == 2.0
    assert by_name.loc[(0, "carbon.ecosystem.total")] == 13.0
    assert by_name.loc[(1, "carbon.products.total")] == 1.0
    assert by_name.loc[(1, "carbon.flux.npp")] == 1.5
    assert by_name.loc[(1, "carbon.flux.decay")] == 0.2
    assert by_name.loc[(1, "carbon.flux.disturbance")] == 0.5
    assert by_name.loc[(1, "carbon.flux.net")] == pytest.approx(-0.8)
    assert by_name.loc[(0, "carbon.co2e.ecosystem.total")] == pytest.approx(13.0 * 44 / 12)
    assert by_name.loc[(1, "carbon.stock.change")] == 1.0


def test_write_carbon_run_writes_files_and_manifest(tmp_path: Path) -> None:
    """The writer writes the wide/long tables, accounts, and manifest."""
    schedule = pd.DataFrame({"block_id": [1], "treatment": ["cc"], "offset": [0]})
    result = write_carbon_run(
        _run(),
        tmp_path / "run",
        package=_package(),
        dataset_dir=tmp_path / "dataset",
        schedule=schedule,
        n_steps=2,
    )
    assert result.pools_path.is_file()
    assert result.flux_path.is_file()
    assert result.accounts_path.is_file()
    assert result.manifest_path.is_file()
    assert result.ecosystem_start_tc == 13.0
    assert result.ecosystem_end_tc == 14.0
    manifest = result.manifest_path.read_text(encoding="utf-8")
    assert '"libcbm_version": "2.10.2"' in manifest
    assert result.accounts_path.read_text(encoding="utf-8").count("carbon.ecosystem.total") == 2
