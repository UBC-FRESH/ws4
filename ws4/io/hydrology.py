"""Read and validate FEMIC hydrology response bundles.

WS4 consumes the FEMIC producer contract. This module pins a response bundle,
verifies its manifest and artifact checksums, and exposes the response-surface
and flood-risk records without re-running FEMIC discovery, frequency fitting,
or surrogate training.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ws4.model.schema import load_manifest

from .hydrology_exposure import (
    HYDROLOGY_EXPOSURE_DERIVED_FEATURES,
    HYDROLOGY_EXPOSURE_FEATURES,
    HydrologyExposure,
)

FEMIC_HYDROLOGY_MANIFEST_SCHEMA = "femic.hydrology.response.v1"
FEMIC_HYDROLOGY_MANIFEST_NAME = "manifest.json"
FEMIC_HYDROLOGY_SIDECAR_NAME = "hydrology_products.json"
FEMIC_HYDROLOGY_METADATA_KEY = "hydrology_products"
HYDROLOGY_CROSSWALK_SCHEMA = "ws4.hydrology.crosswalk.v1"
HYDROLOGY_MAPPING_SCHEMA = "ws4.hydrology.mapping.v1"
HYDROLOGY_SCREEN_SCHEMA = "ws4.hydrology.screen.v1"
HYDROLOGY_READINESS_STATUSES: tuple[str, ...] = (
    "not_available",
    "provisional",
    "conditionally_ready",
    "ready",
    "blocked",
)
FEMIC_MODEL_CARD_REVIEW_STATUSES: tuple[str, ...] = (
    "not_reviewed",
    "review_pending",
    "reviewed",
    "reviewed_with_conditions",
)
HYDROLOGY_READINESS_POLICIES: tuple[str, ...] = (
    "allow_provisional",
    "require_reviewed",
    "require_ready",
)
HYDROLOGY_CROSSWALK_REVIEW_STATUSES: tuple[str, ...] = (
    "not_reviewed",
    "review_pending",
    "reviewed",
)
FEMIC_HYDROLOGY_RESPONSE_SURFACE_SCHEMA = "femic.hydrology.flood_response.v1"
FEMIC_HYDROLOGY_FLOOD_RISK_SCHEMA = "femic.hydrology.flood_risk.v1"
FEMIC_HYDROLOGY_DOMAIN_SCHEMA = "femic.hydrology.domain.v1"
FEMIC_HYDROLOGY_DISTURBANCE_SCHEMA = "femic.hydrology.disturbance.v1"
FEMIC_HYDROLOGY_SURROGATE_MODEL_SCHEMA = "femic.hydrology.surrogate_model.v1"
FEMIC_HYDROLOGY_VALIDATION_SCHEMA = "femic.hydrology.validation.v1"
FEMIC_HYDROLOGY_MODEL_CARD_SCHEMA = "femic.hydrology.model_card.v1"
FEMIC_HYDROLOGY_PILOT_SCHEMA = "femic.hydrology.pilot.v1"
FEMIC_HYDROLOGY_REQUIRED_ROLES: tuple[str, ...] = (
    "response_surface",
    "flood_risk",
    "domain",
    "disturbance_ledger",
)
FEMIC_HYDROLOGY_OPTIONAL_ROLES: tuple[str, ...] = (
    "surrogate_model",
    "surrogate_validation",
    "frequency_fit",
    "frequency_pairing",
    "tier0_screening",
    "benchmark_check",
    "validation_report",
    "model_card",
    "pilot_run",
)
FEMIC_HYDROLOGY_ROLE_SCHEMAS: dict[str, str] = {
    "response_surface": FEMIC_HYDROLOGY_RESPONSE_SURFACE_SCHEMA,
    "flood_risk": FEMIC_HYDROLOGY_FLOOD_RISK_SCHEMA,
    "domain": FEMIC_HYDROLOGY_DOMAIN_SCHEMA,
    "disturbance_ledger": FEMIC_HYDROLOGY_DISTURBANCE_SCHEMA,
    "surrogate_model": FEMIC_HYDROLOGY_SURROGATE_MODEL_SCHEMA,
    "frequency_fit": "femic.hydrology.flood_frequency.v1",
    "tier0_screening": "femic.hydrology.screening.v1",
    "validation_report": FEMIC_HYDROLOGY_VALIDATION_SCHEMA,
    "model_card": FEMIC_HYDROLOGY_MODEL_CARD_SCHEMA,
    "pilot_run": FEMIC_HYDROLOGY_PILOT_SCHEMA,
}
FEMIC_HYDROLOGY_CONSUMER_CONTRACT_KEYS: tuple[str, ...] = (
    "manifest_path",
    "read_order",
    "pin_rule",
    "applicability_rule",
    "native_units_rule",
    "consumer_phases",
)
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class FemicHydrologyError(RuntimeError):
    """Raised when a FEMIC hydrology bundle cannot be consumed."""


@dataclass(frozen=True)
class FemicHydrologyArtifact:
    """One pinned manifest artifact.

    Attributes
    ----------
    role : str
        Producer artifact role.
    relative_path : str
        Path to the artifact relative to the bundle root.
    schema_version : str | None
        Artifact schema recorded by the producer.
    media_type : str
        Artifact media type.
    size_bytes : int
        Artifact size in bytes.
    sha256 : str
        Artifact SHA-256 digest.
    description : str
        Producer description.
    """

    role: str
    relative_path: str
    schema_version: str | None
    media_type: str
    size_bytes: int
    sha256: str
    description: str


@dataclass(frozen=True)
class FemicFloodRiskRow:
    """One receptor/return-period flood-risk row.

    Attributes
    ----------
    receptor_id : str
        FEMIC receptor identifier.
    watershed_id : str
        FEMIC watershed identifier.
    return_period : float
        Return period in years.
    baseline_peak_flow_m3s : float
        Baseline peak flow in cubic metres per second.
    scenario_peak_flow_m3s : float
        Scenario peak flow in cubic metres per second.
    ratio : float
        Scenario/baseline peak-flow ratio.
    exceedance_probability : float | None
        Optional probability of exceeding a receptor threshold.
    expected_annual_damage : float | None
        Optional expected annual damage in producer units.
    """

    receptor_id: str
    watershed_id: str
    return_period: float
    baseline_peak_flow_m3s: float
    scenario_peak_flow_m3s: float
    ratio: float
    exceedance_probability: float | None
    expected_annual_damage: float | None


@dataclass(frozen=True)
class FemicFloodRiskTable:
    """Pinned FEMIC flood-risk table.

    Attributes
    ----------
    table_id : str
        Producer table identifier.
    generated_utc : str
        Producer generation timestamp.
    source_surface_id : str
        Response-surface identifier linked by the table.
    baseline_name : str
        Producer baseline scenario name.
    rows : tuple[FemicFloodRiskRow, ...]
        Receptor/return-period rows.
    caveats : tuple[str, ...]
        Producer caveats.
    schema_version : str
        Flood-risk schema.
    """

    table_id: str
    generated_utc: str
    source_surface_id: str
    baseline_name: str
    rows: tuple[FemicFloodRiskRow, ...]
    caveats: tuple[str, ...]
    schema_version: str


@dataclass(frozen=True)
class FemicHydrologyBundle:
    """Validated FEMIC hydrology response bundle.

    Attributes
    ----------
    bundle_dir : Path
        Resolved bundle root.
    manifest_path : Path
        Validated manifest path.
    bundle_id : str
        Producer bundle identifier.
    bundle_name : str
        Producer bundle name.
    bundle_version : str
        Producer bundle version.
    generated_utc : str
        Producer generation timestamp.
    domain_id : str
        FEMIC domain identifier.
    ledger_id : str
        FEMIC disturbance-ledger identifier.
    response_surface_id : str
        Response-surface identifier.
    artifacts : dict[str, FemicHydrologyArtifact]
        Artifact records keyed by role.
    response_surface : dict[str, object]
        Producer response-surface summary.
    flood_risk : dict[str, object]
        Producer flood-risk summary.
    applicability_domain : dict[str, object]
        Producer applicability domain.
    uncertainty : dict[str, object]
        Producer uncertainty metadata.
    consumer_contract : dict[str, object]
        Producer consumer contract.
    caveats : tuple[str, ...]
        Producer caveats.
    provenance : dict[str, object]
        Producer provenance.
    manifest_sha256 : str
        SHA-256 digest of the manifest bytes.
    total_bytes : int
        Total size of pinned artifacts.
    """

    bundle_dir: Path
    manifest_path: Path
    bundle_id: str
    bundle_name: str
    bundle_version: str
    generated_utc: str
    domain_id: str
    ledger_id: str
    response_surface_id: str
    artifacts: dict[str, FemicHydrologyArtifact]
    response_surface: dict[str, object]
    flood_risk: dict[str, object]
    applicability_domain: dict[str, object]
    uncertainty: dict[str, object]
    consumer_contract: dict[str, object]
    caveats: tuple[str, ...]
    provenance: dict[str, object]
    manifest_sha256: str
    total_bytes: int


@dataclass(frozen=True)
class FemicHydrologyValidation:
    """Validation report for a FEMIC hydrology response bundle.

    Attributes
    ----------
    bundle_dir : Path
        Resolved bundle root.
    is_valid : bool
        Whether the bundle passed every contract check.
    checked_utc : str
        UTC timestamp of the check.
    errors : tuple[str, ...]
        Contract errors that invalidate the bundle.
    warnings : tuple[str, ...]
        Non-fatal observations.
    artifact_count : int
        Number of pinned artifacts examined.
    total_bytes : int
        Total size of pinned artifacts.
    """

    bundle_dir: Path
    is_valid: bool
    checked_utc: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    artifact_count: int
    total_bytes: int

    def to_dict(self) -> dict[str, object]:
        """Return the validation report as a JSON-serializable mapping.

        Returns
        -------
        dict[str, object]
            JSON-serializable validation report.
        """
        return {
            "bundle_dir": str(self.bundle_dir),
            "is_valid": self.is_valid,
            "checked_utc": self.checked_utc,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "artifact_count": self.artifact_count,
            "total_bytes": self.total_bytes,
        }


def load_femic_hydrology_bundle(
    bundle_path: Path,
    *,
    expected_bundle_id: str | None = None,
    expected_bundle_version: str | None = None,
) -> FemicHydrologyBundle:
    """Load and validate a FEMIC hydrology response bundle.

    Parameters
    ----------
    bundle_path : Path
        Bundle directory or manifest path.
    expected_bundle_id : str | None, optional
        Required producer bundle identifier.
    expected_bundle_version : str | None, optional
        Required producer bundle version.

    Returns
    -------
    FemicHydrologyBundle
        Validated bundle metadata and pinned artifacts.

    Raises
    ------
    FemicHydrologyError
        If the bundle is invalid or does not match the expected pin.
    """
    report, bundle = _validate(
        bundle_path,
        expected_bundle_id=expected_bundle_id,
        expected_bundle_version=expected_bundle_version,
    )
    if bundle is None or not report.is_valid:
        raise FemicHydrologyError("; ".join(report.errors))
    return bundle


def validate_femic_hydrology_bundle(
    bundle_path: Path,
    *,
    expected_bundle_id: str | None = None,
    expected_bundle_version: str | None = None,
) -> FemicHydrologyValidation:
    """Validate a FEMIC hydrology response bundle without raising.

    Parameters
    ----------
    bundle_path : Path
        Bundle directory or manifest path.
    expected_bundle_id : str | None, optional
        Required producer bundle identifier.
    expected_bundle_version : str | None, optional
        Required producer bundle version.

    Returns
    -------
    FemicHydrologyValidation
        Validation report with specific errors and warnings.
    """
    report, _ = _validate(
        bundle_path,
        expected_bundle_id=expected_bundle_id,
        expected_bundle_version=expected_bundle_version,
    )
    return report


def bundle_pin(bundle: FemicHydrologyBundle) -> dict[str, object]:
    """Return the stable downstream pin for a validated bundle.

    Parameters
    ----------
    bundle : FemicHydrologyBundle
        Validated bundle.

    Returns
    -------
    dict[str, object]
        Bundle identity, manifest digest, artifact checksums, and preserved
        producer metadata.
    """
    return {
        "bundle_id": bundle.bundle_id,
        "bundle_version": bundle.bundle_version,
        "manifest_sha256": bundle.manifest_sha256,
        "domain_id": bundle.domain_id,
        "ledger_id": bundle.ledger_id,
        "response_surface_id": bundle.response_surface_id,
        "artifacts": {
            role: {
                "relative_path": artifact.relative_path,
                "schema_version": artifact.schema_version,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for role, artifact in sorted(bundle.artifacts.items())
        },
        "applicability_domain": bundle.applicability_domain,
        "uncertainty": bundle.uncertainty,
        "consumer_contract": bundle.consumer_contract,
        "caveats": list(bundle.caveats),
    }


@dataclass(frozen=True)
class HydrologyCrosswalkMetadata:
    """Review metadata for an explicit WS4-to-FEMIC crosswalk.

    Attributes
    ----------
    crosswalk_id : str
        Stable crosswalk identifier.
    created_utc : str
        Crosswalk creation timestamp.
    review_status : str
        One of ``not_reviewed``, ``review_pending``, or ``reviewed``.
    reviewed_by : str | None
        Reviewer identifier when reviewed.
    method : str
        Crosswalk method or source.
    source : str
        Source document or process.
    caveats : tuple[str, ...]
        Review caveats.
    """

    crosswalk_id: str
    created_utc: str
    review_status: str
    reviewed_by: str | None
    method: str
    source: str
    caveats: tuple[str, ...]


@dataclass(frozen=True)
class HydrologyCrosswalkRow:
    """One explicit fragment/block to FEMIC unit mapping.

    Attributes
    ----------
    fragment_id : int | None
        WS4 fragment identifier, when the row is fragment-level.
    block_id : int | None
        WS4 block identifier, when the row is block-level.
    unit_id : str
        FEMIC disturbance-ledger unit identifier.
    watershed_id : str
        FEMIC watershed identifier.
    receptor_id : str | None
        Optional FEMIC flood-risk receptor identifier.
    notes : str
        Human review notes.
    """

    fragment_id: int | None
    block_id: int | None
    unit_id: str
    watershed_id: str
    receptor_id: str | None
    notes: str


@dataclass(frozen=True)
class HydrologyCrosswalk:
    """Loaded and checksummed explicit crosswalk.

    Attributes
    ----------
    path : Path
        Crosswalk CSV path.
    sha256 : str
        SHA-256 digest of the CSV bytes.
    rows : tuple[HydrologyCrosswalkRow, ...]
        Explicit mapping rows.
    metadata : HydrologyCrosswalkMetadata
        Review metadata.
    """

    path: Path
    sha256: str
    rows: tuple[HydrologyCrosswalkRow, ...]
    metadata: HydrologyCrosswalkMetadata


@dataclass(frozen=True)
class FemicHydrologyReadiness:
    """Reported validation evidence for a pinned hydrology bundle.

    Attributes
    ----------
    bundle_id : str
        FEMIC bundle identifier.
    bundle_version : str
        FEMIC bundle version.
    manifest_sha256 : str
        Bundle manifest digest.
    status : str
        ``not_available``, ``provisional``, ``conditionally_ready``, ``ready``,
        or ``blocked``.
    validation_report_id : str | None
        Validation report identifier, when packaged.
    model_card_id : str | None
        Model card identifier, when packaged.
    review_status : str | None
        Producer model-card review status.
    full_process_pilot_ready : bool | None
        Producer full-pilot readiness flag.
    hydrologist_review_recorded : bool | None
        Producer review-record flag.
    tail_check_failures : dict[str, list[str]]
        Tail-check failures keyed by gauge/station.
    usable_fits : dict[str, list[str]]
        Usable fit methods keyed by gauge/station.
    benchmark_cases : int
        Number of published benchmark cases.
    benchmark_passed : int
        Passed benchmark count.
    benchmark_failed : int
        Failed benchmark count.
    benchmark_not_evaluated : int
        Not-evaluated benchmark count.
    warnings : tuple[str, ...]
        Non-fatal evidence warnings.
    caveats : tuple[str, ...]
        Evidence caveats.
    evidence_sha256 : str
        Deterministic digest of the evidence record.
    """

    bundle_id: str
    bundle_version: str
    manifest_sha256: str
    status: str
    validation_report_id: str | None
    model_card_id: str | None
    review_status: str | None
    full_process_pilot_ready: bool | None
    hydrologist_review_recorded: bool | None
    tail_check_failures: dict[str, list[str]]
    usable_fits: dict[str, list[str]]
    benchmark_cases: int
    benchmark_passed: int
    benchmark_failed: int
    benchmark_not_evaluated: int
    warnings: tuple[str, ...]
    caveats: tuple[str, ...]
    evidence_sha256: str

    def to_dict(self) -> dict[str, object]:
        """Return the readiness report as a JSON-serializable mapping.

        Returns
        -------
        dict[str, object]
            Evidence identity, status, failures, fits, benchmarks, and caveats.
        """
        return {
            "bundle_id": self.bundle_id,
            "bundle_version": self.bundle_version,
            "manifest_sha256": self.manifest_sha256,
            "status": self.status,
            "validation_report_id": self.validation_report_id,
            "model_card_id": self.model_card_id,
            "review_status": self.review_status,
            "full_process_pilot_ready": self.full_process_pilot_ready,
            "hydrologist_review_recorded": self.hydrologist_review_recorded,
            "tail_check_failures": self.tail_check_failures,
            "usable_fits": self.usable_fits,
            "benchmark_cases": self.benchmark_cases,
            "benchmark_passed": self.benchmark_passed,
            "benchmark_failed": self.benchmark_failed,
            "benchmark_not_evaluated": self.benchmark_not_evaluated,
            "warnings": list(self.warnings),
            "caveats": list(self.caveats),
            "evidence_sha256": self.evidence_sha256,
        }


def assess_femic_hydrology_readiness(
    bundle: FemicHydrologyBundle,
) -> FemicHydrologyReadiness:
    """Read validation-report and model-card evidence from a bundle.

    Parameters
    ----------
    bundle : FemicHydrologyBundle
        Validated hydrology bundle.

    Returns
    -------
    FemicHydrologyReadiness
        Review, tail-check, fit, and benchmark evidence. Missing evidence is
        reported explicitly; it is never treated as approval.

    Raises
    ------
    FemicHydrologyError
        If a packaged evidence artifact is malformed.
    """
    validation = _optional_bundle_payload(bundle, "validation_report")
    card = _optional_bundle_payload(bundle, "model_card")
    warnings: list[str] = []
    validation_id: str | None = None
    card_id: str | None = None
    review_status: str | None = None
    full_process_ready: bool | None = None
    review_recorded: bool | None = None
    tail_failures: dict[str, list[str]] = {}
    usable_fits: dict[str, list[str]] = {}
    benchmark_cases = 0
    benchmark_passed = 0
    benchmark_failed = 0
    benchmark_not_evaluated = 0
    if validation is None:
        warnings.append("No validation_report artifact is packaged.")
    else:
        if validation.get("schema_version") != "femic.hydrology.validation.v1":
            raise FemicHydrologyError("Unsupported validation_report schema.")
        validation_id = _text(validation.get("validation_id"), "validation_id")
        summary = _mapping(validation.get("summary"), "validation summary", [])
        tail_failures = _failure_map(
            summary.get("tail_check_failures"),
            "validation tail_check_failures",
        )
        usable_fits = _fit_map(summary.get("usable_fits"), "validation usable_fits")
        full_process_ready = _optional_bool(
            summary.get("full_process_pilot_ready"),
            "validation full_process_pilot_ready",
        )
        review_recorded = _optional_bool(
            summary.get("hydrologist_review_recorded"),
            "validation hydrologist_review_recorded",
        )
        benchmark_cases = (
            _evidence_int(
                summary.get("benchmark_cases"),
                "validation benchmark_cases",
            )
            or 0
        )
        benchmark_passed = (
            _evidence_int(
                summary.get("benchmark_passed"),
                "validation benchmark_passed",
            )
            or 0
        )
        benchmark_failed = (
            _evidence_int(
                summary.get("benchmark_failed"),
                "validation benchmark_failed",
            )
            or 0
        )
        benchmark_not_evaluated = (
            _evidence_int(
                summary.get("benchmark_not_evaluated"),
                "validation benchmark_not_evaluated",
            )
            or 0
        )
        if benchmark_not_evaluated:
            warnings.append(
                f"{benchmark_not_evaluated} published benchmark case(s) are not evaluated."
            )
    if card is None:
        warnings.append("No model_card artifact is packaged.")
    else:
        if card.get("schema_version") != "femic.hydrology.model_card.v1":
            raise FemicHydrologyError("Unsupported model_card schema.")
        card_id = _text(card.get("model_card_id"), "model_card_id")
        review_status = _text(card.get("review_status"), "model_card review_status")
        if review_status not in FEMIC_MODEL_CARD_REVIEW_STATUSES:
            raise FemicHydrologyError(f"Unsupported model card review status {review_status!r}.")
        summary = _mapping(card.get("validation_summary"), "model_card summary", [])
        card_failures = _failure_map(
            summary.get("tail_check_failures"),
            "model_card tail_check_failures",
        )
        if card_failures:
            tail_failures = card_failures
        card_fits = _fit_map(summary.get("usable_fits"), "model_card usable_fits")
        if card_fits:
            usable_fits = card_fits
        card_full = _optional_bool(
            summary.get("full_process_pilot_ready"),
            "model_card full_process_pilot_ready",
        )
        if card_full is not None:
            full_process_ready = card_full
        card_review = _optional_bool(
            summary.get("hydrologist_review_recorded"),
            "model_card hydrologist_review_recorded",
        )
        if card_review is not None:
            review_recorded = card_review
        if validation_id is not None:
            linked = _optional_text(card.get("validation_report_id"))
            if linked is not None and linked != validation_id:
                raise FemicHydrologyError(
                    "Model card validation_report_id does not match the report."
                )
    if tail_failures:
        warnings.append("Tail-check failures are recorded and must not be used silently.")
    if review_status is not None and review_status != "reviewed":
        warnings.append(f"Model card review status is {review_status!r}.")
    if validation is None and card is None:
        status = "not_available"
    elif tail_failures:
        status = "blocked"
    elif review_status == "reviewed" and review_recorded:
        status = "ready"
    elif review_status == "reviewed_with_conditions":
        status = "conditionally_ready"
    else:
        status = "provisional"
    caveats = (
        "Readiness reports producer evidence; it does not create a hydrologist review.",
        "A structural bundle/checksum pass is not hydrologic validation.",
    )
    evidence = {
        "bundle_id": bundle.bundle_id,
        "bundle_version": bundle.bundle_version,
        "manifest_sha256": bundle.manifest_sha256,
        "validation_report_id": validation_id,
        "model_card_id": card_id,
        "review_status": review_status,
        "full_process_pilot_ready": full_process_ready,
        "hydrologist_review_recorded": review_recorded,
        "tail_check_failures": tail_failures,
        "usable_fits": usable_fits,
        "benchmark_cases": benchmark_cases,
        "benchmark_passed": benchmark_passed,
        "benchmark_failed": benchmark_failed,
        "benchmark_not_evaluated": benchmark_not_evaluated,
        "status": status,
    }
    digest = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return FemicHydrologyReadiness(
        bundle_id=bundle.bundle_id,
        bundle_version=bundle.bundle_version,
        manifest_sha256=bundle.manifest_sha256,
        status=status,
        validation_report_id=validation_id,
        model_card_id=card_id,
        review_status=review_status,
        full_process_pilot_ready=full_process_ready,
        hydrologist_review_recorded=review_recorded,
        tail_check_failures=tail_failures,
        usable_fits=usable_fits,
        benchmark_cases=benchmark_cases,
        benchmark_passed=benchmark_passed,
        benchmark_failed=benchmark_failed,
        benchmark_not_evaluated=benchmark_not_evaluated,
        warnings=tuple(warnings),
        caveats=caveats,
        evidence_sha256=f"hydro-evidence-{digest[:16]}",
    )


def enforce_hydrology_readiness(
    readiness: FemicHydrologyReadiness,
    *,
    policy: str = "allow_provisional",
    allow_tail_failures: bool = False,
) -> None:
    """Enforce a readiness policy for screening or optimization.

    Parameters
    ----------
    readiness : FemicHydrologyReadiness
        Evidence report.
    policy : str, optional
        ``allow_provisional`` (default), ``require_reviewed``, or
        ``require_ready``.
    allow_tail_failures : bool, optional
        Permit a tail-check block only under ``allow_provisional``. This is an
        explicit risk acceptance, not a claim that the fit is safe.

    Raises
    ------
    FemicHydrologyError
        If the evidence does not satisfy the policy.
    """
    if policy not in HYDROLOGY_READINESS_POLICIES:
        raise FemicHydrologyError(f"Unsupported readiness policy {policy!r}.")
    if readiness.status == "blocked":
        if not allow_tail_failures or policy != "allow_provisional":
            raise FemicHydrologyError(
                "Tail-check failures block hydrology use; an explicit "
                "allow_tail_failures override under allow_provisional is required."
            )
        return
    if policy == "allow_provisional":
        return
    if policy == "require_reviewed":
        if readiness.status not in ("ready", "conditionally_ready"):
            raise FemicHydrologyError(f"Readiness status {readiness.status!r} is not reviewed.")
        return
    if policy == "require_ready" and readiness.status != "ready":
        raise FemicHydrologyError(f"Readiness status {readiness.status!r} is not fully ready.")


@dataclass(frozen=True)
class HydrologyMapping:
    """Validated WS4-to-FEMIC mapping.

    Attributes
    ----------
    mapping_id : str
        Deterministic mapping identifier.
    generated_utc : str
        Mapping generation timestamp.
    bundle_id : str
        FEMIC bundle identifier.
    bundle_version : str
        FEMIC bundle version.
    manifest_sha256 : str
        FEMIC manifest digest.
    crosswalk_id : str
        Crosswalk metadata identifier.
    crosswalk_sha256 : str
        Crosswalk CSV digest.
    review_status : str
        Crosswalk review status.
    fragments : tuple[dict[str, object], ...]
        Fragment mapping rows.
    blocks : tuple[dict[str, object], ...]
        Block mapping rows.
    coverage : dict[str, object]
        Dataset/mapped/unmapped counts and IDs.
    warnings : tuple[str, ...]
        Non-fatal mapping observations.
    caveats : tuple[str, ...]
        Mapping and review caveats.
    """

    mapping_id: str
    generated_utc: str
    bundle_id: str
    bundle_version: str
    manifest_sha256: str
    crosswalk_id: str
    crosswalk_sha256: str
    review_status: str
    fragments: tuple[dict[str, object], ...]
    blocks: tuple[dict[str, object], ...]
    coverage: dict[str, object]
    warnings: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the mapping manifest as a JSON-serializable mapping.

        Returns
        -------
        dict[str, object]
            Mapping identity, provenance, coverage, warnings, and caveats.
        """
        return {
            "schema_version": HYDROLOGY_MAPPING_SCHEMA,
            "mapping_id": self.mapping_id,
            "generated_utc": self.generated_utc,
            "bundle_id": self.bundle_id,
            "bundle_version": self.bundle_version,
            "manifest_sha256": self.manifest_sha256,
            "crosswalk_id": self.crosswalk_id,
            "crosswalk_sha256": self.crosswalk_sha256,
            "review_status": self.review_status,
            "fragment_count": len(self.fragments),
            "block_count": len(self.blocks),
            "coverage": self.coverage,
            "warnings": list(self.warnings),
            "caveats": list(self.caveats),
        }


