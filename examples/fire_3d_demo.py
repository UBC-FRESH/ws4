"""Build a synthetic forest and a standalone 3D fire scene.

Run from the repository root:

    python examples/fire_3d_demo.py

The script writes ``tmp/fire-3d-demo/viewer.html``. The tree layer is synthetic. The fire
timing comes from the P156 FBP growth field: each tree samples the cell ignition time at its
position, so the front moves through the stand instead of igniting whole fragments.
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.ecosystem.fire import FireBehaviourConfig, FireConfig, FireRun, synthetic_grid  # noqa: E402
from ws4.fire import (  # noqa: E402
    GrowthConfig,
    SiteGrid,
    fbp_crown_fire,
    grow_fire,
)
from ws4.scene import (  # noqa: E402
    compile_fire_scene,
    sample_tree_ignition,
    synthetic_tree_inventory,
)

SCENE_CELL_M = 5.0
SCENE_MARGIN_M = 30.0
BURN_DURATION_MINUTES = 2.0


def main() -> None:
    """Run the fire, compile the scene, and print the viewer path."""
    _, state, edges = synthetic_grid(3, 3)
    fire = FireRun(
        state,
        edges,
        FireConfig(
            ignition_rate_per_fragment_year=0.08,
            base_spread_probability=0.55,
            distance_scale_m=180.0,
            wind_direction_deg=225.0,
            wind_strength=0.35,
            behaviour=FireBehaviourConfig(
                fuel_type="C2",
                ffmc=92.0,
                bui=70.0,
                wind_kmh=25.0,
                wind_direction_deg=225.0,
                slope_percent=20.0,
                aspect_deg=225.0,
                time_step_min=30.0,
            ),
        ),
        scenario_id="fire-3d-demo",
        seed=7,
    ).run(15)
    trees = synthetic_tree_inventory(
        fire.state.fragment_areas,
        seed=7,
        trees_per_ha=250.0,
        surface_fuel_t_ha=12.0,
    )
    scene = compile_fire_scene(
        fire,
        trees,
        particle_budget=5000,
        burn_duration_years=BURN_DURATION_MINUTES,
        time_unit="minutes",
    )

    min_x = min(tree.x for tree in trees.trees) - SCENE_MARGIN_M
    max_x = max(tree.x for tree in trees.trees) + SCENE_MARGIN_M
    min_y = min(tree.y for tree in trees.trees) - SCENE_MARGIN_M
    max_y = max(tree.y for tree in trees.trees) + SCENE_MARGIN_M
    cols = max(1, math.ceil((max_x - min_x) / SCENE_CELL_M))
    rows = max(1, math.ceil((max_y - min_y) / SCENE_CELL_M))
    growth_grid = SiteGrid(
        fuel_type="C2",
        rows=rows,
        cols=cols,
        cell_size_m=SCENE_CELL_M,
        ffmc=92.0,
        bui=70.0,
        wind_kmh=25.0,
        wind_direction_deg=225.0,
        slope_percent=20.0,
        aspect_deg=225.0,
    )
    ignition_row = max(1, rows // 5)
    ignition_col = max(1, cols // 5)
    growth = grow_fire(
        growth_grid,
        GrowthConfig(
            ignition_cells=((ignition_row, ignition_col),),
            max_time_min=120.0,
            snapshot_interval_min=120.0,
            neighbor_radius=2,
        ),
    )
    wind = growth.effective_wind
    crown = fbp_crown_fire("C2", 92.0, 70.0, wind.speed_kmh)
    smoke_base = min(
        1.0,
        (crown.surface_fuel_consumption_kg_m2 + crown.crown_fuel_consumption_kg_m2) / 5.0,
    )
    animation = sample_tree_ignition(
        trees,
        growth,
        cell_size_m=SCENE_CELL_M,
        margin_m=SCENE_MARGIN_M,
        flame_length_m=crown.flame_length_m,
        smoke_strength=smoke_base,
        burn_duration=BURN_DURATION_MINUTES,
    )
    fragment_times = (
        animation.dropna(subset=["ignition_time"]).groupby("fragment_id")["ignition_time"].min()
    )
    fires = scene.fires.copy()
    fires["time"] = fires["fragment_id"].map(fragment_times).fillna(0.0)
    fires["year"] = 0
    stands = scene.stands.copy()
    stands["burn_time"] = np.nan
    scene = replace(
        scene,
        stands=stands,
        fires=fires,
        animation=animation,
        manifest=replace(
            scene.manifest, burn_duration_years=BURN_DURATION_MINUTES, time_unit="minutes"
        ),
    )
    paths = scene.write(ROOT / "tmp" / "fire-3d-demo")
    summary = scene.summary()
    print("WS4 3D fire scene")
    print(f"fragments: {scene.manifest.fragment_count}")
    print(f"trees: {scene.manifest.tree_count}")
    print(f"fire events: {summary['fire_count']}")
    print(f"growth area: {growth.burned_area_ha:.2f} ha")
    print(f"ROS range: {growth.head_ros_m_min:.2f} m/min; flame: {crown.flame_length_m:.2f} m")
    ignition = animation["ignition_time"].dropna()
    print(
        f"ignition time range: {float(ignition.min()):.1f} to {float(ignition.max()):.1f} minutes"
    )
    print(f"replay digest: {summary['run_replay_token']}")
    print(f"viewer: {paths.viewer}")


if __name__ == "__main__":
    main()
