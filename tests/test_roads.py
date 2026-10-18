"""Tests for road network routing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.roads.accounts import RouteCostLedger, RouteModel, load_route_config
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
    """A product only routes to an eligible destination, and a map says what is delivered."""
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
    # A product the map does not name is not delivered at all, rather than sent anywhere: a
    # configuration that says where wood goes is saying what the wood is.
    assert model.eligible("product.Conif") == ()
    assert not model.delivers("product.Conif")
    # With no map at all, every product may go to either destination and the nearest wins.
    open_model = RouteModel(network)
    assert open_model.assign(1, "product.Conif")[0] == "destination.MILL1"


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


def test_route_accounts_sum_costs_and_volume() -> None:
    """Route accounts sum the haul cost and volume per destination."""
    from ws4.roads.accounts import RouteAccount

    network = _network()
    ledger = RouteCostLedger(network)
    route = network.route(1, "10")
    assert route is not None
    ledger.record(0, 1, "product.Yield", 10.0, "10", route)
    accounts = ledger.account_values(
        [
            RouteAccount("10", "haul", "route.mill.haul"),
            RouteAccount("10", "volume", "product.mill.Yield"),
        ]
    )
    values = dict(zip(accounts["account"], accounts["value"], strict=True))
    assert values["route.mill.haul"] == 300.0  # 10 volume * (10 + 20) haul rate
    assert values["product.mill.Yield"] == 10.0


def test_duplicate_accounts_copy_and_scale() -> None:
    """A duplicate account copies its master into a target, scaled."""
    from ws4.roads.accounts import DuplicateAccount, resolve_account_values

    values = pd.DataFrame({"year": [0], "account": ["a"], "value": [5.0]})
    extra = pd.DataFrame({"year": [0], "account": ["route.haul"], "value": [100.0]})
    resolved = resolve_account_values(
        values, extra, [DuplicateAccount("route.haul", "route.total", 0.5)]
    )
    lookup = dict(zip(resolved["account"], resolved["value"], strict=True))
    assert lookup["a"] == 5.0
    assert lookup["route.total"] == 50.0


def test_load_route_config(tmp_path: Path) -> None:
    """A route config loads the network, eligibility, and accounts."""
    from ws4.roads.accounts import load_route_config

    (tmp_path / "segments.csv").write_text(
        "SEGMENT,FNODE,TNODE,LENGTH,HAUL\n1,1,2,100.0,10.0\n", encoding="utf-8"
    )
    (tmp_path / "destinations.csv").write_text(
        "NODE,ACCOUNT\n2,destination.MILL1\n", encoding="utf-8"
    )
    (tmp_path / "linkages.csv").write_text("BLOCK,NODE\n1,1\n", encoding="utf-8")
    (tmp_path / "eligibility.csv").write_text(
        "product,destination\nproduct.Decid,destination.MILL1\n", encoding="utf-8"
    )
    config_path = tmp_path / "route.yaml"
    config_path.write_text(
        "route:\n"
        "  segments: segments.csv\n"
        "  destinations: destinations.csv\n"
        "  linkages: linkages.csv\n"
        "  eligibility: eligibility.csv\n"
        "route_accounts:\n"
        "  - {destination: destination.MILL1, kind: haul, account: route.Mill1.haul}\n"
        "duplicate_accounts:\n"
        "  - {master: route.Mill1.haul, target: route.Total.haul}\n",
        encoding="utf-8",
    )
    config = load_route_config(config_path)
    assert config.model.network.destination_names() == ("destination.MILL1",)
    assert config.model.eligible("product.Decid") == ("destination.MILL1",)
    assert config.route_accounts[0].account == "route.Mill1.haul"
    assert config.duplicate_accounts[0].target == "route.Total.haul"


def test_load_route_config_requires_the_tables(tmp_path: Path) -> None:
    """A route config without the route tables is rejected."""
    from ws4.roads.accounts import load_route_config

    path = tmp_path / "route.yaml"
    path.write_text("route:\n  segments: s.csv\n", encoding="utf-8")
    with pytest.raises(ValueError, match="destinations, linkages"):
        load_route_config(path)


def test_maintenance_is_charged_once_however_much_traffic_the_road_carries() -> None:
    """A road is maintained once in a period, not once per tonne that passes over it."""
    network = _network()
    route = network.route(1, "10")
    assert route is not None
    one = RouteCostLedger(network)
    one.record(0, 1, "product.Yield", 10.0, "10", route)
    ten = RouteCostLedger(network)
    ten.record(0, 1, "product.Yield", 10.0, "10", route)
    ten.record(0, 2, "product.Yield", 90.0, "10", route)
    single = one.route_cost_report()["maintain_expense"].iloc[0]
    heavier = ten.route_cost_report()["maintain_expense"].iloc[0]
    assert single > 0.0
    # nine times the volume over the same segments: the maintenance is the same, and the haul is not
    assert heavier == single
    assert (
        ten.route_cost_report()["haul_expense"].iloc[0]
        > one.route_cost_report()["haul_expense"].iloc[0]
    )


def test_a_volume_account_can_name_the_product_it_tracks() -> None:
    """A volume account with a product sums only that product's volume to that destination."""
    from ws4.roads.accounts import RouteAccount

    network = _network()
    ledger = RouteCostLedger(network)
    route = network.route(1, "10")
    assert route is not None
    ledger.record(0, 1, "product.Conif", 10.0, "10", route)
    ledger.record(0, 1, "product.Decid", 4.0, "10", route)
    accounts = ledger.account_values(
        [
            RouteAccount("10", "volume", "product.mill.Conif", product="product.Conif"),
            RouteAccount("10", "volume", "product.mill.everything"),
        ]
    )
    values = dict(zip(accounts["account"], accounts["value"], strict=True))
    assert values["product.mill.Conif"] == 10.0
    assert values["product.mill.everything"] == 14.0


