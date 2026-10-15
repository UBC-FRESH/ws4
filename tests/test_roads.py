"""Tests for road network routing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.roads.accounts import RouteCostLedger, RouteModel
from ws4.roads.network import RouteNetwork, load_route_eligibility


def _network() -> RouteNetwork:
    """Build a three-vertex network: block 1 -> vertex 1, destination 'mill' -> vertex 3."""
    segments = pd.DataFrame(
        {
            "from_vertex": [1, 2],
            "to_vertex": [2, 3],
            "length_m": [100.0, 200.0],
            "cost": [10.0, 20.0],
            "build_cost": [5.0, 5.0],
            "maintain_cost": [1.0, 1.0],
        }
    )
    destinations = pd.DataFrame({"dest_id": [10], "vertex_id": [3]})
    linkages = pd.DataFrame({"block_id": [1], "vertex_id": [1]})
    return RouteNetwork.from_tables(segments, destinations, linkages)


def test_route_length_and_cost() -> None:
    """Route length and cost are the shortest path over the segments."""
    network = _network()
    assert network.route_length(1, "10") == 300.0
    assert network.route_cost(1, "10") == 30.0


def test_nearest_destination() -> None:
    """The nearest destination is reported by account name with its route length."""
    assert _network().nearest_destination(1) == ("10", 300.0)


def test_unlinked_block_has_no_route() -> None:
    """A block that is not linked to the network has no route."""
    assert _network().route_length(99, "10") is None


def test_the_legacy_column_names_are_accepted() -> None:
    """The established route-table column names build the same network."""
    segments = pd.DataFrame(
        {
            "SEGMENT": [62, 63],
            "FNODE": [1, 2],
            "TNODE": [2, 3],
            "LENGTH": [100.0, 200.0],
            "HAUL": [10.0, 20.0],
            "BUILD": [1.0, 1.0],
            "MAINTAIN": [0.5, 0.5],
        }
    )
    destinations = pd.DataFrame({"NODE": [3], "ACCOUNT": ["destination.MILL1"]})
    linkages = pd.DataFrame({"BLOCK": [1], "NODE": [1]})
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    route = network.route(1, "destination.MILL1")
    assert route is not None
    assert route.length_m == 300.0
    assert route.haul_cost == 30.0
    assert route.build_cost == 2.0


def test_two_destinations_can_share_a_vertex() -> None:
    """Two destination accounts at the same vertex are both kept, by name."""
    segments = pd.DataFrame(
        {"from_vertex": [1], "to_vertex": [2], "length_m": [100.0], "cost": [10.0]}
    )
    destinations = pd.DataFrame(
        {"NODE": [2, 2], "ACCOUNT": ["destination.MILL1", "destination.MILL3"]}
    )
    linkages = pd.DataFrame({"BLOCK": [1], "NODE": [1]})
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    assert set(network.destination_names()) == {"destination.MILL1", "destination.MILL3"}
    assert network.route_length(1, "destination.MILL3") == 100.0


def test_eligibility_restricts_the_destination() -> None:
    """A product only routes to an eligible destination."""
    segments = pd.DataFrame(
        {
            "from_vertex": [1, 1],
            "to_vertex": [2, 3],
            "length_m": [100.0, 500.0],
            "cost": [10.0, 50.0],
        }
    )
    destinations = pd.DataFrame(
        {"NODE": [2, 3], "ACCOUNT": ["destination.MILL1", "destination.MILL2"]}
    )
    linkages = pd.DataFrame({"block_id": [1], "vertex_id": [1]})
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    # MILL2 is farther, but the product may only go there.
    model = RouteModel(network, eligibility={"product.Decid": ("destination.MILL2",)})
    assert model.assign(1, "product.Decid")[0] == "destination.MILL2"
    # An unlisted product may go to either; the nearest wins.
    assert model.assign(1, "product.Conif")[0] == "destination.MILL1"


def test_load_route_eligibility(tmp_path: Path) -> None:
    """The eligibility table maps a product to its destinations."""
    path = tmp_path / "eligibility.csv"
    path.write_text(
        "product,destination\nproduct.Decid,destination.MILL1\nproduct.Decid,destination.MILL3\n",
        encoding="utf-8",
    )
    assert load_route_eligibility(path) == {
        "product.Decid": ("destination.MILL1", "destination.MILL3")
    }


def test_route_cost_ledger_charges_build_once_and_maintenance_each_year() -> None:
    """Build cost is charged once; maintenance is charged every period used."""
    network = _network()
    ledger = RouteCostLedger(network)
    route = network.route(1, "10")
    assert route is not None
    ledger.record(0, 1, "product.Yield", 10.0, "10", route)
    ledger.record(1, 1, "product.Yield", 10.0, "10", route)
    report = ledger.route_cost_report()
    build = dict(zip(report["period"], report["build_expense"], strict=True))
    maintain = dict(zip(report["period"], report["maintain_expense"], strict=True))
    assert build[0] > 0.0
    assert build[1] == 0.0  # built once
    assert maintain[0] == maintain[1] > 0.0  # maintained each period
