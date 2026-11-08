"""Print the FBP surface-fire behaviour of the standard fuel types.

The demo uses FFMC 90, BUI 60, a 10 km/h wind, flat ground, and the default M/O blend
parameters. It is a surface-fire table, not a crown-fire or growth run.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.fire import FBP_FUEL_TYPES, fbp_surface_fire  # noqa: E402


def main() -> None:
    """Print the FBP surface-fire table."""
    print("fuel  ISI    SFC kg/m2  ROS m/min  HFI kW/m  flame m")
    for fuel in FBP_FUEL_TYPES:
        result = fbp_surface_fire(fuel, 90.0, 60.0, 10.0)
        print(
            f"{fuel:>4}  {result.isi:5.2f}  {result.surface_fuel_consumption_kg_m2:9.3f}  "
            f"{result.rate_of_spread_m_min:9.2f}  {result.head_fire_intensity_kw_m:8.1f}  "
            f"{result.flame_length_m:7.2f}"
        )
    print("surface-only: crown fire is a separate P156.3 layer")


if __name__ == "__main__":
    main()
