"""Tests for the fire fuel, moisture, and environment contracts."""

from __future__ import annotations

import pytest
from ws4.fire.environment import FireEnvironment
from ws4.fire.fuel import (
    ANDERSON_13,
    DEFAULT_MOISTURE,
    MOISTURE_SCENARIOS,
    FireFuelError,
    FuelClass,
    FuelModel,
    FuelMoisture,
)


def test_standard_fuel_models_are_present_and_well_formed() -> None:
    assert len(ANDERSON_13) == 13
    assert set(ANDERSON_13) == {f"A{index}" for index in range(1, 14)}
    for model in ANDERSON_13.values():
        assert sum(model.loads_t_ha) > 0.0
        assert len(model.classes) == 5
        assert model.depth_cm > 0.0
        assert model.moisture_of_extinction_percent > 0.0


def test_moisture_scenarios_are_present() -> None:
    assert "D2L2" in MOISTURE_SCENARIOS
    assert DEFAULT_MOISTURE is MOISTURE_SCENARIOS["D2L2"]
    assert DEFAULT_MOISTURE.as_tuple() == (6.0, 7.0, 8.0, 60.0, 90.0)
    assert len(MOISTURE_SCENARIOS) == 16


def test_fuel_model_round_trip() -> None:
    model = ANDERSON_13["A3"]

    assert FuelModel.from_dict(model.to_dict()) == model


def test_moisture_round_trip() -> None:
    moisture = MOISTURE_SCENARIOS["D2L2"]

    assert FuelMoisture.from_dict(moisture.to_dict()) == moisture


def test_environment_round_trip() -> None:
    environment = FireEnvironment(
        wind_kmh=8.0,
        slope_percent=12.0,
        wind_direction_deg=225.0,
        aspect_deg=180.0,
        elevation_m=900.0,
        temperature_c=25.0,
        relative_humidity_percent=35.0,
    )

    assert FireEnvironment.from_dict(environment.to_dict()) == environment


def test_environment_normalizes_directions() -> None:
    environment = FireEnvironment(
        wind_kmh=1.0,
        slope_percent=1.0,
        wind_direction_deg=370.0,
        aspect_deg=-10.0,
    )

    assert environment.wind_direction_deg == pytest.approx(10.0)
    assert environment.aspect_deg == pytest.approx(350.0)


def test_invalid_fuel_values_are_rejected() -> None:
    with pytest.raises(FireFuelError, match="load_t_ha"):
        FuelClass(-1.0, 100.0, 18000.0)
    with pytest.raises(FireFuelError, match="sav_m2_m3"):
        FuelClass(1.0, 0.0, 18000.0)
    with pytest.raises(FireFuelError, match="heat_kj_kg"):
        FuelClass(1.0, 100.0, 0.0)
    with pytest.raises(FireFuelError, match="positive fuel load"):
        FuelModel(
            name="empty",
            model_type="S",
            classes=(FuelClass(0, 0, 18000),) * 5,
            depth_cm=10.0,
            moisture_of_extinction_percent=20.0,
        )
    with pytest.raises(FireFuelError, match="model_type"):
        FuelModel(
            name="bad",
            model_type="X",
            classes=ANDERSON_13["A1"].classes,
            depth_cm=10.0,
            moisture_of_extinction_percent=20.0,
        )
    with pytest.raises(FireFuelError, match="depth_cm"):
        FuelModel(
            name="bad",
            model_type="S",
            classes=ANDERSON_13["A1"].classes,
            depth_cm=0.0,
            moisture_of_extinction_percent=20.0,
        )


def test_invalid_moisture_is_rejected() -> None:
    with pytest.raises(FireFuelError, match="live herbaceous"):
        FuelMoisture(6, 7, 8, 20, 60)
    with pytest.raises(FireFuelError, match="dead_1h_percent"):
        FuelMoisture(-1, 7, 8, 60, 90)


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(FireFuelError, match="wind_kmh"):
        FireEnvironment(wind_kmh=-1.0)
    with pytest.raises(FireFuelError, match="slope_percent"):
        FireEnvironment(slope_percent=-1.0)
    with pytest.raises(FireFuelError, match="relative_humidity_percent"):
        FireEnvironment(relative_humidity_percent=120.0)
