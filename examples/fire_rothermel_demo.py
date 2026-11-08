"""Print the Rothermel surface-fire behaviour of the standard fuel models.

The demo uses the D2L2 moisture scenario, an 8 km/h midflame wind, and level ground. It is a
validation/demo table, not a landscape fire growth run.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.fire import ANDERSON_13, MOISTURE_SCENARIOS, FireEnvironment, surface_fire  # noqa: E402


def main() -> None:
    """Print the standard-model behaviour table."""
    environment = FireEnvironment(wind_kmh=8.0, slope_percent=0.0)
    moisture = MOISTURE_SCENARIOS["D2L2"]
    print("model  ROS m/min  reaction kW/m2  intensity kW/m  flame m")
    for name in sorted(ANDERSON_13, key=lambda value: int(value[1:])):
        result = surface_fire(ANDERSON_13[name], moisture, environment)
        print(
            f"{name:>3}  {result.rate_of_spread_m_min:9.2f}  "
            f"{result.reaction_intensity_kw_m2:13.2f}  "
            f"{result.head_fire_intensity_kw_m:13.1f}  "
            f"{result.flame_length_m:7.2f}"
        )


if __name__ == "__main__":
    main()
