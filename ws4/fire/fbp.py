"""Canadian FBP fuel types and surface-fire equations.

The FBP System is the Canadian operational fire-behaviour model. This module implements the
surface-fire component: surface fuel consumption, the buildup effect, the initial surface rate
of spread, and the surface head fire intensity for the standard FBP fuel types. Crown fire is a
separate layer (P154.3); the result says ``surface_only`` so a caller cannot mistake the
surface intensity for a crown-fire intensity.

The equations are the published FBP System equations. The implementation is original Python.
The ``cffdrs`` R package is used only as a validation oracle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from .fuel import FireFuelError, _non_negative, _number, _probability
from .fwi import initial_spread_index

FBP_FUEL_TYPES: Final[tuple[str, ...]] = (
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7",
    "D1",
    "M1",
    "M2",
    "M3",
    "M4",
    "S1",
    "S2",
    "S3",
    "O1A",
    "O1B",
)

#: FBP rate-of-spread coefficients: a, b, c.
_ROS_COEFFICIENTS: Final[dict[str, tuple[float, float, float]]] = {
    "C1": (90.0, 0.0649, 4.5),
    "C2": (110.0, 0.0282, 1.5),
    "C3": (110.0, 0.0444, 3.0),
    "C4": (110.0, 0.0293, 1.5),
    "C5": (30.0, 0.0697, 4.0),
    "C6": (30.0, 0.0800, 3.0),
    "C7": (45.0, 0.0305, 2.0),
    "D1": (30.0, 0.0232, 1.6),
    "M1": (0.0, 0.0, 0.0),
    "M2": (0.0, 0.0, 0.0),
    "M3": (120.0, 0.0572, 1.4),
    "M4": (100.0, 0.0404, 1.48),
    "S1": (75.0, 0.0297, 1.3),
    "S2": (40.0, 0.0438, 1.7),
    "S3": (55.0, 0.0829, 3.2),
    "O1A": (190.0, 0.0310, 1.4),
    "O1B": (250.0, 0.0350, 1.7),
}

#: FBP buildup-effect parameters: BUIo and Q.
_BUILDUP_PARAMETERS: Final[dict[str, tuple[float, float]]] = {
    "C1": (72.0, 0.9),
    "C2": (64.0, 0.7),
    "C3": (62.0, 0.75),
    "C4": (66.0, 0.8),
    "C5": (56.0, 0.8),
    "C6": (62.0, 0.8),
    "C7": (106.0, 0.85),
    "D1": (32.0, 0.9),
    "M1": (50.0, 0.8),
    "M2": (50.0, 0.8),
    "M3": (50.0, 0.8),
    "M4": (50.0, 0.8),
    "S1": (38.0, 0.75),
    "S2": (63.0, 0.75),
    "S3": (31.0, 0.75),
    "O1A": (1.0, 1.0),
    "O1B": (1.0, 1.0),
}


@dataclass(frozen=True)
class FBPFuelType:
    """One FBP fuel type and its surface rate-of-spread coefficients.

    Parameters
    ----------
    name : str
        Canonical fuel type, such as ``C2`` or ``O1A``.
    a : float
        Rate-of-spread coefficient.
    b : float
        Rate-of-spread exponent scale.
    c : float
        Rate-of-spread exponent.
    bui_o : float
        Reference buildup index for the buildup effect.
    q : float
        Buildup-effect shape parameter.
    """

    name: str
    a: float
    b: float
    c: float
    bui_o: float
    q: float

    def to_dict(self) -> dict[str, object]:
        """Return the fuel type as a JSON-serializable mapping.

        Returns
        -------
        dict
            The fuel-type fields.
        """
        return {
            "name": self.name,
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "bui_o": self.bui_o,
            "q": self.q,
        }


#: The standard FBP fuel types.
FBP_FUEL_TYPE_TABLE: Final[dict[str, FBPFuelType]] = {
    name: FBPFuelType(
        name=name,
        a=_ROS_COEFFICIENTS[name][0],
        b=_ROS_COEFFICIENTS[name][1],
        c=_ROS_COEFFICIENTS[name][2],
        bui_o=_BUILDUP_PARAMETERS[name][0],
        q=_BUILDUP_PARAMETERS[name][1],
    )
    for name in FBP_FUEL_TYPES
}


@dataclass(frozen=True)
class FBPSurfaceResult:
    """The FBP surface-fire result for one fuel type and weather condition.

    Attributes
    ----------
    fuel_type : str
        Canonical FBP fuel type.
    isi : float
        Initial Spread Index.
    surface_fuel_consumption_kg_m2 : float
        Surface fuel consumption.
    buildup_effect : float
        The FBP buildup effect.
    initial_ros_m_min : float
        The initial surface rate of spread before the buildup effect.
    rate_of_spread_m_min : float
        The surface head fire rate of spread.
    head_fire_intensity_kw_m : float
        The surface head fire intensity, ``300 x SFC x ROS``.
    flame_length_m : float
        Byram flame length derived from the surface intensity.
    surface_only : bool
        True; crown fire is a separate layer.
    """

    fuel_type: str
    isi: float
    surface_fuel_consumption_kg_m2: float
    buildup_effect: float
    initial_ros_m_min: float
    rate_of_spread_m_min: float
    head_fire_intensity_kw_m: float
    flame_length_m: float
    surface_only: bool = True

    def to_dict(self) -> dict[str, object]:
        """Return the result as a JSON-serializable mapping.

        Returns
        -------
        dict
            The result fields.
        """
        return {
            "fuel_type": self.fuel_type,
            "isi": self.isi,
            "surface_fuel_consumption_kg_m2": self.surface_fuel_consumption_kg_m2,
            "buildup_effect": self.buildup_effect,
            "initial_ros_m_min": self.initial_ros_m_min,
            "rate_of_spread_m_min": self.rate_of_spread_m_min,
            "head_fire_intensity_kw_m": self.head_fire_intensity_kw_m,
            "flame_length_m": self.flame_length_m,
            "surface_only": self.surface_only,
        }


def canonical_fuel_type(value: str) -> str:
    """Return the canonical FBP fuel-type name.

    Parameters
    ----------
    value : str
        A fuel type such as ``C2``, ``C-2``, or ``o1a``.

    Returns
    -------
    str
        The canonical name.

    Raises
    ------
    FireFuelError
        If the fuel type is not supported.
    """
    if not isinstance(value, str):
        raise FireFuelError("fuel_type must be a string")
    name = value.strip().upper().replace("-", "").replace(" ", "")
    if name not in FBP_FUEL_TYPE_TABLE:
        supported = ", ".join(FBP_FUEL_TYPES)
        raise FireFuelError(f"fuel_type must be one of: {supported}; got {value!r}")
    return name


def surface_fuel_consumption(
    fuel_type: str,
    ffmc: float,
    bui: float,
    *,
    conifer_percent: float = 50.0,
    grass_fuel_load_kg_m2: float = 0.35,
) -> float:
    """Return the FBP surface fuel consumption.

    Parameters
    ----------
    fuel_type : str
        FBP fuel type.
    ffmc : float
        Fine Fuel Moisture Code.
    bui : float
        Buildup Index.
    conifer_percent : float, optional
        Conifer percentage for the M1/M2 blend (default 50).
    grass_fuel_load_kg_m2 : float, optional
        Grass fuel load for O1 (default 0.35 kg/m²).

    Returns
    -------
    float
        Surface fuel consumption in kilograms per square metre.
    """
    name = canonical_fuel_type(fuel_type)
    code = _number(ffmc, "ffmc")
    if code < 0.0 or code > 101.0:
        raise FireFuelError("ffmc must be between 0 and 101")
    buildup = _non_negative(bui, "bui")
    conifer = _probability(conifer_percent / 100.0, "conifer_percent") * 100.0
    grass = _non_negative(grass_fuel_load_kg_m2, "grass_fuel_load_kg_m2")
    if name == "C1":
        value = (
            0.75 + 0.75 * (1.0 - math.exp(-0.23 * (code - 84.0))) ** 0.5
            if code > 84.0
            else 0.75 - 0.75 * (1.0 - math.exp(-0.23 * (84.0 - code))) ** 0.5
        )
    elif name in {"C2", "M3", "M4"}:
        value = 5.0 * (1.0 - math.exp(-0.0115 * buildup))
    elif name in {"C3", "C4"}:
        value = 5.0 * (1.0 - math.exp(-0.0164 * buildup)) ** 2.24
    elif name in {"C5", "C6"}:
        value = 5.0 * (1.0 - math.exp(-0.0149 * buildup)) ** 2.48
    elif name == "C7":
        grass_part = 2.0 * (1.0 - math.exp(-0.104 * (code - 70.0))) if code > 70.0 else 0.0
        value = grass_part + 1.5 * (1.0 - math.exp(-0.0201 * buildup))
    elif name == "D1":
        value = 1.5 * (1.0 - math.exp(-0.0183 * buildup))
    elif name in {"M1", "M2"}:
        value = conifer / 100.0 * 5.0 * (1.0 - math.exp(-0.0115 * buildup)) + (
            (100.0 - conifer) / 100.0 * 1.5 * (1.0 - math.exp(-0.0183 * buildup))
        )
    elif name in {"O1A", "O1B"}:
        value = grass
    elif name == "S1":
        value = 4.0 * (1.0 - math.exp(-0.025 * buildup)) + 4.0 * (1.0 - math.exp(-0.034 * buildup))
    elif name == "S2":
        value = 10.0 * (1.0 - math.exp(-0.013 * buildup)) + 6.0 * (1.0 - math.exp(-0.06 * buildup))
    elif name == "S3":
        value = 12.0 * (1.0 - math.exp(-0.0166 * buildup)) + 20.0 * (
            1.0 - math.exp(-0.021 * buildup)
        )
    else:  # pragma: no cover - canonical_fuel_type already rejects unknown names
        raise FireFuelError(f"unsupported fuel type: {name!r}")
    return max(float(value), 1e-6)


def buildup_effect(fuel_type: str, bui: float) -> float:
    """Return the FBP buildup effect.

    Parameters
    ----------
    fuel_type : str
        FBP fuel type.
    bui : float
        Buildup Index.

    Returns
    -------
    float
        The buildup effect multiplier.
    """
    name = canonical_fuel_type(fuel_type)
    buildup = _non_negative(bui, "bui")
    fuel = FBP_FUEL_TYPE_TABLE[name]
    if buildup <= 0.0 or fuel.bui_o <= 0.0:
        return 1.0
    return float(math.exp(50.0 * math.log(fuel.q) * (1.0 / buildup - 1.0 / fuel.bui_o)))


def _base_surface_ros(fuel_type: str, isi: float) -> float:
    """Return the base surface rate of spread for a simple fuel type."""
    fuel = FBP_FUEL_TYPE_TABLE[fuel_type]
    return float(fuel.a * (1.0 - math.exp(-fuel.b * isi)) ** fuel.c)


def _initial_surface_ros(
    fuel_type: str,
    isi: float,
    *,
    conifer_percent: float,
    dead_fir_percent: float,
    crown_closure_percent: float,
) -> float:
    """Return the initial surface rate of spread for an FBP fuel type."""
    name = canonical_fuel_type(fuel_type)
    if name == "C6":
        return float(30.0 * (1.0 - math.exp(-0.08 * isi)) ** 3)
    if name in {"M1", "M2"}:
        c2 = _base_surface_ros("C2", isi)
        d1 = _base_surface_ros("D1", isi)
        if name == "M1":
            return conifer_percent / 100.0 * c2 + (100.0 - conifer_percent) / 100.0 * d1
        return conifer_percent / 100.0 * c2 + 0.2 * (100.0 - conifer_percent) / 100.0 * d1
    if name in {"M3", "M4"}:
        base = _base_surface_ros(name, isi)
        d1 = _base_surface_ros("D1", isi)
        if name == "M3":
            return dead_fir_percent / 100.0 * base + (100.0 - dead_fir_percent) / 100.0 * d1
        return dead_fir_percent / 100.0 * base + 0.2 * (100.0 - dead_fir_percent) / 100.0 * d1
    if name in {"O1A", "O1B"}:
        cf = (
            0.005 * (math.exp(0.061 * crown_closure_percent) - 1.0)
            if crown_closure_percent < 58.8
            else 0.176 + 0.02 * (crown_closure_percent - 58.8)
        )
        return _base_surface_ros(name, isi) * cf
    return _base_surface_ros(name, isi)


def fbp_surface_fire(
    fuel_type: str,
    ffmc: float,
    bui: float,
    wind_kmh: float,
    *,
    conifer_percent: float = 50.0,
    dead_fir_percent: float = 35.0,
    crown_closure_percent: float = 80.0,
    grass_fuel_load_kg_m2: float = 0.35,
) -> FBPSurfaceResult:
    """Compute the FBP surface-fire result.

    Parameters
    ----------
    fuel_type : str
        FBP fuel type, such as ``C2`` or ``C-2``.
    ffmc : float
        Fine Fuel Moisture Code.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed. The FBP high-wind ISI form is used.
    conifer_percent : float, optional
        Conifer percentage for M1/M2 (default 50).
    dead_fir_percent : float, optional
        Dead fir percentage for M3/M4 (default 35).
    crown_closure_percent : float, optional
        Crown closure for O1 (default 80).
    grass_fuel_load_kg_m2 : float, optional
        Grass fuel load for O1 (default 0.35 kg/m²).

    Returns
    -------
    FBPSurfaceResult
        Surface rate of spread, intensity, and fuel consumption.

    Raises
    ------
    FireFuelError
        If an input is out of range.
    """
    name = canonical_fuel_type(fuel_type)
    code = _number(ffmc, "ffmc")
    if code < 0.0 or code > 101.0:
        raise FireFuelError("ffmc must be between 0 and 101")
    buildup = _non_negative(bui, "bui")
    wind = _non_negative(wind_kmh, "wind_kmh")
    conifer = _probability(conifer_percent / 100.0, "conifer_percent") * 100.0
    dead_fir = _probability(dead_fir_percent / 100.0, "dead_fir_percent") * 100.0
    closure = _probability(crown_closure_percent / 100.0, "crown_closure_percent") * 100.0
    isi = initial_spread_index(code, wind, fbp=True)
    sfc = surface_fuel_consumption(
        name,
        code,
        buildup,
        conifer_percent=conifer,
        grass_fuel_load_kg_m2=grass_fuel_load_kg_m2,
    )
    initial_ros = _initial_surface_ros(
        name,
        isi,
        conifer_percent=conifer,
        dead_fir_percent=dead_fir,
        crown_closure_percent=closure,
    )
    be = buildup_effect(name, buildup)
    ros = max(initial_ros * be, 1e-6)
    intensity = 300.0 * sfc * ros
    flame_length = 0.0 if intensity <= 0.0 else 0.0775 * intensity**0.46
    return FBPSurfaceResult(
        fuel_type=name,
        isi=isi,
        surface_fuel_consumption_kg_m2=sfc,
        buildup_effect=be,
        initial_ros_m_min=initial_ros,
        rate_of_spread_m_min=ros,
        head_fire_intensity_kw_m=intensity,
        flame_length_m=flame_length,
    )
