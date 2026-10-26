from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner
from ws4.cli import app
from ws4.io.hydrology import (
    FemicHydrologyBundle,
    FemicHydrologyError,
    load_femic_hydrology_bundle,
    load_registered_femic_hydrology_bundle,
    register_femic_hydrology_bundle,
)
from ws4.io.hydrology_preflight import (
    HYDROLOGY_PREFLIGHT_SCHEMA,
    build_hydrology_preflight,
)

from test_hydrology_contract import (
    GENERATED_UTC,
    _bundle,
    _compiled_dataset,
    _complete_fragment_rows,
    _domain_payload,
    _ledger_payload,
    _write_crosswalk,
    _write_metadata,
)

runner = CliRunner()


def _validation_payload() -> dict[str, object]:
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


def _model_card_payload(review_status: str = "reviewed") -> dict[str, object]:
    return {
        "schema_version": "femic.hydrology.model_card.v1",
        "model_card_id": "fixture-card",
        "review_status": review_status,
        "validation_report_id": "fixture-validation",
        "validation_summary": {
            "tail_check_failures": {},
            "usable_fits": {"fixture-station": ["gev", "lp3"]},
            "full_process_pilot_ready": True,
            "hydrologist_review_recorded": True,
        },
    }


def _ready_fixture(
    root: Path,
    *,
    rows: list[dict[str, object]] | None = None,
    review_status: str = "reviewed",
    card_review_status: str = "reviewed",
) -> tuple[Path, Path, Path]:
    dataset = _compiled_dataset(root / "dataset")
    bundle_root = root / "bundle"
    _bundle(
        bundle_root,
        domain_payload=_domain_payload(),
        ledger_payload=_ledger_payload(),
        validation_report_payload=_validation_payload(),
        model_card_payload=_model_card_payload(card_review_status),
    )
    bundle = load_femic_hydrology_bundle(bundle_root)
    register_femic_hydrology_bundle(
        dataset,
        bundle.bundle_dir,
        registered_utc=GENERATED_UTC,
    )
    crosswalk = _write_crosswalk(
        root / "crosswalk.csv",
        rows if rows is not None else _complete_fragment_rows(),
    )
    metadata = _write_metadata(
        root / "crosswalk.meta.json",
        crosswalk_sha256=hashlib.sha256(crosswalk.read_bytes()).hexdigest(),
        review_status=review_status,
    )
    return dataset, crosswalk, metadata


def _bundle_from_dataset(dataset: Path) -> FemicHydrologyBundle:
    return load_registered_femic_hydrology_bundle(dataset)