def test_a_cost_account_cannot_name_a_product() -> None:
    """A product on a cost account is refused rather than ignored."""
    from ws4.roads.accounts import RouteAccount

    with pytest.raises(ValueError, match="only be named on a volume account"):
        RouteAccount("10", "haul", "route.mill.haul", product="product.Conif")


def test_a_product_allocation_partitions_a_master_across_destinations() -> None:
    """The shares come from the routed volumes and the rest is the unallocated account."""
    from ws4.roads.accounts import ProductAllocation, resolve_allocation_values

    values = pd.DataFrame(
        {"year": [0, 0], "account": ["product.yield", "other"], "value": [100.0, 5.0]}
    )
    volumes = pd.DataFrame(
        {
            "year": [0, 0],
            "destination": ["mill1", "mill2"],
            "product": ["product.yield"] * 2,
            "volume": [30.0, 45.0],
        }
    )
    shares = resolve_allocation_values(
        values,
        volumes,
        [
            ProductAllocation(
                master="product.yield",
                allocations=(("mill1", "product.mill1"), ("mill2", "product.mill2")),
                unallocated="product.unallocated",
            )
        ],
    )
    got = {
        (account, year): value
        for account, year, value in zip(
            shares["account"], shares["year"], shares["value"], strict=True
        )
    }
    assert got[("product.mill1", 0)] == 30.0
    assert got[("product.mill2", 0)] == 45.0
    assert got[("product.unallocated", 0)] == 25.0  # 100 - 30 - 45


def test_an_allocation_that_exceeds_its_master_is_refused() -> None:
    """Shares larger than the master would mean the configuration and routing disagree."""
    from ws4.roads.accounts import ProductAllocation, resolve_allocation_values

    values = pd.DataFrame({"year": [0], "account": ["product.yield"], "value": [10.0]})
    volumes = pd.DataFrame(
        {"year": [0], "destination": ["mill1"], "product": ["product.yield"], "volume": [99.0]}
    )
    with pytest.raises(ValueError, match="exceed its own value"):
        resolve_allocation_values(
            values,
            volumes,
            [
                ProductAllocation(
                    master="product.yield",
                    allocations=(("mill1", "product.mill1"),),
                    unallocated="product.unallocated",
                )
            ],
        )


def test_a_product_that_cannot_reach_a_destination_goes_to_its_own_surplus() -> None:
    """The surplus account can be named per product, as the reference declares it."""
    segments = pd.DataFrame(
        {"from_vertex": [1], "to_vertex": [2], "length_m": [100.0], "cost": [10.0]}
    )
    destinations = pd.DataFrame({"NODE": [2], "ACCOUNT": ["destination.MILL1"]})
    linkages = pd.DataFrame({"block_id": [1], "vertex_id": [9]})
    network = RouteNetwork.from_tables(segments, destinations, linkages)
    model = RouteModel(
        network,
        eligibility={"product.Decid": ("destination.MILL2",)},
        unutilized={"product.Decid": "product.unutilized.Decid"},
    )
    # deciduous may only go to MILL2, which this block cannot reach, so it is its own surplus
    assert model.assign(1, "product.Decid") == ("product.unutilized.Decid", None)
    assert model.surplus_account("product.Decid") == "product.unutilized.Decid"
    # a product with no entry has no surplus account in a mapping, so nothing is filed wrongly
    assert model.surplus_account("product.Conif") == ""


