"""Print the FBP surface and crown-fire behaviour of the standard fuel types.

The demo uses FFMC 90, BUI 60, a 10 km/h wind, flat ground, and the default site inputs for
foliar moisture. It shows the surface/crown classification and the head fire intensity.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.fire import FBP_FUEL_TYPES, fbp_crown_fire  # noqa: E402


def main() -> None:
    """Print the FBP surface and crown-fire table."""
    print("fuel  CFB    FD  surface ROS  head ROS  HFI kW/m  flame m")
    for fuel in FBP_FUEL_TYPES:
        result = fbp_crown_fire(fuel, 90.0, 60.0, 10.0)
        print(
            f"{fuel:>4}  {result.crown_fraction_burned:5.3f}  {result.fire_description}  "
            f"{result.surface_rate_of_spread_m_min:10.2f}  "
            f"{result.rate_of_spread_m_min:8.2f}  "
            f"{result.head_fire_intensity_kw_m:9.1f}  {result.flame_length_m:6.2f}"
        )
    print("FD: S surface, I intermittent/passive crown, C active crown")
    crown = fbp_crown_fire("C6", 95.0, 80.0, 20.0, canopy_bulk_density_kg_m3=0.1)
    print(
        f"C6 crown case: FFMC 95, BUI 80, WS 20 -> CFB {crown.crown_fraction_burned:.3f}, "
        f"{crown.fire_description}, HFI {crown.head_fire_intensity_kw_m:.1f} kW/m"
    )


if __name__ == "__main__":
    main()
