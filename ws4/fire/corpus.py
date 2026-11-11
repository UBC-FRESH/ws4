"""Public fire-corpus contracts, candidate inventory, and admission gate.

The corpus is deliberately tiered. Hourly/FBP depth cases and daily CFSDS breadth cases are
not interchangeable, and model-to-model evidence is never counted as an observed fire.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

from .fuel import FireFuelError

DEPTH_MINIMUM: Final[int] = 3
BREADTH_MINIMUM: Final[int] = 20


class CorpusTier(StrEnum):
    """Evidence tier for a fire case.

    Attributes
    ----------
    DEPTH
        Hourly weather, observed perimeter, FBP fuel, terrain, and ignition.
    BREADTH
        Daily CFSDS progression and daily weather with documented assumptions.
    MODEL_ONLY
        Model output, not an observed fire.
    """

    DEPTH = "hourly_fbp"
    BREADTH = "daily_cfsds"
    MODEL_ONLY = "model_only"


class CorpusStatus(StrEnum):
    """Admission status for a fire case.

    Attributes
    ----------
    READY
        All required inputs are present.
    READY_WITH_LIMIT
        Usable for the corpus, with a documented limitation.
    CANDIDATE
        Potentially usable, but inputs or provenance are incomplete.
    BLOCKED
        Cannot enter the corpus without a missing adapter or dataset.
    REJECTED
        Duplicate or otherwise inadmissible.
    MODEL_ONLY
        Model output, not observed evidence.
    """

    READY = "ready"
    READY_WITH_LIMIT = "ready_with_limit"
    CANDIDATE = "candidate"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    MODEL_ONLY = "model_only"


@dataclass(frozen=True)
class CorpusInputs:
    """Boolean record of the inputs available for a fire case.

    Parameters
    ----------
    perimeter : bool, optional
        Observed or satellite-derived perimeter is available.
    hourly_weather : bool, optional
        Hourly weather is available.
    daily_weather : bool, optional
        Daily weather is available.
    ignition : bool, optional
        Ignition location/time is observed or reconstructed.
    fuel : bool, optional
        A compatible fuel map is available.
    terrain : bool, optional
        Terrain is available.
    provenance : bool, optional
        Source and processing provenance are recorded.
    licence_documented : bool, optional
        Redistribution terms are documented.
    """

    perimeter: bool = False
    hourly_weather: bool = False
    daily_weather: bool = False
    ignition: bool = False
    fuel: bool = False
    terrain: bool = False
    provenance: bool = False
    licence_documented: bool = False

    def missing_for(self, tier: CorpusTier) -> tuple[str, ...]:
        """Return missing required inputs for a tier.

        Parameters
        ----------
        tier : CorpusTier
            Evidence tier.

        Returns
        -------
        tuple of str
            Missing input names. Model-only cases require no observed inputs.
        """
        required: tuple[str, ...]
        if tier is CorpusTier.DEPTH:
            required = (
                "perimeter",
                "hourly_weather",
                "ignition",
                "fuel",
                "terrain",
                "provenance",
                "licence_documented",
            )
        elif tier is CorpusTier.BREADTH:
            required = (
                "perimeter",
                "daily_weather",
                "fuel",
                "terrain",
                "provenance",
                "licence_documented",
            )
        else:
            required = ()
        return tuple(name for name in required if not bool(getattr(self, name)))


@dataclass(frozen=True)
class FireCase:
    """One fire-corpus candidate or admitted case.

    Parameters
    ----------
    case_id : str
        Stable identifier.
    name : str
        Human-readable event name.
    region : str
        Region or jurisdiction.
    year : int
        Fire year.
    tier : CorpusTier
        Evidence tier.
    status : CorpusStatus
        Admission status.
    source : str
        Data source.
    licence : str
        Licence or redistribution note.
    inputs : CorpusInputs
        Available inputs.
    notes : str
        Known limitations.
    duplicate_of : str or None, optional
        Case identifier if this is the same event as another case.
    """

    case_id: str
    name: str
    region: str
    year: int
    tier: CorpusTier
    status: CorpusStatus
    source: str
    licence: str
    inputs: CorpusInputs
    notes: str
    duplicate_of: str | None = None

    def __post_init__(self) -> None:
        """Validate case metadata and status consistency."""
        for field_name in ("case_id", "name", "region", "source", "licence", "notes"):
            if not str(getattr(self, field_name)).strip():
                raise FireFuelError(f"{field_name} must be non-empty")
        if not 1800 <= self.year <= 2100:
            raise FireFuelError("year must be between 1800 and 2100")
        if not isinstance(self.tier, CorpusTier):
            raise FireFuelError("tier must be a CorpusTier")
        if not isinstance(self.status, CorpusStatus):
            raise FireFuelError("status must be a CorpusStatus")
        if self.tier is CorpusTier.MODEL_ONLY and self.status is not CorpusStatus.MODEL_ONLY:
            raise FireFuelError("model-only tier requires model-only status")
        if self.status is CorpusStatus.MODEL_ONLY and self.tier is not CorpusTier.MODEL_ONLY:
            raise FireFuelError("model-only status requires model-only tier")
        if self.status is CorpusStatus.REJECTED and self.duplicate_of is None:
            raise FireFuelError("rejected cases must name the original case")
        if self.duplicate_of is not None and self.status is not CorpusStatus.REJECTED:
            raise FireFuelError("duplicate cases must be rejected")
        if self.status is CorpusStatus.READY_WITH_LIMIT and not self.notes.strip():
            raise FireFuelError("limited cases must document the limitation")

    @property
    def missing_inputs(self) -> tuple[str, ...]:
        """Return missing inputs for this case's tier.

        Returns
        -------
        tuple of str
            Missing required input names.
        """
        return self.inputs.missing_for(self.tier)

    @property
    def independent(self) -> bool:
        """Return whether the case is an independent observed event.

        Returns
        -------
        bool
            True when not a duplicate or rejected case.
        """
        return self.duplicate_of is None and self.status is not CorpusStatus.REJECTED

    @property
    def ready(self) -> bool:
        """Return whether the case is admitted in any form.

        Returns
        -------
        bool
            True for ready, limited-ready, or model-only cases.
        """
        return self.status in (
            CorpusStatus.READY,
            CorpusStatus.READY_WITH_LIMIT,
            CorpusStatus.MODEL_ONLY,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the case as a JSON-serializable mapping.

        Returns
        -------
        dict
            Case fields plus the missing-input list.
        """
        return {
            "case_id": self.case_id,
            "name": self.name,
            "region": self.region,
            "year": self.year,
            "tier": self.tier.value,
            "status": self.status.value,
            "source": self.source,
            "licence": self.licence,
            "inputs": self.inputs.__dict__.copy(),
            "missing_inputs": self.missing_inputs,
            "notes": self.notes,
            "duplicate_of": self.duplicate_of,
            "independent": self.independent,
            "ready": self.ready,
        }