def test_a_route_config_states_a_surplus_per_product(tmp_path: Path) -> None:
    """The configuration accepts one account or a mapping, and keeps both."""
    for name, frame in (
        ("segments.csv", {"from_vertex": [1], "to_vertex": [2], "length_m": [10.0], "cost": [1.0]}),
        ("destinations.csv", {"name": ["destination.MILL1"], "vertex_id": [2]}),
        ("linkages.csv", {"block_id": [1], "vertex_id": [1]}),
    ):
        pd.DataFrame(frame).to_csv(tmp_path / name, index=False)
    shared = (
        "route:\n  segments: segments.csv\n  destinations: destinations.csv\n"
        "  linkages: linkages.csv\n  unutilized: {surplus}\n"
    )
    one = tmp_path / "one.yaml"
    one.write_text(shared.format(surplus="product.Unutilized"), encoding="utf-8")
    assert load_route_config(one).model.unutilized == "product.Unutilized"
    many = tmp_path / "many.yaml"
    many.write_text(
        "route:\n  segments: segments.csv\n  destinations: destinations.csv\n"
        "  linkages: linkages.csv\n  unutilized:\n"
        "    product.Decid: product.unutilized.Decid\n",
        encoding="utf-8",
    )
    model = load_route_config(many).model
    assert model.surplus_account("product.Decid") == "product.unutilized.Decid"


def test_the_route_report_is_folded_into_the_models_periods() -> None:
    """A period width folds the years into the report's rows, the way the reference labels them."""
    network = _network()
    ledger = RouteCostLedger(network, period_width=10)
    route = network.route(1, "10")
    assert route is not None
    for year in range(1, 21):
        ledger.record(year, 1, "product.Yield", 10.0, "10", route)
    report = ledger.route_cost_report()
    assert list(report["period"]) == [1, 2]
    assert list(report["year"]) == [10, 20]
    assert set(report["period_width"]) == {10}
    # the extensive columns are summed over the ten years, the averages are recomputed from them
    assert report["volume"].sum() == 200.0
    assert report["length"].sum() == 2 * 10 * 300.0
    first = report.iloc[0]
    assert first["volume"] == 100.0
    assert abs(first["average_haul_cost"] - first["haul_expense"] / 100.0) < 1e-9
    # the per-year report of a one-year model is unchanged by the folding
    yearly = RouteCostLedger(network, period_width=1)
    for year in range(1, 4):
        yearly.record(year, 1, "product.Yield", 10.0, "10", route)
    plain = yearly.route_cost_report()
    assert list(plain["period"]) == [1, 2, 3]
    assert list(plain["year"]) == [1, 2, 3]


def test_a_run_that_stops_inside_a_period_covers_only_the_years_it_simulated() -> None:
    """The period keeps the reference's label; what it holds is what the run actually simulated."""
    network = _network()
    ledger = RouteCostLedger(network, period_width=10)
    route = network.route(1, "10")
    assert route is not None
    for year in range(1, 15):
        ledger.record(year, 1, "product.Yield", 10.0, "10", route)
    report = ledger.route_cost_report()
    assert list(report["period"]) == [1, 2]
    assert list(report["year"]) == [10, 20]
    assert report["volume"].iloc[1] == 40.0  # four years of the second period


def test_a_destination_can_be_reported_on_alone() -> None:
    """The report is per destination when one is named, which is how the reference ships it."""
    network = _network()
    ledger = RouteCostLedger(network, period_width=10)
    route = network.route(1, "10")
    assert route is not None
    ledger.record(1, 1, "product.Yield", 10.0, "10", route)
    mine = ledger.route_cost_report("10")
    assert list(mine["period"]) == [1]
    assert mine["volume"].iloc[0] == 10.0
    # a destination nothing was routed to has no periods at all, rather than zero rows
    assert ledger.route_cost_report("11").empty


def test_a_per_destination_report_measures_the_length_it_built() -> None:
    """The per-destination state records the built length, as the network-wide state does."""
    network = _network()
    ledger = RouteCostLedger(network)
    route = network.route(1, "10")
    assert route is not None
    ledger.record(1, 1, "product.Yield", 10.0, "10", route)
    report = ledger.route_cost_report("10")
    assert report["built_length"].iloc[0] == report["length"].iloc[0] > 0.0
    assert report["build_expense"].iloc[0] > 0.0
