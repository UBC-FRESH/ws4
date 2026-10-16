"""Tests for target-weight calibration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner
from ws4.build.compiler import build_canonical_dataset
from ws4.cli import app
from ws4.opt.calibrate import calibrate, pilot_peaks, write_targets
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target, balance_targets, load_targets, objective_terms

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_objective_terms_reports_each_target() -> None:
    """The per-target penalties come back in order."""
    values = pd.DataFrame({"year": [0, 0], "account": ["a", "b"], "value": [5.0, 100.0]})
    targets = [Target("a", 0, minimum=10.0), Target("b", 0, maximum=50.0)]
    assert objective_terms(values, targets) == [5.0, 50.0]


def test_balance_targets_equalises_the_peaks() -> None:
    """Active targets are rescaled to the mean peak."""
    targets = [Target("a", 0, minimum=10.0), Target("b", 0, minimum=1.0)]
    scaled = balance_targets(targets, [100.0, 20.0])  # mean 60, so factors 0.6 and 3.0
    assert scaled[0].min_weight == pytest.approx(0.6)
    assert scaled[1].min_weight == pytest.approx(3.0)
    assert 100.0 * scaled[0].min_weight == pytest.approx(20.0 * scaled[1].min_weight)


def test_balance_targets_scales_both_sides_when_present() -> None:
    """A two-sided target scales both weights; an absent side keeps its weight."""
    two_sided = Target("a", 0, minimum=10.0, maximum=20.0)
    one_sided = Target("b", 0, minimum=1.0)
    scaled = balance_targets([two_sided, one_sided], [30.0, 10.0])  # mean 20, factors 2/3 and 2
    assert scaled[0].min_weight == pytest.approx(2.0 / 3.0)
    assert scaled[0].max_weight == pytest.approx(2.0 / 3.0)
    assert scaled[1].min_weight == pytest.approx(2.0)
    assert scaled[1].max_weight == 1.0


def test_balance_targets_leaves_inactive_targets_alone() -> None:
    """A target that never fired keeps its weights."""
    targets = [Target("a", 0, minimum=10.0), Target("b", 0, maximum=5.0)]
    scaled = balance_targets(targets, [40.0, 0.0])
    assert scaled[0] == targets[0]
    assert scaled[1] == targets[1]


def test_balance_targets_needs_matching_lengths() -> None:
    """A peaks/targets length mismatch is an error."""
    with pytest.raises(ValueError, match="same length"):
        balance_targets([Target("a", 0, minimum=1.0)], [1.0, 2.0])


def test_write_targets_round_trips(tmp_path: Path) -> None:
    """A written targets file loads back to the same targets."""
    targets = [
        Target("a", 0, minimum=1.0, maximum=2.0, min_weight=3.0, period_width=5),
        Target("b", 10, maximum=4.0),
    ]
    path = write_targets(tmp_path / "t.yaml", targets)
    assert load_targets(path) == targets


def _optimizer(tmp_path: Path, targets_path: Path) -> Optimizer:
    """Build a small fixture optimizer with the given targets file."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    return Optimizer.from_dataset(
        dataset, OptimizeConfig(years=2, iterations=20, seed=1, targets_path=str(targets_path))
    )


def test_calibrate_rescales_a_missed_target(tmp_path: Path) -> None:
    """The pilot peaks a missed minimum and the target is rescaled to the mean peak."""
    targets = [Target("feature.Volume", 0, maximum=1.0), Target("product.Volume", 0, minimum=300.0)]
    targets_path = write_targets(tmp_path / "t.yaml", targets)
    optimizer = _optimizer(tmp_path, targets_path)
    peaks = pilot_peaks(optimizer, targets, iterations=20, seed=1, samples=4)
    assert peaks[1] > 0.0  # the minimum is missed at the empty schedule
    scaled = calibrate(optimizer, targets, iterations=20, seed=1, samples=4)
    active = [peak for peak in peaks if peak > 0.0]
    mean_peak = sum(active) / len(active)
    assert scaled[1].min_weight == pytest.approx(targets[1].min_weight * mean_peak / peaks[1])
    assert scaled[1].max_weight == targets[1].max_weight


def test_calibrate_command_writes_a_targets_file(tmp_path: Path) -> None:
    """The calibrate command writes a balanced targets file."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "t.yaml"
    targets.write_text(
        "targets:\n  - account: product.Volume\n    year: 0\n    minimum: 300\n", encoding="utf-8"
    )
    out = tmp_path / "calibrated.yaml"
    result = CliRunner().invoke(
        app,
        [
            "calibrate",
            "--dataset",
            str(dataset),
            "--targets",
            str(targets),
            "--out",
            str(out),
            "--years",
            "2",
            "--iterations",
            "20",
        ],
    )
    assert result.exit_code == 0, result.output
    calibrated = load_targets(out)
    assert len(calibrated) == 1
    assert calibrated[0].account == "product.Volume"
    assert calibrated[0].minimum == 300.0
    assert calibrated[0].min_weight > 0.0