CASES: Final[tuple[FireCase, ...]] = (
    FireCase(
        case_id="dogrib-2b",
        name="Dogrib RWF085 Scenario 2b",
        region="Northwest Territories, Canada",
        year=2001,
        tier=CorpusTier.DEPTH,
        status=CorpusStatus.READY_WITH_LIMIT,
        source="Prometheus sample archive (Dogrib RWF085)",
        licence="Prometheus sample terms; redistribution review required",
        inputs=CorpusInputs(
            perimeter=True,
            hourly_weather=True,
            ignition=True,
            fuel=True,
            terrain=True,
            provenance=True,
            licence_documented=False,
        ),
        notes=(
            "Existing P157 fixture with observed start perimeter and hourly patches. "
            "Licence-cleared redistribution is not established."
        ),
    ),
    FireCase(
        case_id="hay-river-2023-320",
        name="Hay River / K'atl'odeeche 2023_320",
        region="South Slave, Northwest Territories, Canada",
        year=2023,
        tier=CorpusTier.DEPTH,
        status=CorpusStatus.READY_WITH_LIMIT,
        source="CFSDS 2023_320; ECCC Hay River 2202402; FireSTARR 2023 fuel; NRCan DEM",
        licence="Open government data; verify third-party fuel terms",
        inputs=CorpusInputs(
            perimeter=True,
            hourly_weather=True,
            daily_weather=True,
            ignition=True,
            fuel=True,
            terrain=True,
            provenance=True,
            licence_documented=True,
        ),
        notes=(
            "Existing P161 fixture. Daily CFSDS weather is expanded to hourly; point ignition "
            "is reconstructed; the full event saturates the burnable domain."
        ),
    ),
    FireCase(
        case_id="cfsds-2023-321-daily",
        name="Enterprise / Hay River 2023_321 daily candidate",
        region="South Slave, Northwest Territories, Canada",
        year=2023,
        tier=CorpusTier.BREADTH,
        status=CorpusStatus.CANDIDATE,
        source="CFSDS 2023_321; FireSTARR 2023 fuel; NRCan DEM",
        licence="Open government data; fuel terms to verify",
        inputs=CorpusInputs(
            perimeter=True,
            daily_weather=True,
            fuel=True,
            terrain=True,
            provenance=True,
            licence_documented=True,
        ),
        notes=(
            "Daily candidate not yet acquired. First-burn ignition must be reconstructed; "
            "fuel is year-limited and requires a documented crosswalk."
        ),
    ),
    FireCase(
        case_id="cfsds-2023-320-daily",
        name="Hay River 2023_320 daily duplicate",
        region="South Slave, Northwest Territories, Canada",
        year=2023,
        tier=CorpusTier.BREADTH,
        status=CorpusStatus.REJECTED,
        source="CFSDS 2023_320 daily grids",
        licence="Open government data",
        inputs=CorpusInputs(
            perimeter=True,
            daily_weather=True,
            fuel=True,
            terrain=True,
            provenance=True,
            licence_documented=True,
        ),
        notes="Same event as hay-river-2023-320; not an independent breadth case.",
        duplicate_of="hay-river-2023-320",
    ),
    FireCase(
        case_id="wildfireav-us",
        name="WildfireAV US fires",
        region="Western United States",
        year=2020,
        tier=CorpusTier.DEPTH,
        status=CorpusStatus.BLOCKED,
        source="WildfireAV event archive",
        licence="Source terms vary by dataset; review required",
        inputs=CorpusInputs(
            perimeter=True,
            hourly_weather=True,
            terrain=True,
            provenance=True,
            licence_documented=False,
        ),
        notes=(
            "LANDFIRE FBFM40 fuels are not Canadian FBP. A separate US fuel/growth adapter "
            "and licensing review are required before admission."
        ),
    ),
    FireCase(
        case_id="firestarr-model-only",
        name="FireSTARR model output",
        region="Model domain",
        year=2023,
        tier=CorpusTier.MODEL_ONLY,
        status=CorpusStatus.MODEL_ONLY,
        source="FireSTARR simulation",
        licence="Model output; source terms apply",
        inputs=CorpusInputs(provenance=True),
        notes="Model-to-model evidence only; not an observed fire.",
    ),
    FireCase(
        case_id="burnp3-model-only",
        name="BurnP3 model output",
        region="Model domain",
        year=2023,
        tier=CorpusTier.MODEL_ONLY,
        status=CorpusStatus.MODEL_ONLY,
        source="BurnP3 simulation",
        licence="Model output; source terms apply",
        inputs=CorpusInputs(provenance=True),
        notes="Model-to-model evidence only; not an observed fire.",
    ),
)


