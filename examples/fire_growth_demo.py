"""Grow a homogeneous FBP fire and print its area and perimeter over time.

The demo uses C2, FFMC 90, BUI 60, a 20 km/h wind from the west, and flat ground. It is a
growth-engine demo, not a calibrated landscape fire.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.fire import GrowthConfig, SiteGrid, grow_fire  # noqa: E402


def main() -> None:
    """Run the wind-driven growth case and print snapshots."""
    grid = SiteGrid(
        fuel_type="C2",
        rows=201,
        cols=201,
        cell_size_m=10.0,
        ffmc=90.0,
        bui=60.0,
        wind_kmh=20.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((100, 100),),
            max_time_min=60.0,
            snapshot_interval_min=15.0,
        ),
    )
    print(
        f"effective wind: {result.effective_wind.speed_kmh:.2f} km/h at "
        f"{result.effective_wind.azimuth_deg:.1f} deg"
    )
    print(f"head ROS: {result.head_ros_m_min:.2f} m/min; LB: {result.length_to_breadth:.2f}")
    print("time min  burned cells  area ha  perimeter m")
    for snapshot in result.snapshots:
        print(
            f"{snapshot.time_min:8.0f}  {snapshot.burned_cells:12d}  "
            f"{snapshot.area_ha:7.2f}  {snapshot.perimeter_m:10.0f}"
        )


if __name__ == "__main__":
    main()
