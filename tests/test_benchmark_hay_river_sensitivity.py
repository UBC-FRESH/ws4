"""Tests for the P162 calibration-sensitivity script wiring."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest
from ws4.fire.comparison import PerimeterMetrics

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module = importlib.import_module("benchmark_hay_river_sensitivity")


class FakeCase:
    """A minimal case for the sensitivity script."""

    def __init__(self, scenario: str, area: float) -> None:
        """Build one fake case."""
        self.scenario = scenario
        self.metrics = PerimeterMetrics(
            area_sim_ha=area,
            area_obs_ha=100.0,
            area_bias=(area - 100.0) / 100.0,
            perimeter_sim_m=120.0,
            perimeter_obs_m=100.0,
            perimeter_bias=0.2,
            centroid_distance_m=1000.0,
            iou=0.5,
            sorensen=0.6,
            orientation_error_deg=10.0,
        )


def test_main_writes_fixed_sensitivity_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script writes nine rows and the sensitivity summary."""
    import ws4.fire.comparison as comparison_module

    def fake_run(fire: object, **kwargs: object) -> FakeCase:
        wind = kwargs["wind_multiplier"]
        assert isinstance(wind, (int, float))
        assert not isinstance(wind, bool)
        return FakeCase(str(kwargs["scenario"]), 100.0 + float(wind))

    monkeypatch.setattr(comparison_module, "run_observed_case", fake_run)
    output = tmp_path / "sensitivity.csv"
    summary = tmp_path / "sensitivity.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark_hay_river_sensitivity.py", "--output", str(output), "--summary", str(summary)],
    )

    module.main()

    frame = pd.read_csv(output)
    assert len(frame) == 9
    assert set(frame["window"]) == {"day-1", "day-3", "full"}
    assert summary.is_file()
