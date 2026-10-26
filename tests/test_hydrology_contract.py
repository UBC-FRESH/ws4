from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner
from ws4.cli import app
from ws4.io.hydrology import (
    FemicHydrologyBundle,
    FemicHydrologyError,
    HydrologyCrosswalk,
    bundle_pin,
    load_femic_hydrology_bundle,
    load_hydrology_crosswalk,
    load_hydrology_mapping,
    load_registered_femic_hydrology_bundle,
    map_femic_hydrology_to_dataset,
    read_femic_flood_risk,
    read_registered_femic_hydrology,
    register_femic_hydrology_bundle,
    screen_schedule_flood_risk,
    validate_femic_hydrology_bundle,
    validate_registered_femic_hydrology,
    write_hydrology_mapping,
    write_hydrology_screen,
)

runner = CliRunner()
BUNDLE_ID = "hydro-response-test00000001"
BUNDLE_VERSION = "2026.10.0"
GENERATED_UTC = "2026-10-26T00:00:00+00:00"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact(
    root: Path,
    role: str,
    schema_version: str,
    payload: dict[str, object],
) -> dict[str, object]:
    relative = f"artifacts/{role}/{role}.json"
    path = root / relative
    _write_json(path, payload)
    return {
        "artifact_id": f"{role}:test",
        "role": role,
        "relative_path": relative,
        "schema_version": schema_version,
        "media_type": "application/json",
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "description": f"Synthetic {role}",
    }


def _response_surface() -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.flood_response.v1",
        "surface_id": "fixture-surface",
        "generated_utc": GENERATED_UTC,
        "station_id": "fixture-station",
        "method": "nonstationary_gev",
        "baseline_name": "baseline",
        "return_periods": [2.0, 100.0],
        "scenarios": [],
        "summary": {"row_count": 1},
        "rows": [],
        "diagnostics": {},
        "warnings": [],
        "caveats": ["Synthetic fixture only."],
    }


def _flood_risk() -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.flood_risk.v1",
        "table_id": "hydro-risk-fixture",
        "generated_utc": GENERATED_UTC,
        "source_surface_id": "fixture-surface",
        "baseline_name": "baseline",
        "summary": {"row_count": 1},
        "rows": [
            {
                "receptor_id": "receptor-1",
                "watershed_id": "watershed-1",
                "return_period": 100.0,
                "baseline_peak_flow_m3s": 120.0,
                "scenario_peak_flow_m3s": 150.0,
                "ratio": 1.25,
                "exceedance_probability": 0.01,
                "expected_annual_damage": 42000.0,
            }
        ],
        "caveats": ["Screening only; synthetic fixture."],
    }