@dataclass(frozen=True)
class CorpusGate:
    """Admission gate result for the observed-fire corpus.

    Parameters
    ----------
    depth_ready : int
        Independent fully ready depth cases.
    depth_ready_with_limit : int
        Independent depth cases admitted with a documented limit.
    breadth_ready : int
        Independent fully ready breadth cases.
    breadth_ready_with_limit : int
        Independent breadth cases admitted with a documented limit.
    """

    depth_ready: int
    depth_ready_with_limit: int
    breadth_ready: int
    breadth_ready_with_limit: int

    @property
    def status(self) -> Literal["pass", "blocked"]:
        """Return whether the corpus meets the minimum size.

        Returns
        -------
        str
            ``pass`` or ``blocked``.
        """
        if self.depth_ready >= DEPTH_MINIMUM and self.breadth_ready >= BREADTH_MINIMUM:
            return "pass"
        return "blocked"

    def to_dict(self) -> dict[str, object]:
        """Return the gate as a JSON-serializable mapping.

        Returns
        -------
        dict
            Counts, minimums, status, and reason.
        """
        reason = (
            "Corpus gate passed."
            if self.status == "pass"
            else (
                f"Need {DEPTH_MINIMUM} fully ready depth cases and {BREADTH_MINIMUM} fully "
                f"ready breadth cases; have {self.depth_ready} and {self.breadth_ready}."
            )
        )
        return {
            "status": self.status,
            "reason": reason,
            "depth_ready": self.depth_ready,
            "depth_ready_with_limit": self.depth_ready_with_limit,
            "depth_minimum": DEPTH_MINIMUM,
            "breadth_ready": self.breadth_ready,
            "breadth_ready_with_limit": self.breadth_ready_with_limit,
            "breadth_minimum": BREADTH_MINIMUM,
        }


