"""Tests for the scale benchmark: the synthetic inventory, the memory probe, and the run."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_c5_scenario_needs_a_sample_dir() -> None:
    """The C5 scenario requires the sample directory."""
    with pytest.raises(SystemExit):
        bm.main(["--scenario", "c5"])


def _tiny_sample(root: Path) -> Path:
    """Write a tiny legacy sample (tracks, roads, topology) and return its root."""
    tracks = root / "tracks"
    roads = root / "roads"
    blocks = root / "blocks"
    for directory in (tracks, roads, blocks):
        directory.mkdir(parents=True, exist_ok=True)
    (tracks / "blocks.csv").write_text(
        "BLOCK,TRACK,OFFSET,AREA\n1,1,10,5.0\n2,1,20,5.0\n", encoding="utf-8"
    )
    (tracks / "tracknames.csv").write_text("TRACK,STRATA\n1,status(managed)\n", encoding="utf-8")
    (tracks / "strata.csv").write_text("TRACK,OFFSET,NEXTAGE,CYCLE\n1,0,100,0\n", encoding="utf-8")
    (tracks / "treatments.csv").write_text(
        "TRACK,BEGIN,END,TREATMENT,NEWTRACK,OFFSET,RETAIN\n1,10,100,CC,1,0,0\n", encoding="utf-8"
    )
    (tracks / "curves.csv").write_text("CURVE,X,Y\n1,0,0\n1,100,100\n", encoding="utf-8")
    (tracks / "features.csv").write_text(
        "TRACK,LABEL,CURVE\n1,feature.Seral.young,1\n", encoding="utf-8"
    )
    (tracks / "products.csv").write_text(
        "TRACK,TREATMENT,LABEL,CURVE\n1,CC,product.Yield,1\n", encoding="utf-8"
    )
    (tracks / "accounts.csv").write_text(
        "GROUP,ATTRIBUTE,ACCOUNT,SUM\n_ALL_,feature.Seral.young,feature.Seral.young,1\n",
        encoding="utf-8",
    )
    (tracks / "groups.csv").write_text("BLOCK,GROUP\n1,forest\n", encoding="utf-8")
    (tracks / "messages.csv").write_text("SEVERITY,MESSAGE\ninfo,loaded\n", encoding="utf-8")
    (roads / "segments.csv").write_text(
        "SEGMENT,FNODE,TNODE,LENGTH,HAUL\n1,1,2,100.0,10.0\n", encoding="utf-8"
    )
    (roads / "destinations.csv").write_text("NODE,ACCOUNT\n2,destination.MILL1\n", encoding="utf-8")
    (roads / "linkages.csv").write_text("BLOCK,NODE\n1,1\n2,1\n", encoding="utf-8")
    (blocks / "topology_blocks_200r.csv").write_text(
        "BLOCK1,BLOCK2,DISTANCE,LENGTH\n1,2,0.0,50.0\n", encoding="utf-8"
    )
    return root


def test_run_spatial_benchmark_reports_each_component(tmp_path: Path) -> None:
    """The C5 spatial scenario times each component on a tiny sample."""
    sample = _tiny_sample(tmp_path / "sample")
    result = bm.run_spatial_benchmark(
        sample, tmp_path / "work", years=1, route_blocks=2, spatial_years=1
    )
    for key in (
        "ingest_seconds",
        "simulate_base_seconds",
        "simulate_edge_seconds",
        "simulate_routing_seconds",
        "patch_accounts_seconds",
        "optimizer_eval_seconds",
    ):
        assert result[key] >= 0.0
    assert result["fragments"] == 2.0
