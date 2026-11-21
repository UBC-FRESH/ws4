"""Tests for the P164.8 regime calibration harness."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from ws4.fire.regime_calibration import (
    ESCAPE_CAP_BOUNDS,
    PotentialFire,
    RegimeCalibrationError,
    RegimeMetrics,
    RegimeParameters,
    gate_results,
    load_potential_records,
    parameter_candidates,
    passes_gates,
    search_training,
    simulate,
    size_metrics,
    validate,
)


def _parameters() -> RegimeParameters:
    """Return a valid mid-range parameter point."""
    return RegimeParameters(
        contained_fraction_median=1e-3,
        contained_fraction_sigma=0.8,
        escaped_fraction_median=0.2,
        escaped_fraction_sigma=0.2,
        escape_cap_ha=12_000.0,
        intercept=-4.5,
    )


def _records() -> tuple[PotentialFire, ...]:
    """Return a small deterministic potential sample."""
    return (
        PotentialFire(potential_ha=1_000.0, active_days=2.0, fwi=20.0, bui=60.0, wind_kmh=10.0),
        PotentialFire(potential_ha=20_000.0, active_days=5.0, fwi=35.0, bui=100.0, wind_kmh=20.0),
        PotentialFire(potential_ha=8_000.0, active_days=1.0, fwi=12.0, bui=50.0, wind_kmh=5.0),
    )


def test_size_metrics_and_thresholds() -> None:
    metrics = size_metrics([10.0, 20.0, 100.0, 1_000.0, 10_000.0])

    assert metrics.count == 5
    assert metrics.median == pytest.approx(100.0)
    assert metrics.maximum == pytest.approx(10_000.0)
    assert metrics.over_100 == pytest.approx(0.4)
    assert metrics.over_1000 == pytest.approx(0.2)


def test_gate_results_are_specific_and_all_required() -> None:
    metrics = RegimeMetrics(
        count=10,
        mean=500.0,
        median=25.0,
        p90=500.0,
        p95=900.0,
        over_100=0.25,
        over_500=0.09,
        over_1000=0.06,
        over_5000=0.02,
        maximum=12_000.0,
    )

    results = gate_results(metrics)

    assert all(results.values())
    assert passes_gates(metrics)
    failing = replace(metrics, median=60.0)
    assert not gate_results(failing)["median"]
    assert not passes_gates(failing)


def test_parameters_reject_values_outside_the_protocol_bounds() -> None:
    with pytest.raises(RegimeCalibrationError, match="escape_cap_ha"):
        RegimeParameters(
            contained_fraction_median=1e-3,
            contained_fraction_sigma=0.8,
            escaped_fraction_median=0.2,
            escaped_fraction_sigma=0.2,
            escape_cap_ha=ESCAPE_CAP_BOUNDS[1] + 1.0,
            intercept=-4.5,
        )


def test_candidates_are_deterministic_and_bounded() -> None:
    first = parameter_candidates(7, count=5)
    second = parameter_candidates(7, count=5)

    assert first == second
    assert len(first) == 5
    for parameters in first:
        assert ESCAPE_CAP_BOUNDS[0] <= parameters.escape_cap_ha <= ESCAPE_CAP_BOUNDS[1]


def test_simulation_and_search_are_deterministic() -> None:
    records = _records()
    first = simulate(_parameters(), records, seed=11)
    second = simulate(_parameters(), records, seed=11)
    result = search_training(records, seed=3, count=5)

    assert first == second
    assert result.seed == 3
    assert result.candidates == 5
    assert result.score >= 0.0
    assert result.metrics.count == len(records)
    assert validate(result.parameters, records, seed=4).count == len(records)


def test_invalid_metric_and_candidate_inputs() -> None:
    with pytest.raises(RegimeCalibrationError, match="at least one"):
        size_metrics([])
    with pytest.raises(RegimeCalibrationError, match="count"):
        parameter_candidates(1, count=0)
    with pytest.raises(RegimeCalibrationError, match="seed"):
        parameter_candidates(-1)
    with pytest.raises(RegimeCalibrationError, match="potential_ha"):
        PotentialFire(potential_ha=0.0, active_days=1.0, fwi=20.0, bui=60.0, wind_kmh=5.0)


def test_load_potential_records_from_json(tmp_path: Path) -> None:
    path = tmp_path / "potential.json"
    path.write_text(
        (
            '[{"potential_ha": 1000.0, "active_days": 2.0, '
            '"fwi": 20.0, "bui": 60.0, "wind_kmh": 10.0}]'
        ),
        encoding="utf-8",
    )

    records = load_potential_records(path)

    assert len(records) == 1
    assert records[0].potential_ha == pytest.approx(1_000.0)
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(RegimeCalibrationError, match="JSON list"):
        load_potential_records(bad)


def test_calibration_cli_writes_a_training_result(tmp_path: Path) -> None:
    potential = tmp_path / "potential.json"
    potential.write_text(
        (
            '[{"potential_ha": 1000.0, "active_days": 2.0, '
            '"fwi": 20.0, "bui": 60.0, "wind_kmh": 10.0}]'
        ),
        encoding="utf-8",
    )
    output = tmp_path / "result.json"
    script = Path(__file__).resolve().parents[1] / "scripts" / "fire_regime" / "calibrate.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--potential",
            str(potential),
            "--output",
            str(output),
            "--candidates",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["protocol"] == "P164.8"
    assert payload["candidates"] == 2
    assert payload["training"]["metrics"]["count"] == 1
