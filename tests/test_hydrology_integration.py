from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from typer.testing import CliRunner
from ws4.cli import app
from ws4.io.hydrology import (
    FemicHydrologyBundle,
    FemicHydrologyError,
    load_femic_hydrology_bundle,
    load_hydrology_crosswalk,
    load_hydrology_mapping,
    map_femic_hydrology_to_dataset,
    register_femic_hydrology_bundle,
    screen_schedule_flood_risk,
    write_hydrology_mapping,
)
from ws4.io.hydrology_exposure import HydrologyExposure, load_hydrology_exposure
from ws4.io.hydrology_preflight import build_hydrology_preflight
from ws4.opt.flood import FloodRiskRefusalError, load_flood_screen_config

from test_hydrology_contract import (
    GENERATED_UTC,
    _bundle,
    _compiled_dataset,
    _complete_fragment_rows,
    _domain_payload,
    _exposure_surface_payload,
    _ledger_payload,
    _model_card_payload,
    _screen_risk_payload,
    _validation_evidence_payload,
    _write_crosswalk,
    _write_exposure,
    _write_metadata,
    _write_schedule,
)

runner = CliRunner()


@dataclass(frozen=True)
class IntegrationFixture:
    dataset: Path
    bundle: FemicHydrologyBundle
    crosswalk: Path
    metadata: Path
    mapping_manifest: Path
    schedule: Path
    exposure_path: Path
    exposure: HydrologyExposure


def _ready_validation() -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.validation.v1",
        "validation_id": "fixture-validation",
        "summary": {
            "tail_check_failures": {},
            "usable_fits": {"fixture-station": ["gev", "lp3"]},
            "full_process_pilot_ready": True,
            "hydrologist_review_recorded": True,
            "benchmark_cases": 1,
            "benchmark_passed": 1,
            "benchmark_failed": 0,
            "benchmark_not_evaluated": 0,
        },
    }


def _ready_card() -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.model_card.v1",
        "model_card_id": "fixture-card",
        "review_status": "reviewed",
        "validation_report_id": "fixture-validation",
        "validation_summary": {
            "tail_check_failures": {},
            "usable_fits": {"fixture-station": ["gev", "lp3"]},
            "full_process_pilot_ready": True,
            "hydrologist_review_recorded": True,
        },
    }


def _integration_fixture(
    root: Path,
    *,
    tail_failures: dict[str, list[str]] | None = None,
    crosswalk_review_status: str = "reviewed",
    crosswalk_rows: list[dict[str, object]] | None = None,
    mapping_allow_partial: bool = False,
    exposure_schedule_sha256: str | None = None,
) -> IntegrationFixture:
    dataset = _compiled_dataset(root / "dataset")
    validation = (
        _validation_evidence_payload(tail_failures=tail_failures)
        if tail_failures is not None
        else _ready_validation()
    )
    card = (
        _model_card_payload(tail_failures=tail_failures)
        if tail_failures is not None
        else _ready_card()
    )
    bundle = load_femic_hydrology_bundle(
        _bundle(
            root / "bundle",
            domain_payload=_domain_payload(),
            ledger_payload=_ledger_payload(),
            response_surface_payload=_exposure_surface_payload(),
            flood_risk_payload=_screen_risk_payload(),
            validation_report_payload=validation,
            model_card_payload=card,
        )
    )
    register_femic_hydrology_bundle(dataset, bundle.bundle_dir, registered_utc=GENERATED_UTC)
    crosswalk_path = _write_crosswalk(
        root / "crosswalk.csv",
        crosswalk_rows if crosswalk_rows is not None else _complete_fragment_rows(),
    )
    metadata = _write_metadata(
        root / "crosswalk.meta.json",
        crosswalk_sha256=hashlib.sha256(crosswalk_path.read_bytes()).hexdigest(),
        review_status=crosswalk_review_status,
    )
    crosswalk = load_hydrology_crosswalk(crosswalk_path, metadata_path=metadata)
    mapping = map_femic_hydrology_to_dataset(
        dataset,
        bundle,
        crosswalk,
        allow_partial=mapping_allow_partial,
        generated_utc=GENERATED_UTC,
    )
    mapping_paths = write_hydrology_mapping(mapping, root / "mapping")
    schedule = _write_schedule(root / "schedule.csv")
    exposure_path = _write_exposure(
        root / "exposure.json",
        schedule,
        road_used={
            ("watershed-1", 0): 1.0,
            ("watershed-1", 1): 2.0,
            ("watershed-2", 1): 1.0,
        },
        schedule_sha256=exposure_schedule_sha256,
    )
    exposure = load_hydrology_exposure(exposure_path)
    return IntegrationFixture(
        dataset=dataset,
        bundle=bundle,
        crosswalk=crosswalk_path,
        metadata=metadata,
        mapping_manifest=mapping_paths["manifest"],
        schedule=schedule,
        exposure_path=exposure_path,
        exposure=exposure,
    )


