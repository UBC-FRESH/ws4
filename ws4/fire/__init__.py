"""Credible surface-fire behaviour for WS4.

The package starts with the fuel, moisture, and environment contracts and the validated
Rothermel (1972) surface-fire kernel. Crown fire, FBP-specific fuel types, and spatially
explicit growth follow in later P151 tasks.
"""

from __future__ import annotations

from .environment import FireEnvironment
from .fuel import (
    ANDERSON_13,
    DEFAULT_MOISTURE,
    FUEL_CLASSES,
    MOISTURE_SCENARIOS,
    FireFuelError,
    FuelClass,
    FuelModel,
    FuelMoisture,
)
from .fwi import (
    DEFAULT_LATITUDE,
    FFMC_COEFFICIENT,
    DailyWeather,
    FWIEngine,
    FWIState,
    buildup_index,
    drought_code,
    duff_moisture_code,
    fine_fuel_moisture_code,
    fire_weather_index,
    fwi_sequence,
    initial_fwi_state,
    initial_spread_index,
)
from .rothermel import (
    DEFAULT_CONSUMPTION_FRACTION,
    DEFAULT_HEAT_YIELD_KJ_KG,
    KERNEL_VERSION,
    RothermelResult,
    surface_fire,
)

__all__ = [
    "ANDERSON_13",
    "DEFAULT_CONSUMPTION_FRACTION",
    "DEFAULT_HEAT_YIELD_KJ_KG",
    "DEFAULT_LATITUDE",
    "DEFAULT_MOISTURE",
    "FFMC_COEFFICIENT",
    "FUEL_CLASSES",
    "KERNEL_VERSION",
    "MOISTURE_SCENARIOS",
    "DailyWeather",
    "FWIEngine",
    "FWIState",
    "FireEnvironment",
    "FireFuelError",
    "FuelClass",
    "FuelModel",
    "FuelMoisture",
    "RothermelResult",
    "buildup_index",
    "drought_code",
    "duff_moisture_code",
    "fine_fuel_moisture_code",
    "fire_weather_index",
    "fwi_sequence",
    "initial_fwi_state",
    "initial_spread_index",
    "surface_fire",
]
