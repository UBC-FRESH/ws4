"""Tests for the scale benchmark: the synthetic inventory, the memory probe, and the run."""

from __future__ import annotations

from pathlib import Path

import benchmark as bm


def test_synthetic_fragments_has_the_expected_shape() -> None:
    """The inventory has one row per fragment and the fixture's columns."""
    frame = bm.synthetic_fragments(50, 10, seed=1)
    assert len(frame) == 50
    assert list(frame.columns) == ["BLOCK", "AREA_HA", "F_AGE", "AU", "IFM", "RETENTION"]
    assert frame["BLOCK"].max() <= 10


def test_peak_memory_is_positive() -> None:
    """The process reports a positive peak memory."""
    assert bm.peak_memory_mb() > 0.0


def test_run_benchmark_reports_the_timings(tmp_path: Path) -> None:
    """A small benchmark returns the fragment count and non-negative timings."""
    result = bm.run_benchmark(200, 100, years=2, seed=1, workdir=tmp_path)
    assert result["fragments"] > 0
    assert result["build_seconds"] >= 0.0
    assert result["simulate_seconds"] >= 0.0


def test_main_runs(tmp_path: Path) -> None:
    """The command returns 0."""
    assert bm.main(["--fragments", "100", "--years", "2", "--workdir", str(tmp_path)]) == 0
