"""Tests for the annual simulator."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
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


def test_products_are_routed_to_the_nearest_mill(tmp_path: Path) -> None:
    """With a road network, a product is routed to the block's nearest destination."""
    dataset = _dataset(tmp_path)
    segments = pd.DataFrame(
        {"from_vertex": [1], "to_vertex": [2], "length_m": [100.0], "cost": [10.0]}
    )
    destinations = pd.DataFrame({"dest_id": [10], "vertex_id": [2]})
    linkages = pd.DataFrame({"block_id": [1, 2], "vertex_id": [1, 2]})
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    schedule = _schedule(tmp_path, "cc.csv", [(1, "CC", 0)])
    out = tmp_path / "route"
    Simulator.from_dataset(dataset).run(schedule, years=1, out_dir=out, network=network)
    routes = pd.read_csv(out / "route_values.csv")
    assert list(routes["dest_id"]) == [10]
    assert routes["volume"].iloc[0] == 360.0
    assert routes["length_m"].iloc[0] == 100.0


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
