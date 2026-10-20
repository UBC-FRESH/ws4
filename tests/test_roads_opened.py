"""Opened-network routing: roads exist from the period they are built.

The reference routes only through roads built on or before the current period and opens the
rest to reach the blocks it selects. These tests pin the mechanism: a planned segment opens
when a block first needs it, an opened road is preferred to a shorter unopened one, the route
cache is invalidated when the network grows, and the build is charged once in the period it
was opened.
"""

from __future__ import annotations

import pandas as pd
from ws4.roads.accounts import RouteCostLedger, RouteModel
from ws4.roads.network import RouteNetwork, existing_segments

_SEGMENTS = pd.DataFrame(
    {
        "from_vertex": [1, 2],
        "to_vertex": [2, 3],
        "length_m": [100.0, 200.0],
        "haul_cost": [1.0, 1.0],
        "build_cost": [0.0, 500.0],
        "maintain_cost": [1.0, 1.0],
    }
)
_DESTINATIONS = pd.DataFrame({"dest_id": ["mill"], "vertex_id": [3]})
_LINKAGES = pd.DataFrame({"block_id": [1, 2], "vertex_id": [1, 1]})


def _network(opened: set[int] | None) -> RouteNetwork:
    """Return the two-segment network with the given initial open set."""
    return RouteNetwork.from_tables(_SEGMENTS, _DESTINATIONS, _LINKAGES, initial_open=opened)


def test_a_block_beyond_the_opened_network_opens_its_path_once() -> None:
    """The access path is opened when the block is first routed, and not again."""
    network = _network(set())
    model = RouteModel(network)
    destination, route = model.assign(1, "product.Volume")
    assert destination == "mill"
    assert route is not None
    assert route.segment_ids == (0, 1)
    assert network.opened == {0, 1}
    # the second block reaches the same opened network without opening anything
    _, second = model.assign(2, "product.Volume")
    assert second is not None
    assert network.opened == {0, 1}


def test_an_opened_road_is_preferred_over_a_shorter_unopened_one() -> None:
    """The route uses the road that exists, even when a planned shortcut is cheaper."""
    segments = pd.DataFrame(
        {
            "from_vertex": [1, 1, 3],
            "to_vertex": [2, 3, 2],
            "length_m": [100.0, 30.0, 30.0],
            "haul_cost": [10.0, 1.0, 1.0],
            "build_cost": [0.0, 100.0, 100.0],
            "maintain_cost": [1.0, 1.0, 1.0],
        }
    )
    destinations = pd.DataFrame({"dest_id": ["mill"], "vertex_id": [2]})
    linkages = pd.DataFrame({"block_id": [1], "vertex_id": [1]})
    network = RouteNetwork.from_tables(segments, destinations, linkages, initial_open={0})
    opened_route = network.route(1, "mill")
    assert opened_route is not None
    assert opened_route.segment_ids == (0,)
    planned_route = network.route(1, "mill", open_only=False)
    assert planned_route is not None
    assert planned_route.segment_ids == (1, 2)

    model = RouteModel(network)
    _, route = model.assign(1, "product.Volume")
    assert route is not None
    assert route.segment_ids == (0,)
    assert network.opened == {0}


def test_opening_a_segment_invalidates_the_cached_route() -> None:
    """A route computed before the network grew is not returned after it does."""
    segments = pd.DataFrame(
        {
            "from_vertex": [1, 1, 3],
            "to_vertex": [2, 3, 2],
            "length_m": [100.0, 30.0, 30.0],
            "haul_cost": [10.0, 1.0, 1.0],
            "build_cost": [0.0, 100.0, 100.0],
            "maintain_cost": [1.0, 1.0, 1.0],
        }
    )
    destinations = pd.DataFrame({"dest_id": ["mill"], "vertex_id": [2]})
    linkages = pd.DataFrame({"block_id": [1], "vertex_id": [1]})
    network = RouteNetwork.from_tables(segments, destinations, linkages, initial_open={0})
    before = network.route(1, "mill")
    assert before is not None
    assert before.length_m == 100.0
    network.open_segments([1, 2])
    after = network.route(1, "mill")
    assert after is not None
    assert after.length_m == 60.0


def test_the_build_is_charged_once_and_existing_road_is_not_built_length() -> None:
    """An existing segment is open but not built; only the planned one is charged, once."""
    network = _network({0})
    model = RouteModel(network)
    ledger = RouteCostLedger(network)
    _, route = model.assign(1, "product.Volume")
    assert route is not None
    assert route.segment_ids == (0, 1)
    ledger.record(0, 1, "product.Volume", 10.0, "mill", route)
    ledger.record(1, 1, "product.Volume", 10.0, "mill", route)
    report = ledger.route_cost_report()
    first = report[report["period"] == 0].iloc[0]
    second = report[report["period"] == 1].iloc[0]
    # only the planned segment (200 m, 500 cost) is built; the existing 100 m is not
    assert float(first["built_length"]) == 200.0
    assert float(first["build_expense"]) == 500.0
    assert float(second["built_length"]) == 0.0
    assert float(second["build_expense"]) == 0.0
    assert float(second["length"]) == 300.0


def test_existing_segments_are_the_zero_build_cost_rows() -> None:
    """The period-1 road set is the zero-build-cost rows, which is how analysts encode existence."""
    assert existing_segments(_SEGMENTS) == {0}
    assert existing_segments(pd.DataFrame({"SEGMENT": [4, 5], "BUILD": [0.0, 7.0]})) == {4}


def test_a_network_with_no_open_set_behaves_as_the_whole_planned_network() -> None:
    """The default keeps the pre-P17 behaviour: every segment is routable."""
    network = _network(None)
    assert network.opened is None
    assert network.route(1, "mill") is not None
    assert network.open_segments([0, 1]) == ()
