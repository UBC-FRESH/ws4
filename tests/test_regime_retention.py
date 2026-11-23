"""Tests for the P164.9 size-dependent retention model."""

from __future__ import annotations

import random

import pytest
from ws4.fire.regime_calibration import PotentialFire
from ws4.fire.regime_retention import (
    RetentionParameters,
    draw_retention,
    metrics_for,
    retention_candidates,
    simulate_retention,
)


def _parameters() -> RetentionParameters:
    """Return a valid retention parameter point."""
    return RetentionParameters(
        contained_median_ha=20.0,
        contained_sigma=0.2,
        contained_exponent=0.0,
        escaped_fraction_median=0.2,
        escaped_fraction_sigma=0.2,
        escape_cap_ha=20_000.0,
        intercept=-7.0,
    )


def _records() -> list[PotentialFire]:
    """Return a large-potential sample."""
    return [
        PotentialFire(potential_ha=1_000.0, active_days=2.0, fwi=20.0, bui=60.0, wind_kmh=10.0),
        PotentialFire(potential_ha=5_000.0, active_days=4.0, fwi=28.0, bui=80.0, wind_kmh=12.0),
        PotentialFire(potential_ha=20_000.0, active_days=6.0, fwi=35.0, bui=100.0, wind_kmh=20.0),
    ]


def test_contained_component_can_produce_intermediate_sizes() -> None:
    values = simulate_retention(_parameters(), _records(), seed=3)

    assert len(values) == 3
    assert all(6.25 <= value <= 1_000.0 for value in values)
    assert max(values) > 6.25


def test_draw_is_deterministic_and_bounded() -> None:
    first = draw_retention(_parameters(), random.Random(7), _records()[2])
    second = draw_retention(_parameters(), random.Random(7), _records()[2])

    assert first == second
    assert 6.25 <= first.target_area_ha <= 20_000.0


def test_candidates_are_deterministic_and_bounded() -> None:
    first = retention_candidates(9, count=6)
    second = retention_candidates(9, count=6)

    assert first == second
    for parameters in first:
        assert 6.25 <= parameters.contained_median_ha <= 2_000.0
        assert 0.0 <= parameters.contained_exponent <= 1.0


def test_metrics_use_five_draws() -> None:
    metrics = metrics_for(_parameters(), _records(), seed=4)

    assert metrics.count == 15


def test_invalid_candidate_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="count"):
        retention_candidates(1, count=0)
    with pytest.raises(ValueError, match="seed"):
        retention_candidates(-1)
