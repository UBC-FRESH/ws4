"""Contract tests for the package + dataset + schedule SIT compiler."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.carbon.package import CarbonPackage, load_carbon_package
from ws4.carbon.sit import (
    CarbonSitError,
    build_sit_tables,
    read_schedule,
    write_sit_tables,
)

PACKAGE_TABLES: dict[str, list[list[object]]] = {
    "classifiers": [
        ["classifier_id", "classifier", "value", "description"],
        [1, "track", "track1", "first track"],
        [1, "track", "track2", "second track"],
        [2, "species", "softwood", "softwood"],
        [2, "species", "hardwood", "hardwood"],
    ],
    "disturbance_types": [
        [
            "user_dist_type",
            "default_dist_type",
            "removes_biomass",
            "transition_reset_age",
            "regen_delay",
        ],
        ["CC", "Clearcut harvesting without salvage", "true", 0, 0],
        ["fire", "Wildfire", "true", 0, 0],
    ],
    "age_classes": [
        ["name", "class_size"],
        ["age_0", 0],
        ["age_1", 10],
        ["age_2", 10],
        ["age_3", 10],
    ],
    "inventory": [
        [
            "track_name",
            "age",
            "area_ha",
            "delay",
            "landclass",
            "historic_disturbance",
            "last_pass_disturbance",
        ],
        ["track1", 40, 3.0, 0, 0, "fire", "CC"],
        ["track2", 20, 2.0, 0, 0, "fire", "fire"],
    ],
    "yield": [
        ["track_name", "species", "leading_species", "age", "volume_m3_ha"],
        ["track1", "softwood", "Spruce", 0, 0.0],
        ["track1", "softwood", "Spruce", 10, 50.0],
        ["track1", "softwood", "Spruce", 20, 120.0],
        ["track1", "softwood", "Spruce", 30, 180.0],
        ["track2", "hardwood", "Trembling aspen", 0, 0.0],
        ["track2", "hardwood", "Trembling aspen", 10, 30.0],
        ["track2", "hardwood", "Trembling aspen", 20, 70.0],
        ["track2", "hardwood", "Trembling aspen", 30, 100.0],
    ],
    "track_carbon_map": [
        [
            "track_name",
            "classifier_set",
            "leading_species",
            "softwood_share",
            "hardwood_share",
            "landclass",
            "last_disturbance",
            "eco_boundary",
            "volume_feature_label",
        ],
        [
            "track1",
            "track1;softwood",
            "Spruce",
            1.0,
            0.0,
            0,
            "CC",
            "Montane Cordillera",
            "feature.Volume",
        ],
        [
            "track2",
            "track2;hardwood",
            "Trembling aspen",
            0.0,
            1.0,
            0,
            "fire",
            "Montane Cordillera",
            "feature.Volume",
        ],
    ],
    "curve_carbon_map": [
        ["track_name", "feature_label", "species", "share"],
        ["track1", "feature.Volume", "softwood", 1.0],
        ["track2", "feature.Volume", "hardwood", 1.0],
    ],
    "species_map": [
        ["bc_species", "cbm_species", "wood_type", "confidence", "notes"],
        ["SW", "Spruce", "softwood", "high", "synthetic fixture"],
        ["AT", "Trembling aspen", "hardwood", "high", "synthetic fixture"],
    ],
    "boundaries": [
        ["admin_boundary", "eco_boundary"],
        ["British Columbia", "Montane Cordillera"],
    ],
}


def _write_package(root: Path) -> CarbonPackage:
    """Write and load the synthetic package."""
    root.mkdir(parents=True, exist_ok=True)
    for name, rows in PACKAGE_TABLES.items():
        pd.DataFrame(rows[1:], columns=rows[0]).to_csv(root / f"{name}.csv", index=False)
    hashes = {
        name: hashlib.sha256((root / f"{name}.csv").read_bytes()).hexdigest()
        for name in PACKAGE_TABLES
    }
    manifest: dict[str, object] = {
        "schema_version": "0.1",
        "package_id": "femic-carbon-sit-fixture",
        "created_utc": "2026-10-25T00:00:00Z",
        "producer": {"name": "femic", "version": "0.0.0-test"},
        "sources": [{"path": "synthetic", "sha256": "a" * 64}],
        "cbm_defaults": {
            "version": "1.2.9300.391",
            "sha256": "b" * 64,
            "source": "libcbm",
        },
        "units": {
            "area": "ha",
            "volume": "m3/ha",
            "carbon": "tC",
            "carbon_density": "tC/ha",
            "co2e": "tCO2e",
        },
        "boundaries": {"admin": "British Columbia", "eco": "Montane Cordillera"},
        "mapping": {
            "track_key": "track_name",
            "species_classifier": "species",
            "disturbance_classifier": "user_dist_type",
        },
        "event_source": "ws4.schedule",
        "transition_source": "ws4.treatments",
        "table_hashes": hashes,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return load_carbon_package(root)


def _write_dataset(root: Path, *, retain: int = 0) -> Path:
    """Write a minimal compiled dataset with two fragments and one treatment."""
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "fragment_id": [1, 2],
            "block_id": [1, 2],
            "area_ha": [3.0, 2.0],
            "age": [40, 20],
            "track_id": [1, 2],
        }
    ).to_parquet(root / "fragments.parquet", index=False)
    pd.DataFrame({"track_id": [1, 2], "name": ["track1", "track2"]}).to_parquet(
        root / "tracks.parquet", index=False
    )
    pd.DataFrame(
        {
            "track_id": [1],
            "begin": [0],
            "end": [200],
            "treatment": ["CC"],
            "new_track": [2],
            "offset": [0],
            "retain": [retain],
        }
    ).to_parquet(root / "treatments.parquet", index=False)
    pd.DataFrame(
        {
            "track_id": [1, 2],
            "label": ["feature.Volume", "feature.Volume"],
            "curve_id": [1, 2],
        }
    ).to_parquet(root / "features.parquet", index=False)
    pd.DataFrame(
        {
            "curve_id": [1, 1, 1, 2, 2, 2],
            "x": [0.0, 40.0, 80.0, 0.0, 10.0, 40.0],
            "y": [0.0, 120.0, 220.0, 0.0, 50.0, 180.0],
        }
    ).to_parquet(root / "curves.parquet", index=False)
    return root


def _schedule() -> pd.DataFrame:
    """Return the two-event synthetic schedule."""
    return pd.DataFrame(
        {
            "block_id": [1, 2],
            "treatment": ["CC", "fire"],
            "offset": [0, 5],
        }
    )


def test_build_sit_tables_maps_inventory_events_and_transitions(tmp_path: Path) -> None:
    """The compiler builds the expected SIT tables and event timing."""
    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset")

    tables = build_sit_tables(package, dataset, _schedule())

    assert tables.inventory.shape == (2, 9)
    assert tables.inventory_area_ha == pytest.approx(5.0)
    assert tables.events.shape == (2, 34)
    assert tables.events["time_step"].tolist() == [1, 6]
    assert tables.events["target"].tolist() == pytest.approx([3.0, 2.0])
    assert tables.events["disturbance_type"].tolist() == ["CC", "fire"]
    assert tables.transitions.shape == (1, 13)
    assert tables.transitions.loc[0, "track"] == "track1"
    assert tables.transitions.loc[0, "track_tr"] == "track2"
    assert tables.classifiers["name"].tolist().count("_CLASSIFIER") == 2
    assert tables.yield_table.shape == (2, 7)
    assert tables.yield_table.loc[0, "v1"] == pytest.approx(50.0)


def test_yield_uses_the_package_grid(tmp_path: Path) -> None:
    """The package yield is pivoted onto the age-class grid."""
    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset")
    tables = build_sit_tables(package, dataset, _schedule())

    first = tables.yield_table.loc[tables.yield_table["track"] == "track1"].iloc[0]
    assert first["leading_species"] == "Spruce"
    assert first["v0"] == pytest.approx(0.0)
    assert first["v1"] == pytest.approx(50.0)
    assert first["v2"] == pytest.approx(120.0)
    assert first["v3"] == pytest.approx(180.0)


def test_retention_is_rejected(tmp_path: Path) -> None:
    """A retention split is a clear error, not a silent approximation."""
    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset", retain=1)
    with pytest.raises(CarbonSitError) as error:
        build_sit_tables(package, dataset, _schedule())
    codes = {finding.code for finding in error.value.findings}
    assert "CARBON-RETENTION-UNSUPPORTED" in codes


def test_unknown_treatment_is_rejected(tmp_path: Path) -> None:
    """A treatment outside the package map is rejected."""
    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset")
    schedule = pd.DataFrame({"block_id": [1], "treatment": ["XX"], "offset": [0]})
    with pytest.raises(CarbonSitError) as error:
        build_sit_tables(package, dataset, schedule)
    codes = {finding.code for finding in error.value.findings}
    assert "CARBON-UNKNOWN-DISTURBANCE" in codes


def test_unmatched_track_is_rejected(tmp_path: Path) -> None:
    """A dataset track absent from the package is rejected."""
    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset")
    tracks = pd.DataFrame({"track_id": [1, 2], "name": ["track1", "track3"]})
    tracks.to_parquet(dataset / "tracks.parquet", index=False)
    with pytest.raises(CarbonSitError) as error:
        build_sit_tables(package, dataset, _schedule())
    codes = {finding.code for finding in error.value.findings}
    assert "CARBON-UNMATCHED-TRACK" in codes


def test_missing_dataset_table_is_reported(tmp_path: Path) -> None:
    """A missing dataset table is reported before compilation."""
    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset")
    (dataset / "fragments.parquet").unlink()
    with pytest.raises(CarbonSitError) as error:
        build_sit_tables(package, dataset, _schedule())
    codes = {finding.code for finding in error.value.findings}
    assert "CARBON-DATASET-TABLE" in codes


def test_write_sit_tables_writes_the_audit_copy(tmp_path: Path) -> None:
    """The audit writer writes every SIT table."""
    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset")
    tables = build_sit_tables(package, dataset, _schedule())
    paths = write_sit_tables(tables, tmp_path / "sit")
    assert set(paths) == {
        "sit_classifiers",
        "sit_disturbance_types",
        "sit_age_classes",
        "sit_inventory",
        "sit_yield",
        "sit_events",
        "sit_transitions",
    }
    for path in paths.values():
        assert path.is_file()


def test_read_schedule_uses_offset_clock(tmp_path: Path) -> None:
    """The schedule reader preserves the offset clock."""
    path = tmp_path / "schedule.csv"
    pd.DataFrame({"block_id": [1], "treatment": ["CC"], "offset": [0]}).to_csv(path, index=False)
    schedule = read_schedule(path)
    assert schedule.loc[0, "offset"] == 0


def test_optional_libcbm_parse(tmp_path: Path) -> None:
    """The generated tables parse in libcbm when it is installed."""
    libcbm = pytest.importorskip("libcbm")
    from libcbm.input.sit import sit_cbm_factory, sit_reader  # type: ignore[import-not-found]

    package = _write_package(tmp_path / "package")
    dataset = _write_dataset(tmp_path / "dataset")
    tables = build_sit_tables(package, dataset, _schedule())
    parsed = sit_reader.parse(
        sit_classifiers=tables.classifiers,
        sit_disturbance_types=tables.disturbance_types,
        sit_age_classes=tables.age_classes,
        sit_inventory=tables.inventory,
        sit_yield=tables.yield_table,
        sit_events=tables.events,
        sit_transitions=tables.transitions,
        sit_eligibilities=None,
    )
    config = {
        "mapping_config": {
            "nonforest": None,
            "species": {
                "species_classifier": "species",
                "species_mapping": [
                    {"user_species": "softwood", "default_species": "Softwood forest type"},
                    {"user_species": "hardwood", "default_species": "Hardwood forest type"},
                ],
            },
            "spatial_units": {
                "mapping_mode": "SingleDefaultSpatialUnit",
                "admin_boundary": "British Columbia",
                "eco_boundary": "Montane Cordillera",
            },
            "disturbance_types": {
                "disturbance_type_mapping": [
                    {
                        "user_dist_type": "CC",
                        "default_dist_type": "Clearcut harvesting without salvage",
                    },
                    {"user_dist_type": "fire", "default_dist_type": "Wildfire"},
                ]
            },
        }
    }
    sit = sit_cbm_factory.initialize_sit(sit_data=parsed, config=config)
    classifiers, inventory = sit_cbm_factory.initialize_inventory(sit)
    assert classifiers.n_rows == 2
    assert inventory.n_rows == 2
    assert libcbm is not None
