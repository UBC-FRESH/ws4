"""Tests for sampling a P156 growth field at synthetic tree positions."""

from __future__ import annotations

import math

import pytest
from ws4.fire.growth import GrowthConfig, GrowthResult, SiteGrid, grow_fire
from ws4.scene import (
    IgnitionSamplingError,
    TreeInventory,
    sample_tree_ignition,
    synthetic_tree_inventory,
)


def make_case() -> tuple[TreeInventory, GrowthResult, float]:
    """Build a small tree inventory and a growth field over it."""
    areas = {1: 10.0, 2: 10.0}
    trees = synthetic_tree_inventory(areas, seed=7, trees_per_ha=20.0)
    min_x = min(tree.x for tree in trees.trees) - 30.0
    min_y = min(tree.y for tree in trees.trees) - 30.0
    max_x = max(tree.x for tree in trees.trees) + 30.0
    max_y = max(tree.y for tree in trees.trees) + 30.0
    cell = 5.0
    cols = math.ceil((max_x - min_x) / cell)
    rows = math.ceil((max_y - min_y) / cell)
    grid = SiteGrid(
        fuel_type="C2",
        rows=rows,
        cols=cols,
        cell_size_m=cell,
        ffmc=92.0,
        bui=70.0,
        wind_kmh=20.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
    )
    growth = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((rows // 4, cols // 4),),
            max_time_min=60.0,
            snapshot_interval_min=60.0,
            neighbor_radius=2,
        ),
    )
    return trees, growth, cell


def test_sampling_gives_per_tree_ignition_times() -> None:
    trees, growth, cell = make_case()

    animation = sample_tree_ignition(
        trees,
        growth,
        cell_size_m=cell,
        flame_length_m=10.0,
        smoke_strength=0.6,
        burn_duration=2.0,
    )

    assert len(animation) == len(trees.trees)
    assert list(animation.columns) == [
        "tree_id",
        "fragment_id",
        "ignition_time",
        "burn_duration",
        "flame_intensity",
        "smoke_strength",
        "post_fire_state",
    ]
    burned = animation[animation["post_fire_state"] == "burned"]
    assert not burned.empty
    assert burned["ignition_time"].nunique() > 1
    assert burned["ignition_time"].min() >= 0.0
    assert burned["burn_duration"].eq(2.0).all()
    assert burned["flame_intensity"].between(0.0, 1.0).all()
    assert burned["smoke_strength"].between(0.0, 1.0).all()


def test_sampling_rejects_bad_inputs() -> None:
    trees, growth, cell = make_case()
    with pytest.raises(IgnitionSamplingError, match="TreeInventory"):
        sample_tree_ignition(object(), growth, cell_size_m=cell)  # type: ignore[arg-type]
    with pytest.raises(IgnitionSamplingError, match="GrowthResult"):
        sample_tree_ignition(trees, object(), cell_size_m=cell)  # type: ignore[arg-type]
    with pytest.raises(IgnitionSamplingError, match="cell_size_m"):
        sample_tree_ignition(trees, growth, cell_size_m=0.0)
    with pytest.raises(IgnitionSamplingError, match="burn_duration"):
        sample_tree_ignition(trees, growth, cell_size_m=cell, burn_duration=0.0)