def load_hydrology_crosswalk(
    path: Path,
    *,
    metadata_path: Path | None = None,
) -> HydrologyCrosswalk:
    """Load and validate an explicit WS4-to-FEMIC crosswalk CSV.

    Parameters
    ----------
    path : Path
        Crosswalk CSV with one of ``fragment_id`` or ``block_id`` per row.
    metadata_path : Path | None, optional
        JSON review metadata. Missing metadata is recorded as ``not_reviewed``.

    Returns
    -------
    HydrologyCrosswalk
        Checksummed rows and review metadata.

    Raises
    ------
    FemicHydrologyError
        If the CSV or metadata is malformed.
    """
    resolved = path.expanduser().resolve()
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise FemicHydrologyError(f"Unable to read hydrology crosswalk: {resolved}: {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FemicHydrologyError(f"Crosswalk is not UTF-8: {resolved}") from exc
    try:
        rows = _crosswalk_rows(text.splitlines(), digest=digest)
    except csv.Error as exc:
        raise FemicHydrologyError(f"Unable to parse crosswalk CSV: {exc}") from exc
    metadata = _crosswalk_metadata(
        metadata_path,
        fallback_id=f"crosswalk-{digest[:16]}",
        crosswalk_sha256=digest,
    )
    return HydrologyCrosswalk(
        path=resolved,
        sha256=digest,
        rows=rows,
        metadata=metadata,
    )


def map_femic_hydrology_to_dataset(
    dataset_dir: Path,
    bundle: FemicHydrologyBundle,
    crosswalk: HydrologyCrosswalk,
    *,
    allow_partial: bool = False,
    generated_utc: str | None = None,
) -> HydrologyMapping:
    """Map explicit crosswalk rows onto compiled WS4 fragments and blocks.

    Parameters
    ----------
    dataset_dir : Path
        Compiled WS4 dataset directory.
    bundle : FemicHydrologyBundle
        Registered and validated FEMIC bundle.
    crosswalk : HydrologyCrosswalk
        Explicit reviewed crosswalk.
    allow_partial : bool, optional
        Allow missing fragment/block coverage and record it as warnings.
    generated_utc : str | None, optional
        Mapping timestamp; defaults to the current UTC time.

    Returns
    -------
    HydrologyMapping
        Validated fragment/block rows, coverage, warnings, and caveats.

    Raises
    ------
    FemicHydrologyError
        If IDs are unknown, rows conflict, or coverage is incomplete without
        ``allow_partial``.
    """
    dataset_root = dataset_dir.expanduser().resolve()
    fragments, blocks = _load_dataset_support(dataset_root)
    unit_to_watershed, watersheds, receptors = _bundle_domain_ids(bundle)
    fragment_map: dict[int, dict[str, object]] = {}
    block_map: dict[int, dict[str, object]] = {}
    for row in crosswalk.rows:
        if row.watershed_id not in watersheds:
            raise FemicHydrologyError(
                f"Crosswalk watershed {row.watershed_id!r} is not in the FEMIC domain."
            )
        if row.unit_id not in unit_to_watershed:
            raise FemicHydrologyError(
                f"Crosswalk unit {row.unit_id!r} is not in the FEMIC disturbance ledger."
            )
        expected_watershed = unit_to_watershed[row.unit_id]
        if expected_watershed and expected_watershed != row.watershed_id:
            raise FemicHydrologyError(
                f"Crosswalk unit {row.unit_id!r} belongs to watershed "
                f"{expected_watershed!r}, not {row.watershed_id!r}."
            )
        if row.receptor_id is not None and row.receptor_id not in receptors:
            raise FemicHydrologyError(
                f"Crosswalk receptor {row.receptor_id!r} is not in the FEMIC domain."
            )
        record = _mapping_record(
            bundle=bundle,
            crosswalk=crosswalk,
            unit_id=row.unit_id,
            watershed_id=row.watershed_id,
            receptor_id=row.receptor_id,
        )
        if row.fragment_id is not None:
            if row.fragment_id not in fragments:
                raise FemicHydrologyError(
                    f"Crosswalk fragment {row.fragment_id} is not in the dataset."
                )
            fragment_map[row.fragment_id] = {**record, "source": "fragment_crosswalk"}
        if row.block_id is not None:
            if row.block_id not in blocks:
                raise FemicHydrologyError(f"Crosswalk block {row.block_id} is not in the dataset.")
            block_map[row.block_id] = {**record, "source": "block_crosswalk"}

    # Expand explicit block rows to fragments, and derive block rows from
    # complete, consistent fragment rows.
    fragment_to_block = {fragment_id: int(block_id) for fragment_id, block_id in fragments.items()}
    for block_id, block_record in list(block_map.items()):
        for fragment_id, parent in fragment_to_block.items():
            if parent != block_id:
                continue
            existing = fragment_map.get(fragment_id)
            if existing is not None and not _same_mapping(existing, block_record):
                raise FemicHydrologyError(
                    f"Fragment {fragment_id} conflicts with the explicit block {block_id} mapping."
                )
            fragment_map[fragment_id] = {
                **block_record,
                "source": "block_crosswalk",
            }
    for block_id in blocks:
        block_fragments = [
            fragment_id for fragment_id, parent in fragment_to_block.items() if parent == block_id
        ]
        mapped = [
            fragment_map[fragment_id]
            for fragment_id in block_fragments
            if fragment_id in fragment_map
        ]
        if not mapped:
            continue
        if any(not _same_mapping(mapped[0], item) for item in mapped[1:]):
            raise FemicHydrologyError(
                f"Fragments in block {block_id} have conflicting FEMIC mappings."
            )
        existing = block_map.get(block_id)
        if existing is not None and not _same_mapping(existing, mapped[0]):
            raise FemicHydrologyError(f"Block {block_id} conflicts with its fragment mappings.")
        if existing is None and len(mapped) == len(block_fragments):
            block_map[block_id] = {**mapped[0], "source": "derived_from_fragments"}

    all_fragment_ids = set(fragments)
    all_block_ids = set(blocks)
    unmapped_fragments = sorted(all_fragment_ids - set(fragment_map))
    unmapped_blocks = sorted(all_block_ids - set(block_map))
    coverage = {
        "dataset_fragments": len(all_fragment_ids),
        "mapped_fragments": len(fragment_map),
        "unmapped_fragments": unmapped_fragments,
        "dataset_blocks": len(all_block_ids),
        "mapped_blocks": len(block_map),
        "unmapped_blocks": unmapped_blocks,
    }
    warnings: list[str] = []
    if crosswalk.metadata.review_status != "reviewed":
        warnings.append(
            "Crosswalk review status is "
            f"{crosswalk.metadata.review_status!r}; mapping is provisional."
        )
    if unmapped_fragments or unmapped_blocks:
        if not allow_partial:
            raise FemicHydrologyError(
                "Crosswalk does not cover the dataset: "
                f"{len(unmapped_fragments)} fragment(s) and "
                f"{len(unmapped_blocks)} block(s) are unmapped."
            )
        warnings.append(
            "Partial mapping: "
            f"{len(unmapped_fragments)} fragment(s) and "
            f"{len(unmapped_blocks)} block(s) are unmapped."
        )
    fragment_rows = tuple(
        _fragment_mapping_row(fragment_id, fragments[fragment_id], fragment_map[fragment_id])
        for fragment_id in sorted(fragment_map)
    )
    block_rows = tuple(
        _block_mapping_row(block_id, block_map[block_id]) for block_id in sorted(block_map)
    )
    timestamp = generated_utc or datetime.now(UTC).isoformat()
    material = {
        "bundle_id": bundle.bundle_id,
        "bundle_version": bundle.bundle_version,
        "manifest_sha256": bundle.manifest_sha256,
        "crosswalk_sha256": crosswalk.sha256,
        "fragments": fragment_rows,
        "blocks": block_rows,
        "coverage": coverage,
    }
    mapping_id = (
        "ws4-hydro-mapping-"
        + hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
    )
    caveats = tuple(
        {
            "Mapping is an explicit reviewed crosswalk; it is not a spatial join "
            "or a watershed inference.",
            "A mapping is not a hydrologic validation; preserve the FEMIC "
            "screening-only and hydrologist-review conditions.",
            *crosswalk.metadata.caveats,
        }
    )
    return HydrologyMapping(
        mapping_id=mapping_id,
        generated_utc=timestamp,
        bundle_id=bundle.bundle_id,
        bundle_version=bundle.bundle_version,
        manifest_sha256=bundle.manifest_sha256,
        crosswalk_id=crosswalk.metadata.crosswalk_id,
        crosswalk_sha256=crosswalk.sha256,
        review_status=crosswalk.metadata.review_status,
        fragments=fragment_rows,
        blocks=block_rows,
        coverage=coverage,
        warnings=tuple(warnings),
        caveats=caveats,
    )


def write_hydrology_mapping(mapping: HydrologyMapping, out_dir: Path) -> dict[str, Path]:
    """Write hydrology mapping CSVs and manifest.

    Parameters
    ----------
    mapping : HydrologyMapping
        Validated mapping.
    out_dir : Path
        Output directory.

    Returns
    -------
    dict[str, Path]
        Paths keyed by ``fragments``, ``blocks``, and ``manifest``.
    """
    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    fragments_path = output / "hydrology_fragments.csv"
    blocks_path = output / "hydrology_blocks.csv"
    _write_csv(fragments_path, mapping.fragments, _FRAGMENT_COLUMNS)
    _write_csv(blocks_path, mapping.blocks, _BLOCK_COLUMNS)
    manifest_path = output / "hydrology_mapping.json"
    manifest_path.write_text(
        json.dumps(mapping.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "fragments": fragments_path,
        "blocks": blocks_path,
        "manifest": manifest_path,
    }


@dataclass(frozen=True)
class HydrologyScreen:
    """Read-only schedule-level flood-risk screening result.

    Attributes
    ----------
    screen_id : str
        Deterministic screening identifier.
    generated_utc : str
        Screening timestamp.
    bundle_id : str
        FEMIC bundle identifier.
    bundle_version : str
        FEMIC bundle version.
    manifest_sha256 : str
        FEMIC manifest digest.
    mapping_id : str
        Mapping identifier.
    mapping_sha256 : str
        Mapping manifest digest.
    schedule_sha256 : str
        Schedule CSV digest.
    exposure_id : str | None
        Schedule-bound exposure identifier, when supplied.
    exposure_sha256 : str | None
        Exposure file digest, when supplied.
    exposure_review_status : str | None
        Exposure review state, when supplied.
    scenario_tolerance : float
        Maximum feature difference allowed when selecting a response scenario.
    covariates : dict[str, float]
        Global response features supplied by the caller.
    rows : tuple[dict[str, object], ...]
        Inside-domain screening rows.
    refusals : tuple[dict[str, object], ...]
        Refused schedule/watershed/return-period combinations.
    coverage : dict[str, object]
        Schedule period and watershed coverage.
    warnings : tuple[str, ...]
        Non-fatal screening observations.
    caveats : tuple[str, ...]
        Screening-only caveats.
    """

    screen_id: str
    generated_utc: str
    bundle_id: str
    bundle_version: str
    manifest_sha256: str
    mapping_id: str
    mapping_sha256: str
    schedule_sha256: str
    exposure_id: str | None
    exposure_sha256: str | None
    exposure_review_status: str | None
    scenario_tolerance: float
    covariates: dict[str, float]
    rows: tuple[dict[str, object], ...]
    refusals: tuple[dict[str, object], ...]
    coverage: dict[str, object]
    warnings: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the screening manifest as a JSON-serializable mapping.

        Returns
        -------
        dict[str, object]
            Identity, provenance, coverage, refusals, and caveats.
        """
        return {
            "schema_version": HYDROLOGY_SCREEN_SCHEMA,
            "screen_id": self.screen_id,
            "generated_utc": self.generated_utc,
            "bundle_id": self.bundle_id,
            "bundle_version": self.bundle_version,
            "manifest_sha256": self.manifest_sha256,
            "mapping_id": self.mapping_id,
            "mapping_sha256": self.mapping_sha256,
            "schedule_sha256": self.schedule_sha256,
            "exposure": (
                None
                if self.exposure_id is None
                else {
                    "exposure_id": self.exposure_id,
                    "exposure_sha256": self.exposure_sha256,
                    "review_status": self.exposure_review_status,
                }
            ),
            "scenario_tolerance": self.scenario_tolerance,
            "covariates": self.covariates,
            "row_count": len(self.rows),
            "refusal_count": len(self.refusals),
            "coverage": self.coverage,
            "refusals": list(self.refusals),
            "warnings": list(self.warnings),
            "caveats": list(self.caveats),
        }


def load_hydrology_mapping(path: Path) -> HydrologyMapping:
    """Load a hydrology mapping manifest and its fragment/block CSVs.

    Parameters
    ----------
    path : Path
        Mapping directory or ``hydrology_mapping.json`` path.

    Returns
    -------
    HydrologyMapping
        Validated mapping with fragment/block rows.

    Raises
    ------
    FemicHydrologyError
        If the manifest or CSVs are missing or inconsistent.
    """
    resolved = path.expanduser().resolve()
    manifest_path = resolved / "hydrology_mapping.json" if resolved.is_dir() else resolved
    payload = _read_json_object(manifest_path, context="hydrology mapping manifest")
    if payload.get("schema_version") != HYDROLOGY_MAPPING_SCHEMA:
        raise FemicHydrologyError(
            f"Unsupported hydrology mapping schema {payload.get('schema_version')!r}."
        )
    root = manifest_path.parent
    fragments = _csv_mapping_rows(root / "hydrology_fragments.csv", "fragment")
    blocks = _csv_mapping_rows(root / "hydrology_blocks.csv", "block")
    if _int(payload.get("fragment_count", -1), "fragment_count") != len(fragments):
        raise FemicHydrologyError("Hydrology mapping fragment count does not match the CSV.")
    if _int(payload.get("block_count", -1), "block_count") != len(blocks):
        raise FemicHydrologyError("Hydrology mapping block count does not match the CSV.")
    coverage = payload.get("coverage")
    if not isinstance(coverage, Mapping):
        raise FemicHydrologyError("Hydrology mapping coverage must be an object.")
    return HydrologyMapping(
        mapping_id=_text(payload.get("mapping_id"), "mapping_id"),
        generated_utc=_text(payload.get("generated_utc"), "mapping generated_utc"),
        bundle_id=_text(payload.get("bundle_id"), "mapping bundle_id"),
        bundle_version=_text(payload.get("bundle_version"), "mapping bundle_version"),
        manifest_sha256=_text(payload.get("manifest_sha256"), "mapping manifest_sha256"),
        crosswalk_id=_text(payload.get("crosswalk_id"), "mapping crosswalk_id"),
        crosswalk_sha256=_text(payload.get("crosswalk_sha256"), "mapping crosswalk_sha256"),
        review_status=_text(payload.get("review_status"), "mapping review_status"),
        fragments=fragments,
        blocks=blocks,
        coverage={str(key): item for key, item in coverage.items()},
        warnings=_strict_strings(payload.get("warnings"), "mapping warnings"),
        caveats=_strict_strings(payload.get("caveats"), "mapping caveats"),
    )


def screen_schedule_flood_risk(
    dataset_dir: Path,
    bundle: FemicHydrologyBundle,
    mapping: HydrologyMapping,
    schedule_source: Path | pd.DataFrame,
    *,
    mapping_manifest_path: Path | None = None,
    exposure: HydrologyExposure | None = None,
    covariates: Mapping[str, float] | None = None,
    scenario_tolerance: float = 0.05,
    periods: Sequence[int] | None = None,
    allow_refused: bool = False,
    generated_utc: str | None = None,
) -> HydrologyScreen:
    """Screen a WS4 schedule against the FEMIC response and flood-risk rows.

    Parameters
    ----------
    dataset_dir : Path
        Compiled WS4 dataset directory.
    bundle : FemicHydrologyBundle
        Pinned FEMIC bundle.
    mapping : HydrologyMapping
        Explicit WS4-to-FEMIC mapping.
    schedule_source : Path or pandas.DataFrame
        WS4 schedule CSV or frame with ``block_id``, ``treatment``, and
        ``offset``.
    mapping_manifest_path : Path | None, optional
        Mapping manifest path used to record its digest.
    exposure : HydrologyExposure | None, optional
        Explicit, reviewed exposure table bound to this schedule. Missing
        declared watershed/period rows or a schedule-hash mismatch refuse.
    covariates : Mapping[str, float] | None, optional
        Global response features not derived from the schedule. They may not
        duplicate exposure feature names. Missing scenario features cause
        refusal.
    scenario_tolerance : float, optional
        Maximum absolute feature difference allowed when selecting a response
        scenario.
    periods : sequence of int, optional
        Offsets to screen even when no treatment occurs there. The default uses
        the schedule's own offsets.
    allow_refused : bool, optional
        Return inside-domain rows plus refusals instead of failing on refusal.
    generated_utc : str | None, optional
        Screening timestamp.

    Returns
    -------
    HydrologyScreen
        Screening rows, refusals, coverage, and caveats.

    Raises
    ------
    FemicHydrologyError
        If inputs are malformed or a refusal occurs without ``allow_refused``.
    """
    if scenario_tolerance <= 0 or not math.isfinite(scenario_tolerance):
        raise FemicHydrologyError("Scenario tolerance must be positive and finite.")
    if (
        mapping.bundle_id != bundle.bundle_id
        or mapping.bundle_version != bundle.bundle_version
        or mapping.manifest_sha256 != bundle.manifest_sha256
    ):
        raise FemicHydrologyError("Hydrology mapping was built from a different FEMIC bundle pin.")
    supplied = {str(name): float(value) for name, value in (covariates or {}).items()}
    if any(not math.isfinite(value) for value in supplied.values()):
        raise FemicHydrologyError("Covariate values must be finite.")
    exposure_names = set(HYDROLOGY_EXPOSURE_FEATURES) | set(HYDROLOGY_EXPOSURE_DERIVED_FEATURES)
    overlap = sorted(set(supplied) & exposure_names)
    if exposure is not None and overlap:
        raise FemicHydrologyError(
            "Exposure features may not also be supplied as global covariates: " + ", ".join(overlap)
        )
    schedule = _schedule_source(schedule_source)
    schedule_sha = _schedule_digest(schedule_source)
    if exposure is not None and exposure.schedule_sha256 != schedule_sha:
        raise FemicHydrologyError(
            "Exposure schedule hash does not match the schedule; regenerate the "
            "exposure table for this schedule."
        )
    block_records = {_int(row["block_id"], "mapping block_id"): row for row in mapping.blocks}
    dataset_blocks = _load_block_areas(dataset_dir.expanduser().resolve())
    watershed_areas = _watershed_areas(bundle)
    scenarios = _response_scenarios(bundle)
    surface_rows = _response_surface_rows(bundle)
    risk_rows = read_femic_flood_risk(bundle).rows
    risk_by_watershed: dict[str, list[FemicFloodRiskRow]] = {}
    for row in risk_rows:
        risk_by_watershed.setdefault(row.watershed_id, []).append(row)
    requested_periods = {int(period) for period in (periods or ())}
    periods = sorted(requested_periods | {item.offset for item in schedule})
    if not periods:
        raise FemicHydrologyError("Schedule has no treatments and no screening periods.")
    harvested_by_period: dict[int, set[int]] = {period: set() for period in periods}
    for item in schedule:
        block_id = item.block_id
        if block_id not in block_records:
            raise FemicHydrologyError(f"Schedule block {block_id} has no explicit FEMIC mapping.")
        harvested_by_period[item.offset].add(block_id)
    cumulative_blocks: set[int] = set()
    rows: list[dict[str, object]] = []
    refusals: list[dict[str, object]] = []
    screened_watersheds: set[str] = set()
    for period in periods:
        cumulative_blocks |= harvested_by_period[period]
        area_by_watershed: dict[str, float] = {}
        for block_id in cumulative_blocks:
            record = block_records[block_id]
            watershed_id = _text(record.get("watershed_id"), "mapping watershed_id")
            area_by_watershed[watershed_id] = area_by_watershed.get(
                watershed_id, 0.0
            ) + dataset_blocks.get(block_id, 0.0)
        if not area_by_watershed:
            continue
        for watershed_id in sorted(area_by_watershed):
            screened_watersheds.add(watershed_id)
            area = area_by_watershed[watershed_id]
            watershed_area = watershed_areas.get(watershed_id)
            if watershed_area is None or watershed_area <= 0:
                refusals.append(
                    {
                        "period": period,
                        "watershed_id": watershed_id,
                        "receptor_id": None,
                        "return_period": None,
                        "reason": "FEMIC domain has no positive watershed area.",
                    }
                )
                continue
            harvest_fraction = area / watershed_area
            if harvest_fraction > 1.0:
                refusals.append(
                    {
                        "period": period,
                        "watershed_id": watershed_id,
                        "receptor_id": None,
                        "return_period": None,
                        "reason": "Cumulative harvest fraction exceeds 1.0.",
                    }
                )
                continue
            exposure_features: dict[str, float] = {}
            if exposure is not None:
                if watershed_id not in exposure.watershed_ids or period not in exposure.periods:
                    refusals.append(
                        {
                            "period": period,
                            "watershed_id": watershed_id,
                            "receptor_id": None,
                            "return_period": None,
                            "reason": (
                                "Exposure has no declared row for watershed "
                                f"{watershed_id!r} period {period}."
                            ),
                        }
                    )
                    continue
                exposure_features = _exposure_screen_features(
                    exposure,
                    watershed_id,
                    period,
                    watershed_area,
                )
            features = {**supplied, "harvest_fraction": harvest_fraction, **exposure_features}
            selected = _select_scenario(scenarios, features, scenario_tolerance)
            if selected is None:
                refusals.append(
                    {
                        "period": period,
                        "watershed_id": watershed_id,
                        "receptor_id": None,
                        "return_period": None,
                        "reason": (
                            "No response-surface scenario is inside the "
                            f"{scenario_tolerance:g} feature tolerance."
                        ),
                    }
                )
                continue
            scenario_name, scenario_covariates = selected
            watershed_risk = risk_by_watershed.get(watershed_id, [])
            if not watershed_risk:
                refusals.append(
                    {
                        "period": period,
                        "watershed_id": watershed_id,
                        "receptor_id": None,
                        "return_period": None,
                        "reason": "No flood-risk row exists for this watershed.",
                    }
                )
                continue
            for risk in watershed_risk:
                surface = surface_rows.get((scenario_name, risk.return_period))
                if surface is None:
                    refusals.append(
                        {
                            "period": period,
                            "watershed_id": watershed_id,
                            "receptor_id": risk.receptor_id,
                            "return_period": risk.return_period,
                            "reason": (
                                "Response surface has no row for the selected "
                                "scenario and return period."
                            ),
                        }
                    )
                    continue
                ratio = _float(surface.get("ratio"), "surface ratio")
                rows.append(
                    {
                        "period": period,
                        "watershed_id": watershed_id,
                        "receptor_id": risk.receptor_id,
                        "return_period": risk.return_period,
                        "harvested_area_ha": area,
                        "watershed_area_ha": watershed_area,
                        "harvest_fraction": harvest_fraction,
                        "scenario_name": scenario_name,
                        "scenario_covariates": dict(scenario_covariates),
                        "exposure_used": exposure is not None,
                        **{
                            feature: exposure_features.get(feature)
                            for feature in (
                                *HYDROLOGY_EXPOSURE_FEATURES,
                                *HYDROLOGY_EXPOSURE_DERIVED_FEATURES,
                            )
                        },
                        "response_ratio": ratio,
                        "baseline_peak_flow_m3s": risk.baseline_peak_flow_m3s,
                        "screening_peak_flow_m3s": risk.baseline_peak_flow_m3s * ratio,
                        "bundle_scenario_peak_flow_m3s": risk.scenario_peak_flow_m3s,
                        "exceedance_probability": risk.exceedance_probability,
                        "expected_annual_damage": risk.expected_annual_damage,
                    }
                )
    if refusals and not allow_refused:
        reasons = "; ".join(str(item["reason"]) for item in refusals[:3])
        raise FemicHydrologyError(f"Schedule screening refused {len(refusals)} row(s): {reasons}")
    mapping_sha = _sha256_file(mapping_manifest_path) if mapping_manifest_path is not None else ""
    timestamp = generated_utc or datetime.now(UTC).isoformat()
    material = {
        "bundle_id": bundle.bundle_id,
        "mapping_id": mapping.mapping_id,
        "schedule_sha256": schedule_sha,
        "exposure_id": exposure.exposure_id if exposure is not None else None,
        "exposure_sha256": exposure.sha256 if exposure is not None else None,
        "rows": rows,
        "refusals": refusals,
        "covariates": supplied,
        "scenario_tolerance": scenario_tolerance,
    }
    screen_id = (
        "ws4-hydro-screen-"
        + hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
    )
    warnings: list[str] = []
    if mapping.review_status != "reviewed":
        warnings.append("Mapping is not reviewed; schedule screening is provisional.")
    if exposure is not None and exposure.review_status != "reviewed":
        warnings.append("Exposure is not reviewed; schedule screening is provisional.")
    if exposure is not None and not _exposure_is_used(scenarios, exposure_names):
        warnings.append("Exposure was supplied but no response-surface scenario uses its features.")
    if refusals:
        warnings.append(f"{len(refusals)} screening row(s) were refused.")
    coverage = {
        "periods": periods,
        "watersheds": sorted(screened_watersheds),
        "mapped_blocks": len(block_records),
        "screened_rows": len(rows),
        "refused_rows": len(refusals),
        "exposure_used": exposure is not None,
    }
    caveats = (
        "Schedule screening uses a precomputed response-surface scenario, not a "
        "schedule-specific process simulation.",
        "Baseline flows, receptor rows, and bundle scenario flows come from the "
        "pinned FEMIC flood-risk table.",
        "Screening only; not a regulatory flood map or operational safety determination.",
        "Hydrologist review and a completed process-model pilot remain required.",
        "Exposure features are explicit inputs; they are not inferred from road "
        "or culvert geometry.",
        *mapping.caveats,
    )
    return HydrologyScreen(
        screen_id=screen_id,
        generated_utc=timestamp,
        bundle_id=bundle.bundle_id,
        bundle_version=bundle.bundle_version,
        manifest_sha256=bundle.manifest_sha256,
        mapping_id=mapping.mapping_id,
        mapping_sha256=mapping_sha,
        schedule_sha256=schedule_sha,
        exposure_id=exposure.exposure_id if exposure is not None else None,
        exposure_sha256=exposure.sha256 if exposure is not None else None,
        exposure_review_status=exposure.review_status if exposure is not None else None,
        scenario_tolerance=scenario_tolerance,
        covariates=supplied,
        rows=tuple(rows),
        refusals=tuple(refusals),
        coverage=coverage,
        warnings=tuple(warnings),
        caveats=caveats,
    )


def write_hydrology_screen(screen: HydrologyScreen, out_dir: Path) -> dict[str, Path]:
    """Write screening CSV and manifest.

    Parameters
    ----------
    screen : HydrologyScreen
        Screening result.
    out_dir : Path
        Output directory.

    Returns
    -------
    dict[str, Path]
        Paths keyed by ``rows`` and ``manifest``.
    """
    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows_path = output / "hydrology_screen.csv"
    columns = (
        "period",
        "watershed_id",
        "receptor_id",
        "return_period",
        "harvested_area_ha",
        "watershed_area_ha",
        "harvest_fraction",
        "scenario_name",
        "exposure_used",
        "road_built_km",
        "road_used_km",
        "road_decommissioned_km",
        "culvert_count",
        "culvert_exposed_count",
        "road_built_density_km_per_km2",
        "road_used_density_km_per_km2",
        "road_decommissioned_density_km_per_km2",
        "culvert_exposure_per_km2",
        "response_ratio",
        "baseline_peak_flow_m3s",
        "screening_peak_flow_m3s",
        "bundle_scenario_peak_flow_m3s",
        "exceedance_probability",
        "expected_annual_damage",
    )
    with rows_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(screen.rows)
    manifest_path = output / "hydrology_screen.json"
    manifest_path.write_text(
        json.dumps(screen.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"rows": rows_path, "manifest": manifest_path}


def register_femic_hydrology_bundle(
    dataset_dir: Path,
    bundle_dir: Path,
    *,
    expected_bundle_id: str | None = None,
    expected_bundle_version: str | None = None,
    registered_utc: str | None = None,
) -> dict[str, object]:
    """Register a validated FEMIC hydrology bundle in a compiled dataset.

    Writes the pin to the dataset manifest metadata and a
    ``hydrology_products.json`` sidecar. The bundle is referenced, not copied.

    Parameters
    ----------
    dataset_dir : Path
        Compiled WS4 dataset directory.
    bundle_dir : Path
        FEMIC hydrology bundle root to pin.
    expected_bundle_id : str | None, optional
        Required bundle identifier.
    expected_bundle_version : str | None, optional
        Required bundle version.
    registered_utc : str | None, optional
        Registration timestamp; defaults to the current UTC time.

    Returns
    -------
    dict[str, object]
        Registration record written to the dataset.

    Raises
    ------
    FemicHydrologyError
        If the dataset or bundle cannot be registered.
    """
    dataset_root = dataset_dir.expanduser().resolve()
    manifest_path = dataset_root / FEMIC_HYDROLOGY_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FemicHydrologyError(f"Dataset manifest is missing: {manifest_path}")
    bundle = load_femic_hydrology_bundle(
        bundle_dir,
        expected_bundle_id=expected_bundle_id,
        expected_bundle_version=expected_bundle_version,
    )
    try:
        manifest = load_manifest(dataset_root)
    except (OSError, ValueError) as exc:
        raise FemicHydrologyError(f"Unable to read dataset manifest: {exc}") from exc
    registration: dict[str, object] = {
        **bundle_pin(bundle),
        "bundle_dir": _bundle_reference(dataset_root, bundle.bundle_dir),
        "registered_utc": registered_utc or datetime.now(UTC).isoformat(),
    }
    metadata = dict(manifest.metadata)
    metadata[FEMIC_HYDROLOGY_METADATA_KEY] = registration
    manifest = manifest.model_copy(update={"metadata": metadata})
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    sidecar = dataset_root / FEMIC_HYDROLOGY_SIDECAR_NAME
    sidecar.write_text(
        json.dumps(registration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registration


def read_registered_femic_hydrology(dataset_dir: Path) -> dict[str, object] | None:
    """Read the registered FEMIC hydrology pin from a dataset, if present.

    Parameters
    ----------
    dataset_dir : Path
        Compiled WS4 dataset directory.

    Returns
    -------
    dict[str, object] | None
        Registration record, or ``None`` when the dataset has no pin.
    """
    dataset_root = dataset_dir.expanduser().resolve()
    sidecar = dataset_root / FEMIC_HYDROLOGY_SIDECAR_NAME
    if sidecar.is_file():
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FemicHydrologyError(f"Invalid hydrology sidecar: {sidecar}") from exc
        if not isinstance(payload, Mapping):
            raise FemicHydrologyError(f"Hydrology sidecar must be an object: {sidecar}")
        return {str(key): item for key, item in payload.items()}
    manifest_path = dataset_root / FEMIC_HYDROLOGY_MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    try:
        manifest = load_manifest(dataset_root)
    except (OSError, ValueError) as exc:
        raise FemicHydrologyError(f"Unable to read dataset manifest: {exc}") from exc
    value = manifest.metadata.get(FEMIC_HYDROLOGY_METADATA_KEY)
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return None


def load_registered_femic_hydrology_bundle(
    dataset_dir: Path,
) -> FemicHydrologyBundle:
    """Load and revalidate the hydrology bundle pinned by a dataset.

    Parameters
    ----------
    dataset_dir : Path
        Compiled WS4 dataset directory.

    Returns
    -------
    FemicHydrologyBundle
        Validated bundle referenced by the dataset.

    Raises
    ------
    FemicHydrologyError
        If no pin exists, the pin is stale, or the bundle is invalid.
    """
    registration = read_registered_femic_hydrology(dataset_dir)
    if registration is None:
        raise FemicHydrologyError("Dataset has no registered FEMIC hydrology bundle.")
    bundle_path = _registered_bundle_path(dataset_dir, registration)
    bundle = load_femic_hydrology_bundle(
        bundle_path,
        expected_bundle_id=_registration_text(registration, "bundle_id"),
        expected_bundle_version=_registration_text(registration, "bundle_version"),
    )
    _check_registered_manifest(bundle, registration)
    return bundle


def validate_registered_femic_hydrology(
    dataset_dir: Path,
) -> FemicHydrologyValidation:
    """Revalidate the hydrology bundle pinned by a dataset.

    Parameters
    ----------
    dataset_dir : Path
        Compiled WS4 dataset directory.

    Returns
    -------
    FemicHydrologyValidation
        Validation report for the registered bundle.
    """
    registration = read_registered_femic_hydrology(dataset_dir)
    if registration is None:
        raise FemicHydrologyError("Dataset has no registered FEMIC hydrology bundle.")
    bundle_path = _registered_bundle_path(dataset_dir, registration)
    report = validate_femic_hydrology_bundle(
        bundle_path,
        expected_bundle_id=_registration_text(registration, "bundle_id"),
        expected_bundle_version=_registration_text(registration, "bundle_version"),
    )
    if not report.is_valid:
        return report
    bundle = load_femic_hydrology_bundle(bundle_path)
    try:
        _check_registered_manifest(bundle, registration)
    except FemicHydrologyError as exc:
        return replace(
            report,
            is_valid=False,
            errors=(*report.errors, str(exc)),
        )
    return report


def _registered_bundle_path(
    dataset_dir: Path,
    registration: Mapping[str, object],
) -> Path:
    value = registration.get("bundle_dir")
    if not isinstance(value, str) or not value.strip():
        raise FemicHydrologyError("Registered hydrology pin has no bundle_dir.")
    path = Path(value)
    if path.is_absolute():
        return path
    return dataset_dir.expanduser().resolve() / path


def _registration_text(registration: Mapping[str, object], key: str) -> str:
    value = registration.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FemicHydrologyError(f"Registered hydrology pin has no {key}.")
    return value


def _check_registered_manifest(
    bundle: FemicHydrologyBundle,
    registration: Mapping[str, object],
) -> None:
    expected = _registration_text(registration, "manifest_sha256")
    if bundle.manifest_sha256 != expected:
        raise FemicHydrologyError("Registered hydrology manifest digest does not match the bundle.")


def _bundle_reference(dataset_root: Path, bundle_root: Path) -> str:
    try:
        return str(bundle_root.resolve().relative_to(dataset_root))
    except ValueError:
        return str(bundle_root.resolve())


def read_femic_flood_risk(bundle: FemicHydrologyBundle) -> FemicFloodRiskTable:
    """Read and validate the pinned flood-risk table.

    Parameters
    ----------
    bundle : FemicHydrologyBundle
        Validated bundle.

    Returns
    -------
    FemicFloodRiskTable
        Typed flood-risk table.

    Raises
    ------
    FemicHydrologyError
        If the flood-risk artifact is absent or malformed.
    """
    artifact = bundle.artifacts.get("flood_risk")
    if artifact is None:
        raise FemicHydrologyError("Bundle has no flood_risk artifact.")
    payload = _read_json_object(
        _resolve_member(bundle.bundle_dir, artifact.relative_path),
        context="flood-risk artifact",
    )
    return _flood_risk_from_payload(payload, expected_surface=bundle.response_surface_id)


def _validate(
    bundle_path: Path,
    *,
    expected_bundle_id: str | None,
    expected_bundle_version: str | None,
) -> tuple[FemicHydrologyValidation, FemicHydrologyBundle | None]:
    root, manifest_path = _resolve_manifest_path(bundle_path)
    checked_utc = datetime.now(UTC).isoformat()
    errors: list[str] = []
    warnings: list[str] = []
    artifacts: dict[str, FemicHydrologyArtifact] = {}
    total_bytes = 0
    manifest_sha256 = ""
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        payload = _json_object(manifest_bytes, context="manifest")
    except (OSError, FemicHydrologyError) as exc:
        return (
            FemicHydrologyValidation(
                bundle_dir=root,
                is_valid=False,
                checked_utc=checked_utc,
                errors=(str(exc),),
                warnings=(),
                artifact_count=0,
                total_bytes=0,
            ),
            None,
        )
    if payload.get("schema_version") != FEMIC_HYDROLOGY_MANIFEST_SCHEMA:
        errors.append(
            "Unsupported hydrology manifest schema "
            f"{payload.get('schema_version')!r}; expected "
            f"{FEMIC_HYDROLOGY_MANIFEST_SCHEMA!r}."
        )
    bundle_id = _required_text(payload.get("bundle_id"), "bundle_id", errors)
    bundle_name = _required_text(payload.get("bundle_name"), "bundle_name", errors)
    bundle_version = _required_text(payload.get("bundle_version"), "bundle_version", errors)
    generated_utc = _required_text(payload.get("generated_utc"), "generated_utc", errors)
    domain_id = _required_text(payload.get("domain_id"), "domain_id", errors)
    ledger_id = _required_text(payload.get("ledger_id"), "ledger_id", errors)
    response_surface_id = _required_text(
        payload.get("response_surface_id"), "response_surface_id", errors
    )
    if bundle_id and not bundle_id.startswith("hydro-response-"):
        errors.append("Bundle ID does not use the FEMIC hydro-response prefix.")
    if bundle_id and bundle_name and not bundle_name.startswith(bundle_id):
        errors.append("Bundle name does not start with the bundle ID.")
    if expected_bundle_id is not None and bundle_id != expected_bundle_id:
        errors.append(f"Bundle ID {bundle_id!r} does not match expected {expected_bundle_id!r}.")
    if expected_bundle_version is not None and bundle_version != expected_bundle_version:
        errors.append(
            f"Bundle version {bundle_version!r} does not match expected "
            f"{expected_bundle_version!r}."
        )
    response_surface = _mapping(payload.get("response_surface"), "response_surface", errors)
    flood_risk = _mapping(payload.get("flood_risk"), "flood_risk", errors)
    applicability_domain = _mapping(
        payload.get("applicability_domain"), "applicability_domain", errors
    )
    uncertainty = _mapping(payload.get("uncertainty"), "uncertainty", errors)
    consumer_contract = _mapping(payload.get("consumer_contract"), "consumer_contract", errors)
    caveats = _strings(payload.get("caveats"), "caveats", errors)
    provenance = _mapping(payload.get("provenance"), "provenance", errors)
    _validate_consumer_contract(consumer_contract, errors, warnings)
    if not response_surface:
        errors.append("Manifest has no response_surface summary.")
    else:
        for key in ("surface_id", "baseline_name", "return_periods"):
            if key not in response_surface:
                errors.append(f"response_surface summary is missing {key!r}.")
        if response_surface.get("surface_id") != response_surface_id:
            errors.append("response_surface summary ID does not match response_surface_id.")
    if not flood_risk:
        errors.append("Manifest has no flood_risk summary.")
    else:
        for key in ("table_id", "row_count", "baseline_name"):
            if key not in flood_risk:
                errors.append(f"flood_risk summary is missing {key!r}.")

    artifact_payload: list[object] = _list(payload.get("artifacts"), "artifacts", errors)
    seen_roles: set[str] = set()
    for index, item in enumerate(artifact_payload, start=1):
        artifact = _artifact_from_payload(item, index=index, errors=errors)
        if artifact is None:
            continue
        if artifact.role in seen_roles:
            errors.append(f"Duplicate artifact role {artifact.role!r}.")
            continue
        if (
            artifact.role not in FEMIC_HYDROLOGY_REQUIRED_ROLES
            and artifact.role not in FEMIC_HYDROLOGY_OPTIONAL_ROLES
        ):
            warnings.append(f"Unrecognised optional artifact role {artifact.role!r}.")
        seen_roles.add(artifact.role)
        artifacts[artifact.role] = artifact
        expected_schema = FEMIC_HYDROLOGY_ROLE_SCHEMAS.get(artifact.role)
        if expected_schema is not None and artifact.schema_version != expected_schema:
            errors.append(
                f"Artifact {artifact.role!r} schema {artifact.schema_version!r} "
                f"does not match {expected_schema!r}."
            )
        member = _resolve_member(root, artifact.relative_path)
        if member is None:
            errors.append(
                f"Artifact {artifact.role!r} path escapes the bundle: {artifact.relative_path!r}."
            )
            continue
        if not member.is_file():
            errors.append(f"Artifact {artifact.role!r} is missing: {artifact.relative_path}.")
            continue
        size = member.stat().st_size
        total_bytes += size
        if size != artifact.size_bytes:
            errors.append(
                f"Artifact {artifact.role!r} size mismatch: {size} != {artifact.size_bytes}."
            )
        digest = _sha256_file(member)
        if digest.lower() != artifact.sha256.lower():
            errors.append(f"Artifact {artifact.role!r} checksum mismatch.")
    missing_roles = [role for role in FEMIC_HYDROLOGY_REQUIRED_ROLES if role not in artifacts]
    if missing_roles:
        errors.append(
            "Bundle is missing required artifact roles: " + ", ".join(missing_roles) + "."
        )

    try:
        _validate_artifact_payloads(
            root,
            artifacts,
            response_surface_id=response_surface_id,
            domain_id=domain_id,
            ledger_id=ledger_id,
            response_surface=response_surface,
            flood_risk=flood_risk,
            errors=errors,
        )
    except FemicHydrologyError as exc:
        errors.append(str(exc))
    report = FemicHydrologyValidation(
        bundle_dir=root,
        is_valid=not errors,
        checked_utc=checked_utc,
        errors=tuple(errors),
        warnings=tuple(warnings),
        artifact_count=len(artifacts),
        total_bytes=total_bytes,
    )
    if not report.is_valid:
        return report, None
    bundle = FemicHydrologyBundle(
        bundle_dir=root,
        manifest_path=manifest_path,
        bundle_id=bundle_id,
        bundle_name=bundle_name,
        bundle_version=bundle_version,
        generated_utc=generated_utc,
        domain_id=domain_id,
        ledger_id=ledger_id,
        response_surface_id=response_surface_id,
        artifacts=artifacts,
        response_surface=response_surface,
        flood_risk=flood_risk,
        applicability_domain=applicability_domain,
        uncertainty=uncertainty,
        consumer_contract=consumer_contract,
        caveats=caveats,
        provenance=provenance,
        manifest_sha256=manifest_sha256,
        total_bytes=total_bytes,
    )
    return report, bundle


def _validate_consumer_contract(
    contract: Mapping[str, object],
    errors: list[str],
    warnings: list[str],
) -> None:
    for key in FEMIC_HYDROLOGY_CONSUMER_CONTRACT_KEYS:
        if key not in contract:
            errors.append(f"consumer_contract is missing {key!r}.")
    phases = contract.get("consumer_phases")
    if isinstance(phases, Mapping):
        for consumer in ("ws4", "fhops"):
            value = phases.get(consumer)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"consumer_contract consumer_phases[{consumer!r}] must be text.")
    elif phases is not None:
        errors.append("consumer_contract consumer_phases must be an object.")
    if "read_order" in contract and not isinstance(contract["read_order"], list):
        errors.append("consumer_contract read_order must be a list.")
    if "caveats" in contract:
        warnings.append(
            "Consumer contract caveats are producer metadata; preserve the "
            "bundle caveats in downstream outputs."
        )


def _validate_artifact_payloads(
    root: Path,
    artifacts: Mapping[str, FemicHydrologyArtifact],
    *,
    response_surface_id: str,
    domain_id: str,
    ledger_id: str,
    response_surface: Mapping[str, object],
    flood_risk: Mapping[str, object],
    errors: list[str],
) -> None:
    surface_artifact = artifacts.get("response_surface")
    if surface_artifact is not None:
        member = _resolve_member(root, surface_artifact.relative_path)
        if member is not None and member.is_file():
            payload = _read_json_object(member, context="response-surface artifact")
            if payload.get("surface_id") != response_surface_id:
                errors.append("response-surface artifact ID does not match the manifest.")
            if payload.get("baseline_name") != response_surface.get("baseline_name"):
                errors.append("response-surface baseline does not match the manifest summary.")
            periods = payload.get("return_periods")
            if not isinstance(periods, list) or not periods:
                errors.append("response-surface artifact has no return periods.")
            elif not _same_periods(periods, response_surface.get("return_periods")):
                errors.append("response-surface return periods do not match the manifest summary.")
    risk_artifact = artifacts.get("flood_risk")
    if risk_artifact is not None:
        member = _resolve_member(root, risk_artifact.relative_path)
        if member is not None and member.is_file():
            payload = _read_json_object(member, context="flood-risk artifact")
            try:
                table = _flood_risk_from_payload(
                    payload,
                    expected_surface=response_surface_id,
                )
            except FemicHydrologyError as exc:
                errors.append(str(exc))
            else:
                if table.table_id != flood_risk.get("table_id"):
                    errors.append("flood-risk table ID does not match the manifest.")
                if table.baseline_name != flood_risk.get("baseline_name"):
                    errors.append("flood-risk baseline does not match the manifest summary.")
                if len(table.rows) != flood_risk.get("row_count"):
                    errors.append("flood-risk row count does not match the manifest.")
    domain_artifact = artifacts.get("domain")
    if domain_artifact is not None:
        member = _resolve_member(root, domain_artifact.relative_path)
        if member is not None and member.is_file():
            payload = _read_json_object(member, context="domain artifact")
            if payload.get("domain_id") != domain_id:
                errors.append("domain artifact ID does not match the manifest.")
    ledger_artifact = artifacts.get("disturbance_ledger")
    if ledger_artifact is not None:
        member = _resolve_member(root, ledger_artifact.relative_path)
        if member is not None and member.is_file():
            payload = _read_json_object(member, context="disturbance-ledger artifact")
            if payload.get("ledger_id") != ledger_id:
                errors.append("disturbance-ledger ID does not match the manifest.")
            if payload.get("domain_id") != domain_id:
                errors.append("disturbance-ledger domain ID does not match the manifest.")


def _flood_risk_from_payload(
    payload: Mapping[str, object],
    *,
    expected_surface: str,
) -> FemicFloodRiskTable:
    if payload.get("schema_version") != FEMIC_HYDROLOGY_FLOOD_RISK_SCHEMA:
        raise FemicHydrologyError("Unsupported flood-risk artifact schema.")
    table_id = _text(payload.get("table_id"), "flood-risk table_id")
    generated_utc = _text(payload.get("generated_utc"), "flood-risk generated_utc")
    source_surface_id = _text(payload.get("source_surface_id"), "flood-risk source_surface_id")
    baseline_name = _text(payload.get("baseline_name"), "flood-risk baseline_name")
    if source_surface_id != expected_surface:
        raise FemicHydrologyError("flood-risk source surface does not match the response surface.")
    rows_value = payload.get("rows")
    if not isinstance(rows_value, list) or not rows_value:
        raise FemicHydrologyError("Flood-risk artifact must contain rows.")
    rows: list[FemicFloodRiskRow] = []
    seen: set[tuple[str, float]] = set()
    for index, item in enumerate(rows_value, start=1):
        row = _flood_risk_row(item, index=index)
        key = (row.receptor_id, row.return_period)
        if key in seen:
            raise FemicHydrologyError(
                f"Duplicate flood-risk row for {row.receptor_id}/{row.return_period}."
            )
        seen.add(key)
        rows.append(row)
    summary = payload.get("summary")
    if isinstance(summary, Mapping):
        row_count = summary.get("row_count")
        if row_count is not None and _int(row_count, "flood-risk row_count") != len(rows):
            raise FemicHydrologyError("Flood-risk summary row count does not match the rows.")
    return FemicFloodRiskTable(
        table_id=table_id,
        generated_utc=generated_utc,
        source_surface_id=source_surface_id,
        baseline_name=baseline_name,
        rows=tuple(rows),
        caveats=_strings(payload.get("caveats"), "flood-risk caveats", []),
        schema_version=FEMIC_HYDROLOGY_FLOOD_RISK_SCHEMA,
    )


def _flood_risk_row(item: object, *, index: int) -> FemicFloodRiskRow:
    payload = _mapping(item, f"flood-risk row {index}", [])
    receptor_id = _text(payload.get("receptor_id"), f"flood-risk row {index} receptor")
    watershed_id = _text(payload.get("watershed_id"), f"flood-risk row {index} watershed")
    return_period = _float(payload.get("return_period"), f"flood-risk row {index} return_period")
    baseline = _float(
        payload.get("baseline_peak_flow_m3s"),
        f"flood-risk row {index} baseline_peak_flow_m3s",
    )
    scenario = _float(
        payload.get("scenario_peak_flow_m3s"),
        f"flood-risk row {index} scenario_peak_flow_m3s",
    )
    ratio = _float(payload.get("ratio"), f"flood-risk row {index} ratio")
    if return_period <= 1 or not math.isfinite(return_period):
        raise FemicHydrologyError("Flood-risk return periods must be > 1.")
    if baseline <= 0 or scenario <= 0:
        raise FemicHydrologyError("Flood-risk flows must be positive.")
    if not math.isclose(ratio, scenario / baseline, rel_tol=1e-6, abs_tol=1e-9):
        raise FemicHydrologyError(f"Flood-risk row {index} ratio does not equal scenario/baseline.")
    exceedance = _optional_float(
        payload.get("exceedance_probability"),
        f"flood-risk row {index} exceedance_probability",
    )
    if exceedance is not None and not 0 <= exceedance <= 1:
        raise FemicHydrologyError("Flood-risk exceedance probability must be in [0, 1].")
    damage = _optional_float(
        payload.get("expected_annual_damage"),
        f"flood-risk row {index} expected_annual_damage",
    )
    if damage is not None and damage < 0:
        raise FemicHydrologyError("Flood-risk expected annual damage cannot be negative.")
    return FemicFloodRiskRow(
        receptor_id=receptor_id,
        watershed_id=watershed_id,
        return_period=return_period,
        baseline_peak_flow_m3s=baseline,
        scenario_peak_flow_m3s=scenario,
        ratio=ratio,
        exceedance_probability=exceedance,
        expected_annual_damage=damage,
    )


def _artifact_from_payload(
    item: object,
    *,
    index: int,
    errors: list[str],
) -> FemicHydrologyArtifact | None:
    payload = _mapping(item, f"artifact {index}", errors)
    role = _required_text(payload.get("role"), f"artifact {index} role", errors)
    relative_path = _required_text(
        payload.get("relative_path"), f"artifact {index} relative_path", errors
    )
    schema_version = _optional_text(payload.get("schema_version"))
    media_type = _required_text(payload.get("media_type"), f"artifact {index} media_type", errors)
    size_bytes = _required_int(payload.get("size_bytes"), f"artifact {index} size_bytes", errors)
    sha256 = _required_text(payload.get("sha256"), f"artifact {index} sha256", errors)
    description = _optional_text(payload.get("description")) or ""
    if not role or not relative_path:
        return None
    path = Path(relative_path)
    if path.is_absolute():
        errors.append(f"Artifact {role!r} path must be relative.")
    if ".." in path.parts:
        errors.append(f"Artifact {role!r} path must not traverse parents.")
    if media_type and media_type != "application/json":
        errors.append(f"Artifact {role!r} media_type must be application/json.")
    if size_bytes is not None and size_bytes < 0:
        errors.append(f"Artifact {role!r} size must be non-negative.")
    if sha256 and not SHA256_PATTERN.match(sha256):
        errors.append(f"Artifact {role!r} has an invalid SHA-256.")
    if size_bytes is None or not sha256:
        return None
    return FemicHydrologyArtifact(
        role=role,
        relative_path=relative_path,
        schema_version=schema_version,
        media_type=media_type,
        size_bytes=size_bytes,
        sha256=sha256,
        description=description,
    )


def _resolve_manifest_path(bundle_path: Path) -> tuple[Path, Path]:
    resolved = bundle_path.expanduser().resolve()
    manifest_path = resolved
    if resolved.is_dir():
        manifest_path = resolved / FEMIC_HYDROLOGY_MANIFEST_NAME
    root = manifest_path.parent
    return root, manifest_path


def _resolve_member(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _read_json_object(path: Path | None, *, context: str) -> dict[str, object]:
    if path is None:
        raise FemicHydrologyError(f"Unable to resolve {context}.")
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FemicHydrologyError(f"Unable to read {context}: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FemicHydrologyError(f"Invalid JSON in {context}: {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise FemicHydrologyError(f"{context} must be a JSON object: {path}")
    return {str(key): value for key, value in payload.items()}


def _json_object(payload: bytes, *, context: str) -> dict[str, object]:
    try:
        parsed: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FemicHydrologyError(f"Invalid JSON in {context}: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise FemicHydrologyError(f"{context} must be a JSON object.")
    return {str(key): value for key, value in parsed.items()}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_periods(left: object, right: object) -> bool:
    if not isinstance(left, list) or not isinstance(right, list):
        return False
    if len(left) != len(right):
        return False
    try:
        return all(
            math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-12)
            for a, b in zip(left, right, strict=True)
        )
    except (TypeError, ValueError):
        return False


def _mapping(
    value: object,
    context: str,
    errors: list[str],
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        errors.append(f"{context} must be an object.")
        return {}
    return {str(key): item for key, item in value.items()}


def _list(value: object, context: str, errors: list[str]) -> list[object]:
    if not isinstance(value, list):
        errors.append(f"{context} must be a list.")
        return []
    return value


def _strings(value: object, context: str, errors: list[str]) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        errors.append(f"{context} must be a list.")
        return ()
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            errors.append(f"{context} entries must be text.")
            continue
        text = item.strip()
        if text:
            result.append(text)
    return tuple(result)


def _required_text(value: object, field_name: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"Manifest field {field_name!r} must be non-empty text.")
        return ""
    return value.strip()


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FemicHydrologyError(f"{field_name} must be non-empty text.")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _required_int(value: object, field_name: str, errors: list[str]) -> int | None:
    if isinstance(value, bool):
        errors.append(f"Manifest field {field_name!r} must be an integer.")
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        errors.append(f"Manifest field {field_name!r} must be an integer.")
        return None
    if parsed < 0:
        errors.append(f"Manifest field {field_name!r} must be non-negative.")
        return None
    return parsed


def _int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise FemicHydrologyError(f"{field_name} must be an integer.")
    try:
        return int(str(value))
    except (TypeError, ValueError) as exc:
        raise FemicHydrologyError(f"{field_name} must be an integer.") from exc


def _float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise FemicHydrologyError(f"{field_name} must be numeric.")
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise FemicHydrologyError(f"{field_name} must be numeric.") from exc
    if not math.isfinite(parsed):
        raise FemicHydrologyError(f"{field_name} must be finite.")
    return parsed


def _optional_float(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    return _float(value, field_name)


_FRAGMENT_COLUMNS = (
    "fragment_id",
    "block_id",
    "unit_id",
    "watershed_id",
    "receptor_id",
    "source",
)
_BLOCK_COLUMNS = ("block_id", "unit_id", "watershed_id", "receptor_id", "source")


def _crosswalk_rows(
    lines: list[str],
    *,
    digest: str,
) -> tuple[HydrologyCrosswalkRow, ...]:
    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        raise FemicHydrologyError("Crosswalk CSV has no header.")
    required = {"fragment_id", "block_id", "unit_id", "watershed_id"}
    if not required.issubset(reader.fieldnames):
        raise FemicHydrologyError(
            "Crosswalk CSV is missing required columns: "
            + ", ".join(sorted(required - set(reader.fieldnames)))
            + "."
        )
    rows: list[HydrologyCrosswalkRow] = []
    seen: set[tuple[str, int]] = set()
    for index, payload in enumerate(reader, start=2):
        fragment_id = _optional_int(payload.get("fragment_id"))
        block_id = _optional_int(payload.get("block_id"))
        if (fragment_id is None) == (block_id is None):
            raise FemicHydrologyError(
                f"Crosswalk row {index} must set exactly one of fragment_id/block_id."
            )
        if fragment_id is not None:
            key = ("fragment", fragment_id)
        else:
            assert block_id is not None
            key = ("block", block_id)
        if key in seen:
            raise FemicHydrologyError(f"Duplicate crosswalk support {key[0]} {key[1]}.")
        seen.add(key)
        rows.append(
            HydrologyCrosswalkRow(
                fragment_id=fragment_id,
                block_id=block_id,
                unit_id=_text(payload.get("unit_id"), f"crosswalk row {index} unit_id"),
                watershed_id=_text(
                    payload.get("watershed_id"), f"crosswalk row {index} watershed_id"
                ),
                receptor_id=_optional_text(payload.get("receptor_id")),
                notes=_optional_text(payload.get("notes")) or "",
            )
        )
    if not rows:
        raise FemicHydrologyError("Crosswalk CSV contains no mapping rows.")
    return tuple(rows)


def _crosswalk_metadata(
    path: Path | None,
    *,
    fallback_id: str,
    crosswalk_sha256: str,
) -> HydrologyCrosswalkMetadata:
    if path is None:
        return HydrologyCrosswalkMetadata(
            crosswalk_id=fallback_id,
            created_utc="",
            review_status="not_reviewed",
            reviewed_by=None,
            method="unspecified",
            source="",
            caveats=("No crosswalk review metadata was supplied.",),
        )
    payload = _read_json_object(path, context="crosswalk metadata")
    if payload.get("schema_version") != HYDROLOGY_CROSSWALK_SCHEMA:
        raise FemicHydrologyError(
            f"Unsupported crosswalk metadata schema {payload.get('schema_version')!r}."
        )
    recorded_sha = _optional_text(payload.get("crosswalk_sha256"))
    if recorded_sha is not None and recorded_sha.lower() != crosswalk_sha256.lower():
        raise FemicHydrologyError("Crosswalk metadata checksum does not match the CSV.")
    review_status = _text(payload.get("review_status"), "crosswalk review_status")
    if review_status not in HYDROLOGY_CROSSWALK_REVIEW_STATUSES:
        raise FemicHydrologyError(f"Unsupported crosswalk review status {review_status!r}.")
    reviewed_by = _optional_text(payload.get("reviewed_by"))
    if review_status == "reviewed" and reviewed_by is None:
        raise FemicHydrologyError("Reviewed crosswalk metadata requires reviewed_by.")
    return HydrologyCrosswalkMetadata(
        crosswalk_id=_text(payload.get("crosswalk_id"), "crosswalk_id"),
        created_utc=_text(payload.get("created_utc"), "crosswalk created_utc"),
        review_status=review_status,
        reviewed_by=reviewed_by,
        method=_text(payload.get("method"), "crosswalk method"),
        source=_optional_text(payload.get("source")) or "",
        caveats=_strict_strings(payload.get("caveats"), "crosswalk caveats"),
    )


def _load_dataset_support(
    dataset_root: Path,
) -> tuple[dict[int, int], set[int]]:
    fragments_path = dataset_root / "fragments.parquet"
    blocks_path = dataset_root / "blocks.parquet"
    if not fragments_path.is_file():
        raise FemicHydrologyError(f"Dataset fragments are missing: {fragments_path}")
    if not blocks_path.is_file():
        raise FemicHydrologyError(f"Dataset blocks are missing: {blocks_path}")
    try:
        fragment_frame = pd.read_parquet(fragments_path)
        block_frame = pd.read_parquet(blocks_path)
    except (OSError, ValueError) as exc:
        raise FemicHydrologyError(f"Unable to read dataset support tables: {exc}") from exc
    for column in ("fragment_id", "block_id"):
        if column not in fragment_frame.columns:
            raise FemicHydrologyError(f"fragments.parquet is missing {column!r}.")
    if "block_id" not in block_frame.columns:
        raise FemicHydrologyError("blocks.parquet is missing 'block_id'.")
    fragments: dict[int, int] = {}
    for fragment_id, block_id in zip(
        fragment_frame["fragment_id"],
        fragment_frame["block_id"],
        strict=True,
    ):
        parsed_fragment = _int(fragment_id, "fragment_id")
        parsed_block = _int(block_id, "block_id")
        if parsed_fragment in fragments:
            raise FemicHydrologyError(f"Duplicate dataset fragment {parsed_fragment}.")
        fragments[parsed_fragment] = parsed_block
    blocks: set[int] = set()
    for block_id in block_frame["block_id"]:
        parsed_block = _int(block_id, "block_id")
        if parsed_block in blocks:
            raise FemicHydrologyError(f"Duplicate dataset block {parsed_block}.")
        blocks.add(parsed_block)
    unknown_blocks = sorted(set(fragments.values()) - blocks)
    if unknown_blocks:
        raise FemicHydrologyError(
            "Dataset fragments reference unknown blocks: "
            + ", ".join(str(value) for value in unknown_blocks)
            + "."
        )
    return fragments, blocks


def _bundle_domain_ids(
    bundle: FemicHydrologyBundle,
) -> tuple[dict[str, str], set[str], set[str]]:
    domain = _bundle_payload(bundle, "domain")
    ledger = _bundle_payload(bundle, "disturbance_ledger")
    domain_watersheds = {
        _text(item.get("watershed_id"), "domain watershed_id")
        for item in _dict_list(domain.get("watersheds"), "domain watersheds")
    }
    receptors = {
        _text(item.get("receptor_id"), "domain receptor_id")
        for item in _dict_list(domain.get("receptors"), "domain receptors")
    }
    units = _dict_list(ledger.get("units"), "disturbance-ledger units")
    if not units:
        raise FemicHydrologyError(
            "FEMIC disturbance ledger has no units; cannot validate the crosswalk."
        )
    unit_to_watershed: dict[str, str] = {}
    for unit in units:
        unit_id = _text(unit.get("unit_id"), "ledger unit_id")
        watershed_id = _text(unit.get("watershed_id"), "ledger watershed_id")
        previous = unit_to_watershed.get(unit_id)
        if previous is not None and previous != watershed_id:
            raise FemicHydrologyError(f"FEMIC ledger unit {unit_id!r} has conflicting watersheds.")
        unit_to_watershed[unit_id] = watershed_id
    watersheds = domain_watersheds | set(unit_to_watershed.values())
    if not watersheds:
        raise FemicHydrologyError("FEMIC domain has no watersheds.")
    return unit_to_watershed, watersheds, receptors


def _bundle_payload(
    bundle: FemicHydrologyBundle,
    role: str,
) -> dict[str, object]:
    artifact = bundle.artifacts.get(role)
    if artifact is None:
        raise FemicHydrologyError(f"Bundle has no {role} artifact.")
    member = _resolve_member(bundle.bundle_dir, artifact.relative_path)
    return _read_json_object(member, context=f"{role} artifact")


def _dict_list(value: object, context: str) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise FemicHydrologyError(f"{context} must be a list.")
    result: list[dict[str, object]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            raise FemicHydrologyError(f"{context} entry {index} must be an object.")
        result.append({str(key): entry for key, entry in item.items()})
    return result


def _strict_strings(value: object, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise FemicHydrologyError(f"{context} must be a list of text.")
    return tuple(item.strip() for item in value if item.strip())


def _mapping_record(
    *,
    bundle: FemicHydrologyBundle,
    crosswalk: HydrologyCrosswalk,
    unit_id: str,
    watershed_id: str,
    receptor_id: str | None,
) -> dict[str, object]:
    return {
        "bundle_id": bundle.bundle_id,
        "bundle_version": bundle.bundle_version,
        "manifest_sha256": bundle.manifest_sha256,
        "crosswalk_id": crosswalk.metadata.crosswalk_id,
        "crosswalk_sha256": crosswalk.sha256,
        "unit_id": unit_id,
        "watershed_id": watershed_id,
        "receptor_id": receptor_id,
    }


def _same_mapping(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    return all(
        left.get(key) == right.get(key) for key in ("unit_id", "watershed_id", "receptor_id")
    )


def _fragment_mapping_row(
    fragment_id: int,
    block_id: int,
    record: Mapping[str, object],
) -> dict[str, object]:
    return {
        "fragment_id": fragment_id,
        "block_id": block_id,
        "unit_id": record["unit_id"],
        "watershed_id": record["watershed_id"],
        "receptor_id": record["receptor_id"],
        "source": record["source"],
    }


def _block_mapping_row(
    block_id: int,
    record: Mapping[str, object],
) -> dict[str, object]:
    return {
        "block_id": block_id,
        "unit_id": record["unit_id"],
        "watershed_id": record["watershed_id"],
        "receptor_id": record["receptor_id"],
        "source": record["source"],
    }


def _write_csv(
    path: Path,
    rows: tuple[dict[str, object], ...],
    columns: tuple[str, ...],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return _int(value, "support_id")


def _csv_mapping_rows(path: Path, kind: str) -> tuple[dict[str, object], ...]:
    if not path.is_file():
        raise FemicHydrologyError(f"Hydrology mapping CSV is missing: {path}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows: list[dict[str, object]] = []
            for payload in reader:
                if kind == "fragment":
                    rows.append(
                        {
                            "fragment_id": _int(payload.get("fragment_id"), "fragment_id"),
                            "block_id": _int(payload.get("block_id"), "block_id"),
                            "unit_id": _text(payload.get("unit_id"), "unit_id"),
                            "watershed_id": _text(payload.get("watershed_id"), "watershed_id"),
                            "receptor_id": _optional_text(payload.get("receptor_id")),
                            "source": _text(payload.get("source"), "source"),
                        }
                    )
                elif kind == "block":
                    rows.append(
                        {
                            "block_id": _int(payload.get("block_id"), "block_id"),
                            "unit_id": _text(payload.get("unit_id"), "unit_id"),
                            "watershed_id": _text(payload.get("watershed_id"), "watershed_id"),
                            "receptor_id": _optional_text(payload.get("receptor_id")),
                            "source": _text(payload.get("source"), "source"),
                        }
                    )
                else:
                    raise FemicHydrologyError(f"Unknown mapping row kind {kind!r}.")
    except OSError as exc:
        raise FemicHydrologyError(f"Unable to read hydrology mapping CSV: {exc}") from exc
    return tuple(rows)


@dataclass(frozen=True)
class _ScheduleItem:
    block_id: int
    treatment: str
    offset: int


def _schedule_source(source: Path | pd.DataFrame) -> tuple[_ScheduleItem, ...]:
    if isinstance(source, Path):
        return _load_schedule(source)
    return _schedule_from_frame(source)


def _schedule_from_frame(frame: pd.DataFrame) -> tuple[_ScheduleItem, ...]:
    required = {"block_id", "treatment", "offset"}
    missing = required - set(frame.columns)
    if missing:
        raise FemicHydrologyError(
            "Schedule is missing required columns: " + ", ".join(sorted(missing)) + "."
        )
    rows: list[_ScheduleItem] = []
    for _, row in frame.iterrows():
        rows.append(
            _ScheduleItem(
                block_id=_int(row["block_id"], "schedule block_id"),
                treatment=_text(row["treatment"], "schedule treatment"),
                offset=_int(row["offset"], "schedule offset"),
            )
        )
    return tuple(rows)


def _load_schedule(path: Path) -> tuple[_ScheduleItem, ...]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FemicHydrologyError(f"Schedule is missing: {resolved}")
    try:
        frame = pd.read_csv(resolved)
    except (OSError, ValueError) as exc:
        raise FemicHydrologyError(f"Unable to read schedule: {exc}") from exc
    required = {"block_id", "treatment", "offset"}
    missing = required - set(frame.columns)
    if missing:
        raise FemicHydrologyError(
            "Schedule is missing required columns: " + ", ".join(sorted(missing)) + "."
        )
    rows: list[_ScheduleItem] = []
    for _, row in frame.iterrows():
        rows.append(
            _ScheduleItem(
                block_id=_int(row["block_id"], "schedule block_id"),
                treatment=_text(row["treatment"], "schedule treatment"),
                offset=_int(row["offset"], "schedule offset"),
            )
        )
    return tuple(rows)


def _load_block_areas(dataset_root: Path) -> dict[int, float]:
    path = dataset_root / "blocks.parquet"
    if not path.is_file():
        raise FemicHydrologyError(f"Dataset blocks are missing: {path}")
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError) as exc:
        raise FemicHydrologyError(f"Unable to read dataset blocks: {exc}") from exc
    for column in ("block_id", "area_ha"):
        if column not in frame.columns:
            raise FemicHydrologyError(f"blocks.parquet is missing {column!r}.")
    areas: dict[int, float] = {}
    for block_id, area in zip(frame["block_id"], frame["area_ha"], strict=True):
        areas[_int(block_id, "block_id")] = _float(area, "block area_ha")
    return areas


def _watershed_areas(bundle: FemicHydrologyBundle) -> dict[str, float]:
    domain = _bundle_payload(bundle, "domain")
    areas: dict[str, float] = {}
    for item in _dict_list(domain.get("watersheds"), "domain watersheds"):
        watershed_id = _text(item.get("watershed_id"), "domain watershed_id")
        raw_area = item.get("area_km2")
        if raw_area is None:
            continue
        area_km2 = _float(raw_area, "watershed area_km2")
        if area_km2 > 0:
            areas[watershed_id] = area_km2 * 100.0
    return areas


def _response_scenarios(
    bundle: FemicHydrologyBundle,
) -> tuple[tuple[str, dict[str, float]], ...]:
    surface = _bundle_payload(bundle, "response_surface")
    scenarios: list[tuple[str, dict[str, float]]] = []
    for item in _dict_list(surface.get("scenarios"), "response scenarios"):
        name = _text(item.get("name"), "scenario name")
        covariates = item.get("covariates")
        if not isinstance(covariates, Mapping):
            raise FemicHydrologyError(f"Scenario {name!r} has no covariates object.")
        scenarios.append(
            (
                name,
                {
                    str(key): _float(value, f"scenario {name} {key}")
                    for key, value in covariates.items()
                },
            )
        )
    if not scenarios:
        raise FemicHydrologyError("Response surface has no scenarios.")
    return tuple(scenarios)


def _response_surface_rows(
    bundle: FemicHydrologyBundle,
) -> dict[tuple[str, float], dict[str, object]]:
    surface = _bundle_payload(bundle, "response_surface")
    rows: dict[tuple[str, float], dict[str, object]] = {}
    for item in _dict_list(surface.get("rows"), "response rows"):
        scenario = _text(item.get("scenario_name"), "response scenario_name")
        period = _float(item.get("return_period"), "response return_period")
        rows[(scenario, period)] = item
    if not rows:
        raise FemicHydrologyError("Response surface has no rows.")
    return rows


def _select_scenario(
    scenarios: tuple[tuple[str, dict[str, float]], ...],
    features: Mapping[str, float],
    tolerance: float,
) -> tuple[str, dict[str, float]] | None:
    best: tuple[float, str, dict[str, float]] | None = None
    for name, covariates in scenarios:
        if "harvest_fraction" not in covariates:
            continue
        if any(key not in features for key in covariates):
            continue
        distance = max(abs(float(features[key]) - value) for key, value in covariates.items())
        if distance <= tolerance and (best is None or distance < best[0]):
            best = (distance, name, covariates)
    if best is None:
        return None
    return best[1], best[2]


def _schedule_digest(schedule_source: Path | pd.DataFrame) -> str:
    """Return the schedule digest used by the exposure binding."""
    if isinstance(schedule_source, Path):
        return _sha256_file(schedule_source)
    return hashlib.sha256(schedule_source.to_csv(index=False).encode("utf-8")).hexdigest()


def _exposure_screen_features(
    exposure: HydrologyExposure,
    watershed_id: str,
    period: int,
    watershed_area_ha: float,
) -> dict[str, float]:
    """Return raw and derived exposure features for one watershed/period."""
    features = exposure.features_for(watershed_id, period)
    area_km2 = watershed_area_ha / 100.0
    features["road_built_density_km_per_km2"] = features["road_built_km"] / area_km2
    features["road_used_density_km_per_km2"] = features["road_used_km"] / area_km2
    features["road_decommissioned_density_km_per_km2"] = (
        features["road_decommissioned_km"] / area_km2
    )
    features["culvert_exposure_per_km2"] = features["culvert_exposed_count"] / area_km2
    return features


def _exposure_is_used(
    scenarios: tuple[tuple[str, dict[str, float]], ...],
    exposure_names: set[str],
) -> bool:
    """Return whether any response scenario names an exposure feature."""
    return any(set(covariates) & exposure_names for _name, covariates in scenarios)


def _optional_bundle_payload(
    bundle: FemicHydrologyBundle,
    role: str,
) -> dict[str, object] | None:
    if role not in bundle.artifacts:
        return None
    return _bundle_payload(bundle, role)


def _failure_map(value: object, context: str) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise FemicHydrologyError(f"{context} must be an object.")
    result: dict[str, list[str]] = {}
    for key, item in value.items():
        if not isinstance(item, list):
            raise FemicHydrologyError(f"{context} values must be lists.")
        reasons = [str(entry) for entry in item if isinstance(entry, str) and entry.strip()]
        if reasons:
            result[str(key)] = reasons
    return result


def _fit_map(value: object, context: str) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise FemicHydrologyError(f"{context} must be an object.")
    result: dict[str, list[str]] = {}
    for key, item in value.items():
        if not isinstance(item, list):
            raise FemicHydrologyError(f"{context} values must be lists.")
        fits = [str(entry) for entry in item if isinstance(entry, str) and entry.strip()]
        if fits:
            result[str(key)] = fits
    return result


def _optional_bool(value: object, field_name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise FemicHydrologyError(f"{field_name} must be boolean.")
    return value


def _evidence_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _int(value, field_name)
