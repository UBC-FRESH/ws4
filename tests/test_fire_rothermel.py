"""Standard-case tests for the Rothermel surface-fire kernel.

The reference values were generated with the ``Rothermel`` R package (Vacchiano and Ascoli,
2015), which implements Rothermel (1972) with the Frandsen, Albini, and Andrews corrections.
The package is used here only as a validation oracle, not as a runtime dependency. The inputs
and the standard fuel-model parameters are public scientific data.
"""

from __future__ import annotations

import pytest
from ws4.fire.environment import FireEnvironment
from ws4.fire.fuel import ANDERSON_13, MOISTURE_SCENARIOS, FuelClass, FuelModel, FuelMoisture
from ws4.fire.rothermel import RothermelResult, surface_fire

STANDARD_REFS = [
    ("A1", 30.65, 156.87, 21.10, 200.36, 392.14),
    ("A2", 13.29, 668.71, 14.45, 550.87, 2485.98),
    ("A3", 39.12, 550.01, 24.92, 388.87, 596.30),
    ("A4", 27.17, 2272.80, 17.18, 1330.95, 2938.30),
    ("A5", 4.10, 328.65, 19.34, 202.13, 2960.25),
    ("A6", 11.16, 407.12, 17.72, 226.51, 1217.99),
    ("A7", 9.70, 450.11, 19.36, 265.02, 1638.91),
    ("A8", 0.66, 171.72, 7.44, 134.62, 12275.96),
    ("A9", 2.85, 446.36, 9.32, 428.81, 9036.17),
    ("A10", 2.97, 1115.88, 9.62, 577.05, 11657.71),
    ("A11", 2.00, 440.76, 9.71, 159.86, 4799.49),
    ("A12", 4.52, 1112.66, 9.20, 411.24, 5453.34),
    ("A13", 5.31, 1847.20, 7.65, 696.53, 7864.84),
]

A3_GRID_REFS = [
    (0.0, 0.0, 1.51, 0.0),
    (0.0, 10.0, 2.05, 0.0),
    (0.0, 30.0, 6.34, 0.0),
    (5.0, 0.0, 21.82, 13.46),
    (5.0, 10.0, 22.36, 13.46),
    (5.0, 30.0, 26.65, 13.46),
    (10.0, 0.0, 51.90, 33.38),
    (10.0, 10.0, 52.44, 33.38),
    (10.0, 30.0, 56.73, 33.38),
    (15.0, 0.0, 87.24, 56.79),
    (15.0, 10.0, 87.78, 56.79),
    (15.0, 30.0, 92.07, 56.79),
    (20.0, 0.0, 126.51, 82.80),
    (20.0, 10.0, 127.05, 82.80),
    (20.0, 30.0, 131.34, 82.80),
]


def custom_fuel() -> FuelModel:
    """Return the dynamic custom fuel model from the R package example."""
    return FuelModel(
        name="custom",
        model_type="D",
        classes=(
            FuelClass(2.0, 5600.0, 18622.0),
            FuelClass(1.0, 358.0, 18622.0),
            FuelClass(0.5, 98.0, 18622.0),
            FuelClass(3.0, 6200.0, 19500.0),
            FuelClass(8.0, 8000.0, 20000.0),
        ),
        depth_cm=50.0,
        moisture_of_extinction_percent=30.0,
    )


@pytest.mark.parametrize(
    ("model", "ros", "reaction", "wind", "heat_source", "heat_sink"),
    STANDARD_REFS,
)
def test_standard_fuel_models_match_the_reference(
    model: str, ros: float, reaction: float, wind: float, heat_source: float, heat_sink: float
) -> None:
    result = surface_fire(
        ANDERSON_13[model],
        MOISTURE_SCENARIOS["D2L2"],
        FireEnvironment(wind_kmh=8.0, slope_percent=0.0),
    )

    assert result.rate_of_spread_m_min == pytest.approx(ros, abs=0.01)
    assert result.reaction_intensity_kw_m2 == pytest.approx(reaction, abs=0.01)
    assert result.wind_factor == pytest.approx(wind, abs=0.01)
    assert result.heat_source_kw_m2 == pytest.approx(heat_source, abs=0.01)
    assert result.heat_sink_kj_m3 == pytest.approx(heat_sink, abs=0.01)


