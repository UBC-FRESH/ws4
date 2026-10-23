"""The sample estate stays usable: it compiles, simulates, routes, and forms openings."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.model.schema import validate_dataset
from ws4.roads.accounts import load_route_config
from ws4.sim.engine import Simulator

ESTATE: Path = Path(__file__).resolve().parents[1] / "examples" / "estate"


def test_the_estate_compiles_and_validates(tmp_path: Path) -> None:
    """The shipped recipe and inventory compile into a dataset that passes validation."""
    dataset = build_canonical_dataset(
        ESTATE / "recipe.xml", ESTATE / "fragments.csv", tmp_path / "compiled"
    )

    assert validate_dataset(dataset) == []
    features = pd.read_parquet(dataset / "features.parquet")
    products = pd.read_parquet(dataset / "products.parquet")
    assert "feature.Seral.regen" in set(features["label"])
    assert "product.Harvested.CC" in set(products["label"])


def test_the_estate_forms_openings_and_routes_to_both_mills(tmp_path: Path) -> None:
    """A small schedule opens patches on the grid, and its volume splits between the two mills."""
    dataset = build_canonical_dataset(
        ESTATE / "recipe.xml", ESTATE / "fragments.csv", tmp_path / "compiled"
    )
    schedule = pd.DataFrame(
        {"block_id": [1, 2, 9, 10, 57, 58, 63, 64], "treatment": ["CC"] * 8, "offset": [0] * 8}
    )
    schedule_csv = tmp_path / "schedule.csv"
    schedule.to_csv(schedule_csv, index=False)

    config = load_route_config(ESTATE / "route.yaml")
    simulator = Simulator.from_dataset(dataset)
    simulator.run(
        schedule_csv,
        10,
        tmp_path / "run",
        topology_csv=ESTATE / "topology.csv",
        network=config.model.network if config.model else None,
        route_model=config.model,
        route_accounts=config.route_accounts,
        duplicate_accounts=config.duplicate_accounts,
    )

    values = pd.read_csv(tmp_path / "run" / "account_values.csv")
    year_zero = dict(
        zip(values[values.offset == 0]["account"], values[values.offset == 0]["value"], strict=True)
    )
    assert year_zero["feature.Seral.regen"] > 0.0, "the cuts should have formed openings"
    assert year_zero["product.Harvested.CC"] > 0.0

    routed = pd.read_csv(tmp_path / "run" / "route_values.csv")
    assert set(routed["destination"]) == {"destination.MILL1", "destination.MILL2"}, (
        "both mills should ship"
    )
    assert year_zero["route.Total.haul"] > 0.0

    metrics = pd.read_csv(tmp_path / "run" / "patch_metrics.csv")
    assert int(metrics.loc[metrics.offset == 0, "patch_count"].iloc[0]) > 0
