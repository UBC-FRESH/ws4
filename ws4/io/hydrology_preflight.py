"""Fail-closed preflight for the FEMIC hydrology consumer.

The preflight is orchestration over the existing bundle validator, readiness
assessment, crosswalk loader, and mapping function. It does not add a second
validator, run a schedule, or write files.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .hydrology import (
    HYDROLOGY_READINESS_POLICIES,
    FemicHydrologyBundle,
    FemicHydrologyError,
    HydrologyMapping,
    assess_femic_hydrology_readiness,
    bundle_pin,
    enforce_hydrology_readiness,
    load_hydrology_crosswalk,
    map_femic_hydrology_to_dataset,
)

HYDROLOGY_PREFLIGHT_SCHEMA = "ws4.hydrology.preflight.v1"
DEFAULT_HYDROLOGY_PREFLIGHT_POLICY = "require_reviewed"


@dataclass(frozen=True)
class HydrologyPreflight:
    """Joint readiness report for a bundle, crosswalk, and dataset.

    Attributes
    ----------
    generated_utc : str
        Report timestamp.
    policy : str
        Readiness policy applied by the report.
    bundle : dict[str, object]
        Stable bundle pin.
    readiness : dict[str, object]
        Producer evidence report.
    mapping : dict[str, object] | None
        Mapping identity and coverage, when a crosswalk was supplied.
    screening_ready : bool
        True only when every required condition passed.
    blocking_reasons : tuple[str, ...]
        Conditions that prevent screening.
    warnings : tuple[str, ...]
        Non-fatal observations.
    caveats : tuple[str, ...]
        Screening-only and evidence caveats.
    """

    generated_utc: str
    policy: str
    bundle: dict[str, object]
    readiness: dict[str, object]
    mapping: dict[str, object] | None
    screening_ready: bool
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the preflight report as a JSON-serializable mapping.

        Returns
        -------
        dict[str, object]
            Schema, bundle, readiness, mapping, policy, decision, and caveats.
        """
        return {
            "schema_version": HYDROLOGY_PREFLIGHT_SCHEMA,
            "generated_utc": self.generated_utc,
            "policy": self.policy,
            "bundle": self.bundle,
            "readiness": self.readiness,
            "mapping": self.mapping,
            "screening_ready": self.screening_ready,
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
            "caveats": list(self.caveats),
        }


def build_hydrology_preflight(
    bundle: FemicHydrologyBundle,
    *,
    dataset_dir: Path | None = None,
    crosswalk_path: Path | None = None,
    crosswalk_metadata_path: Path | None = None,
    policy: str = DEFAULT_HYDROLOGY_PREFLIGHT_POLICY,
    allow_partial: bool = False,
    generated_utc: str | None = None,
) -> HydrologyPreflight:
    """Build a fail-closed preflight report.

    Parameters
    ----------
    bundle : FemicHydrologyBundle
        Validated and pinned bundle.
    dataset_dir : Path | None, optional
        Compiled WS4 dataset. Required when ``crosswalk_path`` is supplied.
    crosswalk_path : Path | None, optional
        Explicit crosswalk CSV. Without it, the report cannot say that screening
        is safe.
    crosswalk_metadata_path : Path | None, optional
        Crosswalk review metadata JSON.
    policy : str, optional
        Readiness policy. Defaults to ``require_reviewed``.
    allow_partial : bool, optional
        Allow the mapping to be built with gaps. The gaps still block
        ``screening_ready``.
    generated_utc : str | None, optional
        Report timestamp; defaults to the current UTC time.

    Returns
    -------
    HydrologyPreflight
        Bundle, readiness, mapping, and the joint screening decision.

    Raises
    ------
    FemicHydrologyError
        If the policy is unknown, a crosswalk is supplied without a dataset, or
        a supplied crosswalk or dataset is malformed.
    """
    if policy not in HYDROLOGY_READINESS_POLICIES:
        raise FemicHydrologyError(f"Unsupported readiness policy {policy!r}.")
    if crosswalk_path is not None and dataset_dir is None:
        raise FemicHydrologyError("Crosswalk preflight requires a compiled dataset.")
    timestamp = generated_utc or datetime.now(UTC).isoformat()
    readiness = assess_femic_hydrology_readiness(bundle)
    blocking: list[str] = []
    warnings: list[str] = list(readiness.warnings)
    try:
        enforce_hydrology_readiness(readiness, policy=policy)
    except FemicHydrologyError as exc:
        blocking.append(f"Readiness policy blocked the bundle: {exc}")

    mapping_summary: dict[str, object] | None = None
    if crosswalk_path is None:
        blocking.append(
            "No explicit crosswalk was supplied; screening requires a reviewed mapping."
        )
    else:
        assert dataset_dir is not None
        try:
            crosswalk = load_hydrology_crosswalk(
                crosswalk_path,
                metadata_path=crosswalk_metadata_path,
            )
            mapping = map_femic_hydrology_to_dataset(
                dataset_dir,
                bundle,
                crosswalk,
                allow_partial=allow_partial,
                generated_utc=timestamp,
            )
        except FemicHydrologyError as exc:
            blocking.append(f"Crosswalk mapping failed: {exc}")
        else:
            mapping_summary = _mapping_summary(mapping)
            warnings.extend(mapping.warnings)
            if mapping.review_status != "reviewed" and policy != "allow_provisional":
                blocking.append(
                    "Crosswalk review status is "
                    f"{mapping.review_status!r}; the selected policy requires "
                    "'reviewed'."
                )
            unmapped_fragments = _coverage_ids(mapping.coverage.get("unmapped_fragments"))
            unmapped_blocks = _coverage_ids(mapping.coverage.get("unmapped_blocks"))
            if unmapped_fragments or unmapped_blocks:
                blocking.append(
                    "Mapping is incomplete: "
                    f"{len(unmapped_fragments)} fragment(s) and "
                    f"{len(unmapped_blocks)} block(s) are unmapped."
                )

    reasons = _unique(blocking)
    return HydrologyPreflight(
        generated_utc=timestamp,
        policy=policy,
        bundle=bundle_pin(bundle),
        readiness=readiness.to_dict(),
        mapping=mapping_summary,
        screening_ready=not reasons,
        blocking_reasons=reasons,
        warnings=_unique(warnings),
        caveats=(
            "Preflight checks bundle structure, readiness evidence, and explicit "
            "crosswalk coverage; it is not a hydrologic validation.",
            "A ready preflight is not a hydrologist review, a regulatory flood "
            "map, or an operational safety determination.",
            "No schedule is screened and no FEMIC model is re-run.",
        ),
    )


def _mapping_summary(mapping: HydrologyMapping) -> dict[str, object]:
    """Return the stable subset of a mapping suitable for the preflight report."""
    return {
        "mapping_id": mapping.mapping_id,
        "crosswalk_id": mapping.crosswalk_id,
        "crosswalk_sha256": mapping.crosswalk_sha256,
        "review_status": mapping.review_status,
        "fragment_count": len(mapping.fragments),
        "block_count": len(mapping.blocks),
        "coverage": dict(mapping.coverage),
        "warnings": list(mapping.warnings),
    }


def _coverage_ids(value: object) -> list[int]:
    """Return integer IDs from a coverage value, ignoring malformed entries."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, int) and not isinstance(item, bool)]


def _unique(items: Sequence[str]) -> tuple[str, ...]:
    """Return non-empty strings in first-seen order."""
    return tuple(dict.fromkeys(item for item in items if item))
