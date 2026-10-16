"""Tests for the annual simulator."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.roads.network import RouteNetwork
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
_RECIPE = _FIXTURE / "recipe.xml"
_FRAGMENTS = _FIXTURE / "fragments.csv"


def _dataset(tmp_path: Path) -> Path:
    """Compile the synthetic fixture."""
    return build_canonical_dataset(_RECIPE, _FRAGMENTS, tmp_path / "compiled")


def _schedule(tmp_path: Path, name: str, rows: list[tuple[int, str, int]]) -> Path:
    """Write a schedule CSV."""
    path = tmp_path / name
    pd.DataFrame(rows, columns=["block_id", "treatment", "period"]).to_csv(path, index=False)
    return path


def _run(dataset: Path, schedule: Path, tmp_path: Path, years: int, tag: str) -> pd.DataFrame:
    """Run the simulator and return the account values."""
    out = tmp_path / tag
    Simulator.from_dataset(dataset).run(schedule, years=years, out_dir=out)
    return pd.read_csv(out / "account_values.csv")


def test_replay_is_deterministic(tmp_path: Path) -> None:
    """Two runs of the same schedule produce identical account values."""
    dataset = _dataset(tmp_path)
    schedule = _schedule(tmp_path, "s.csv", [(1, "CC", 1)])
    first = _run(dataset, schedule, tmp_path, years=3, tag="a")
    second = _run(dataset, schedule, tmp_path, years=3, tag="b")
    pd.testing.assert_frame_equal(first, second)


def test_run_records_the_dataset_reference(tmp_path: Path) -> None:
    """A run directory identifies the dataset that produced it."""
    dataset = _dataset(tmp_path)
    out = tmp_path / "ref"
    Simulator.from_dataset(dataset).run(_schedule(tmp_path, "s.csv", []), years=1, out_dir=out)
    reference = json.loads((out / "dataset.json").read_text(encoding="utf-8"))
    assert reference["schema_version"] == "0.1"
    assert len(reference["manifest_sha256"]) == 64


def test_curve_evaluation_uses_the_precomputed_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Account values gather from the precomputed age table, not per-fragment interpolation."""
    dataset = _dataset(tmp_path)
    simulator = Simulator.from_dataset(dataset)
    calls: list[int] = []
    real_interp = np.interp

    def counting(
        x: np.ndarray, xp: np.ndarray, fp: np.ndarray, *args: float, **kwargs: float
    ) -> np.ndarray:
        calls.append(1)
        return np.asarray(real_interp(x, xp, fp, *args, **kwargs), dtype=float)

    monkeypatch.setattr(np, "interp", counting)
    simulator.account_values(0)
    assert calls == []  # no interpolation at evaluation time
    assert simulator._curve_table.table.shape[0] == simulator.curves["curve_id"].nunique()


def test_a_treatment_records_its_product_yield(tmp_path: Path) -> None:
    """Applying CC to block 1 produces the product at the pre-treatment offset."""
    dataset = _dataset(tmp_path)
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0)])
    out = tmp_path / "prod"
    Simulator.from_dataset(dataset).run(schedule, years=1, out_dir=out)
    products = pd.read_csv(out / "product_values.csv")
    # block 1's fragment is 3.0 ha at offset 40; natural_volume(40) = 120 -> 360.
    assert list(products["account"]) == ["product.Volume"]
    assert products["value"].iloc[0] == 360.0


def test_simulate_reports_the_product_account(tmp_path: Path) -> None:
    """A produced product is an account value in the year it is produced."""
    dataset = _dataset(tmp_path)
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0)])
    values = Simulator.from_dataset(dataset).simulate(pd.read_csv(schedule), years=2)
    produced = values[values["account"] == "product.Volume"].set_index("year")["value"]
    assert produced.loc[0] == pytest.approx(360.0)
    assert 1 not in produced.index  # produced once, in the treatment year


def test_simulate_aggregates_products_per_year_and_account(tmp_path: Path) -> None:
    """Products of a year sum into one account row, matching the per-block trajectories."""
    dataset = _dataset(tmp_path)
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0), (2, "CC", 0)])
    values = Simulator.from_dataset(dataset).simulate(pd.read_csv(schedule), years=1)
    rows = values[values["account"] == "product.Volume"]
    assert not rows[["year", "account"]].duplicated().any()
    expected = sum(
        Simulator.from_dataset(dataset)
        .block_trajectory(block, "CC", 0, 1)
        .get((0, "product.Volume"), 0.0)
        for block in (1, 2)
    )
    assert rows["value"].sum() == pytest.approx(expected)


def test_block_trajectory_includes_the_product_account(tmp_path: Path) -> None:
    """A block's isolated trajectory reports the product its treatment produces."""
    dataset = _dataset(tmp_path)
    trajectory = Simulator.from_dataset(dataset).block_trajectory(1, "CC", 0, 2)
    assert trajectory[(0, "product.Volume")] == pytest.approx(360.0)
    assert (1, "product.Volume") not in trajectory


