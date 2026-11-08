"""Fuel and moisture contracts for the surface-fire kernel.

The units are explicit and metric: fuel load in tonnes per hectare, surface-to-volume ratio in
square metres per cubic metre, heat content in kilojoules per kilogram, fuel bed depth in
centimetres, and moisture in percent of dry weight. The 13 Anderson standard fuel models are
included as the first validation set. The parameters are public scientific data from the
standard fuel-model literature; this module is an original implementation of the contract.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

FUEL_CLASSES: Final[tuple[str, ...]] = (
    "1h",
    "10h",
    "100h",
    "live_herb",
    "live_woody",
)

FuelModelData = tuple[str, list[float], list[float], float, float, list[float]]

ANDERSON_13_DATA: Final[dict[str, FuelModelData]] = {
    "A1": (
        "S",
        [1.66, 0, 0, 0, 0],
        [11483, 0, 0, 0, 0],
        30,
        12,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A2": (
        "S",
        [4.49, 2.25, 1.12, 1.12, 0],
        [9843, 358, 98, 4921, 0],
        30,
        15,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A3": (
        "S",
        [6.74, 0, 0, 0, 0],
        [4921, 0, 0, 0, 0],
        76,
        25,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A4": (
        "S",
        [11.23, 8.98, 4.49, 0, 11.23],
        [6562, 358, 98, 0, 4921],
        183,
        20,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A5": (
        "S",
        [2.25, 1.12, 0, 0, 5.79],
        [6562, 358, 98, 0, 4921],
        61,
        20,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A6": (
        "S",
        [3.7, 6.18, 4.94, 0, 0],
        [5741, 358, 98, 0, 0],
        76,
        25,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A7": (
        "S",
        [2.72, 4.69, 3.71, 0, 0.91],
        [5741, 358, 98, 0, 4921],
        76,
        40,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A8": (
        "S",
        [3.37, 2.25, 5.61, 0, 0],
        [6562, 358, 98, 0, 0],
        6,
        30,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A9": (
        "S",
        [6.54, 0.93, 0.34, 0, 0],
        [8202, 358, 98, 0, 0],
        6,
        25,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A10": (
        "S",
        [6.74, 4.49, 11.23, 0, 4.49],
        [6562, 358, 98, 0, 4921],
        30,
        25,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A11": (
        "S",
        [3.37, 10.1, 12.35, 0, 0],
        [4921, 358, 98, 0, 0],
        30,
        15,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A12": (
        "S",
        [8.98, 21.44, 37.06, 0, 0],
        [4921, 358, 98, 0, 0],
        70,
        20,
        [18622, 18622, 18622, 18622, 18622],
    ),
    "A13": (
        "S",
        [15.72, 51.66, 62.89, 0, 0],
        [4921, 358, 98, 0, 0],
        91,
        25,
        [18622, 18622, 18622, 18622, 18622],
    ),
}

MOISTURE_SCENARIOS_DATA: Final[dict[str, tuple[float, float, float, float, float]]] = {
    "D1L1": (3, 4, 5, 30, 60),
    "D2L2": (6, 7, 8, 60, 90),
    "D3L3": (9, 10, 11, 90, 120),
    "D4L4": (12, 13, 14, 120, 150),
    "D1L2": (3, 4, 5, 60, 90),
    "D1L3": (3, 4, 5, 90, 120),
    "D1L4": (3, 4, 5, 120, 150),
    "D2L1": (6, 7, 8, 30, 60),
    "D2L3": (6, 7, 8, 90, 120),
    "D2L4": (6, 7, 8, 120, 150),
    "D3L1": (9, 10, 11, 30, 60),
    "D3L2": (9, 10, 11, 60, 90),
    "D3L4": (9, 10, 11, 120, 150),
    "D4L1": (12, 13, 15, 30, 60),
    "D4L2": (12, 13, 15, 60, 90),
    "D4L3": (12, 13, 15, 90, 120),
}


class FireFuelError(ValueError):
    """Raised when a fuel, moisture, or environment value is invalid."""


def _text(value: object, field: str) -> str:
    """Return a non-empty, stripped string."""
    if not isinstance(value, str) or not value.strip():
        raise FireFuelError(f"{field} must be a non-empty string")
    return value.strip()


def _number(value: object, field: str) -> float:
    """Return a finite float, normalizing negative zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FireFuelError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise FireFuelError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


