"""Tests for the Nemora tree-table to VRI polygon adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.scene import (
    NEMORA_ADAPTER_VERSION,
    NemoraAdapterError,
    load_nemora_scene,
    load_nemora_tree_table,
    load_vri_polygons,
    trees_from_nemora,
)

FIXTURES = Path(__file__).parent / "fixtures" / "scene"


def test_vri_polygons_load_with_ids_areas_and_rings() -> None:
    polygons = load_vri_polygons(FIXTURES / "vri_polygons.geojson")

    assert set(polygons) == {1, 2}
    assert polygons[1].area_ha == 1.0
    assert polygons[1].ring[0] == (0.0, 0.0)
    assert polygons[1].properties["age"] == 60


def test_nemora_table_maps_aliases_and_fuels() -> None:
    frame = load_nemora_tree_table(
        FIXTURES / "nemora_trees.csv",
        nemora_version="0.3.0-test",
    )

    assert len(frame) == 8
    assert {"x", "y", "dbh_cm", "height_m", "crown_fuel_t", "surface_fuel_t_ha"} <= set(
        frame.columns
    )
    assert frame["tree_id"].is_unique
    assert (frame["crown_fuel_t"] > 0.0).all()
    assert frame["provenance"].str.contains("0.3.0-test").all()


def test_nemora_trees_join_to_polygons_and_stay_inside() -> None:
    polygons = load_vri_polygons(FIXTURES / "vri_polygons.geojson")
    frame = load_nemora_tree_table(FIXTURES / "nemora_trees.csv", nemora_version="0.3.0-test")
    inventory = trees_from_nemora(
        frame,
        polygons,
        seed=7,
        source="public-vri-fixture",
        crs="local",
        nemora_version="0.3.0-test",
    )

    assert len(inventory.trees) == 8
    assert set(inventory.fragment_polygons) == {1, 2}
    assert inventory.bounds_violations() == ()
    assert {tree.fragment_id for tree in inventory.trees} == {1, 2}
    assert NEMORA_ADAPTER_VERSION in inventory.source


def test_load_nemora_scene_is_the_public_entry_point() -> None:
    inventory = load_nemora_scene(
        FIXTURES / "nemora_trees.csv",
        FIXTURES / "vri_polygons.geojson",
        seed=11,
        source="public-vri-fixture",
        crs="EPSG:3005",
        nemora_version="0.3.0-test",
    )

    assert inventory.seed == 11
    assert "EPSG:3005" in inventory.source
    assert len(inventory.trees) == 8


def test_tree_outside_every_polygon_fails() -> None:
    polygons = load_vri_polygons(FIXTURES / "vri_polygons.geojson")
    frame = load_nemora_tree_table(FIXTURES / "nemora_trees.csv")
    frame.loc[0, "x"] = 250.0

    with pytest.raises(NemoraAdapterError, match="belongs to 0 VRI polygons"):
        trees_from_nemora(frame, polygons, seed=7, source="fixture")


def test_explicit_fragment_outside_polygon_fails() -> None:
    polygons = load_vri_polygons(FIXTURES / "vri_polygons.geojson")
    frame = load_nemora_tree_table(FIXTURES / "nemora_trees.csv")
    frame["fragment_id"] = 1
    frame.loc[4, "x"] = 150.0

    with pytest.raises(NemoraAdapterError, match="lies outside VRI fragment 1"):
        trees_from_nemora(frame, polygons, seed=7, source="fixture")


def test_missing_required_column_fails(tmp_path: Path) -> None:
    frame = pd.read_csv(FIXTURES / "nemora_trees.csv").drop(columns=["dbh"])
    path = tmp_path / "missing.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(NemoraAdapterError, match="dbh_cm"):
        load_nemora_tree_table(path)


def test_duplicate_vri_id_fails(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "vri_polygons.geojson").read_text(encoding="utf-8"))
    payload["features"][1]["properties"]["fragment_id"] = 1
    path = tmp_path / "duplicate.geojson"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(NemoraAdapterError, match="duplicate"):
        load_vri_polygons(path)
