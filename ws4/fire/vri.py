"""Map a VRI-style stand description to an FBP fuel type with provenance.

VRI attributes are an inventory description, not a fuel model. This module makes the
mapping decision explicit: every assignment names the rule, version, source fields, and
confidence, and an unknown forest description raises instead of silently choosing a type.

The rules are a WS4 modelling decision. They are deterministic and documented so a caller
can audit or replace them without changing the FBP kernel.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import pandas as pd

from .fbp import canonical_fuel_type
from .fuel import FireFuelError

#: The VRI-to-FBP mapping version recorded on every assignment.
VRI_FBP_VERSION: Final[str] = "ws4.vri-fbp.v1"

_LAND_COVER_ALIASES: Final[dict[str, str]] = {
    "": "forest",
    "forest": "forest",
    "forested": "forest",
    "non-forest": "non-forest",
    "nonforest": "non-forest",
    "non_forest": "non-forest",
    "water": "water",
    "urban": "urban",
    "grass": "grass",
    "grassland": "grass",
    "range": "grass",
    "shrub": "shrub",
    "shrubland": "shrub",
    "slash": "slash",
    "wetland": "wetland",
    "rock": "rock",
    "ice": "ice",
    "agriculture": "agriculture",
    "agricultural": "agriculture",
    "agriculture-crop": "agriculture",
}

_NON_FUEL_COVER: Final[frozenset[str]] = frozenset({"non-forest", "water", "urban", "rock", "ice"})

_SPECIES_ALIASES: Final[dict[str, str]] = {
    "FD": "FD",
    "DOUGLASFIR": "FD",
    "PL": "PL",
    "LODGEPOLEPINE": "PL",
    "LODGEPOLE": "PL",
    "PY": "PY",
    "PONDEROSAPINE": "PY",
    "PW": "PW",
    "WESTERNWHITEPINE": "PW",
    "PA": "PA",
    "WHITEBARKPINE": "PA",
    "PJ": "PJ",
    "JACKPINE": "PJ",
    "PF": "PF",
    "LIMBERPINE": "PF",
    "LT": "LT",
    "LARCH": "LT",
    "TAMARACK": "LT",
    "SX": "SX",
    "SPRUCE": "SX",
    "SPRUCEHYBRID": "SX",
    "SW": "SW",
    "WHITESPRUCE": "SW",
    "SE": "SE",
    "ENGELMANNSPRUCE": "SE",
    "SS": "SS",
    "SITKASPRUCE": "SS",
    "BL": "BL",
    "SUBALPINEFIR": "BL",
    "BA": "BA",
    "BALSAMFIR": "BA",
    "BG": "BG",
    "GRANDFIR": "BG",
    "HW": "HW",
    "WESTERNHEMLOCK": "HW",
    "HM": "HM",
    "MOUNTAINHEMLOCK": "HM",
    "CW": "CW",
    "WESTERNREDCEDAR": "CW",
    "YC": "YC",
    "YELLOWCEDAR": "YC",
    "AT": "AT",
    "TREMBLINGASPEN": "AT",
    "ASPEN": "AT",
    "AC": "AC",
    "BLACKCOTTONWOOD": "AC",
    "COTTONWOOD": "AC",
    "DR": "DR",
    "REDALDER": "DR",
    "ALDER": "DR",
    "EP": "EP",
    "PAPERBIRCH": "EP",
    "BIRCH": "EP",
    "MB": "MB",
    "BIGLEAFMAPLE": "MB",
    "MAPLE": "MB",
    "QA": "AT",
    "QUAKINGASPEN": "AT",
    "PB": "EP",
}

_PINE: Final[frozenset[str]] = frozenset({"PL", "PY", "PW", "PA", "PJ", "PF"})
_DOUGLAS_FIR: Final[frozenset[str]] = frozenset({"FD"})
_SPRUCE_FIR: Final[frozenset[str]] = frozenset(
    {"SX", "SW", "SE", "SS", "BL", "BA", "BG", "HW", "HM", "CW", "YC"}
)
_LARCH: Final[frozenset[str]] = frozenset({"LT"})
_DECIDUOUS: Final[frozenset[str]] = frozenset({"AT", "AC", "DR", "EP", "MB"})

_NON_FUEL_TYPES: Final[frozenset[str]] = frozenset({"NF", "NONFUEL", "NON-FUEL", "WA", "WATER"})


class VriError(RuntimeError):
    """Raised when a VRI stand description cannot be mapped explicitly."""


@dataclass(frozen=True)
class VriStand:
    """The VRI-style stand fields used by the FBP mapping.

    Parameters
    ----------
    stand_id : str
        Stable stand identifier.
    leading_species : str or None
        VRI species code or common name, such as ``Pl`` or ``Lodgepole pine``.
    conifer_fraction : float
        Conifer fraction of the stand, in [0, 1].
    deciduous_fraction : float
        Deciduous fraction of the stand, in [0, 1].
    crown_closure_percent : float
        Crown closure in percent, in [0, 100].
    age_years : int or None, optional
        Stand age in years.
    height_m : float or None, optional
        Top height in metres.
    land_cover : str, optional
        VRI land-cover class (default ``forest``).
    fuel_type : str or None, optional
        An explicit VRI fuel type; when present it takes precedence.
    treatment : str or None, optional
        Fuel-treatment state, such as ``slash`` or ``matted grass``.
    """

    stand_id: str
    leading_species: str | None
    conifer_fraction: float
    deciduous_fraction: float
    crown_closure_percent: float
    age_years: int | None = None
    height_m: float | None = None
    land_cover: str = "forest"
    fuel_type: str | None = None
    treatment: str | None = None

    def __post_init__(self) -> None:
        """Validate the stand fields and normalize labels."""
        stand_id = str(self.stand_id).strip()
        if not stand_id:
            raise VriError("stand_id must be non-empty")
        conifer = _fraction(self.conifer_fraction, "conifer_fraction")
        deciduous = _fraction(self.deciduous_fraction, "deciduous_fraction")
        if conifer + deciduous > 1.001:
            raise VriError("conifer_fraction and deciduous_fraction must sum to at most one")
        closure = _number(self.crown_closure_percent, "crown_closure_percent")
        if closure < 0.0 or closure > 100.0:
            raise VriError("crown_closure_percent must be between 0 and 100")
        age = None if self.age_years is None else _integer(self.age_years, "age_years")
        if age is not None and age < 0:
            raise VriError("age_years must be non-negative")
        height = None if self.height_m is None else _number(self.height_m, "height_m")
        if height is not None and height <= 0.0:
            raise VriError("height_m must be positive")
        cover = _normalize_cover(self.land_cover)
        species = None if self.leading_species is None else _normalize_species(self.leading_species)
        explicit = None if self.fuel_type is None else str(self.fuel_type).strip()
        treatment = None if self.treatment is None else _normalize_token(self.treatment)
        object.__setattr__(self, "stand_id", stand_id)
        object.__setattr__(self, "conifer_fraction", conifer)
        object.__setattr__(self, "deciduous_fraction", deciduous)
        object.__setattr__(self, "crown_closure_percent", closure)
        object.__setattr__(self, "age_years", age)
        object.__setattr__(self, "height_m", height)
        object.__setattr__(self, "land_cover", cover)
        object.__setattr__(self, "leading_species", species)
        object.__setattr__(self, "fuel_type", explicit)
        object.__setattr__(self, "treatment", treatment or None)

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> VriStand:
        """Build a stand from one mapping or DataFrame row.

        Parameters
        ----------
        row : mapping
            Row with the VRI fields. Optional fields may be missing or null.

        Returns
        -------
        VriStand
            The validated stand.

        Raises
        ------
        VriError
            If a required field is missing or invalid.
        """
        return cls(
            stand_id=str(_value(row, "stand_id", required=True)),
            leading_species=_optional_text(_value(row, "leading_species")),
            conifer_fraction=_fraction(
                _value(row, "conifer_fraction", required=True), "conifer_fraction"
            ),
            deciduous_fraction=_fraction(
                _value(row, "deciduous_fraction", required=True), "deciduous_fraction"
            ),
            crown_closure_percent=_number(
                _value(row, "crown_closure_percent", required=True), "crown_closure_percent"
            ),
            age_years=_optional_integer(_value(row, "age_years")),
            height_m=_optional_positive(_value(row, "height_m")),
            land_cover=str(_value(row, "land_cover") or "forest"),
            fuel_type=_optional_text(_value(row, "fuel_type")),
            treatment=_optional_text(_value(row, "treatment")),
        )


@dataclass(frozen=True)
class FbpFuelAssignment:
    """One VRI-to-FBP assignment with its provenance.

    Parameters
    ----------
    stand_id : str
        The stand identifier.
    fuel_type : str or None
        Canonical FBP fuel type, or None for an explicit non-fuel stand.
    rule_id : str
        The rule that produced the assignment.
    confidence : float
        Rule confidence in [0, 1].
    source_fields : tuple of str
        The VRI fields the rule used.
    version : str, optional
        Mapping version (default :data:`VRI_FBP_VERSION`).
    notes : str or None, optional
        A short explanation.
    """

    stand_id: str
    fuel_type: str | None
    rule_id: str
    confidence: float
    source_fields: tuple[str, ...]
    version: str = VRI_FBP_VERSION
    notes: str | None = None

    @property
    def is_burnable(self) -> bool:
        """Return whether the assignment names a burnable FBP fuel type.

        Returns
        -------
        bool
            True when ``fuel_type`` is not None.
        """
        return self.fuel_type is not None

    def to_dict(self) -> dict[str, object]:
        """Return the assignment as a JSON-serializable mapping.

        Returns
        -------
        dict
            Stand id, fuel type, rule, confidence, source fields, version, and notes.
        """
        return {
            "stand_id": self.stand_id,
            "fuel_type": self.fuel_type,
            "rule_id": self.rule_id,
            "confidence": self.confidence,
            "source_fields": list(self.source_fields),
            "version": self.version,
            "notes": self.notes,
        }


def _value(row: Mapping[str, object], name: str, *, required: bool = False) -> object:
    """Return a row value, treating missing and NaN as None."""
    if name not in row:
        if required:
            raise VriError(f"stand row is missing {name!r}")
        return None
    value = row[name]
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _optional_text(value: object) -> str | None:
    """Return an optional non-empty string."""
    return None if value is None else str(value).strip() or None


def _optional_number(value: object) -> float | None:
    """Return an optional finite number."""
    return None if value is None else _number(value, "value")


def _optional_integer(value: object) -> int | None:
    """Return an optional integer."""
    return None if value is None else _integer(value, "value")


def _optional_positive(value: object) -> float | None:
    """Return an optional positive number, treating zero as missing."""
    if value is None:
        return None
    number = _number(value, "value")
    return None if number <= 0.0 else number


def _number(value: object, field: str) -> float:
    """Return a finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VriError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise VriError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