def test_preflight_ready_with_reviewed_bundle_and_crosswalk(tmp_path: Path) -> None:
    dataset, crosswalk, metadata = _ready_fixture(tmp_path)
    bundle = _bundle_from_dataset(dataset)

    result = build_hydrology_preflight(
        bundle,
        dataset_dir=dataset,
        crosswalk_path=crosswalk,
        crosswalk_metadata_path=metadata,
        policy="require_reviewed",
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is True
    assert result.blocking_reasons == ()
    assert result.readiness["status"] == "ready"
    assert result.mapping is not None
    assert result.mapping["review_status"] == "reviewed"
    coverage = result.mapping.get("coverage")
    assert isinstance(coverage, dict)
    assert coverage["unmapped_fragments"] == []
    assert result.to_dict()["schema_version"] == HYDROLOGY_PREFLIGHT_SCHEMA


def test_preflight_blocks_unreviewed_crosswalk_under_require_reviewed(tmp_path: Path) -> None:
    dataset, crosswalk, metadata = _ready_fixture(tmp_path, review_status="not_reviewed")
    bundle = _bundle_from_dataset(dataset)

    result = build_hydrology_preflight(
        bundle,
        dataset_dir=dataset,
        crosswalk_path=crosswalk,
        crosswalk_metadata_path=metadata,
        policy="require_reviewed",
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is False
    assert any("Crosswalk review status" in reason for reason in result.blocking_reasons)
    assert result.mapping is not None
    assert result.mapping["review_status"] == "not_reviewed"


def test_preflight_blocks_provisional_readiness_under_require_reviewed(tmp_path: Path) -> None:
    dataset, crosswalk, metadata = _ready_fixture(tmp_path, card_review_status="not_reviewed")
    bundle = _bundle_from_dataset(dataset)

    result = build_hydrology_preflight(
        bundle,
        dataset_dir=dataset,
        crosswalk_path=crosswalk,
        crosswalk_metadata_path=metadata,
        policy="require_reviewed",
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is False
    assert result.readiness["status"] == "provisional"
    assert any("Readiness policy blocked" in reason for reason in result.blocking_reasons)


def test_preflight_blocks_conditionally_ready_under_require_ready(tmp_path: Path) -> None:
    dataset, crosswalk, metadata = _ready_fixture(
        tmp_path,
        card_review_status="reviewed_with_conditions",
    )
    bundle = _bundle_from_dataset(dataset)

    result = build_hydrology_preflight(
        bundle,
        dataset_dir=dataset,
        crosswalk_path=crosswalk,
        crosswalk_metadata_path=metadata,
        policy="require_ready",
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is False
    assert result.readiness["status"] == "conditionally_ready"
    assert any("Readiness policy blocked" in reason for reason in result.blocking_reasons)


def test_preflight_blocks_incomplete_mapping_even_with_partial_allowed(tmp_path: Path) -> None:
    dataset, crosswalk, metadata = _ready_fixture(
        tmp_path,
        rows=[_complete_fragment_rows()[0]],
    )
    bundle = _bundle_from_dataset(dataset)

    result = build_hydrology_preflight(
        bundle,
        dataset_dir=dataset,
        crosswalk_path=crosswalk,
        crosswalk_metadata_path=metadata,
        policy="require_reviewed",
        allow_partial=True,
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is False
    assert result.mapping is not None
    coverage = result.mapping.get("coverage")
    assert isinstance(coverage, dict)
    assert coverage["unmapped_fragments"] == [2, 3, 4]
    assert any("Mapping is incomplete" in reason for reason in result.blocking_reasons)


def test_preflight_blocks_without_a_crosswalk(tmp_path: Path) -> None:
    dataset, _crosswalk, _metadata = _ready_fixture(tmp_path)
    bundle = _bundle_from_dataset(dataset)

    result = build_hydrology_preflight(
        bundle,
        policy="require_reviewed",
        generated_utc=GENERATED_UTC,
    )

    assert result.screening_ready is False
    assert result.mapping is None
    assert any("No explicit crosswalk" in reason for reason in result.blocking_reasons)


def test_preflight_rejects_crosswalk_without_dataset(tmp_path: Path) -> None:
    dataset, crosswalk, metadata = _ready_fixture(tmp_path)
    bundle = _bundle_from_dataset(dataset)

    with pytest.raises(FemicHydrologyError, match="requires a compiled dataset"):
        build_hydrology_preflight(
            bundle,
            crosswalk_path=crosswalk,
            crosswalk_metadata_path=metadata,
        )


def test_cli_preflight_json_ready_and_blocked(tmp_path: Path) -> None:
    dataset, crosswalk, metadata = _ready_fixture(tmp_path)
    ready = runner.invoke(
        app,
        [
            "hydrology",
            "preflight",
            "--dataset",
            str(dataset),
            "--crosswalk",
            str(crosswalk),
            "--metadata",
            str(metadata),
            "--policy",
            "require_reviewed",
            "--json",
        ],
    )
    assert ready.exit_code == 0, ready.output
    payload = json.loads(ready.output)
    assert payload["screening_ready"] is True
    assert payload["schema_version"] == HYDROLOGY_PREFLIGHT_SCHEMA

    blocked_dataset, blocked_crosswalk, blocked_metadata = _ready_fixture(
        tmp_path / "blocked",
        review_status="not_reviewed",
    )
    blocked = runner.invoke(
        app,
        [
            "hydrology",
            "preflight",
            "--dataset",
            str(blocked_dataset),
            "--crosswalk",
            str(blocked_crosswalk),
            "--metadata",
            str(blocked_metadata),
            "--policy",
            "require_reviewed",
            "--json",
        ],
    )
    assert blocked.exit_code == 1, blocked.output
    blocked_payload = json.loads(blocked.output)
    assert blocked_payload["screening_ready"] is False
    assert blocked_payload["blocking_reasons"]


def test_cli_preflight_requires_exactly_one_bundle_or_dataset(tmp_path: Path) -> None:
    neither = runner.invoke(app, ["hydrology", "preflight"])
    assert neither.exit_code == 1
    assert "exactly one" in neither.output
