"""Tests for road network routing."""

from __future__ import annotations

import pandas as pd
from ws4.roads.network import RouteNetwork


def _network() -> RouteNetwork:
    """Build a three-vertex network: block 1 -> vertex 1, destination 10 -> vertex 3."""
    segments = pd.DataFrame(
        {
            "from_vertex": [1, 2],
            "to_vertex": [2, 3],
            "length_m": [100.0, 200.0],
            "cost": [10.0, 20.0],
        }
    )
    destinations = pd.DataFrame({"dest_id": [10], "vertex_id": [3]})
    linkages = pd.DataFrame({"block_id": [1], "vertex_id": [1]})
    return RouteNetwork.from_tables(segments, destinations, linkages)


def test_route_length_and_cost() -> None:
    """Route length and cost are the shortest path over the segments."""
    network = _network()
    assert network.route_length(1, 10) == 300.0
    assert network.route_cost(1, 10) == 30.0


def test_nearest_destination() -> None:
    """The nearest destination is reported with its route length."""
    assert _network().nearest_destination(1) == (10, 300.0)


def test_unlinked_block_has_no_route() -> None:
    """A block that is not linked to the network has no route."""
    assert _network().route_length(99, 10) is None
