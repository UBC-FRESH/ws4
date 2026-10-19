"""Tests for the time limit: it stops a run, says so, and refuses nonsense.

The cut is asserted structurally rather than by the clock. A budget that cannot be spent in the
limit is given — five million iterations against a one-second bound, where the fixture spends about
a million in seven seconds — so the run *must* be stopped by the clock, and the only timing
assertion is that it finished long before the budget could have been spent.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.solvers import parse_time_limit

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _config(tmp_path: Path, **overrides: object) -> OptimizeConfig:
    """A run with a target, so the search has something to work on."""
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    minimum: 500\n", encoding="utf-8"
    )
    settings: dict[str, object] = {"years": 1, "targets_path": str(targets)}
    settings.update(overrides)
    return OptimizeConfig(**settings)  # type: ignore[arg-type]


def _dataset(tmp_path: Path) -> Path:
    """Compile the synthetic fixture."""
    return build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "c"
    )


def test_a_limit_is_read_off_its_own_text() -> None:
    """Hours, minutes and seconds are read, and nonsense is refused rather than ignored."""
    assert parse_time_limit("") is None
    assert parse_time_limit("00:03:00") == 180.0
    assert parse_time_limit("01:01:01") == 3661.0
    for text in ("three minutes", "1:00", "00:60:00", "00:00:00", "00:00:30:00", "-1:00:00"):
        with pytest.raises(ValueError, match="time limit"):
            parse_time_limit(text)


def test_a_limit_that_cannot_be_reached_stops_the_run_and_says_so(tmp_path: Path) -> None:
    """Five million iterations take about half a minute, so a one-second bound must cut them."""
    dataset = _dataset(tmp_path)
    config = _config(tmp_path, iterations=5_000_000, seed=1, time_limit="00:00:01")
    started = time.monotonic()
    summary = Optimizer.from_dataset(dataset, config).run(tmp_path / "cut")
    elapsed = time.monotonic() - started
    assert summary["time_limit_reached"] is True
    # and it stopped early by a wide margin, not merely eventually
    assert elapsed < 30.0
    # the run is still a run: its outputs are written as usual
    assert (tmp_path / "cut" / "summary.json").is_file()
    assert (tmp_path / "cut" / "report_targets.csv").is_file()


def test_a_generous_limit_leaves_the_run_to_its_budget(tmp_path: Path) -> None:
    """A limit the budget cannot reach is not a limit, and the run says it was not cut."""
    dataset = _dataset(tmp_path)
    config = _config(tmp_path, iterations=30, seed=1, time_limit="01:00:00")
    summary = Optimizer.from_dataset(dataset, config).run(tmp_path / "whole")
    assert summary["time_limit_reached"] is False
    assert json.loads((tmp_path / "whole" / "summary.json").read_text())["status"] == "ok"
