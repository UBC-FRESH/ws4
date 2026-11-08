"""Tests for the synthetic individual-tree inventory."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from ws4.scene.trees import (
    TREE_COLUMNS,
    Tree,
    TreeError,
    TreeInventory,
    synthetic_tree_inventory,
)


def make_tree(tree_id: str = "t1", *, fragment: int = 1, x: float = 1.0, y: float = 1.0) -> Tree:
    """Build one valid tree."""
    return Tree(
        tree_id=tree_id,
        fragment_id=fragment,
        x=x,
        y=y,
        z=0.0,
        species="PL",
        dbh_cm=30.0,
        height_m=20.0,
        crown_ratio=0.45,
        crown_radius_m=2.4,
        live=True,
        decay_class=0,
        crown_fuel_t=0.05,
        surface_fuel_t_ha=10.0,
        snag_t=0.0,
        provenance="test",
    )


def test_tree_round_trips_and_computes_basal_area() -> None:
    tree = make_tree()

    assert Tree.from_dict(tree.to_dict()) == tree
    assert tree.basal_area_m2 == pytest.approx(math.pi * (0.15**2))
    assert tree.to_dict()["tree_id"] == "t1"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"dbh_cm": 0.0}, "dbh_cm must be positive"),
        ({"height_m": -1.0}, "height_m must be positive"),
        ({"crown_ratio": 1.5}, "crown_ratio must be between"),
        ({"crown_fuel_t": -1.0}, "fuel values must be non-negative"),
        ({"fragment_id": 0}, "fragment_id must be positive"),
        ({"live": "yes"}, "live must be a boolean"),
    ],
)
def test_invalid_tree_values_are_rejected(overrides: dict[str, object], message: str) -> None:
    payload = make_tree().to_dict()
    payload.update(overrides)

    with pytest.raises(TreeError, match=message):
        Tree.from_dict(payload)


def test_inventory_is_deterministic() -> None:
    first = synthetic_tree_inventory({1: 10.0, 2: 10.0}, seed=7, trees_per_ha=50.0)
    second = synthetic_tree_inventory({1: 10.0, 2: 10.0}, seed=7, trees_per_ha=50.0)
    different = synthetic_tree_inventory({1: 10.0, 2: 10.0}, seed=8, trees_per_ha=50.0)

    assert first.to_frame().equals(second.to_frame())
    assert not first.to_frame().equals(different.to_frame())
    assert first.bounds_violations() == ()


def test_inventory_summary_and_fragment_summary() -> None:
    inventory = synthetic_tree_inventory({1: 10.0, 2: 10.0}, seed=7, trees_per_ha=50.0)
    summary = inventory.summary()
    fragments = inventory.fragment_summary().set_index("fragment_id")

    assert summary["tree_count"] == 1000
    assert summary["area_ha"] == pytest.approx(20.0)
    assert summary["stems_per_ha"] == pytest.approx(50.0)
    assert float(str(summary["basal_area_m2_per_ha"])) > 0.0
    assert summary["species"] == ["PL"]
    assert fragments.loc[1, "tree_count"] == 500
    assert fragments.loc[1, "stems_per_ha"] == pytest.approx(50.0)


def test_inventory_frame_round_trip() -> None:
    inventory = synthetic_tree_inventory({1: 10.0}, seed=3, trees_per_ha=20.0)

    again = TreeInventory.from_frame(
        inventory.to_frame(),
        fragment_areas=inventory.fragment_areas,
        fragment_origins=inventory.fragment_origins,
        seed=inventory.seed,
        source=inventory.source,
    )

    assert again == inventory


def test_bounds_violations_detect_a_tree_outside_its_fragment() -> None:
    inventory = synthetic_tree_inventory(
        {1: 10.0},
        seed=3,
        trees_per_ha=20.0,
        fragment_origins={1: (0.0, 0.0)},
    )
    trees = list(inventory.trees)
    trees[0] = make_tree(trees[0].tree_id, fragment=1, x=-10.0, y=5.0)
    broken = TreeInventory(
        trees=tuple(trees),
        fragment_areas=inventory.fragment_areas,
        fragment_origins=inventory.fragment_origins,
        seed=inventory.seed,
        source=inventory.source,
    )

    assert broken.bounds_violations() == (trees[0].tree_id,)


def test_inventory_rejects_duplicate_ids_and_unknown_fragments() -> None:
    tree = make_tree()
    with pytest.raises(TreeError, match="duplicate tree id"):
        TreeInventory((tree, tree), {1: 10.0}, {1: (0.0, 0.0)}, 1, "test")
    with pytest.raises(TreeError, match="unknown fragment"):
        TreeInventory((tree,), {2: 10.0}, {2: (0.0, 0.0)}, 1, "test")


def test_synthetic_inventory_requires_origins_for_every_fragment() -> None:
    with pytest.raises(TreeError, match="missing fragment origins"):
        synthetic_tree_inventory({1: 10.0, 2: 10.0}, seed=1, fragment_origins={1: (0.0, 0.0)})


def test_empty_fragment_map_is_rejected() -> None:
    with pytest.raises(TreeError, match="at least one fragment"):
        synthetic_tree_inventory({}, seed=1)


@settings(max_examples=20, deadline=None)
@given(
    areas=st.dictionaries(
        keys=st.integers(min_value=1, max_value=20),
        values=st.floats(min_value=0.5, max_value=50.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=6,
    ),
    seed=st.integers(min_value=0, max_value=1000),
)
def test_generated_inventory_is_inside_its_fragments(areas: dict[int, float], seed: int) -> None:
    inventory = synthetic_tree_inventory(areas, seed=seed, trees_per_ha=20.0)

    assert inventory.bounds_violations() == ()
    assert len(inventory.trees) == sum(max(1, round(20.0 * area)) for area in areas.values())
    assert set(TREE_COLUMNS) == set(inventory.to_frame().columns)
