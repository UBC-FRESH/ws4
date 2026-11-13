"""Exact scfm fire-regime formula tests."""

from __future__ import annotations

import math

import pytest
from ws4.fire.regime import (
    FireRegimeError,
    fire_regime_diagnostics,
    fire_regime_parameters,
)


def test_scfm_regime_parameters_match_the_toy_polygon() -> None:
    params = fire_regime_parameters(
        [1.0, 2.0, 50.0, 100.0],
        years=10.0,
        burnable_area_ha=180.0 * 6.25,
        cell_size_ha=6.25,
    )

    assert params.n_fires == 4
    assert params.ignition_rate == pytest.approx(4.0 / (10.0 * 1125.0))
    assert params.p_escape == pytest.approx(0.5)
    assert params.mean_escaped_size_ha == pytest.approx(75.0)
    assert params.max_escaped_size_ha == pytest.approx(100.0)
    assert params.empirical_burn_rate == pytest.approx(153.0 / (10.0 * 1125.0))
    assert params.p_ignition == pytest.approx(params.ignition_rate * 6.25)
    assert params.max_burn_cells == 12


def test_scfm_regime_diagnostics_match_the_toy_simulation() -> None:
    diagnostics = fire_regime_diagnostics(
        burnable_area_ha=2500.0,
        years=2.0,
        ignition_rate=4e-4,
        p_escape=0.5,
        historical_sizes_ha=[1.0, 20.0, 40.0],
        simulated_sizes_ha=[6.25, 50.0, 100.0],
        cell_size_ha=6.25,
        empirical_burn_rate=0.01,
    )

    assert diagnostics.burnable_area_ha == pytest.approx(2500.0)
    assert diagnostics.target_ignitions == pytest.approx(1.0)
    assert diagnostics.achieved_ignitions == pytest.approx(1.5)
    assert diagnostics.target_escapes == pytest.approx(0.5)
    assert diagnostics.achieved_escapes == pytest.approx(1.0)
    assert diagnostics.model_mean_size_ha == pytest.approx(75.0)
    assert diagnostics.historical_mean_size_ha == pytest.approx(30.0)
    assert diagnostics.historical_median_size_ha == pytest.approx(30.0)
    assert diagnostics.achieved_fri_years == pytest.approx(2.0 / (150.0 / 2500.0))
    assert diagnostics.target_fri_years == pytest.approx(100.0)


def test_empty_regime_has_zero_ignition_and_nan_sizes() -> None:
    params = fire_regime_parameters([], years=10.0, burnable_area_ha=2500.0, cell_size_ha=6.25)

    assert params.n_fires == 0
    assert params.ignition_rate == 0.0
    assert params.p_ignition == 0.0
    assert math.isnan(params.mean_escaped_size_ha)
    assert params.max_burn_cells == 0


def test_bad_regime_inputs_fail() -> None:
    with pytest.raises(FireRegimeError, match="years"):
        fire_regime_parameters([], years=0.0, burnable_area_ha=2500.0, cell_size_ha=6.25)
    with pytest.raises(FireRegimeError, match="sizes_ha"):
        fire_regime_parameters([-1.0], years=1.0, burnable_area_ha=1.0, cell_size_ha=1.0)
    with pytest.raises(FireRegimeError, match="p_escape"):
        fire_regime_diagnostics(
            burnable_area_ha=1.0,
            years=1.0,
            ignition_rate=0.1,
            p_escape=1.5,
            historical_sizes_ha=[1.0],
            simulated_sizes_ha=[1.0],
            cell_size_ha=1.0,
        )
