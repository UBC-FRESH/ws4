"""Build a 3D fire scene over a real VRI polygon cluster.

The fixture in ``examples/fire_scene_vri`` is a 12-polygon cluster from the public TSA 24
block geometry, populated with Nemora-placed synthetic stems. The fire growth field is masked
to the polygons, so the front moves through the real stand shapes rather than a square grid.

Run from the repository root:

    python examples/fire_3d_vri_demo.py

The script writes ``tmp/fire-3d-vri-demo/viewer.html``.
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.ecosystem.fire import FireConfig, FireRun, synthetic_grid  # noqa: E402
from ws4.fire import GrowthConfig, SiteGrid, fbp_crown_fire, grow_fire  # noqa: E402
from ws4.scene import (  # noqa: E402
    compile_fire_scene,
    load_nemora_scene,
    sample_tree_ignition,
)

FIXTURE = ROOT / "examples" / "fire_scene_vri"
CELL_M = 5.0
MARGIN_M = 30.0
BURN_DURATION_MINUTES = 2.0


def main() -> None:
    """Compile the VRI scene and print the viewer path."""
    trees = load_nemora_scene(
        FIXTURE / "nemora_trees.csv",
        FIXTURE / "vri_polygons.geojson",
        seed=20261108,
        source="public TSA 24 block geometry (femic-tsa24-instance)",
        crs="local",
        nemora_version="ws4-fixture",
    )
    _, state, edges = synthetic_grid(1, len(trees.fragment_areas), fragment_area_ha=10.0)
    fire = FireRun(
        state,
        edges,
        FireConfig(ignition_rate_per_fragment_year=0.2, base_spread_probability=0.6),
        scenario_id="fire-3d-vri-demo",
        seed=7,
    ).run(5)
    scene = compile_fire_scene(
        fire,
        trees,
        particle_budget=5000,
        burn_duration_years=BURN_DURATION_MINUTES,
        time_unit="minutes",
    )

    min_x = min(tree.x for tree in trees.trees) - MARGIN_M
    min_y = min(tree.y for tree in trees.trees) - MARGIN_M
    max_x = max(tree.x for tree in trees.trees) + MARGIN_M
    max_y = max(tree.y for tree in trees.trees) + MARGIN_M
    cols = max(1, math.ceil((max_x - min_x) / CELL_M))
    rows = max(1, math.ceil((max_y - min_y) / CELL_M))
    polygons = [Polygon(ring).buffer(1.5) for ring in trees.fragment_polygons.values()]
    burnable = np.zeros((rows, cols), dtype=bool)
    for row in range(rows):
        y = min_y + (row + 0.5) * CELL_M
        for col in range(cols):
            x = min_x + (col + 0.5) * CELL_M
            point = Point(x, y)
            burnable[row, col] = any(polygon.contains(point) for polygon in polygons)
    center_x = sum(tree.x for tree in trees.trees) / len(trees.trees)
    center_y = sum(tree.y for tree in trees.trees) / len(trees.trees)
    start = min(
        trees.trees,
        key=lambda tree: (tree.x - center_x) ** 2 + (tree.y - center_y) ** 2,
    )
    ignition_col = min(cols - 1, max(0, int((start.x - min_x) / CELL_M)))
    ignition_row = min(rows - 1, max(0, int((start.y - min_y) / CELL_M)))
    if not burnable[ignition_row, ignition_col]:
        candidates = np.argwhere(burnable)
        if len(candidates) == 0:
            raise RuntimeError("no burnable cell in the VRI polygons")
        ignition_row, ignition_col = (int(value) for value in candidates[0])
    grid = SiteGrid(
        fuel_type="C3",
        rows=rows,
        cols=cols,
        cell_size_m=CELL_M,
        ffmc=92.0,
        bui=70.0,
        wind_kmh=25.0,
        wind_direction_deg=225.0,
        slope_percent=10.0,
        aspect_deg=225.0,
        burnable=burnable,
    )
    growth = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((ignition_row, ignition_col),),
            max_time_min=240.0,
            snapshot_interval_min=240.0,
            neighbor_radius=2,
        ),
    )
    wind = growth.effective_wind
    crown = fbp_crown_fire("C3", 92.0, 70.0, wind.speed_kmh)
    smoke_base = min(
        1.0,
        (crown.surface_fuel_consumption_kg_m2 + crown.crown_fuel_consumption_kg_m2) / 5.0,
    )
    animation = sample_tree_ignition(
        trees,
        growth,
        cell_size_m=CELL_M,
        margin_m=MARGIN_M,
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
            scene.manifest,
            burn_duration_years=BURN_DURATION_MINUTES,
            time_unit="minutes",
        ),
    )
    paths = scene.write(ROOT / "tmp" / "fire-3d-vri-demo")
    ignition = animation["ignition_time"].dropna()
    print("WS4 VRI 3D fire scene")
    print(f"polygons: {scene.manifest.fragment_count}")
    print(f"trees: {scene.manifest.tree_count}")
    print(f"burned area: {growth.burned_area_ha:.2f} ha")
    print(f"ROS: {growth.head_ros_m_min:.2f} m/min; flame: {crown.flame_length_m:.2f} m")
    print(f"ignition range: {float(ignition.min()):.1f} to {float(ignition.max()):.1f} minutes")
    print(f"source: {scene.manifest.source}")
    print(f"viewer: {paths.viewer}")


if __name__ == "__main__":
    main()
