"""Tests for the fire-scene package and its embedded viewer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.ecosystem.fire import FireConfig, FireRun, synthetic_grid
from ws4.ecosystem.log import EventLog
from ws4.scene import (
    FireScene,
    SceneError,
    SceneManifest,
    TreeInventory,
    compile_fire_scene,
    synthetic_tree_inventory,
)


def make_fire(seed: int = 1, years: int = 5) -> tuple[FireRun, TreeInventory]:
    """Run a small deterministic fire and return the run and its tree inventory."""
    _, state, edges = synthetic_grid(3, 3)
    run = FireRun(
        state,
        edges,
        FireConfig(ignition_rate_per_fragment_year=0.2, base_spread_probability=0.6),
        scenario_id="scene",
        seed=seed,
    )
    trees = synthetic_tree_inventory(run.state.fragment_areas, seed=11, trees_per_ha=20.0)
    return run, trees


def compile_scene(seed: int = 1) -> FireScene:
    """Compile a deterministic test scene."""
    run, trees = make_fire(seed)
    return compile_fire_scene(
        run.run(5),
        trees,
        scene_id="test",
        particle_budget=500,
        created_utc="2026-11-08T00:00:00+00:00",
    )


def test_scene_manifest_round_trip() -> None:
    scene = compile_scene()
    manifest = scene.manifest

    assert SceneManifest.from_dict(manifest.to_dict()) == manifest
    assert manifest.schema_version == "ws4.fire.scene.v1"
    assert manifest.synthetic_trees is True
    assert manifest.tree_count == 1800
    assert manifest.fragment_count == 9


def test_scene_maps_every_burned_fragment_to_trees() -> None:
    scene = compile_scene()
    burned = {
        int(event.fragment_ids[0]) for event in scene.event_log.events if event.event_type == "fire"
    }
    mapped = {
        int(value)
        for value in scene.animation.loc[scene.animation["ignition_time"].notna(), "fragment_id"]
    }

    assert burned == mapped
    assert {int(value) for value in scene.fires["fragment_id"]} == burned
    assert scene.manifest.run_replay_token == scene.event_log.replay_token


def test_scene_payload_has_bounds_timeline_and_counts() -> None:
    scene = compile_scene()
    payload = scene.viewer_payload()
    counts = payload["counts"]
    timeline = payload["timeline"]
    bounds = payload["bounds"]
    stands = payload["stands"]
    trees = payload["trees"]
    assert isinstance(counts, dict)
    assert isinstance(timeline, dict)
    assert isinstance(bounds, dict)
    assert isinstance(stands, list)
    assert isinstance(trees, list)

    assert counts["fragments"] == 9
    assert counts["trees"] == 1800
    assert float(timeline["end"]) > 0.0
    assert float(bounds["max_x"]) > float(bounds["min_x"])
    assert len(stands) == 9
    assert len(trees) == 1800
    states = {str(tree["post_fire_state"]) for tree in trees}
    assert states <= {"unburned", "scorched", "torched", "consumed"}


def test_scene_is_deterministic() -> None:
    first = compile_scene()
    second = compile_scene()

    assert first.animation.equals(second.animation)
    assert first.stands.equals(second.stands)
    assert first.fires.equals(second.fires)
    assert first.manifest.to_dict() == second.manifest.to_dict()


def test_scene_write_produces_every_artifact(tmp_path: Path) -> None:
    scene = compile_scene()

    paths = scene.write(tmp_path)

    for path in (
        paths.manifest,
        paths.viewer,
        paths.trees,
        paths.stands,
        paths.fires,
        paths.animation,
        paths.event_log,
        paths.summary,
        paths.payload,
    ):
        assert path.is_file()
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    assert manifest["scene_id"] == "test"
    assert manifest["synthetic_trees"] is True
    assert EventLog.read(paths.event_log) == scene.event_log
    html = paths.viewer.read_text(encoding="utf-8")
    assert "WS4 fire scene" in html
    assert "__SCENE_DATA__" not in html
    assert '"trees"' in html
    assert pd.read_parquet(paths.trees).shape[0] == 1800


def test_scene_rejects_trees_outside_the_fire_state() -> None:
    run, trees = make_fire()
    extra = dict(trees.fragment_areas)
    extra[99] = 1.0
    broken = synthetic_tree_inventory(extra, seed=11, trees_per_ha=1.0)

    with pytest.raises(SceneError, match="outside the fire state"):
        compile_fire_scene(run.run(1), broken)


def test_scene_manifest_rejects_bad_counts() -> None:
    with pytest.raises(SceneError, match="fragment_count"):
        SceneManifest(
            scene_id="bad",
            seed=1,
            run_replay_token="token",
            scenario_id="s",
            fragment_count=0,
            tree_count=1,
            synthetic_trees=True,
            source="test",
            particle_budget=10,
            burn_duration_years=0.1,
        )


def test_viewer_template_contains_the_expected_hooks() -> None:
    template = Path(__file__).resolve().parents[1] / "ws4" / "scene" / "viewer.html"
    text = template.read_text(encoding="utf-8")

    assert "__SCENE_DATA__" in text
    assert "OrbitControls" in text
    assert "timeline" in text
    assert "Play" in text
    assert "three" in text
    assert "UnrealBloomPass" in text
    assert "spawnEmber" in text
    assert "scorchedCrown" in text
    assert "heatHaze" in text
    assert "__ws4FireStats" in text
    assert "ShapeGeometry" in text
    assert "particle_budget" in text


def test_scene_time_unit_round_trips_and_reaches_the_viewer() -> None:
    """The scene clock can be minutes and the viewer payload carries the unit."""
    run, trees = make_fire()
    scene = compile_fire_scene(
        run.run(5),
        trees,
        scene_id="minutes",
        particle_budget=500,
        burn_duration_years=2.0,
        time_unit="minutes",
    )

    assert scene.manifest.time_unit == "minutes"
    assert SceneManifest.from_dict(scene.manifest.to_dict()).time_unit == "minutes"
    payload = scene.viewer_payload()
    timeline = payload["timeline"]
    assert isinstance(timeline, dict)
    assert timeline["unit"] == "minutes"
