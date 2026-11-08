"""Crown fire initiation, propagation, and the FBP crown-fire classification.

The surface-fire layer answers how fast the surface fire spreads. This module adds the crown
fire question: does the surface fire ignite the canopy, how much of the canopy burns, and how
does the total fuel consumption change the head fire intensity?

The initiation threshold is Van Wagner's critical surface intensity. The FBP crown-fire
fraction and the C6 crown rate of spread are the Canadian FBP formulations. A separate Van
Wagner active-crown threshold is available when a canopy bulk density is supplied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from .fbp import FBPSurfaceResult, canonical_fuel_type, fbp_surface_fire
from .fuel import FireFuelError, _number, _probability

#: Default crown base height by FBP fuel type, in metres.
CROWN_BASE_HEIGHT_M: Final[dict[str, float]] = {
    "C1": 2.0,
    "C2": 3.0,
    "C3": 8.0,
    "C4": 4.0,
    "C5": 18.0,
    "C6": 7.0,
    "C7": 10.0,
    "D1": 0.0,
    "M1": 6.0,
    "M2": 6.0,
    "M3": 6.0,
    "M4": 6.0,
    "S1": 0.0,
    "S2": 0.0,
    "S3": 0.0,
    "O1A": 0.0,
    "O1B": 0.0,
}

#: Default crown fuel load by FBP fuel type, in kilograms per square metre.
CROWN_FUEL_LOAD_KG_M2: Final[dict[str, float]] = {
    "C1": 0.75,
    "C2": 0.80,
    "C3": 1.15,
    "C4": 1.20,
    "C5": 1.20,
    "C6": 1.80,
    "C7": 0.50,
    "D1": 0.0,
    "M1": 0.80,
    "M2": 0.80,
    "M3": 0.80,
    "M4": 0.80,
    "S1": 0.0,
    "S2": 0.0,
    "S3": 0.0,
    "O1A": 0.0,
    "O1B": 0.0,
}

_FME_AVG: Final[float] = 0.778


@dataclass(frozen=True)
class CrownFireResult:
    """The FBP crown-fire result for one fuel type and weather condition.

    Attributes
    ----------
    fuel_type : str
        Canonical FBP fuel type.
    isi : float
        Initial Spread Index.
    surface_fuel_consumption_kg_m2 : float
        Surface fuel consumption.
    surface_rate_of_spread_m_min : float
        Surface rate of spread.
    critical_surface_intensity_kw_m : float
        Van Wagner critical surface intensity for crown initiation.
    critical_surface_ros_m_min : float
        The surface rate of spread at the critical intensity.
    crown_fraction_burned : float
        The FBP crown fraction burned, in [0, 1].
    crown_fuel_consumption_kg_m2 : float
        Crown fuel consumed.
    total_fuel_consumption_kg_m2 : float
        Surface plus crown fuel consumed.
    rate_of_spread_m_min : float
        Head fire rate of spread, including the C6 crown adjustment.
    head_fire_intensity_kw_m : float
        Head fire intensity using total fuel consumption.
    flame_length_m : float
        Byram flame length derived from the head fire intensity.
    fire_description : str
        ``S`` surface, ``I`` intermittent/passive, or ``C`` active crown fire.
    crown_rate_of_spread_m_min : float or None
        The C6 crown rate of spread, when the fuel type provides one.
    active_crown : bool or None
        The Van Wagner active-crown threshold, when a canopy bulk density is supplied.
    foliar_moisture_percent : float
        Foliar moisture content used by the initiation threshold.
    crown_base_height_m : float
        Crown base height used by the threshold.
    crown_fuel_load_kg_m2 : float
        Crown fuel load used by the consumption.
    surface_only : bool
        False; the result includes crown fire.
    """

    fuel_type: str
    isi: float
    surface_fuel_consumption_kg_m2: float
    surface_rate_of_spread_m_min: float
    critical_surface_intensity_kw_m: float
    critical_surface_ros_m_min: float
    crown_fraction_burned: float
    crown_fuel_consumption_kg_m2: float
    total_fuel_consumption_kg_m2: float
    rate_of_spread_m_min: float
    head_fire_intensity_kw_m: float
    flame_length_m: float
    fire_description: str
    crown_rate_of_spread_m_min: float | None
    active_crown: bool | None
    foliar_moisture_percent: float
    crown_base_height_m: float
    crown_fuel_load_kg_m2: float
    surface_only: bool = False

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
            "surface_rate_of_spread_m_min": self.surface_rate_of_spread_m_min,
            "critical_surface_intensity_kw_m": self.critical_surface_intensity_kw_m,
            "critical_surface_ros_m_min": self.critical_surface_ros_m_min,
            "crown_fraction_burned": self.crown_fraction_burned,
            "crown_fuel_consumption_kg_m2": self.crown_fuel_consumption_kg_m2,
            "total_fuel_consumption_kg_m2": self.total_fuel_consumption_kg_m2,
            "rate_of_spread_m_min": self.rate_of_spread_m_min,
            "head_fire_intensity_kw_m": self.head_fire_intensity_kw_m,
            "flame_length_m": self.flame_length_m,
            "fire_description": self.fire_description,
            "crown_rate_of_spread_m_min": self.crown_rate_of_spread_m_min,
            "active_crown": self.active_crown,
            "foliar_moisture_percent": self.foliar_moisture_percent,
            "crown_base_height_m": self.crown_base_height_m,
            "crown_fuel_load_kg_m2": self.crown_fuel_load_kg_m2,
            "surface_only": self.surface_only,
        }


def foliar_moisture_content(
    latitude_deg: float,
    longitude_deg: float,
    elevation_m: float,
    julian_day: int,
    *,
    greenup_day: float = 0.0,
) -> float:
    """Return the FBP foliar moisture content.

    Parameters
    ----------
    latitude_deg : float
        Latitude in decimal degrees.
    longitude_deg : float
        Longitude in decimal degrees.
    elevation_m : float
        Elevation in metres.
    julian_day : int
        Julian day.
    greenup_day : float, optional
        The green-up day, or 0 to derive it from latitude and longitude.

    Returns
    -------
    float
        Foliar moisture content in percent.

    Raises
    ------
    FireFuelError
        If the latitude, longitude, or day is out of range.
    """
    latitude = _number(latitude_deg, "latitude_deg")
    longitude = _number(longitude_deg, "longitude_deg")
    elevation = _number(elevation_m, "elevation_m")
    day = _number(julian_day, "julian_day")
    if latitude < -90.0 or latitude > 90.0:
        raise FireFuelError("latitude_deg must be between -90 and 90")
    if longitude < -180.0 or longitude > 360.0:
        raise FireFuelError("longitude_deg must be between -180 and 360")
    if day < 0.0 or day > 366.0:
        raise FireFuelError("julian_day must be between 0 and 366")
    greenup = _number(greenup_day, "greenup_day")
    west_longitude = abs(longitude)
    if greenup <= 0.0:
        if elevation <= 0.0:
            latitude_n = 46.0 + 23.4 * math.exp(-0.036 * (150.0 - west_longitude))
        else:
            latitude_n = 43.0 + 33.7 * math.exp(-0.0351 * (150.0 - west_longitude))
        if elevation <= 0.0:
            greenup = 151.0 * (latitude / latitude_n)
        else:
            greenup = 142.1 * (latitude / latitude_n) + 0.0172 * elevation
    greenup = round(greenup)
    distance = abs(day - greenup)
    if distance < 30.0:
        return 85.0 + 0.0189 * distance**2
    if distance < 50.0:
        return 32.9 + 3.17 * distance - 0.0288 * distance**2
    return 120.0


def critical_surface_intensity(foliar_moisture_percent: float, crown_base_height_m: float) -> float:
    """Return Van Wagner's critical surface intensity for crown initiation.

    Parameters
    ----------
    foliar_moisture_percent : float
        Foliar moisture content in percent.
    crown_base_height_m : float
        Crown base height in metres.

    Returns
    -------
    float
        Critical surface intensity in kW/m.
    """
    fmc = _non_negative_helper(foliar_moisture_percent, "foliar_moisture_percent")
    cbh = _non_negative_helper(crown_base_height_m, "crown_base_height_m")
    return float(0.001 * cbh**1.5 * (460.0 + 25.9 * fmc) ** 1.5)


def critical_surface_ros(
    critical_intensity_kw_m: float, surface_fuel_consumption_kg_m2: float
) -> float:
    """Return the surface rate of spread at the critical intensity.

    Parameters
    ----------
    critical_intensity_kw_m : float
        Critical surface intensity in kW/m.
    surface_fuel_consumption_kg_m2 : float
        Surface fuel consumption in kg/m².

    Returns
    -------
    float
        The critical surface rate of spread in m/min.
    """
    intensity = _non_negative_helper(critical_intensity_kw_m, "critical_intensity_kw_m")
    sfc = _non_negative_helper(surface_fuel_consumption_kg_m2, "surface_fuel_consumption_kg_m2")
    if sfc <= 0.0:
        raise FireFuelError("surface_fuel_consumption_kg_m2 must be positive")
    return intensity / (300.0 * sfc)


def crown_fraction_burned(surface_ros_m_min: float, critical_ros_m_min: float) -> float:
    """Return the FBP crown fraction burned.

    Parameters
    ----------
    surface_ros_m_min : float
        The surface rate of spread in m/min.
    critical_ros_m_min : float
        The critical surface rate of spread in m/min.

    Returns
    -------
    float
        The crown fraction burned in [0, 1].
    """
    ros = _non_negative_helper(surface_ros_m_min, "surface_ros_m_min")
    critical = _non_negative_helper(critical_ros_m_min, "critical_ros_m_min")
    if ros <= critical:
        return 0.0
    return 1.0 - math.exp(-0.23 * (ros - critical))


def crown_rate_of_spread_c6(isi: float, foliar_moisture_percent: float) -> float:
    """Return the C6 crown rate of spread.

    Parameters
    ----------
    isi : float
        Initial Spread Index.
    foliar_moisture_percent : float
        Foliar moisture content in percent.

    Returns
    -------
    float
        The C6 crown rate of spread in m/min.
    """
    spread = _non_negative_helper(isi, "isi")
    fmc = _non_negative_helper(foliar_moisture_percent, "foliar_moisture_percent")
    fme = ((1.5 - 0.00275 * fmc) ** 4) / (460.0 + 25.9 * fmc) * 1000.0
    return 60.0 * (1.0 - math.exp(-0.0497 * spread)) * fme / _FME_AVG


def van_wagner_active_crown(rate_of_spread_m_min: float, canopy_bulk_density_kg_m3: float) -> bool:
    """Return whether the Van Wagner active-crown threshold is met.

    Parameters
    ----------
    rate_of_spread_m_min : float
        The head fire rate of spread in m/min.
    canopy_bulk_density_kg_m3 : float
        Canopy bulk density in kg/m³.

    Returns
    -------
    bool
        True when the rate of spread reaches ``3 / canopy bulk density``.

    Raises
    ------
    FireFuelError
        If the canopy bulk density is not positive.
    """
    ros = _non_negative_helper(rate_of_spread_m_min, "rate_of_spread_m_min")
    cbd = _non_negative_helper(canopy_bulk_density_kg_m3, "canopy_bulk_density_kg_m3")
    if cbd <= 0.0:
        raise FireFuelError("canopy_bulk_density_kg_m3 must be positive")
    return ros >= 3.0 / cbd


def _non_negative_helper(value: object, field: str) -> float:
    """Return a finite non-negative float."""
    number = _number(value, field)
    if number < 0.0:
        raise FireFuelError(f"{field} must be non-negative")
    return number


def fbp_crown_fire(
    fuel_type: str,
    ffmc: float,
    bui: float,
    wind_kmh: float,
    *,
    foliar_moisture_percent: float | None = None,
    latitude_deg: float = 55.0,
    longitude_deg: float = -120.0,
    elevation_m: float = 0.0,
    julian_day: int = 180,
    crown_base_height_m: float | None = None,
    crown_fuel_load_kg_m2: float | None = None,
    conifer_percent: float = 50.0,
    dead_fir_percent: float = 35.0,
    crown_closure_percent: float = 80.0,
    grass_fuel_load_kg_m2: float = 0.35,
    canopy_bulk_density_kg_m3: float | None = None,
) -> CrownFireResult:
    """Compute the FBP crown-fire result on top of the surface-fire layer.

    Parameters
    ----------
    fuel_type : str
        FBP fuel type.
    ffmc : float
        Fine Fuel Moisture Code.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed.
    foliar_moisture_percent : float or None, optional
        Foliar moisture content. None derives it from latitude, longitude, elevation, and
        Julian day.
    latitude_deg, longitude_deg, elevation_m, julian_day : optional
        Site and day inputs for the derived foliar moisture.
    crown_base_height_m : float or None, optional
        Crown base height; None uses the fuel-type default.
    crown_fuel_load_kg_m2 : float or None, optional
        Crown fuel load; None uses the fuel-type default.
    conifer_percent : float, optional
        Conifer percentage for M1/M2 (default 50).
    dead_fir_percent : float, optional
        Dead fir percentage for M3/M4 (default 35).
    crown_closure_percent : float, optional
        Crown closure for O1 (default 80).
    grass_fuel_load_kg_m2 : float, optional
        Grass fuel load for O1 (default 0.35).
    canopy_bulk_density_kg_m3 : float or None, optional
        Canopy bulk density for the Van Wagner active-crown threshold.

    Returns
    -------
    CrownFireResult
        Surface and crown fire behaviour.

    Raises
    ------
    FireFuelError
        If an input is out of range.
    """
    name = canonical_fuel_type(fuel_type)
    surface: FBPSurfaceResult = fbp_surface_fire(
        name,
        ffmc,
        bui,
        wind_kmh,
        conifer_percent=conifer_percent,
        dead_fir_percent=dead_fir_percent,
        crown_closure_percent=crown_closure_percent,
        grass_fuel_load_kg_m2=grass_fuel_load_kg_m2,
    )
    fmc = (
        foliar_moisture_content(
            latitude_deg,
            longitude_deg,
            elevation_m,
            julian_day,
        )
        if foliar_moisture_percent is None
        else _non_negative_helper(foliar_moisture_percent, "foliar_moisture_percent")
    )
    cbh = (
        _non_negative_helper(crown_base_height_m, "crown_base_height_m")
        if crown_base_height_m is not None
        else CROWN_BASE_HEIGHT_M[name]
    )
    cfl = (
        _non_negative_helper(crown_fuel_load_kg_m2, "crown_fuel_load_kg_m2")
        if crown_fuel_load_kg_m2 is not None
        else CROWN_FUEL_LOAD_KG_M2[name]
    )
    csi = critical_surface_intensity(fmc, cbh)
    critical_ros = critical_surface_ros(csi, surface.surface_fuel_consumption_kg_m2)
    crown_ros: float | None = None
    if name == "C6":
        crown_ros = crown_rate_of_spread_c6(surface.isi, fmc)
        if crown_ros > surface.rate_of_spread_m_min and (
            surface.rate_of_spread_m_min > critical_ros
        ):
            cfb = crown_fraction_burned(surface.rate_of_spread_m_min, critical_ros)
            ros = surface.rate_of_spread_m_min + cfb * (crown_ros - surface.rate_of_spread_m_min)
        else:
            cfb = 0.0
            ros = surface.rate_of_spread_m_min
    else:
        cfb = (
            crown_fraction_burned(surface.rate_of_spread_m_min, critical_ros) if cfl > 0.0 else 0.0
        )
        ros = surface.rate_of_spread_m_min
    cfc = cfl * cfb
    if name in {"M1", "M2"}:
        cfc *= _probability(conifer_percent / 100.0, "conifer_percent")
    elif name in {"M3", "M4"}:
        cfc *= _probability(dead_fir_percent / 100.0, "dead_fir_percent")
    tfc = surface.surface_fuel_consumption_kg_m2 + cfc
    intensity = 300.0 * tfc * ros
    flame_length = 0.0 if intensity <= 0.0 else 0.0775 * intensity**0.46
    description = "S" if cfb < 0.1 else ("C" if cfb >= 0.9 else "I")
    active = (
        None
        if canopy_bulk_density_kg_m3 is None
        else van_wagner_active_crown(ros, canopy_bulk_density_kg_m3)
    )
    return CrownFireResult(
        fuel_type=name,
        isi=surface.isi,
        surface_fuel_consumption_kg_m2=surface.surface_fuel_consumption_kg_m2,
        surface_rate_of_spread_m_min=surface.rate_of_spread_m_min,
        critical_surface_intensity_kw_m=csi,
        critical_surface_ros_m_min=critical_ros,
        crown_fraction_burned=cfb,
        crown_fuel_consumption_kg_m2=cfc,
        total_fuel_consumption_kg_m2=tfc,
        rate_of_spread_m_min=ros,
        head_fire_intensity_kw_m=intensity,
        flame_length_m=flame_length,
        fire_description=description,
        crown_rate_of_spread_m_min=crown_ros,
        active_crown=active,
        foliar_moisture_percent=fmc,
        crown_base_height_m=cbh,
        crown_fuel_load_kg_m2=cfl,
    )
