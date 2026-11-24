"""Tests for the survival/escape fire process."""

from __future__ import annotations

import random

import pytest
from ws4.fire.fuel import FireFuelError
from ws4.fire.regime_calibration import PotentialFire
from ws4.fire.regime_retention import RetentionParameters, draw_retention
from ws4.fire.survival import (
    RelativeSuppressionConfig,
    SurvivalConfig,
    draw_relative_suppression,
    draw_survival,
)


def test_escape_probability_increases_with_duration_and_weather() -> None:
    config = SurvivalConfig()
    low = config.escape_probability(active_days=0.5, fwi=10.0, bui=50.0, wind_kmh=5.0)
    high = config.escape_probability(active_days=7.0, fwi=40.0, bui=120.0, wind_kmh=30.0)

    assert 0.0 < low < high < 1.0


def test_forced_escape_is_bounded_by_the_cap() -> None:
    config = SurvivalConfig(intercept=100.0, escape_median_ha=8_000.0, escape_cap_ha=10_000.0)
    outcome = draw_survival(
        config,
        random.Random(1),
        active_days=3.0,
        fwi=40.0,
        bui=120.0,
        wind_kmh=20.0,
    )

    assert outcome.escaped is True
    assert outcome.target_area_ha == pytest.approx(outcome.max_burned_area_ha)
    assert 0.0 < outcome.max_burned_area_ha <= 10_000.0


def test_forced_containment_returns_the_contained_distribution() -> None:
    config = SurvivalConfig(intercept=-100.0, contained_median_ha=20.0)
    outcome = draw_survival(
        config,
        random.Random(2),
        active_days=3.0,
        fwi=40.0,
        bui=120.0,
        wind_kmh=20.0,
    )

    assert outcome.escaped is False
    assert 0.0 < outcome.target_area_ha < 100.0
    assert outcome.target_area_ha == pytest.approx(outcome.max_burned_area_ha)


def test_survival_draw_is_deterministic() -> None:
    config = SurvivalConfig()
    kwargs = {"active_days": 2.0, "fwi": 30.0, "bui": 80.0, "wind_kmh": 15.0}
    first = draw_survival(config, random.Random(7), **kwargs)
    second = draw_survival(config, random.Random(7), **kwargs)

    assert first == second


def test_survival_config_rejects_invalid_sizes_and_inputs() -> None:
    with pytest.raises(FireFuelError, match="contained_median_ha"):
        SurvivalConfig(contained_median_ha=0.0)
    with pytest.raises(FireFuelError, match="escape_median_ha"):
        SurvivalConfig(escape_median_ha=20_000.0, escape_cap_ha=10_000.0)
    with pytest.raises(FireFuelError, match="non-negative"):
        SurvivalConfig().escape_probability(
            active_days=-1.0,
            fwi=30.0,
            bui=80.0,
            wind_kmh=15.0,
        )


def test_relative_suppression_keeps_a_fraction_of_potential() -> None:
    config = RelativeSuppressionConfig(
        intercept=-100.0,
        contained_fraction_median=0.2,
        contained_fraction_sigma=0.01,
    )
    outcome = draw_relative_suppression(
        config,
        random.Random(3),
        potential_area_ha=100.0,
        active_days=2.0,
        fwi=30.0,
        bui=80.0,
        wind_kmh=10.0,
    )

    assert outcome.escaped is False
    assert outcome.target_area_ha == pytest.approx(20.0, rel=0.1)
    assert outcome.target_area_ha < 100.0


def test_relative_escape_is_bounded_by_cap() -> None:
    config = RelativeSuppressionConfig(
        intercept=100.0,
        escaped_fraction_median=0.9,
        escaped_fraction_sigma=0.01,
        escape_cap_ha=50.0,
    )
    outcome = draw_relative_suppression(
        config,
        random.Random(4),
        potential_area_ha=200.0,
        active_days=5.0,
        fwi=40.0,
        bui=120.0,
        wind_kmh=20.0,
    )

    assert outcome.escaped is True
    assert outcome.target_area_ha == pytest.approx(50.0)


def test_relative_suppression_rejects_invalid_fractions() -> None:
    with pytest.raises(FireFuelError, match="contained_fraction_median"):
        RelativeSuppressionConfig(contained_fraction_median=1.5)
    with pytest.raises(FireFuelError, match="potential_area_ha"):
        draw_relative_suppression(
            RelativeSuppressionConfig(),
            random.Random(5),
            potential_area_ha=0.0,
            active_days=1.0,
            fwi=20.0,
            bui=60.0,
            wind_kmh=5.0,
        )


def test_relative_suppression_can_use_a_contained_size_distribution() -> None:
    config = RelativeSuppressionConfig(
        intercept=-100.0,
        contained_median_ha=20.0,
        contained_fraction_sigma=0.01,
        contained_exponent=0.0,
    )
    outcome = draw_relative_suppression(
        config,
        random.Random(5),
        potential_area_ha=1_000.0,
        active_days=2.0,
        fwi=30.0,
        bui=80.0,
        wind_kmh=10.0,
    )

    assert outcome.escaped is False
    assert outcome.target_area_ha == pytest.approx(20.0, rel=0.1)
    assert outcome.target_area_ha < 100.0


def test_relative_suppression_matches_the_retention_draw() -> None:
    """The applied config must reproduce the calibration draw exactly."""
    config = RelativeSuppressionConfig(
        contained_median_ha=42.0,
        contained_fraction_sigma=0.37,
        contained_exponent=0.4,
        escaped_fraction_median=0.5,
        escaped_fraction_sigma=0.2,
        escape_cap_ha=12_000.0,
        intercept=-4.0,
    )
    parameters = RetentionParameters(
        contained_median_ha=42.0,
        contained_sigma=0.37,
        contained_exponent=0.4,
        escaped_fraction_median=0.5,
        escaped_fraction_sigma=0.2,
        escape_cap_ha=12_000.0,
        intercept=-4.0,
    )
    record = PotentialFire(
        potential_ha=1_000.0,
        active_days=2.0,
        fwi=30.0,
        bui=80.0,
        wind_kmh=10.0,
    )
    applied = draw_relative_suppression(
        config,
        random.Random(5),
        potential_area_ha=record.potential_ha,
        active_days=record.active_days,
        fwi=record.fwi,
        bui=record.bui,
        wind_kmh=record.wind_kmh,
    )
    calibrated = draw_retention(parameters, random.Random(5), record)

    assert applied.escaped == calibrated.escaped
    assert applied.target_area_ha == pytest.approx(calibrated.target_area_ha)