def _fraction(value: object, field: str) -> float:
    """Return a fraction in [0, 1]."""
    number = _number(value, field)
    if number < 0.0 or number > 1.0:
        raise VriError(f"{field} must be between 0 and 1")
    return number


def _integer(value: object, field: str) -> int:
    """Return an integer, rejecting booleans and non-integers."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise VriError(f"{field} must be an integer")
    return value


def _normalize_token(value: str) -> str:
    """Return a lower-case token with spaces, hyphens, and dots removed."""
    return "".join(character for character in value.lower() if character.isalnum())


def _normalize_cover(value: str) -> str:
    """Return a canonical land-cover class."""
    key = _normalize_token(value)
    if key not in _LAND_COVER_ALIASES:
        allowed = ", ".join(sorted(set(_LAND_COVER_ALIASES.values())))
        raise VriError(f"land_cover must be one of: {allowed}; got {value!r}")
    return _LAND_COVER_ALIASES[key]


def _normalize_species(value: str) -> str:
    """Return a canonical two-letter species code."""
    key = _normalize_token(value).upper()
    if key in _SPECIES_ALIASES:
        return _SPECIES_ALIASES[key]
    for separator in ("/", ",", "+", ";"):
        if separator in value:
            first = _normalize_token(value.split(separator, 1)[0]).upper()
            if first in _SPECIES_ALIASES:
                return _SPECIES_ALIASES[first]
    raise VriError(f"unknown leading_species {value!r}")


def _assignment(
    stand: VriStand,
    fuel_type: str | None,
    rule_id: str,
    confidence: float,
    source_fields: tuple[str, ...],
    notes: str,
) -> FbpFuelAssignment:
    """Build a validated assignment."""
    return FbpFuelAssignment(
        stand_id=stand.stand_id,
        fuel_type=fuel_type,
        rule_id=rule_id,
        confidence=confidence,
        source_fields=source_fields,
        notes=notes,
    )


def _explicit_fuel(stand: VriStand) -> FbpFuelAssignment:
    """Return the assignment for an explicit VRI fuel type."""
    assert stand.fuel_type is not None
    fuel_token = _normalize_token(stand.fuel_type).upper()
    if fuel_token in _NON_FUEL_TYPES:
        return _assignment(
            stand,
            None,
            "explicit-non-fuel",
            1.0,
            ("fuel_type",),
            "VRI fuel type names a non-fuel stand.",
        )
    try:
        fuel_type = canonical_fuel_type(stand.fuel_type)
    except FireFuelError as error:
        raise VriError(f"explicit fuel_type is not an FBP type: {stand.fuel_type!r}") from error
    return _assignment(
        stand,
        fuel_type,
        "explicit-fbp",
        1.0,
        ("fuel_type",),
        "VRI carries an explicit FBP fuel type.",
    )


def _land_cover_assignment(stand: VriStand) -> FbpFuelAssignment | None:
    """Return a non-forest or land-cover assignment, or None to continue to forest rules."""
    cover = stand.land_cover
    if cover in _NON_FUEL_COVER:
        return _assignment(
            stand, None, "land-cover-non-fuel", 1.0, ("land_cover",), f"{cover} is non-fuel."
        )
    if cover == "wetland":
        if stand.conifer_fraction >= 0.5:
            return _assignment(
                stand,
                "C2",
                "wetland-conifer",
                0.6,
                ("land_cover", "conifer_fraction"),
                "Conifer wetland mapped to boreal spruce.",
            )
        return _assignment(
            stand,
            None,
            "wetland-non-fuel",
            0.9,
            ("land_cover", "conifer_fraction"),
            "Non-conifer wetland is treated as non-fuel.",
        )
    if cover == "slash":
        return _assignment(
            stand,
            "S2",
            "land-cover-slash",
            0.9,
            ("land_cover",),
            "Slash land cover mapped to the FBP slash type.",
        )
    if cover in {"grass", "shrub", "agriculture"}:
        fuel_type = "O1A" if stand.treatment and "matted" in stand.treatment else "O1B"
        rule = "land-cover-grass-matted" if fuel_type == "O1A" else "land-cover-grass-standing"
        return _assignment(
            stand,
            fuel_type,
            rule,
            0.9,
            ("land_cover", "treatment"),
            "Open grass or shrub mapped to the FBP grass type.",
        )
    return None


def map_vri_stand(stand: VriStand) -> FbpFuelAssignment:
    """Map one VRI-style stand to an FBP fuel type.

    Parameters
    ----------
    stand : VriStand
        The validated stand description.

    Returns
    -------
    FbpFuelAssignment
        The fuel type and its provenance. ``fuel_type`` is None only for an explicit
        non-fuel stand.

    Raises
    ------
    VriError
        If the stand description is unknown or ambiguous.
    """
    if stand.fuel_type is not None:
        return _explicit_fuel(stand)
    cover_assignment = _land_cover_assignment(stand)
    if cover_assignment is not None:
        return cover_assignment
    if stand.treatment and "slash" in stand.treatment:
        return _assignment(
            stand,
            "S2",
            "treatment-slash",
            0.9,
            ("treatment",),
            "Slash treatment mapped to the FBP slash type.",
        )
    if stand.crown_closure_percent < 5.0 or (
        stand.conifer_fraction + stand.deciduous_fraction < 0.05
    ):
        return _assignment(
            stand,
            None,
            "sparse-cover",
            0.8,
            ("crown_closure_percent", "conifer_fraction", "deciduous_fraction"),
            "Sparse or non-vegetated stand is treated as non-fuel.",
        )
    if stand.leading_species is None:
        raise VriError(f"stand {stand.stand_id!r} has no leading species")
    species = stand.leading_species
    if stand.conifer_fraction >= 0.3 and stand.deciduous_fraction >= 0.3:
        immature = (stand.age_years is not None and stand.age_years < 20) or (
            stand.height_m is not None and stand.height_m < 5.0
        )
        if immature:
            fuel_type = "M3" if stand.conifer_fraction < 0.5 else "M4"
            rule = "mixedwood-immature"
            confidence = 0.65
            note = "Immature mixedwood mapped to the FBP mixedwood type."
        else:
            fuel_type = "M1" if stand.conifer_fraction < 0.5 else "M2"
            rule = "mixedwood"
            confidence = 0.7
            note = "Mixedwood mapped by the conifer share."
        return _assignment(
            stand,
            fuel_type,
            rule,
            confidence,
            (
                "leading_species",
                "conifer_fraction",
                "deciduous_fraction",
                "age_years",
                "height_m",
            ),
            note,
        )
    if species in _DECIDUOUS or (stand.deciduous_fraction >= 0.7 and stand.conifer_fraction < 0.3):
        return _assignment(
            stand,
            "D1",
            "deciduous",
            0.8,
            (
                "leading_species",
                "conifer_fraction",
                "deciduous_fraction",
            ),
            "Deciduous-leading stand mapped to the FBP deciduous type.",
        )
    if species in _PINE:
        mature = stand.age_years is not None and stand.age_years >= 40
        return _assignment(
            stand,
            "C3" if mature else "C4",
            "pine-mature" if mature else "pine-immature",
            0.8 if stand.age_years is not None else 0.65,
            ("leading_species", "age_years"),
            "Pine stand mapped by age.",
        )
    if species in _DOUGLAS_FIR:
        return _assignment(
            stand,
            "C7",
            "douglas-fir",
            0.85,
            ("leading_species",),
            "Douglas-fir mapped to the FBP Douglas-fir type.",
        )
    if species in _LARCH:
        return _assignment(
            stand,
            "C3",
            "larch",
            0.65,
            ("leading_species",),
            "Larch mapped to the mature pine type as a conservative proxy.",
        )
    if species in _SPRUCE_FIR:
        if stand.crown_closure_percent < 40.0:
            return _assignment(
                stand,
                "C1",
                "spruce-open",
                0.7,
                ("leading_species", "crown_closure_percent"),
                "Open spruce/fir mapped to the spruce-lichen type.",
            )
        return _assignment(
            stand,
            "C2",
            "spruce-closed",
            0.8,
            ("leading_species", "crown_closure_percent"),
            "Closed spruce/fir mapped to the boreal spruce type.",
        )
    raise VriError(f"stand {stand.stand_id!r} has an unmapped leading species {species!r}")


def map_vri_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Map every row of a VRI-style table to an FBP fuel type.

    Parameters
    ----------
    frame : pandas.DataFrame
        Stand table. Required columns are ``stand_id``, ``conifer_fraction``,
        ``deciduous_fraction``, and ``crown_closure_percent``. Optional columns are
        ``leading_species``, ``age_years``, ``height_m``, ``land_cover``, ``fuel_type``,
        and ``treatment``.

    Returns
    -------
    pandas.DataFrame
        One row per stand with ``stand_id``, ``fuel_type``, ``rule_id``, ``version``,
        ``confidence``, ``source_fields``, ``is_burnable``, and ``notes``.

    Raises
    ------
    VriError
        If a row is missing a required field or cannot be mapped.
    """
    rows: list[dict[str, object]] = []
    for record in frame.to_dict("records"):
        row = {str(key): value for key, value in record.items()}
        assignment = map_vri_stand(VriStand.from_row(row))
        rows.append(
            {
                "stand_id": assignment.stand_id,
                "fuel_type": assignment.fuel_type,
                "rule_id": assignment.rule_id,
                "version": assignment.version,
                "confidence": assignment.confidence,
                "source_fields": ",".join(assignment.source_fields),
                "is_burnable": assignment.is_burnable,
                "notes": assignment.notes,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "stand_id",
            "fuel_type",
            "rule_id",
            "version",
            "confidence",
            "source_fields",
            "is_burnable",
            "notes",
        ],
    )