def _integer(value: object, field: str) -> int:
    """Return an integer, rejecting booleans and non-integers."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise FireFuelError(f"{field} must be an integer")
    return value


def _positive(value: object, field: str) -> float:
    """Return a finite, strictly positive float."""
    number = _number(value, field)
    if number <= 0.0:
        raise FireFuelError(f"{field} must be positive")
    return number


def _non_negative(value: object, field: str) -> float:
    """Return a finite, non-negative float."""
    number = _number(value, field)
    if number < 0.0:
        raise FireFuelError(f"{field} must be non-negative")
    return number


def _probability(value: object, field: str) -> float:
    """Return a number in [0, 1]."""
    number = _number(value, field)
    if number < 0.0 or number > 1.0:
        raise FireFuelError(f"{field} must be between 0 and 1")
    return number


@dataclass(frozen=True)
class FuelClass:
    """One of the five Rothermel fuel classes.

    Parameters
    ----------
    load_t_ha : float
        Oven-dry fuel load in tonnes per hectare.
    sav_m2_m3 : float
        Surface-to-volume ratio in square metres per cubic metre.
    heat_kj_kg : float
        Heat content in kilojoules per kilogram.
    """

    load_t_ha: float
    sav_m2_m3: float
    heat_kj_kg: float

    def __post_init__(self) -> None:
        """Validate the class values."""
        load = _non_negative(self.load_t_ha, "load_t_ha")
        sav = _non_negative(self.sav_m2_m3, "sav_m2_m3")
        if load > 0.0 and sav <= 0.0:
            raise FireFuelError("sav_m2_m3 must be positive when the load is positive")
        heat = _positive(self.heat_kj_kg, "heat_kj_kg")
        object.__setattr__(self, "load_t_ha", load)
        object.__setattr__(self, "sav_m2_m3", sav)
        object.__setattr__(self, "heat_kj_kg", heat)

    def to_dict(self) -> dict[str, float]:
        """Return the class as a JSON-serializable mapping.

        Returns
        -------
        dict
            Load, surface-to-volume ratio, and heat content.
        """
        return {
            "load_t_ha": self.load_t_ha,
            "sav_m2_m3": self.sav_m2_m3,
            "heat_kj_kg": self.heat_kj_kg,
        }


@dataclass(frozen=True)
class FuelModel:
    """A Rothermel-style surface fuel model.

    Parameters
    ----------
    name : str
        Model name, such as ``A3``.
    model_type : str
        ``S`` for a static model or ``D`` for a dynamic model.
    classes : tuple of FuelClass
        The five fuel classes: 1h, 10h, 100h, live herb, live woody.
    depth_cm : float
        Fuel bed depth in centimetres.
    moisture_of_extinction_percent : float
        Dead fuel moisture of extinction in percent.
    description : str, optional
        A short description.
    """

    name: str
    model_type: str
    classes: tuple[FuelClass, FuelClass, FuelClass, FuelClass, FuelClass]
    depth_cm: float
    moisture_of_extinction_percent: float
    description: str = ""

    def __post_init__(self) -> None:
        """Validate the fuel model."""
        name = _text(self.name, "name")
        model_type = _text(self.model_type, "model_type").upper()
        if model_type not in {"S", "D"}:
            raise FireFuelError("model_type must be 'S' or 'D'")
        if len(self.classes) != 5:
            raise FireFuelError("classes must have five entries")
        if sum(item.load_t_ha for item in self.classes) <= 0.0:
            raise FireFuelError("fuel model must have a positive fuel load")
        depth = _positive(self.depth_cm, "depth_cm")
        extinction = _positive(
            self.moisture_of_extinction_percent, "moisture_of_extinction_percent"
        )
        if extinction > 100.0:
            raise FireFuelError("moisture_of_extinction_percent must be at most 100")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "model_type", model_type)
        object.__setattr__(self, "depth_cm", depth)
        object.__setattr__(self, "moisture_of_extinction_percent", extinction)
        object.__setattr__(self, "description", str(self.description).strip())

    @property
    def loads_t_ha(self) -> tuple[float, float, float, float, float]:
        """Return the five fuel loads.

        Returns
        -------
        tuple of float
            Loads in tonnes per hectare.
        """
        return (
            self.classes[0].load_t_ha,
            self.classes[1].load_t_ha,
            self.classes[2].load_t_ha,
            self.classes[3].load_t_ha,
            self.classes[4].load_t_ha,
        )

    @property
    def sav_m2_m3(self) -> tuple[float, float, float, float, float]:
        """Return the five surface-to-volume ratios.

        Returns
        -------
        tuple of float
            Surface-to-volume ratios in square metres per cubic metre.
        """
        return (
            self.classes[0].sav_m2_m3,
            self.classes[1].sav_m2_m3,
            self.classes[2].sav_m2_m3,
            self.classes[3].sav_m2_m3,
            self.classes[4].sav_m2_m3,
        )

    @property
    def heat_kj_kg(self) -> tuple[float, float, float, float, float]:
        """Return the five heat contents.

        Returns
        -------
        tuple of float
            Heat contents in kilojoules per kilogram.
        """
        return (
            self.classes[0].heat_kj_kg,
            self.classes[1].heat_kj_kg,
            self.classes[2].heat_kj_kg,
            self.classes[3].heat_kj_kg,
            self.classes[4].heat_kj_kg,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the model as a JSON-serializable mapping.

        Returns
        -------
        dict
            The model fields.
        """
        return {
            "name": self.name,
            "model_type": self.model_type,
            "classes": [item.to_dict() for item in self.classes],
            "depth_cm": self.depth_cm,
            "moisture_of_extinction_percent": self.moisture_of_extinction_percent,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> FuelModel:
        """Validate and construct a fuel model from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`.

        Returns
        -------
        FuelModel
            The validated model.
        """
        raw_classes = payload["classes"]
        if not isinstance(raw_classes, list) or len(raw_classes) != 5:
            raise FireFuelError("classes must be a list of five mappings")
        classes: list[FuelClass] = []
        for item in raw_classes:
            if not isinstance(item, Mapping):
                raise FireFuelError("fuel classes must be mappings")
            classes.append(
                FuelClass(
                    load_t_ha=_non_negative(item["load_t_ha"], "load_t_ha"),
                    sav_m2_m3=_non_negative(item["sav_m2_m3"], "sav_m2_m3"),
                    heat_kj_kg=_positive(item["heat_kj_kg"], "heat_kj_kg"),
                )
            )
        return cls(
            name=_text(payload["name"], "name"),
            model_type=_text(payload["model_type"], "model_type"),
            classes=(classes[0], classes[1], classes[2], classes[3], classes[4]),
            depth_cm=_positive(payload["depth_cm"], "depth_cm"),
            moisture_of_extinction_percent=_positive(
                payload["moisture_of_extinction_percent"],
                "moisture_of_extinction_percent",
            ),
            description=str(payload.get("description", "")),
        )


def _build_model(
    name: str,
    data: tuple[str, list[float], list[float], float, float, list[float]],
    description: str = "",
) -> FuelModel:
    """Build one standard fuel model from the table."""
    model_type, loads, savs, depth, extinction, heats = data
    classes = (
        FuelClass(loads[0], savs[0], heats[0]),
        FuelClass(loads[1], savs[1], heats[1]),
        FuelClass(loads[2], savs[2], heats[2]),
        FuelClass(loads[3], savs[3], heats[3]),
        FuelClass(loads[4], savs[4], heats[4]),
    )
    return FuelModel(
        name=name,
        model_type=model_type,
        classes=classes,
        depth_cm=depth,
        moisture_of_extinction_percent=extinction,
        description=description,
    )


#: The 13 Anderson standard fire-behaviour fuel models.
ANDERSON_13: Final[dict[str, FuelModel]] = {
    name: _build_model(name, data) for name, data in ANDERSON_13_DATA.items()
}


@dataclass(frozen=True)
class FuelMoisture:
    """The five fuel-class moisture values.

    Parameters
    ----------
    dead_1h_percent : float
        One-hour dead fuel moisture in percent.
    dead_10h_percent : float
        Ten-hour dead fuel moisture in percent.
    dead_100h_percent : float
        Hundred-hour dead fuel moisture in percent.
    live_herb_percent : float
        Live herbaceous moisture in percent, zero or at least 30.
    live_woody_percent : float
        Live woody moisture in percent.
    """

    dead_1h_percent: float
    dead_10h_percent: float
    dead_100h_percent: float
    live_herb_percent: float
    live_woody_percent: float

    def __post_init__(self) -> None:
        """Validate the moisture values."""
        for field in (
            "dead_1h_percent",
            "dead_10h_percent",
            "dead_100h_percent",
            "live_herb_percent",
            "live_woody_percent",
        ):
            _non_negative(getattr(self, field), field)
        if 0.0 < self.live_herb_percent < 30.0:
            raise FireFuelError("live herbaceous moisture must be zero or at least 30 percent")

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        """Return the values as a five-element tuple.

        Returns
        -------
        tuple of float
            The five moisture percentages.
        """
        return (
            self.dead_1h_percent,
            self.dead_10h_percent,
            self.dead_100h_percent,
            self.live_herb_percent,
            self.live_woody_percent,
        )

    def to_dict(self) -> dict[str, float]:
        """Return the moisture values as a JSON-serializable mapping.

        Returns
        -------
        dict
            The five moisture fields.
        """
        return {
            "dead_1h_percent": self.dead_1h_percent,
            "dead_10h_percent": self.dead_10h_percent,
            "dead_100h_percent": self.dead_100h_percent,
            "live_herb_percent": self.live_herb_percent,
            "live_woody_percent": self.live_woody_percent,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> FuelMoisture:
        """Validate and construct moisture values from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`.

        Returns
        -------
        FuelMoisture
            The validated moisture.
        """
        return cls(
            dead_1h_percent=_non_negative(payload["dead_1h_percent"], "dead_1h_percent"),
            dead_10h_percent=_non_negative(payload["dead_10h_percent"], "dead_10h_percent"),
            dead_100h_percent=_non_negative(payload["dead_100h_percent"], "dead_100h_percent"),
            live_herb_percent=_non_negative(payload["live_herb_percent"], "live_herb_percent"),
            live_woody_percent=_non_negative(payload["live_woody_percent"], "live_woody_percent"),
        )


def _build_moisture(name: str, values: tuple[float, float, float, float, float]) -> FuelMoisture:
    """Build one standard moisture scenario."""
    return FuelMoisture(*values)


#: The 16 Scott and Burgan moisture scenarios.
MOISTURE_SCENARIOS: Final[dict[str, FuelMoisture]] = {
    name: _build_moisture(name, values) for name, values in MOISTURE_SCENARIOS_DATA.items()
}

#: The default dry-dead, two-thirds-cured scenario.
DEFAULT_MOISTURE: Final[FuelMoisture] = MOISTURE_SCENARIOS["D2L2"]
