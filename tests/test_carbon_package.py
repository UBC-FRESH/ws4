"""Contract tests for FEMIC carbon package loading and track resolution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import pytest
from ws4.carbon.package import (
    CarbonPackage,
    CarbonPackageError,
    load_carbon_package,
    package_fingerprint,
    resolve_tracks,
    validate_carbon_package,
)
from ws4.model.schema import Problem

TABLES: dict[str, list[list[object]]] = {
    "classifiers": [
        ["classifier_id", "classifier", "value", "description"],
        [1, "track", "track1", "first track"],
        [1, "track", "track2", "second track"],
        [2, "species", "Spruce", "Spruce"],
        [2, "species", "Trembling aspen", "Trembling aspen"],
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
        ["track1", 40, 10.0, 0, 0, "fire", "CC"],
        ["track2", 20, 5.0, 0, 0, "fire", "fire"],
    ],
    "yield": [
        ["track_name", "species", "leading_species", "age", "volume_m3_ha"],
        ["track1", "Spruce", "Spruce", 0, 0.0],
        ["track1", "Spruce", "Spruce", 10, 50.0],
        ["track1", "Spruce", "Spruce", 20, 120.0],
        ["track1", "Spruce", "Spruce", 30, 180.0],
        ["track2", "Trembling aspen", "Trembling aspen", 0, 0.0],
        ["track2", "Trembling aspen", "Trembling aspen", 10, 30.0],
        ["track2", "Trembling aspen", "Trembling aspen", 20, 70.0],
        ["track2", "Trembling aspen", "Trembling aspen", 30, 100.0],
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
            "track1;Spruce",
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
            "track2;Trembling aspen",
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
        ["track1", "feature.Volume", "Spruce", 1.0],
        ["track2", "feature.Volume", "Trembling aspen", 1.0],
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


def _write_tables(root: Path) -> None:
    """Write the synthetic fixture tables."""
    for name, rows in TABLES.items():
        pd.DataFrame(rows[1:], columns=rows[0]).to_csv(root / f"{name}.csv", index=False)


def _table_hashes(root: Path) -> dict[str, str]:
    """Return hashes for the fixture tables."""
    return {
        name: hashlib.sha256((root / f"{name}.csv").read_bytes()).hexdigest() for name in TABLES
    }


def _manifest(root: Path, *, hashes: bool = False) -> dict[str, object]:
    """Build the fixture manifest."""
    manifest: dict[str, object] = {
        "schema_version": "0.1",
        "package_id": "femic-carbon-fixture",
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
    }
    if hashes:
        manifest["table_hashes"] = _table_hashes(root)
    return manifest


def _write_package(root: Path, *, hashes: bool = False) -> Path:
    """Write a valid fixture package."""
    root.mkdir(parents=True, exist_ok=True)
    _write_tables(root)
    (root / "manifest.json").write_text(
        json.dumps(_manifest(root, hashes=hashes)), encoding="utf-8"
    )
    return root


def _codes(findings: Iterable[Problem]) -> set[str]:
    """Return the finding codes."""
    return {item.code for item in findings}


def test_load_valid_package(tmp_path: Path) -> None:
    """A complete package loads and exposes its tables."""
    package = load_carbon_package(_write_package(tmp_path / "package"))

    assert isinstance(package, CarbonPackage)
    assert package.manifest.package_id == "femic-carbon-fixture"
    assert set(package.tables) == set(TABLES)
    assert len(package.fingerprint) == 64


def test_validate_valid_package(tmp_path: Path) -> None:
    """A complete package has no findings."""
    assert validate_carbon_package(_write_package(tmp_path / "package")) == []


def test_missing_manifest_is_reported(tmp_path: Path) -> None:
    """A package without a manifest is rejected."""
    root = tmp_path / "package"
    root.mkdir()
    with pytest.raises(CarbonPackageError) as error:
        load_carbon_package(root)
    assert "CARBON-MISSING-MANIFEST" in _codes(list(error.value.findings))


def test_missing_table_is_reported(tmp_path: Path) -> None:
    """A missing required table is reported."""
    root = _write_package(tmp_path / "package")
    (root / "yield.csv").unlink()
    assert "CARBON-MISSING-TABLE" in _codes(validate_carbon_package(root))


def test_bad_schema_version_is_reported(tmp_path: Path) -> None:
    """An unsupported schema version is rejected."""
    root = _write_package(tmp_path / "package")
    manifest = _manifest(root)
    manifest["schema_version"] = "9.9"
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert "CARBON-SCHEMA-VERSION" in _codes(validate_carbon_package(root))


def test_bad_unit_is_reported(tmp_path: Path) -> None:
    """A wrong carbon unit is rejected."""
    root = _write_package(tmp_path / "package")
    manifest = _manifest(root)
    manifest["units"] = {
        "area": "ha",
        "volume": "m3/ha",
        "carbon": "kgC",
        "carbon_density": "tC/ha",
        "co2e": "tCO2e",
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert "CARBON-UNIT" in _codes(validate_carbon_package(root))


def test_manifest_unknown_field_is_reported(tmp_path: Path) -> None:
    """A typo in the manifest is rejected rather than ignored."""
    root = _write_package(tmp_path / "package")
    manifest = _manifest(root)
    manifest["typo"] = True
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert "CARBON-MANIFEST-INVALID" in _codes(validate_carbon_package(root))


def test_duplicate_track_name_is_reported(tmp_path: Path) -> None:
    """A duplicated track is rejected."""
    root = _write_package(tmp_path / "package")
    frame = pd.read_csv(root / "track_carbon_map.csv")
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    frame.to_csv(root / "track_carbon_map.csv", index=False)
    assert "CARBON-DUPLICATE-KEY" in _codes(validate_carbon_package(root))


def test_bad_inventory_area_is_reported(tmp_path: Path) -> None:
    """A non-positive inventory area is rejected."""
    root = _write_package(tmp_path / "package")
    frame = pd.read_csv(root / "inventory.csv")
    frame.loc[0, "area_ha"] = 0
    frame.to_csv(root / "inventory.csv", index=False)
    assert "CARBON-INVALID-VALUE" in _codes(validate_carbon_package(root))


def test_unknown_species_is_reported(tmp_path: Path) -> None:
    """A track species outside the species map is rejected."""
    root = _write_package(tmp_path / "package")
    frame = pd.read_csv(root / "track_carbon_map.csv")
    frame.loc[0, "leading_species"] = "Unknown"
    frame.to_csv(root / "track_carbon_map.csv", index=False)
    assert "CARBON-UNKNOWN-SPECIES" in _codes(validate_carbon_package(root))


def test_classifier_set_count_is_reported(tmp_path: Path) -> None:
    """A classifier set with the wrong number of values is rejected."""
    root = _write_package(tmp_path / "package")
    frame = pd.read_csv(root / "track_carbon_map.csv")
    frame.loc[0, "classifier_set"] = "track1"
    frame.to_csv(root / "track_carbon_map.csv", index=False)
    assert "CARBON-INVALID-VALUE" in _codes(validate_carbon_package(root))


def test_eco_boundary_mismatch_is_reported(tmp_path: Path) -> None:
    """A track outside the manifest eco boundary is rejected."""
    root = _write_package(tmp_path / "package")
    frame = pd.read_csv(root / "track_carbon_map.csv")
    frame.loc[0, "eco_boundary"] = "Pacific Maritime"
    frame.to_csv(root / "track_carbon_map.csv", index=False)
    assert "CARBON-ECO-MISMATCH" in _codes(validate_carbon_package(root))


def test_table_hash_mismatch_is_reported(tmp_path: Path) -> None:
    """A changed table no longer matches the manifest hash."""
    root = _write_package(tmp_path / "package", hashes=True)
    frame = pd.read_csv(root / "inventory.csv")
    frame.loc[0, "area_ha"] = 11.0
    frame.to_csv(root / "inventory.csv", index=False)
    assert "CARBON-TABLE-HASH" in _codes(validate_carbon_package(root))


def test_fingerprint_is_stable_and_changes_with_content(tmp_path: Path) -> None:
    """The fingerprint is stable for the same files and changes when a table changes."""
    root = _write_package(tmp_path / "package")
    first = package_fingerprint(load_carbon_package(root))
    second = package_fingerprint(load_carbon_package(root))
    assert first == second

    frame = pd.read_csv(root / "inventory.csv")
    frame.loc[0, "age"] = 41
    frame.to_csv(root / "inventory.csv", index=False)
    third = package_fingerprint(load_carbon_package(root))
    assert third != first


def test_resolve_tracks_maps_and_reports_unmatched(tmp_path: Path) -> None:
    """The join maps exact names and reports dataset tracks absent from the package."""
    package = load_carbon_package(_write_package(tmp_path / "package"))
    tracks = pd.DataFrame(
        {
            "track_id": [10, 11],
            "name": ["track1", "track3"],
        }
    )

    with pytest.raises(CarbonPackageError) as error:
        resolve_tracks(package, tracks)
    assert "CARBON-UNMATCHED-TRACK" in _codes(list(error.value.findings))

    resolution = resolve_tracks(package, tracks, allow_unmatched=True)
    assert resolution.mapping == {"track1": 10}
    assert resolution.unmatched == ("track3",)
    assert resolution.extra == ("track2",)


def test_resolve_tracks_rejects_duplicate_dataset_names(tmp_path: Path) -> None:
    """Duplicate track names in the dataset are rejected."""
    package = load_carbon_package(_write_package(tmp_path / "package"))
    tracks = pd.DataFrame(
        {
            "track_id": [10, 11],
            "name": ["track1", "track1"],
        }
    )
    with pytest.raises(CarbonPackageError) as error:
        resolve_tracks(package, tracks)
    assert "CARBON-DUPLICATE-TRACK-NAME" in _codes(list(error.value.findings))
