from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner
from ws4.cli import app
from ws4.io.hydrology import (
    FemicHydrologyError,
    bundle_pin,
    load_femic_hydrology_bundle,
    read_femic_flood_risk,
    validate_femic_hydrology_bundle,
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
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    artifacts = [
        _artifact(
            root,
            "response_surface",
            "femic.hydrology.flood_response.v1",
            _response_surface(),
        ),
        _artifact(
            root,
            "flood_risk",
            "femic.hydrology.flood_risk.v1",
            _flood_risk(),
        ),
        _artifact(
            root,
            "domain",
            "femic.hydrology.domain.v1",
            {
                "schema_version": "femic.hydrology.domain.v1",
                "domain_id": "fixture-domain",
            },
        ),
        _artifact(
            root,
            "disturbance_ledger",
            "femic.hydrology.disturbance.v1",
            {
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
            "surface_id": "fixture-surface",
            "baseline_name": "baseline",
            "return_periods": [2.0, 100.0],
        },
        "flood_risk": {
            "table_id": "hydro-risk-fixture",
            "row_count": 1,
            "baseline_name": "baseline",
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