def test_custom_dynamic_model_matches_the_reference() -> None:
    result = surface_fire(
        custom_fuel(),
        FuelMoisture(7, 8, 9, 40, 60),
        FireEnvironment(wind_kmh=5.0, slope_percent=10.0),
    )

    assert result.rate_of_spread_m_min == pytest.approx(6.43, abs=0.01)
    assert result.reaction_intensity_kw_m2 == pytest.approx(1486.55, abs=0.01)
    assert result.wind_factor == pytest.approx(6.75, abs=0.01)
    assert result.slope_factor == pytest.approx(0.25, abs=0.01)
    assert result.heat_source_kw_m2 == pytest.approx(501.85, abs=0.01)
    assert result.heat_sink_kj_m3 == pytest.approx(4682.05, abs=0.01)


@pytest.mark.parametrize(("wind", "slope", "ros", "wind_factor"), A3_GRID_REFS)
def test_a3_wind_and_slope_grid_matches_the_reference(
    wind: float, slope: float, ros: float, wind_factor: float
) -> None:
    result = surface_fire(
        ANDERSON_13["A3"],
        MOISTURE_SCENARIOS["D2L2"],
        FireEnvironment(wind_kmh=wind, slope_percent=slope),
    )

    assert result.rate_of_spread_m_min == pytest.approx(ros, abs=0.01)
    assert result.wind_factor == pytest.approx(wind_factor, abs=0.01)


def test_wind_and_slope_increase_rate_of_spread() -> None:
    calm = surface_fire(ANDERSON_13["A3"], MOISTURE_SCENARIOS["D2L2"], FireEnvironment())
    windy = surface_fire(
        ANDERSON_13["A3"],
        MOISTURE_SCENARIOS["D2L2"],
        FireEnvironment(wind_kmh=15.0),
    )
    steep = surface_fire(
        ANDERSON_13["A3"],
        MOISTURE_SCENARIOS["D2L2"],
        FireEnvironment(slope_percent=30.0),
    )

    assert windy.rate_of_spread_m_min > calm.rate_of_spread_m_min
    assert steep.rate_of_spread_m_min > calm.rate_of_spread_m_min
    assert windy.flame_length_m > calm.flame_length_m


def test_moisture_reduces_rate_of_spread_and_extinction_stops_it() -> None:
    dry = surface_fire(ANDERSON_13["A1"], MOISTURE_SCENARIOS["D1L1"], FireEnvironment(wind_kmh=5.0))
    wet = surface_fire(ANDERSON_13["A1"], MOISTURE_SCENARIOS["D4L4"], FireEnvironment(wind_kmh=5.0))
    extinct = surface_fire(
        ANDERSON_13["A1"],
        FuelMoisture(30, 30, 30, 30, 60),
        FireEnvironment(wind_kmh=5.0),
    )

    assert dry.rate_of_spread_m_min > wet.rate_of_spread_m_min
    assert extinct.rate_of_spread_m_min == pytest.approx(0.0)
    assert extinct.reaction_intensity_kw_m2 == pytest.approx(0.0)


def test_result_serializes_with_units() -> None:
    result = surface_fire(
        ANDERSON_13["A3"], MOISTURE_SCENARIOS["D2L2"], FireEnvironment(wind_kmh=8.0)
    )
    payload = result.to_dict()
    units = payload["units"]
    assert isinstance(units, dict)

    assert isinstance(result, RothermelResult)
    assert payload["fuel_model"] == "A3"
    assert units["rate_of_spread"] == "m/min"
    assert float(str(payload["head_fire_intensity_kw_m"])) > 0.0
    assert float(str(payload["flame_length_m"])) > 0.0


def test_surface_fire_rejects_bad_inputs() -> None:
    with pytest.raises(Exception, match="FuelModel"):
        surface_fire("A3", MOISTURE_SCENARIOS["D2L2"], FireEnvironment())  # type: ignore[arg-type]
    with pytest.raises(Exception, match="consumption_fraction"):
        surface_fire(
            ANDERSON_13["A3"],
            MOISTURE_SCENARIOS["D2L2"],
            FireEnvironment(),
            consumption_fraction=1.5,
        )