def validate_registry(cases: tuple[FireCase, ...] = CASES) -> None:
    """Validate the corpus registry.

    Parameters
    ----------
    cases : tuple of FireCase, optional
        Registry to validate.

    Raises
    ------
    FireFuelError
        If identifiers duplicate, a ready case lacks required inputs, or a duplicate is unknown.
    """
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise FireFuelError("case_id values must be unique")
    known = set(ids)
    for case in cases:
        if case.status is CorpusStatus.READY and case.missing_inputs:
            raise FireFuelError(f"ready case {case.case_id!r} is missing {case.missing_inputs!r}")
        if case.duplicate_of is not None and case.duplicate_of not in known:
            raise FireFuelError(f"unknown duplicate_of {case.duplicate_of!r}")
        if case.duplicate_of == case.case_id:
            raise FireFuelError("a case cannot duplicate itself")


def corpus_gate(cases: tuple[FireCase, ...] = CASES) -> CorpusGate:
    """Return the observed-corpus admission gate.

    Parameters
    ----------
    cases : tuple of FireCase, optional
        Registry to evaluate.

    Returns
    -------
    CorpusGate
        Counts and pass/blocked status.
    """
    independent = [case for case in cases if case.independent]
    depth = [case for case in independent if case.tier is CorpusTier.DEPTH]
    breadth = [case for case in independent if case.tier is CorpusTier.BREADTH]
    return CorpusGate(
        depth_ready=sum(case.status is CorpusStatus.READY for case in depth),
        depth_ready_with_limit=sum(case.status is CorpusStatus.READY_WITH_LIMIT for case in depth),
        breadth_ready=sum(case.status is CorpusStatus.READY for case in breadth),
        breadth_ready_with_limit=sum(
            case.status is CorpusStatus.READY_WITH_LIMIT for case in breadth
        ),
    )


def manifest(cases: tuple[FireCase, ...] = CASES) -> dict[str, object]:
    """Return the corpus manifest.

    Parameters
    ----------
    cases : tuple of FireCase, optional
        Registry to summarize.

    Returns
    -------
    dict
        Tier/status counts, gate result, independent cases, and gaps.
    """
    validate_registry(cases)
    status_counts = Counter(case.status.value for case in cases)
    tier_counts = Counter(case.tier.value for case in cases)
    gate = corpus_gate(cases)
    gaps = {
        status.value: sorted(case.case_id for case in cases if case.status is status)
        for status in CorpusStatus
        if any(case.status is status for case in cases)
    }
    return {
        "case_count": len(cases),
        "independent_case_count": sum(case.independent for case in cases),
        "tier_counts": dict(sorted(tier_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "gate": gate.to_dict(),
        "gaps": gaps,
        "cases": [case.to_dict() for case in cases],
    }