def test_patch_metrics_are_written(tmp_path: Path) -> None:
    """With a topology, per-year patch metrics are written for the disturbed blocks."""
    dataset = _dataset(tmp_path)
    topology = tmp_path / "topology.csv"
    pd.DataFrame({"src_block": [1], "dst_block": [2], "distance_m": [10.0]}).to_csv(
        topology, index=False
    )
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0)])
    out = tmp_path / "pat"
    Simulator.from_dataset(dataset).run(schedule, years=1, out_dir=out, topology_csv=topology)
    metrics = pd.read_csv(out / "patch_metrics.csv")
    assert metrics["patch_count"].iloc[0] == 1.0  # only block 1 is disturbed


def test_patch_metrics_report_the_largest_opening(tmp_path: Path) -> None:
    """Two adjacent disturbed blocks form one opening whose area is their sum."""
    dataset = _dataset(tmp_path)
    topology = tmp_path / "topology.csv"
    pd.DataFrame({"src_block": [1], "dst_block": [2], "distance_m": [10.0]}).to_csv(
        topology, index=False
    )
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0), (2, "CC", 0)])
    out = tmp_path / "open"
    Simulator.from_dataset(dataset).run(schedule, years=1, out_dir=out, topology_csv=topology)
    metrics = pd.read_csv(out / "patch_metrics.csv")
    assert metrics["patch_count"].iloc[0] == 1.0
    assert metrics["max_patch_area"].iloc[0] == 5.0  # 3.0 ha + 2.0 ha


def test_a_maximum_opening_violation_is_reported(tmp_path: Path) -> None:
    """A 5 ha opening over a 4 ha maximum is reported."""
    dataset = _dataset(tmp_path)
    topology = tmp_path / "topology.csv"
    pd.DataFrame({"src_block": [1], "dst_block": [2], "distance_m": [10.0]}).to_csv(
        topology, index=False
    )
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0), (2, "CC", 0)])
    out = tmp_path / "spatial"
    Simulator.from_dataset(dataset).run(
        schedule, years=1, out_dir=out, topology_csv=topology, max_opening_ha=4.0
    )
    violations = pd.read_csv(out / "spatial_violations.csv")
    assert list(violations["kind"]) == ["opening"]
    assert violations["area_ha"].iloc[0] == 5.0


def test_a_green_up_violation_is_reported(tmp_path: Path) -> None:
    """Two adjacent blocks disturbed one year apart under a 3-year rule are reported."""
    dataset = _dataset(tmp_path)
    topology = tmp_path / "topology.csv"
    pd.DataFrame({"src_block": [1], "dst_block": [2], "distance_m": [10.0]}).to_csv(
        topology, index=False
    )
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0), (2, "CC", 1)])
    out = tmp_path / "greenup"
    Simulator.from_dataset(dataset).run(
        schedule, years=2, out_dir=out, topology_csv=topology, min_green_up_years=3
    )
    violations = pd.read_csv(out / "spatial_violations.csv")
    assert list(violations["kind"]) == ["green_up"]
    assert violations["years"].iloc[0] == 1


def test_products_are_routed_to_the_nearest_mill(tmp_path: Path) -> None:
    """With a road network, a product is routed to the block's nearest destination."""
    dataset = _dataset(tmp_path)
    segments = pd.DataFrame(
        {"from_vertex": [1], "to_vertex": [2], "length_m": [100.0], "cost": [10.0]}
    )
    destinations = pd.DataFrame({"NODE": [2], "ACCOUNT": ["destination.MILL1"]})
    linkages = pd.DataFrame({"block_id": [1, 2], "vertex_id": [1, 2]})
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0)])
    out = tmp_path / "route"
    Simulator.from_dataset(dataset).run(schedule, years=1, out_dir=out, network=network)
    routes = pd.read_csv(out / "route_values.csv")
    assert list(routes["destination"]) == ["destination.MILL1"]
    assert routes["volume"].iloc[0] == 360.0
    assert routes["length_m"].iloc[0] == 100.0
    assert (out / "route_cost_report.csv").is_file()


def test_a_treatment_the_track_does_not_offer_is_skipped(tmp_path: Path) -> None:
    """A scheduled treatment absent from the fragment's track does not apply."""
    dataset = _dataset(tmp_path)
    offered = _run(dataset, _schedule(tmp_path, "cc.csv", [(1, "CC", 0)]), tmp_path, 1, "cc")
    missing = _run(dataset, _schedule(tmp_path, "zz.csv", [(1, "ZZ", 0)]), tmp_path, 1, "zz")
    baseline = _run(dataset, _schedule(tmp_path, "none.csv", []), tmp_path, 1, "none")
    # CC moves block 1's fragment to the managed track, so its value changes.
    assert offered["value"].iloc[0] != baseline["value"].iloc[0]
    # An unoffered treatment leaves the state unchanged.
    pd.testing.assert_frame_equal(missing, baseline)
