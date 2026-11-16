"""Explicit stand-level treatment prescriptions for BC VRI stands.

The prescription must name a post-treatment FBP fuel type. The FFS deltas are declared
inputs, not an automatic fuel-type conversion. No prescription is inferred.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from .fbp import canonical_fuel_type
from .vri import FbpFuelAssignment, VriStand, map_vri_stand

#: Median FFS treatment effects, percent change.
FFS_TREATMENT_CHANGES: Final[dict[str, dict[str, float]]] = {
    "thin-only": {
        "canopy_cover_pct": -10.8,
        "basal_area_pct": -28.5,
        "surface_fuel_pct": 50.6,
    },
    "burn-only": {
        "canopy_cover_pct": -3.1,
        "basal_area_pct": -0.8,
        "surface_fuel_pct": -45.2,
    },
    "thin-burn": {
        "canopy_cover_pct": -22.9,
        "basal_area_pct": -29.0,
        "surface_fuel_pct": -3.5,
    },
}

_CONIFER: Final[frozenset[str]] = frozenset(
    {
        "HW",
        "FD",
        "PL",
        "PY",
        "PW",
        "PA",
        "PJ",
        "PF",
        "SX",
        "SW",
        "SE",
        "SS",
        "BL",
        "BA",
        "BG",
        "HM",
        "CW",
        "YC",
        "LT",
        "TW",
    }
)
_DECIDUOUS: Final[frozenset[str]] = frozenset({"AT", "AC", "DR", "EP", "MB", "QA"})


class TreatmentPrescriptionError(ValueError):
    """Raised when a treatment prescription or VRI stand is invalid."""


@dataclass(frozen=True)
class TreatmentPrescription:
    """An explicit stand treatment prescription.

    Parameters
    ----------
    name : str
        Treatment label.
    fuel_type : str
        Post-treatment FBP fuel type.
    canopy_cover_pct : float
        Declared percent change in canopy cover.
    basal_area_pct : float
        Declared percent change in live basal area.
    surface_fuel_pct : float
        Declared percent change in surface fuel.
    source : str
        Evidence source for the changes.
    """

    name: str
    fuel_type: str
    canopy_cover_pct: float
    basal_area_pct: float
    surface_fuel_pct: float
    source: str

    def __post_init__(self) -> None:
        """Validate and normalize the prescription."""
        if not self.name.strip() or not self.source.strip():
            raise TreatmentPrescriptionError("name and source must be non-empty")
        fuel = canonical_fuel_type(self.fuel_type)
        for field in ("canopy_cover_pct", "basal_area_pct", "surface_fuel_pct"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TreatmentPrescriptionError(f"{field} must be a number")
            if not math.isfinite(float(value)):
                raise TreatmentPrescriptionError(f"{field} must be finite")
        object.__setattr__(self, "fuel_type", fuel)


@dataclass(frozen=True)
class StandTreatmentPreview:
    """Before/after fuel assignments for one stand prescription.

    Parameters
    ----------
    stand_id : str
        VRI stand identifier.
    pre_fuel_type : str or None
        FBP fuel type before treatment.
    post_fuel_type : str or None
        FBP fuel type after treatment.
    pre_crown_closure_pct : float
        Crown closure before treatment.
    post_crown_closure_pct : float
        Crown closure after treatment.
    basal_area_pct : float
        Declared live basal-area change.
    surface_fuel_pct : float
        Declared surface-fuel change.
    prescription : TreatmentPrescription
        Applied prescription.
    pre_assignment : FbpFuelAssignment
        Full pre-treatment mapping.
    post_assignment : FbpFuelAssignment
        Full post-treatment mapping.
    """

    stand_id: str
    pre_fuel_type: str | None
    post_fuel_type: str | None
    pre_crown_closure_pct: float
    post_crown_closure_pct: float
    basal_area_pct: float
    surface_fuel_pct: float
    prescription: TreatmentPrescription
    pre_assignment: FbpFuelAssignment
    post_assignment: FbpFuelAssignment

    def to_dict(self) -> dict[str, object]:
        """Return the preview as a JSON-serializable mapping.

        Returns
        -------
        dict
            Stand, fuel, closure, declared changes, and both assignments.
        """
        return {
            "stand_id": self.stand_id,
            "pre_fuel_type": self.pre_fuel_type,
            "post_fuel_type": self.post_fuel_type,
            "pre_crown_closure_pct": self.pre_crown_closure_pct,
            "post_crown_closure_pct": self.post_crown_closure_pct,
            "basal_area_pct": self.basal_area_pct,
            "surface_fuel_pct": self.surface_fuel_pct,
            "prescription": {
                "name": self.prescription.name,
                "fuel_type": self.prescription.fuel_type,
                "source": self.prescription.source,
            },
            "pre_assignment": self.pre_assignment.to_dict(),
            "post_assignment": self.post_assignment.to_dict(),
        }


def prescription_from_ffs(treatment: str, *, fuel_type: str) -> TreatmentPrescription:
    """Build an explicit prescription from median FFS changes.

    Parameters
    ----------
    treatment : str
        FFS treatment label: ``thin-only``, ``burn-only``, or ``thin-burn``.
    fuel_type : str
        Post-treatment FBP fuel type selected by the caller.

    Returns
    -------
    TreatmentPrescription
        Prescription with declared FFS medians.

    Raises
    ------
    KeyError
        If the treatment label is unknown.
    """
    if treatment not in FFS_TREATMENT_CHANGES:
        raise KeyError(f"unknown FFS treatment: {treatment!r}")
    changes = FFS_TREATMENT_CHANGES[treatment]
    return TreatmentPrescription(
        name=treatment,
        fuel_type=fuel_type,
        canopy_cover_pct=changes["canopy_cover_pct"],
        basal_area_pct=changes["basal_area_pct"],
        surface_fuel_pct=changes["surface_fuel_pct"],
        source="National Fire and Fire Surrogate study, RDS-2016-0009",
    )


def apply_stand_prescription(
    stand: VriStand,
    prescription: TreatmentPrescription,
) -> StandTreatmentPreview:
    """Apply a stand prescription and map both fuel states.

    Parameters
    ----------
    stand : VriStand
        Pre-treatment VRI stand.
    prescription : TreatmentPrescription
        Explicit treatment prescription.

    Returns
    -------
    StandTreatmentPreview
        Before/after assignments and declared changes.
    """
    pre_assignment = map_vri_stand(stand)
    closure = stand.crown_closure_percent * (1.0 + prescription.canopy_cover_pct / 100.0)
    post_stand = replace(
        stand,
        crown_closure_percent=max(0.0, min(100.0, closure)),
        fuel_type=prescription.fuel_type,
    )
    post_assignment = map_vri_stand(post_stand)
    return StandTreatmentPreview(
        stand_id=stand.stand_id,
        pre_fuel_type=pre_assignment.fuel_type,
        post_fuel_type=post_assignment.fuel_type,
        pre_crown_closure_pct=stand.crown_closure_percent,
        post_crown_closure_pct=post_stand.crown_closure_percent,
        basal_area_pct=prescription.basal_area_pct,
        surface_fuel_pct=prescription.surface_fuel_pct,
        prescription=prescription,
        pre_assignment=pre_assignment,
        post_assignment=post_assignment,
    )


def stand_from_vri_feature(feature: dict[str, object]) -> VriStand | None:
    """Build a VRI stand from one WFS feature.

    Parameters
    ----------
    feature : dict
        GeoJSON feature with VRI properties.

    Returns
    -------
    VriStand or None
        Stand when the feature has complete forest attributes; otherwise None.
    """
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        return None
    if properties.get("BCLCS_LEVEL_1") != "V":
        return None
    species = str(properties.get("SPECIES_CD_1") or "").strip().upper()
    if species not in _CONIFER and species not in _DECIDUOUS:
        return None
    try:
        pct = float(properties["SPECIES_PCT_1"])
        closure = float(properties["CROWN_CLOSURE"])
        height = float(properties["PROJ_HEIGHT_1"])
        age = int(float(properties["PROJ_AGE_1"]))
        stand_id = str(properties["FEATURE_ID"])
    except (KeyError, TypeError, ValueError):
        return None
    conifer = pct / 100.0 if species in _CONIFER else 0.0
    deciduous = pct / 100.0 if species in _DECIDUOUS else 0.0
    return VriStand(
        stand_id=stand_id,
        leading_species=species,
        conifer_fraction=conifer,
        deciduous_fraction=deciduous,
        crown_closure_percent=closure,
        age_years=age,
        height_m=height,
        land_cover="forest",
    )
