"""Tests for the P164 multi-fire benchmark script."""

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

module = importlib.import_module("benchmark_multi_fire")


class FakeCase:
    """A minimal case with metrics."""

    def __init__(self, iou: float, sorensen: float) -> None:
        """Build one fake case."""
        self.metrics = PerimeterMetrics(
            area_sim_ha=120.0,
            area_obs_ha=100.0,
            area_bias=0.2,
            perimeter_sim_m=120.0,
            perimeter_obs_m=100.0,
            perimeter_bias=0.2,
            centroid_distance_m=1000.0,
            iou=iou,
            sorensen=sorensen,
            orientation_error_deg=10.0,
        )


def test_main_writes_two_fire_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script writes both cases and the median/worst summary."""
    import ws4.fire.comparison as comparison_module

    def fake_dogrib(fire: object, **kwargs: object) -> FakeCase:
        return FakeCase(0.4, 0.55)

    def fake_observed(fire: object, **kwargs: object) -> FakeCase:
        return FakeCase(0.2, 0.3)

    monkeypatch.setattr(comparison_module, "run_dogrib_case", fake_dogrib)
    monkeypatch.setattr(comparison_module, "run_observed_case", fake_observed)
    output = tmp_path / "multi.csv"
    summary = tmp_path / "multi.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark_multi_fire.py", "--output", str(output), "--summary", str(summary)],
    )

    module.main()

    frame = pd.read_csv(output)
    assert list(frame["case"]) == ["dogrib-2b", "hay-river-full"]
    assert summary.is_file()