def test_end_to_end_cli_path_with_reviewed_exposure(tmp_path: Path) -> None:
    fixture = _integration_fixture(tmp_path)
    validated = runner.invoke(
        app,
        ["hydrology", "validate", str(fixture.bundle.bundle_dir), "--json"],
    )
    assert validated.exit_code == 0, validated.output
    assert json.loads(validated.output)["is_valid"] is True

    readiness = runner.invoke(
        app,
        ["hydrology", "readiness", "--dataset", str(fixture.dataset), "--json"],
    )
    assert readiness.exit_code == 0, readiness.output
    assert json.loads(readiness.output)["status"] == "ready"

    preflight = runner.invoke(
        app,
        [
            "hydrology",
            "preflight",
            "--dataset",
            str(fixture.dataset),
            "--crosswalk",
            str(fixture.crosswalk),
            "--metadata",
            str(fixture.metadata),
            "--policy",
            "require_reviewed",
            "--json",
        ],
    )
    assert preflight.exit_code == 0, preflight.output
    report = json.loads(preflight.output)
    assert report["screening_ready"] is True
    assert report["readiness"]["status"] == "ready"

    map_out = tmp_path / "cli-mapping"
    mapped = runner.invoke(
        app,
        [
            "hydrology",
            "map",
            "--dataset",
            str(fixture.dataset),
            "--crosswalk",
            str(fixture.crosswalk),
            "--metadata",
            str(fixture.metadata),
            "--out",
            str(map_out),
        ],
    )
    assert mapped.exit_code == 0, mapped.output

    screen_out = tmp_path / "cli-screen"
    screened = runner.invoke(
        app,
        [
            "hydrology",
            "screen",
            "--dataset",
            str(fixture.dataset),
            "--mapping",
            str(map_out / "hydrology_mapping.json"),
            "--schedule",
            str(fixture.schedule),
            "--exposure",
            str(fixture.exposure_path),
            "--out",
            str(screen_out),
        ],
    )
    assert screened.exit_code == 0, screened.output
    manifest = json.loads((screen_out / "hydrology_screen.json").read_text(encoding="utf-8"))
    assert manifest["exposure"]["exposure_id"] == "exposure-fixture-001"
    assert manifest["coverage"]["exposure_used"] is True
    rows = (screen_out / "hydrology_screen.csv").read_text(encoding="utf-8")
    assert "road_used_km" in rows
    assert "road_used_density_km_per_km2" in rows


def test_preflight_blocks_tail_check_failure(tmp_path: Path) -> None:
    fixture = _integration_fixture(
        tmp_path,
        tail_failures={"fixture-station": ["shape outside bounds"]},
    )
    result = build_hydrology_preflight(
        fixture.bundle,
        dataset_dir=fixture.dataset,
        crosswalk_path=fixture.crosswalk,
        crosswalk_metadata_path=fixture.metadata,
        policy="require_reviewed",
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is False
    assert result.readiness["status"] == "blocked"
    assert any("Readiness policy blocked" in reason for reason in result.blocking_reasons)


def test_preflight_blocks_unreviewed_crosswalk(tmp_path: Path) -> None:
    fixture = _integration_fixture(tmp_path, crosswalk_review_status="not_reviewed")
    result = build_hydrology_preflight(
        fixture.bundle,
        dataset_dir=fixture.dataset,
        crosswalk_path=fixture.crosswalk,
        crosswalk_metadata_path=fixture.metadata,
        policy="require_reviewed",
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is False
    assert any("Crosswalk review status" in reason for reason in result.blocking_reasons)


def test_preflight_blocks_partial_mapping(tmp_path: Path) -> None:
    fixture = _integration_fixture(
        tmp_path,
        crosswalk_rows=_complete_fragment_rows()[:3],
        mapping_allow_partial=True,
    )
    result = build_hydrology_preflight(
        fixture.bundle,
        dataset_dir=fixture.dataset,
        crosswalk_path=fixture.crosswalk,
        crosswalk_metadata_path=fixture.metadata,
        policy="require_reviewed",
        allow_partial=True,
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is False
    assert any("Mapping is incomplete" in reason for reason in result.blocking_reasons)


def test_screen_refuses_without_required_exposure(tmp_path: Path) -> None:
    fixture = _integration_fixture(tmp_path)
    mapping = load_hydrology_mapping(fixture.mapping_manifest)
    screen = screen_schedule_flood_risk(
        fixture.dataset,
        fixture.bundle,
        mapping,
        fixture.schedule,
        allow_refused=True,
        generated_utc=GENERATED_UTC,
    )

    assert screen.rows == ()
    assert any("feature tolerance" in str(item["reason"]) for item in screen.refusals)


def test_screen_refuses_exposure_schedule_mismatch(tmp_path: Path) -> None:
    fixture = _integration_fixture(
        tmp_path,
        exposure_schedule_sha256="b" * 64,
    )
    mapping = load_hydrology_mapping(fixture.mapping_manifest)

    with pytest.raises(FemicHydrologyError, match="schedule hash"):
        screen_schedule_flood_risk(
            fixture.dataset,
            fixture.bundle,
            mapping,
            fixture.schedule,
            exposure=fixture.exposure,
        )


def test_optimizer_refuses_exposure_config(tmp_path: Path) -> None:
    fixture = _integration_fixture(tmp_path)
    config = tmp_path / "flood.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "ws4.hydrology.flood_screen.v1",
                "mapping": str(fixture.mapping_manifest),
                "covariates": {},
                "scenario_tolerance": 0.05,
                "refusal_penalty": 1e12,
                "readiness_policy": "require_reviewed",
                "allow_tail_failures": False,
                "exposure": str(fixture.exposure_path),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FloodRiskRefusalError, match="schedule-derived exposure"):
        load_flood_screen_config(config)
