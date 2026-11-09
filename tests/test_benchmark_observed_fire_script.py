"""Tests for the observed-fire benchmark script's scenarios and output path."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module = importlib.import_module("benchmark_observed_fire")


class FakeMetrics:
    """A minimal metrics stand-in."""

    def to_dict(self) -> dict[str, float]:
        """Return a fixed metric mapping."""
        return {
            "area_sim_ha": 6.0,
            "area_obs_ha": 10.0,
            "area_bias": -0.4,
            "perimeter_sim_m": 140.0,
            "perimeter_obs_m": 160.0,
            "perimeter_bias": -0.125,
            "centroid_distance_m": 14.0,
            "iou": 0.07,
            "sorensen": 0.13,
            "orientation_error_deg": 3.0,
        }


class FakeGrowth:
    """A minimal growth stand-in."""

    head_ros_m_min = 40.0
    length_to_breadth = 3.2
    burned_area_ha = 6.0


class FakeCase:
    """A minimal Dogrib case stand-in."""

    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.duration_min = 402.0
        self.fuel_type = "C2"
        self.ffmc = 92.7
        self.bui = 105.0
        self.wind_kmh = 21.0
        self.wind_direction_deg = 267.6
        self.slope_percent = 32.0
        self.aspect_deg = 180.0
        self.start_cells = 759
        self.growth = FakeGrowth()
        self.metrics = FakeMetrics()


class FakeFire:
    """A minimal observed-fire stand-in."""

    def to_dict(self) -> dict[str, object]:
        """Return a fixed fire summary."""
        return {"fire_id": "RWF085"}


def test_scenario_overrides_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(fire: object, **kwargs: object) -> FakeCase:
        calls.append(kwargs)
        return FakeCase(str(kwargs["scenario"]))

    monkeypatch.setattr(module, "run_dogrib_case", fake_run)
    fire = FakeFire()
    for name in module.SCENARIOS:
        case = module.run_scenario(fire, name)
        assert case.scenario == name

    assert calls[0] == {"scenario": "base"}
    assert calls[1] == {"scenario": "wind-27", "wind_kmh": 27.0}
    assert calls[2] == {"scenario": "wind-43", "wind_kmh": 43.0}
    assert calls[3] == {"scenario": "flat", "slope_percent": 0.0}
    assert calls[4] == {"scenario": "no-wind", "wind_kmh": 0.0}
    assert calls[5] == {"scenario": "long-800", "duration_min": 800.0}


def test_main_writes_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "results.csv"
    summary = tmp_path / "summary.json"
    monkeypatch.setattr(module, "load_dogrib", lambda path: FakeFire())
    monkeypatch.setattr(module, "run_scenario", lambda fire, name: FakeCase(name))
    monkeypatch.setattr(module, "write_comparison_svg", lambda fire, case, path: Path(path))
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark_observed_fire.py", "--output", str(output), "--summary", str(summary)],
    )

    module.main()

    assert output.is_file()
    assert summary.is_file()
    frame = pd.read_csv(output)
    assert list(frame["scenario"]) == list(module.SCENARIOS)
    assert "base" in capsys.readouterr().out
    assert "RWF085" in summary.read_text(encoding="utf-8")
