"""Build a synthetic forest and a standalone 3D fire scene.

Run from the repository root:

    python examples/fire_3d_demo.py

The script writes ``tmp/fire-3d-demo/viewer.html``. Open it in a browser with WebGL2 and
internet access for the Three.js module. The tree layer is synthetic; the fire timing comes
from the P144 event log.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.ecosystem.fire import FireConfig, FireRun, synthetic_grid  # noqa: E402
from ws4.scene import compile_fire_scene, synthetic_tree_inventory  # noqa: E402


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
    scene = compile_fire_scene(fire, trees, particle_budget=5000, burn_duration_years=1.5)
    paths = scene.write(ROOT / "tmp" / "fire-3d-demo")
    summary = scene.summary()
    print("WS4 3D fire scene")
    print(f"fragments: {summary['manifest']['fragment_count']}")
    print(f"trees: {summary['manifest']['tree_count']}")
    print(f"fire events: {summary['fire_count']}")
    print(f"replay digest: {summary['run_replay_token']}")
    print(f"viewer: {paths.viewer}")


if __name__ == "__main__":
    main()
