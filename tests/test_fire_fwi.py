"""Tests for the Canadian FWI moisture codes.

The reference sequences in ``tests/fixtures/fire`` were generated with the ``cffdrs`` R
package (Canadian Forest Fire Danger Rating System). The package is a validation oracle only;
the Python implementation is independent.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from ws4.fire.fuel import FireFuelError
from ws4.fire.fwi import (
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

FIXTURES = Path(__file__).parent / "fixtures" / "fire"

WEATHER = [
    DailyWeather(2026, 7, 1, 20, 40, 10, 0, 55),
    DailyWeather(2026, 7, 2, 22, 35, 12, 0, 55),
    DailyWeather(2026, 7, 3, 18, 50, 8, 2, 55),
    DailyWeather(2026, 7, 4, 25, 30, 15, 0, 55),
    DailyWeather(2026, 7, 5, 27, 25, 20, 0, 55),
    DailyWeather(2026, 7, 6, 21, 45, 9, 0, 55),
    DailyWeather(2026, 7, 7, 19, 60, 5, 5, 55),
    DailyWeather(2026, 7, 8, 23, 38, 11, 0, 55),
    DailyWeather(2026, 7, 9, 26, 28, 18, 0, 55),
    DailyWeather(2026, 7, 10, 24, 33, 14, 0, 55),
]


def reference(name: str) -> list[dict[str, str]]:
    """Read one reference sequence."""
    with (FIXTURES / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_fwi_sequence_matches_the_reference_at_lat55() -> None:
    states = fwi_sequence(WEATHER, initial_fwi_state(85, 6, 15))

    for state, row in zip(states, reference("fwi_lat55.csv"), strict=True):
        assert state.ffmc == pytest.approx(float(row["FFMC"]), abs=1e-4)
        assert state.dmc == pytest.approx(float(row["DMC"]), abs=1e-4)
        assert state.dc == pytest.approx(float(row["DC"]), abs=1e-4)
        assert state.isi == pytest.approx(float(row["ISI"]), abs=1e-4)
        assert state.bui == pytest.approx(float(row["BUI"]), abs=1e-4)
        assert state.fwi == pytest.approx(float(row["FWI"]), abs=1e-4)
        assert state.dsr == pytest.approx(float(row["DSR"]), abs=1e-4)


def test_fwi_sequence_matches_the_reference_at_lat20() -> None:
    weather = [
        DailyWeather(
            day.year,
            day.month,
            day.day,
            day.temperature_c,
            day.relative_humidity_percent,
            day.wind_kmh,
            day.precipitation_mm,
            20.0,
        )
        for day in WEATHER
    ]
    states = fwi_sequence(weather, initial_fwi_state(85, 6, 15))

    for state, row in zip(states, reference("fwi_lat20.csv"), strict=True):
        assert state.ffmc == pytest.approx(float(row["FFMC"]), abs=1e-4)
        assert state.dmc == pytest.approx(float(row["DMC"]), abs=1e-4)
        assert state.dc == pytest.approx(float(row["DC"]), abs=1e-4)
        assert state.bui == pytest.approx(float(row["BUI"]), abs=1e-4)


def test_engine_step_and_run_agree() -> None:
    engine = FWIEngine(initial_fwi_state())
    manual = tuple(engine.step(day) for day in WEATHER[:3])
    again = FWIEngine(initial_fwi_state()).run(WEATHER[:3])

    assert manual == again


def test_initial_spread_index_has_an_fbp_high_wind_form() -> None:
    standard = initial_spread_index(90.0, 50.0, fbp=False)
    fbp = initial_spread_index(90.0, 50.0, fbp=True)

    assert fbp < standard
    assert initial_spread_index(90.0, 10.0, fbp=True) == pytest.approx(
        initial_spread_index(90.0, 10.0, fbp=False)
    )


def test_buildup_and_fire_weather_index_are_monotone() -> None:
    assert buildup_index(0.0, 0.0) == 0.0
    assert buildup_index(30.0, 300.0) > buildup_index(10.0, 100.0)
    assert fire_weather_index(10.0, 50.0) > fire_weather_index(5.0, 20.0)


def test_individual_codes_are_finite_for_a_normal_day() -> None:
    day = WEATHER[0]

    ffmc = fine_fuel_moisture_code(
        85.0,
        day.temperature_c,
        day.relative_humidity_percent,
        day.wind_kmh,
        day.precipitation_mm,
    )
    dmc = duff_moisture_code(
        6.0,
        day.temperature_c,
        day.relative_humidity_percent,
        day.precipitation_mm,
        55.0,
        7,
    )
    dc = drought_code(
        15.0,
        day.temperature_c,
        day.relative_humidity_percent,
        day.precipitation_mm,
        55.0,
        7,
    )

    assert 0.0 <= ffmc <= 101.0
    assert dmc >= 0.0
    assert dc >= 0.0


def test_weather_and_state_validate_and_round_trip() -> None:
    day = WEATHER[0]
    state = FWIState(88.0, 10.0, 20.0, 5.0, 9.0, 6.0, 0.5)

    assert DailyWeather.from_dict(day.to_dict()) == day
    assert FWIState.from_dict(state.to_dict()) == state
    with pytest.raises(FireFuelError, match="month"):
        DailyWeather(2026, 13, 1, 20, 40, 10, 0)
    with pytest.raises(FireFuelError, match="relative_humidity"):
        DailyWeather(2026, 7, 1, 20, 120, 10, 0)
    with pytest.raises(FireFuelError, match="precipitation"):
        DailyWeather(2026, 7, 1, 20, 40, 10, -1)
    with pytest.raises(FireFuelError, match="ffmc"):
        FWIState(102.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)


def test_engine_rejects_bad_types() -> None:
    with pytest.raises(FireFuelError, match="FWIState"):
        # deliberately invalid: the engine needs an FWIState
        FWIEngine("state")  # type: ignore[arg-type]
    with pytest.raises(FireFuelError, match="DailyWeather"):
        # deliberately invalid: the step needs a DailyWeather
        FWIEngine(initial_fwi_state()).step("day")  # type: ignore[arg-type]