def _bundle(
    root: Path,
    *,
    include_validation_report: bool = False,
    domain_payload: dict[str, object] | None = None,
    ledger_payload: dict[str, object] | None = None,
    response_surface_payload: dict[str, object] | None = None,
    flood_risk_payload: dict[str, object] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    artifacts = [
        _artifact(
            root,
            "response_surface",
            "femic.hydrology.flood_response.v1",
            response_surface_payload or _response_surface(),
        ),
        _artifact(
            root,
            "flood_risk",
            "femic.hydrology.flood_risk.v1",
            flood_risk_payload or _flood_risk(),
        ),
        _artifact(
            root,
            "domain",
            "femic.hydrology.domain.v1",
            domain_payload
            or {
                "schema_version": "femic.hydrology.domain.v1",
                "domain_id": "fixture-domain",
            },
        ),
        _artifact(
            root,
            "disturbance_ledger",
            "femic.hydrology.disturbance.v1",
            ledger_payload
            or {
                "schema_version": "femic.hydrology.disturbance.v1",
                "ledger_id": "fixture-ledger",
                "domain_id": "fixture-domain",
            },
        ),
    ]
    if include_validation_report:
        artifacts.append(
            _artifact(
                root,
                "validation_report",
                "femic.hydrology.validation.v1",
                {
                    "schema_version": "femic.hydrology.validation.v1",
                    "validation_id": "fixture-validation",
                },
            )
        )
    surface_payload = response_surface_payload or _response_surface()
    risk_payload = flood_risk_payload or _flood_risk()
    risk_summary = risk_payload.get("summary")
    risk_rows = risk_payload.get("rows")
    risk_row_count = (
        risk_summary.get("row_count")
        if isinstance(risk_summary, dict)
        else (len(risk_rows) if isinstance(risk_rows, list) else 0)
    )
    manifest = {
        "schema_version": "femic.hydrology.response.v1",
        "bundle_id": BUNDLE_ID,
        "bundle_name": f"{BUNDLE_ID}-{BUNDLE_VERSION}",
        "bundle_version": BUNDLE_VERSION,
        "generated_utc": GENERATED_UTC,
        "domain_id": "fixture-domain",
        "ledger_id": "fixture-ledger",
        "response_surface_id": "fixture-surface",
        "artifacts": artifacts,
        "response_surface": {
            "surface_id": surface_payload["surface_id"],
            "baseline_name": surface_payload["baseline_name"],
            "return_periods": surface_payload["return_periods"],
        },
        "flood_risk": {
            "table_id": risk_payload["table_id"],
            "row_count": risk_row_count,
            "baseline_name": risk_payload["baseline_name"],
        },
        "applicability_domain": {
            "feature_names": ["harvest_fraction"],
            "min_values": {"harvest_fraction": 0.0},
            "max_values": {"harvest_fraction": 0.6},
            "mean_values": {"harvest_fraction": 0.3},
            "scale_values": {"harvest_fraction": 0.2},
            "max_distance": 3.0,
        },
        "uncertainty": {"interval": "95%", "basis": "synthetic"},
        "consumer_contract": {
            "manifest_path": "manifest.json",
            "read_order": [
                "manifest.json",
                "artifacts/response_surface/*.json",
                "artifacts/flood_risk/*.json",
            ],
            "pin_rule": "Pin identity and verify checksums.",
            "applicability_rule": "Refuse queries outside the domain.",
            "native_units_rule": "Preserve native CRS and units.",
            "consumer_phases": {"ws4": "P49", "fhops": "P14"},
        },
        "caveats": [
            "Screening only; not a regulatory flood map.",
            "Hydrologist review is required before operational use.",
        ],
        "provenance": {"producer": "synthetic-test"},
    }
    manifest_path = root / "manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def _rewrite_manifest(path: Path, manifest: dict[str, object]) -> None:
    _write_json(path, manifest)


def _read_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_valid_bundle_pins_artifacts_and_preserves_caveats(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    bundle = load_femic_hydrology_bundle(
        manifest_path,
        expected_bundle_id=BUNDLE_ID,
        expected_bundle_version=BUNDLE_VERSION,
    )
    validation = validate_femic_hydrology_bundle(manifest_path)
    pin = bundle_pin(bundle)
    risk = read_femic_flood_risk(bundle)

    assert validation.is_valid
    assert validation.errors == ()
    assert validation.artifact_count == 4
    assert bundle.bundle_id == BUNDLE_ID
    assert bundle.bundle_version == BUNDLE_VERSION
    assert pin["bundle_id"] == BUNDLE_ID
    assert pin["manifest_sha256"] == bundle.manifest_sha256
    artifacts = pin["artifacts"]
    assert isinstance(artifacts, dict)
    assert set(artifacts) == {
        "response_surface",
        "flood_risk",
        "domain",
        "disturbance_ledger",
    }
    assert pin["applicability_domain"] == bundle.applicability_domain
    assert "not a regulatory flood map" in bundle.caveats[0]
    assert risk.table_id == "hydro-risk-fixture"
    assert len(risk.rows) == 1
    assert risk.rows[0].ratio == pytest.approx(1.25)
    assert risk.rows[0].expected_annual_damage == pytest.approx(42000.0)


def test_optional_validation_report_role_is_accepted(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle", include_validation_report=True)
    report = validate_femic_hydrology_bundle(manifest_path)

    assert report.is_valid
    assert report.artifact_count == 5


def test_validation_rejects_tampered_artifact(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    artifact = tmp_path / "bundle" / "artifacts" / "response_surface" / "response_surface.json"
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    report = validate_femic_hydrology_bundle(manifest_path)

    assert not report.is_valid
    assert any("size mismatch" in error for error in report.errors)
    assert any("checksum mismatch" in error for error in report.errors)
    with pytest.raises(FemicHydrologyError):
        load_femic_hydrology_bundle(manifest_path)


def test_validation_rejects_missing_artifact(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    (tmp_path / "bundle" / "artifacts" / "domain" / "domain.json").unlink()

    report = validate_femic_hydrology_bundle(manifest_path)

    assert not report.is_valid
    assert any("missing" in error for error in report.errors)


def test_validation_rejects_path_escape_and_absolute_path(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    manifest = _read_manifest(manifest_path)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    first = artifacts[0]
    assert isinstance(first, dict)
    first["relative_path"] = "../escape.json"
    _rewrite_manifest(manifest_path, manifest)

    report = validate_femic_hydrology_bundle(manifest_path)
    assert any("path must not traverse" in error for error in report.errors)

    manifest_path = _bundle(tmp_path / "absolute")
    manifest = _read_manifest(manifest_path)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    first = artifacts[0]
    assert isinstance(first, dict)
    first["relative_path"] = "/tmp/absolute.json"
    _rewrite_manifest(manifest_path, manifest)
    report = validate_femic_hydrology_bundle(manifest_path)
    assert any("path must be relative" in error for error in report.errors)


def test_validation_rejects_missing_required_role(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    manifest = _read_manifest(manifest_path)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    manifest["artifacts"] = [
        item
        for item in artifacts
        if not (isinstance(item, dict) and item.get("role") == "flood_risk")
    ]
    _rewrite_manifest(manifest_path, manifest)

    report = validate_femic_hydrology_bundle(manifest_path)

    assert not report.is_valid
    assert any("missing required artifact roles" in error for error in report.errors)


def test_validation_rejects_wrong_schema_and_summary_mismatch(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    manifest = _read_manifest(manifest_path)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    surface = next(
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("role") == "response_surface"
    )
    surface["schema_version"] = "femic.hydrology.wrong.v1"
    manifest["flood_risk"] = {
        "table_id": "hydro-risk-fixture",
        "row_count": 99,
        "baseline_name": "baseline",
    }
    _rewrite_manifest(manifest_path, manifest)

    report = validate_femic_hydrology_bundle(manifest_path)

    assert any("does not match" in error for error in report.errors)
    assert any("row count does not match" in error for error in report.errors)


def test_validation_rejects_id_mismatches(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    surface = tmp_path / "bundle" / "artifacts" / "response_surface" / "response_surface.json"
    payload = json.loads(surface.read_text(encoding="utf-8"))
    payload["surface_id"] = "other-surface"
    _write_json(surface, payload)

    report = validate_femic_hydrology_bundle(manifest_path)
    assert any("response-surface artifact ID" in error for error in report.errors)

    manifest_path = _bundle(tmp_path / "risk-id")
    risk = tmp_path / "risk-id" / "artifacts" / "flood_risk" / "flood_risk.json"
    payload = json.loads(risk.read_text(encoding="utf-8"))
    payload["source_surface_id"] = "other-surface"
    _write_json(risk, payload)
    report = validate_femic_hydrology_bundle(manifest_path)
    assert any("source surface does not match" in error for error in report.errors)

    manifest_path = _bundle(tmp_path / "domain-id")
    domain = tmp_path / "domain-id" / "artifacts" / "domain" / "domain.json"
    payload = json.loads(domain.read_text(encoding="utf-8"))
    payload["domain_id"] = "other-domain"
    _write_json(domain, payload)
    report = validate_femic_hydrology_bundle(manifest_path)
    assert any("domain artifact ID" in error for error in report.errors)

    manifest_path = _bundle(tmp_path / "ledger-id")
    ledger = tmp_path / "ledger-id" / "artifacts" / "disturbance_ledger" / "disturbance_ledger.json"
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["ledger_id"] = "other-ledger"
    _write_json(ledger, payload)
    report = validate_femic_hydrology_bundle(manifest_path)
    assert any("disturbance-ledger ID" in error for error in report.errors)


def test_validation_rejects_invalid_artifact_json_without_raising(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    surface = tmp_path / "bundle" / "artifacts" / "response_surface" / "response_surface.json"
    surface.write_text("{not-json", encoding="utf-8")

    report = validate_femic_hydrology_bundle(manifest_path)

    assert not report.is_valid
    assert any("Invalid JSON" in error for error in report.errors)
    assert any("checksum mismatch" in error for error in report.errors)


def test_expected_pin_mismatch_fails(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")

    with pytest.raises(FemicHydrologyError, match="does not match expected"):
        load_femic_hydrology_bundle(manifest_path, expected_bundle_id="other")
    with pytest.raises(FemicHydrologyError, match="does not match expected"):
        load_femic_hydrology_bundle(manifest_path, expected_bundle_version="other")


def test_cli_validate_and_inspect(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    valid = runner.invoke(app, ["hydrology", "validate", str(manifest_path)])
    inspect = runner.invoke(app, ["hydrology", "inspect", str(manifest_path), "--json"])

    assert valid.exit_code == 0, valid.output
    assert json.loads(valid.output)["is_valid"] is True
    assert inspect.exit_code == 0, inspect.output
    pin = json.loads(inspect.output)
    assert pin["bundle_id"] == BUNDLE_ID
    assert "response_surface" in pin["artifacts"]

    surface = tmp_path / "bundle" / "artifacts" / "response_surface" / "response_surface.json"
    surface.write_text("{}\n", encoding="utf-8")
    invalid = runner.invoke(app, ["hydrology", "validate", str(manifest_path)])
    assert invalid.exit_code == 1
    assert "checksum mismatch" in invalid.output


def test_cli_inspect_fails_on_invalid_bundle(tmp_path: Path) -> None:
    manifest_path = _bundle(tmp_path / "bundle")
    (tmp_path / "bundle" / "artifacts" / "domain" / "domain.json").unlink()

    result = runner.invoke(app, ["hydrology", "inspect", str(manifest_path)])

    assert result.exit_code == 1
    assert "missing" in result.output


def _dataset(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write_json(
        root / "manifest.json",
        {
            "schema_version": "0.1",
            "tables": {},
            "sources": [],
            "options": {},
            "metadata": {},
        },
    )
    return root


def test_register_bundle_in_dataset_writes_pin_and_sidecar(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path / "dataset")
    manifest_path = _bundle(dataset / "inputs" / "bundle")

    registration = register_femic_hydrology_bundle(
        dataset,
        manifest_path.parent,
        registered_utc=GENERATED_UTC,
    )
    read = read_registered_femic_hydrology(dataset)
    loaded = load_registered_femic_hydrology_bundle(dataset)
    report = validate_registered_femic_hydrology(dataset)

    assert registration["bundle_id"] == BUNDLE_ID
    assert registration["bundle_dir"] == "inputs/bundle"
    assert read == registration
    assert (dataset / "hydrology_products.json").is_file()
    assert (
        json.loads((dataset / "manifest.json").read_text())["metadata"]["hydrology_products"]
        == registration
    )
    assert loaded.bundle_id == BUNDLE_ID
    assert report.is_valid
    assert report.errors == ()


def test_registration_is_idempotent_and_supports_external_reference(
    tmp_path: Path,
) -> None:
    dataset = _dataset(tmp_path / "dataset")
    manifest_path = _bundle(tmp_path / "external_bundle")

    first = register_femic_hydrology_bundle(
        dataset,
        manifest_path.parent,
        registered_utc=GENERATED_UTC,
    )
    second = register_femic_hydrology_bundle(
        dataset,
        manifest_path.parent,
        registered_utc=GENERATED_UTC,
    )

    assert first == second
    assert Path(str(first["bundle_dir"])).is_absolute()
    assert read_registered_femic_hydrology(dataset) == first


def test_registered_bundle_tampering_and_stale_manifest_fail(
    tmp_path: Path,
) -> None:
    dataset = _dataset(tmp_path / "dataset")
    bundle_root = tmp_path / "bundle"
    manifest_path = _bundle(bundle_root)
    register_femic_hydrology_bundle(
        dataset,
        bundle_root,
        registered_utc=GENERATED_UTC,
    )
    artifact = bundle_root / "artifacts" / "response_surface" / "response_surface.json"
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    report = validate_registered_femic_hydrology(dataset)
    assert not report.is_valid
    assert any("checksum mismatch" in error for error in report.errors)
    with pytest.raises(FemicHydrologyError):
        load_registered_femic_hydrology_bundle(dataset)

    dataset = _dataset(tmp_path / "stale_dataset")
    bundle_root = tmp_path / "stale_bundle"
    manifest_path = _bundle(bundle_root)
    register_femic_hydrology_bundle(
        dataset,
        bundle_root,
        registered_utc=GENERATED_UTC,
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["caveats"] = ["Changed after registration."]
    _write_json(manifest_path, payload)

    report = validate_registered_femic_hydrology(dataset)
    assert not report.is_valid
    assert any("manifest digest" in error for error in report.errors)


def test_registration_requires_dataset_manifest_and_matching_pin(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"
    missing.mkdir()
    with pytest.raises(FemicHydrologyError, match="Dataset manifest is missing"):
        register_femic_hydrology_bundle(missing, _bundle(tmp_path / "bundle").parent)

    dataset = _dataset(tmp_path / "dataset")
    with pytest.raises(FemicHydrologyError, match="does not match expected"):
        register_femic_hydrology_bundle(
            dataset,
            _bundle(tmp_path / "bundle2").parent,
            expected_bundle_id="other",
        )


def test_no_registered_bundle_and_invalid_sidecar(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path / "dataset")
    assert read_registered_femic_hydrology(dataset) is None
    with pytest.raises(FemicHydrologyError, match="no registered"):
        validate_registered_femic_hydrology(dataset)
    (dataset / "hydrology_products.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(FemicHydrologyError, match="Invalid hydrology sidecar"):
        read_registered_femic_hydrology(dataset)


def test_cli_register_inspect_and_validate_dataset(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path / "dataset")
    bundle_root = tmp_path / "bundle"
    _bundle(bundle_root)

    register = runner.invoke(
        app,
        [
            "hydrology",
            "register",
            "--dataset",
            str(dataset),
            "--bundle",
            str(bundle_root),
            "--json",
        ],
    )
    assert register.exit_code == 0, register.output
    assert json.loads(register.output)["bundle_id"] == BUNDLE_ID

    inspect = runner.invoke(
        app,
        ["hydrology", "inspect", "--dataset", str(dataset), "--json"],
    )
    assert inspect.exit_code == 0, inspect.output
    assert json.loads(inspect.output)["bundle_id"] == BUNDLE_ID

    validate = runner.invoke(
        app,
        ["hydrology", "validate", "--dataset", str(dataset)],
    )
    assert validate.exit_code == 0, validate.output
    assert json.loads(validate.output)["is_valid"] is True

    artifact = bundle_root / "artifacts" / "domain" / "domain.json"
    artifact.write_text("{}\n", encoding="utf-8")
    invalid = runner.invoke(
        app,
        ["hydrology", "validate", "--dataset", str(dataset)],
    )
    assert invalid.exit_code == 1
    assert "checksum mismatch" in invalid.output


def test_cli_requires_exactly_one_bundle_or_dataset(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path / "dataset")
    bundle_root = tmp_path / "bundle"
    _bundle(bundle_root)

    neither = runner.invoke(app, ["hydrology", "validate"])
    both = runner.invoke(
        app,
        [
            "hydrology",
            "validate",
            str(bundle_root),
            "--dataset",
            str(dataset),
        ],
    )

    assert neither.exit_code == 1
    assert "exactly one" in neither.output
    assert both.exit_code == 1
    assert "exactly one" in both.output


def _domain_payload() -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.domain.v1",
        "domain_id": "fixture-domain",
        "watersheds": [
            {"watershed_id": "watershed-1", "area_km2": 1.0},
            {"watershed_id": "watershed-2", "area_km2": 2.0},
        ],
        "receptors": [
            {"receptor_id": "receptor-1"},
            {"receptor_id": "receptor-2"},
        ],
    }


def _ledger_payload() -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.disturbance.v1",
        "ledger_id": "fixture-ledger",
        "domain_id": "fixture-domain",
        "units": [
            {"unit_id": "unit-1", "watershed_id": "watershed-1"},
            {"unit_id": "unit-2", "watershed_id": "watershed-2"},
        ],
    }


def _compiled_dataset(root: Path) -> Path:
    _dataset(root)
    pd.DataFrame(
        {
            "fragment_id": [1, 2, 3, 4],
            "block_id": [10, 10, 11, 12],
            "area_ha": [1.0, 2.0, 3.0, 4.0],
        }
    ).to_parquet(root / "fragments.parquet", index=False)
    pd.DataFrame(
        {
            "block_id": [10, 11, 12],
            "area_ha": [3.0, 3.0, 4.0],
        }
    ).to_parquet(root / "blocks.parquet", index=False)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["tables"] = {
        "fragments": "fragments.parquet",
        "blocks": "blocks.parquet",
    }
    _write_json(root / "manifest.json", manifest)
    return root


def _write_crosswalk(path: Path, rows: list[dict[str, object]]) -> Path:
    columns = (
        "fragment_id",
        "block_id",
        "unit_id",
        "watershed_id",
        "receptor_id",
        "notes",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_metadata(
    path: Path,
    *,
    crosswalk_sha256: str | None = None,
    review_status: str = "reviewed",
    reviewed_by: str | None = "reviewer-1",
) -> Path:
    payload = {
        "schema_version": "ws4.hydrology.crosswalk.v1",
        "crosswalk_id": "fixture-crosswalk",
        "created_utc": GENERATED_UTC,
        "review_status": review_status,
        "reviewed_by": reviewed_by,
        "method": "Explicit test crosswalk",
        "source": "Synthetic test fixture",
        "caveats": ["Synthetic crosswalk for contract tests."],
    }
    if crosswalk_sha256 is not None:
        payload["crosswalk_sha256"] = crosswalk_sha256
    _write_json(path, payload)
    return path


def _complete_fragment_rows() -> list[dict[str, object]]:
    return [
        {
            "fragment_id": 1,
            "block_id": "",
            "unit_id": "unit-1",
            "watershed_id": "watershed-1",
            "receptor_id": "receptor-1",
            "notes": "",
        },
        {
            "fragment_id": 2,
            "block_id": "",
            "unit_id": "unit-1",
            "watershed_id": "watershed-1",
            "receptor_id": "receptor-1",
            "notes": "",
        },
        {
            "fragment_id": 3,
            "block_id": "",
            "unit_id": "unit-2",
            "watershed_id": "watershed-2",
            "receptor_id": "receptor-2",
            "notes": "",
        },
        {
            "fragment_id": 4,
            "block_id": "",
            "unit_id": "unit-2",
            "watershed_id": "watershed-2",
            "receptor_id": "receptor-2",
            "notes": "",
        },
    ]


def _mapping_fixture(
    root: Path,
    *,
    rows: list[dict[str, object]] | None = None,
    review_status: str = "reviewed",
) -> tuple[Path, HydrologyCrosswalk, FemicHydrologyBundle]:
    dataset = _compiled_dataset(root / "dataset")
    bundle = load_femic_hydrology_bundle(
        _bundle(
            root / "bundle",
            domain_payload=_domain_payload(),
            ledger_payload=_ledger_payload(),
        )
    )
    register_femic_hydrology_bundle(
        dataset,
        bundle.bundle_dir,
        registered_utc=GENERATED_UTC,
    )
    crosswalk_path = _write_crosswalk(
        root / "crosswalk.csv",
        rows if rows is not None else _complete_fragment_rows(),
    )
    metadata = _write_metadata(
        root / "crosswalk.meta.json",
        crosswalk_sha256=hashlib.sha256(crosswalk_path.read_bytes()).hexdigest(),
        review_status=review_status,
    )
    crosswalk = load_hydrology_crosswalk(crosswalk_path, metadata_path=metadata)
    return dataset, crosswalk, bundle


def test_map_complete_fragment_crosswalk_and_write_outputs(tmp_path: Path) -> None:
    dataset, crosswalk, bundle = _mapping_fixture(tmp_path)
    mapping = map_femic_hydrology_to_dataset(
        dataset,
        bundle,
        crosswalk,
        generated_utc=GENERATED_UTC,
    )
    paths = write_hydrology_mapping(mapping, tmp_path / "out")

    assert mapping.review_status == "reviewed"
    assert len(mapping.fragments) == 4
    assert len(mapping.blocks) == 3
    assert mapping.coverage["unmapped_fragments"] == []
    assert mapping.coverage["unmapped_blocks"] == []
    assert mapping.warnings == ()
    assert paths["fragments"].is_file()
    assert paths["blocks"].is_file()
    assert paths["manifest"].is_file()
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "ws4.hydrology.mapping.v1"
    assert manifest["mapping_id"] == mapping.mapping_id
    assert manifest["review_status"] == "reviewed"
    assert manifest["fragment_count"] == 4
    assert manifest["block_count"] == 3


def test_map_block_crosswalk_derives_fragments(tmp_path: Path) -> None:
    rows = [
        {
            "fragment_id": "",
            "block_id": 10,
            "unit_id": "unit-1",
            "watershed_id": "watershed-1",
            "receptor_id": "receptor-1",
            "notes": "",
        },
        {
            "fragment_id": "",
            "block_id": 11,
            "unit_id": "unit-2",
            "watershed_id": "watershed-2",
            "receptor_id": "receptor-2",
            "notes": "",
        },
        {
            "fragment_id": "",
            "block_id": 12,
            "unit_id": "unit-2",
            "watershed_id": "watershed-2",
            "receptor_id": "receptor-2",
            "notes": "",
        },
    ]
    dataset, crosswalk, bundle = _mapping_fixture(tmp_path, rows=rows)
    mapping = map_femic_hydrology_to_dataset(dataset, bundle, crosswalk)

    assert len(mapping.fragments) == 4
    assert len(mapping.blocks) == 3
    assert all(row["source"] == "block_crosswalk" for row in mapping.fragments)
    assert all(row["source"] == "block_crosswalk" for row in mapping.blocks)


def test_map_partial_requires_opt_in_and_records_gaps(tmp_path: Path) -> None:
    rows = [_complete_fragment_rows()[0]]
    dataset, crosswalk, bundle = _mapping_fixture(tmp_path, rows=rows)

    with pytest.raises(FemicHydrologyError, match="does not cover"):
        map_femic_hydrology_to_dataset(dataset, bundle, crosswalk)

    mapping = map_femic_hydrology_to_dataset(
        dataset,
        bundle,
        crosswalk,
        allow_partial=True,
    )
    assert mapping.coverage["unmapped_fragments"] == [2, 3, 4]
    assert mapping.coverage["unmapped_blocks"] == [10, 11, 12]
    assert any("Partial mapping" in warning for warning in mapping.warnings)


def test_map_rejects_unknown_ids_and_bad_rows(tmp_path: Path) -> None:
    rows = [_complete_fragment_rows()[0]]
    dataset, _crosswalk, bundle = _mapping_fixture(tmp_path, rows=rows)

    for replacement, message in (
        ({"fragment_id": 99}, "fragment 99"),
        ({"unit_id": "unit-99"}, "unit 'unit-99'"),
        ({"watershed_id": "watershed-99"}, "watershed 'watershed-99'"),
        ({"receptor_id": "receptor-99"}, "receptor 'receptor-99'"),
    ):
        bad = {**rows[0], **replacement}
        path = _write_crosswalk(tmp_path / f"bad-{len(message)}.csv", [bad])
        loaded = load_hydrology_crosswalk(path)
        with pytest.raises(FemicHydrologyError, match=message):
            map_femic_hydrology_to_dataset(
                dataset,
                bundle,
                loaded,
                allow_partial=True,
            )

    both = {**rows[0], "block_id": 10}
    path = _write_crosswalk(tmp_path / "both.csv", [both])
    with pytest.raises(FemicHydrologyError, match="exactly one"):
        load_hydrology_crosswalk(path)

    neither = {**rows[0], "fragment_id": ""}
    path = _write_crosswalk(tmp_path / "neither.csv", [neither])
    with pytest.raises(FemicHydrologyError, match="exactly one"):
        load_hydrology_crosswalk(path)

    duplicate = [rows[0], rows[0]]
    path = _write_crosswalk(tmp_path / "duplicate.csv", duplicate)
    with pytest.raises(FemicHydrologyError, match="Duplicate crosswalk support"):
        load_hydrology_crosswalk(path)


def test_map_rejects_conflicting_fragment_and_block_mappings(tmp_path: Path) -> None:
    rows = [
        {
            "fragment_id": 1,
            "block_id": "",
            "unit_id": "unit-1",
            "watershed_id": "watershed-1",
            "receptor_id": "receptor-1",
            "notes": "",
        },
        {
            "fragment_id": 2,
            "block_id": "",
            "unit_id": "unit-2",
            "watershed_id": "watershed-2",
            "receptor_id": "receptor-2",
            "notes": "",
        },
        {
            "fragment_id": 3,
            "block_id": "",
            "unit_id": "unit-2",
            "watershed_id": "watershed-2",
            "receptor_id": "receptor-2",
            "notes": "",
        },
        {
            "fragment_id": 4,
            "block_id": "",
            "unit_id": "unit-2",
            "watershed_id": "watershed-2",
            "receptor_id": "receptor-2",
            "notes": "",
        },
    ]
    dataset, crosswalk, bundle = _mapping_fixture(tmp_path, rows=rows)
    with pytest.raises(FemicHydrologyError, match="conflicting FEMIC mappings"):
        map_femic_hydrology_to_dataset(dataset, bundle, crosswalk)

    rows = _complete_fragment_rows()
    rows[0] = {
        **rows[0],
        "unit_id": "unit-2",
        "watershed_id": "watershed-2",
        "receptor_id": "receptor-2",
    }
    rows.append(
        {
            "fragment_id": "",
            "block_id": 10,
            "unit_id": "unit-1",
            "watershed_id": "watershed-1",
            "receptor_id": "receptor-1",
            "notes": "",
        }
    )
    dataset, crosswalk, bundle = _mapping_fixture(tmp_path, rows=rows)
    with pytest.raises(FemicHydrologyError, match="conflicts with the explicit block"):
        map_femic_hydrology_to_dataset(dataset, bundle, crosswalk)


def test_crosswalk_review_metadata_is_explicit(tmp_path: Path) -> None:
    rows = _complete_fragment_rows()
    path = _write_crosswalk(tmp_path / "crosswalk.csv", rows)
    not_reviewed = load_hydrology_crosswalk(path)
    assert not_reviewed.metadata.review_status == "not_reviewed"

    metadata = _write_metadata(
        tmp_path / "bad.meta.json",
        crosswalk_sha256="0" * 64,
    )
    with pytest.raises(FemicHydrologyError, match="checksum"):
        load_hydrology_crosswalk(path, metadata_path=metadata)

    metadata = _write_metadata(
        tmp_path / "review.meta.json",
        crosswalk_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        reviewed_by=None,
    )
    with pytest.raises(FemicHydrologyError, match="reviewed_by"):
        load_hydrology_crosswalk(path, metadata_path=metadata)


def test_map_records_not_reviewed_warning(tmp_path: Path) -> None:
    dataset, crosswalk, bundle = _mapping_fixture(
        tmp_path,
        review_status="not_reviewed",
    )
    mapping = map_femic_hydrology_to_dataset(dataset, bundle, crosswalk)
    assert mapping.review_status == "not_reviewed"
    assert any("provisional" in warning for warning in mapping.warnings)


def test_cli_map_writes_outputs(tmp_path: Path) -> None:
    dataset, crosswalk, bundle = _mapping_fixture(tmp_path)
    _ = bundle
    metadata = tmp_path / "crosswalk.meta.json"
    out = tmp_path / "mapping-out"

    result = runner.invoke(
        app,
        [
            "hydrology",
            "map",
            "--dataset",
            str(dataset),
            "--crosswalk",
            str(crosswalk.path),
            "--metadata",
            str(metadata),
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "mapping_id: ws4-hydro-mapping-" in result.stdout
    assert (out / "hydrology_fragments.csv").is_file()
    assert (out / "hydrology_blocks.csv").is_file()
    assert (out / "hydrology_mapping.json").is_file()


def _screen_surface_payload() -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.flood_response.v1",
        "surface_id": "fixture-surface",
        "generated_utc": GENERATED_UTC,
        "station_id": "fixture-station",
        "method": "nonstationary_gev",
        "baseline_name": "baseline",
        "return_periods": [2.0, 100.0],
        "scenarios": [
            {"name": "baseline", "covariates": {"harvest_fraction": 0.0}},
            {"name": "medium", "covariates": {"harvest_fraction": 0.03}},
            {"name": "high", "covariates": {"harvest_fraction": 0.5}},
        ],
        "summary": {"row_count": 6},
        "rows": [
            {
                "scenario_name": scenario,
                "return_period": period,
                "quantile": 120.0 * ratio,
                "baseline_quantile": 120.0,
                "ratio": ratio,
                "difference": 120.0 * (ratio - 1.0),
            }
            for scenario, ratio in (
                ("baseline", 1.0),
                ("medium", 1.1),
                ("high", 1.25),
            )
            for period in (2.0, 100.0)
        ],
        "diagnostics": {},
        "warnings": [],
        "caveats": ["Synthetic fixture only."],
    }


def _screen_risk_payload() -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.flood_risk.v1",
        "table_id": "hydro-risk-fixture",
        "generated_utc": GENERATED_UTC,
        "source_surface_id": "fixture-surface",
        "baseline_name": "baseline",
        "summary": {"row_count": 2},
        "rows": [
            {
                "receptor_id": "receptor-1",
                "watershed_id": "watershed-1",
                "return_period": 100.0,
                "baseline_peak_flow_m3s": 120.0,
                "scenario_peak_flow_m3s": 150.0,
                "ratio": 1.25,
                "exceedance_probability": 0.01,
                "expected_annual_damage": 42000.0,
            },
            {
                "receptor_id": "receptor-2",
                "watershed_id": "watershed-2",
                "return_period": 100.0,
                "baseline_peak_flow_m3s": 80.0,
                "scenario_peak_flow_m3s": 90.0,
                "ratio": 1.125,
                "exceedance_probability": 0.02,
                "expected_annual_damage": 12000.0,
            },
        ],
        "caveats": ["Screening only; synthetic fixture."],
    }


def _write_schedule(path: Path) -> Path:
    path.write_text(
        "block_id,treatment,offset\n10,clearcut,0\n11,clearcut,1\n",
        encoding="utf-8",
    )
    return path


def _screen_fixture(
    root: Path,
) -> tuple[Path, FemicHydrologyBundle, Path, Path]:
    dataset = _compiled_dataset(root / "dataset")
    bundle = load_femic_hydrology_bundle(
        _bundle(
            root / "bundle",
            domain_payload=_domain_payload(),
            ledger_payload=_ledger_payload(),
            response_surface_payload=_screen_surface_payload(),
            flood_risk_payload=_screen_risk_payload(),
        )
    )
    register_femic_hydrology_bundle(dataset, bundle.bundle_dir, registered_utc=GENERATED_UTC)
    crosswalk_path = _write_crosswalk(root / "crosswalk.csv", _complete_fragment_rows())
    metadata = _write_metadata(
        root / "crosswalk.meta.json",
        crosswalk_sha256=hashlib.sha256(crosswalk_path.read_bytes()).hexdigest(),
    )
    crosswalk = load_hydrology_crosswalk(crosswalk_path, metadata_path=metadata)
    mapping = map_femic_hydrology_to_dataset(
        dataset,
        bundle,
        crosswalk,
        generated_utc=GENERATED_UTC,
    )
    mapping_paths = write_hydrology_mapping(mapping, root / "mapping")
    return dataset, bundle, mapping_paths["manifest"], _write_schedule(root / "schedule.csv")


def test_screen_schedule_produces_receptor_rows(tmp_path: Path) -> None:
    dataset, bundle, mapping_manifest, schedule = _screen_fixture(tmp_path)
    mapping = load_hydrology_mapping(mapping_manifest)
    screen = screen_schedule_flood_risk(
        dataset,
        bundle,
        mapping,
        schedule,
        mapping_manifest_path=mapping_manifest,
        generated_utc=GENERATED_UTC,
    )
    paths = write_hydrology_screen(screen, tmp_path / "screen")

    assert len(screen.rows) == 3
    assert screen.refusals == ()
    assert screen.rows[0]["watershed_id"] == "watershed-1"
    assert screen.rows[0]["scenario_name"] == "medium"
    assert screen.rows[0]["screening_peak_flow_m3s"] == pytest.approx(132.0)
    assert screen.rows[1]["period"] == 1
    assert {row["watershed_id"] for row in screen.rows[1:]} == {
        "watershed-1",
        "watershed-2",
    }
    assert paths["rows"].is_file()
    assert paths["manifest"].is_file()
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "ws4.hydrology.screen.v1"
    assert manifest["row_count"] == 3
    assert manifest["schedule_sha256"] == screen.schedule_sha256
    assert manifest["mapping_sha256"] == screen.mapping_sha256


def test_screen_refuses_outside_tolerance_and_can_allow(tmp_path: Path) -> None:
    dataset, bundle, mapping_manifest, schedule = _screen_fixture(tmp_path)
    mapping = load_hydrology_mapping(mapping_manifest)

    with pytest.raises(FemicHydrologyError, match="refused"):
        screen_schedule_flood_risk(
            dataset,
            bundle,
            mapping,
            schedule,
            scenario_tolerance=0.001,
        )

    screen = screen_schedule_flood_risk(
        dataset,
        bundle,
        mapping,
        schedule,
        scenario_tolerance=0.001,
        allow_refused=True,
        generated_utc=GENERATED_UTC,
    )
    assert screen.refusals
    assert any("tolerance" in str(item["reason"]) for item in screen.refusals)
    assert all(row["watershed_id"] == "watershed-1" for row in screen.rows)


def test_screen_refuses_missing_watershed_area(tmp_path: Path) -> None:
    dataset = _compiled_dataset(tmp_path / "dataset")
    domain = _domain_payload()
    domain["watersheds"] = [{"watershed_id": "watershed-1"}]
    bundle = load_femic_hydrology_bundle(
        _bundle(
            tmp_path / "bundle",
            domain_payload=domain,
            ledger_payload=_ledger_payload(),
            response_surface_payload=_screen_surface_payload(),
            flood_risk_payload=_screen_risk_payload(),
        )
    )
    register_femic_hydrology_bundle(dataset, bundle.bundle_dir)
    crosswalk_path = _write_crosswalk(tmp_path / "crosswalk.csv", _complete_fragment_rows())
    crosswalk = load_hydrology_crosswalk(crosswalk_path)
    mapping = map_femic_hydrology_to_dataset(dataset, bundle, crosswalk)
    schedule = _write_schedule(tmp_path / "schedule.csv")

    screen = screen_schedule_flood_risk(
        dataset,
        bundle,
        mapping,
        schedule,
        allow_refused=True,
    )
    assert any("watershed area" in str(item["reason"]) for item in screen.refusals)


def test_screen_rejects_unknown_schedule_block(tmp_path: Path) -> None:
    dataset, bundle, mapping_manifest, _schedule = _screen_fixture(tmp_path)
    mapping = load_hydrology_mapping(mapping_manifest)
    unknown = tmp_path / "unknown.csv"
    unknown.write_text("block_id,treatment,offset\n999,clearcut,0\n", encoding="utf-8")

    with pytest.raises(FemicHydrologyError, match="no explicit FEMIC mapping"):
        screen_schedule_flood_risk(dataset, bundle, mapping, unknown)


def test_load_mapping_round_trip(tmp_path: Path) -> None:
    dataset, bundle, mapping_manifest, schedule = _screen_fixture(tmp_path)
    _ = dataset, bundle, schedule
    mapping = load_hydrology_mapping(mapping_manifest)
    assert mapping.mapping_id.startswith("ws4-hydro-mapping-")
    assert len(mapping.fragments) == 4
    assert len(mapping.blocks) == 3
    assert mapping.coverage["unmapped_fragments"] == []


def test_cli_screen_writes_outputs(tmp_path: Path) -> None:
    dataset, _bundle_value, mapping_manifest, schedule = _screen_fixture(tmp_path)
    _ = _bundle_value
    out = tmp_path / "screen-out"

    result = runner.invoke(
        app,
        [
            "hydrology",
            "screen",
            "--dataset",
            str(dataset),
            "--mapping",
            str(mapping_manifest),
            "--schedule",
            str(schedule),
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "screen_id: ws4-hydro-screen-" in result.stdout
    assert (out / "hydrology_screen.csv").is_file()
    assert (out / "hydrology_screen.json").is_file()


def test_screen_rejects_mapping_from_other_bundle(tmp_path: Path) -> None:
    dataset, _bundle_value, mapping_manifest, schedule = _screen_fixture(tmp_path)
    mapping = load_hydrology_mapping(mapping_manifest)
    other_domain = _domain_payload()
    other_domain["name"] = "Other synthetic domain"
    other = _bundle(
        tmp_path / "other-bundle",
        domain_payload=other_domain,
        ledger_payload=_ledger_payload(),
        response_surface_payload=_screen_surface_payload(),
        flood_risk_payload=_screen_risk_payload(),
    )
    other_bundle = load_femic_hydrology_bundle(other)

    with pytest.raises(FemicHydrologyError, match="different FEMIC bundle pin"):
        screen_schedule_flood_risk(dataset, other_bundle, mapping, schedule)
