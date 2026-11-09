"""Run the Dogrib observed-fire comparison and a small sensitivity set.

The script writes a per-scenario CSV and JSON summary under ``notes/reports``. It is a
validation artifact, not a calibration: every override is explicit in the scenario table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.fire.comparison import DogribCase, run_dogrib_case  # noqa: E402
from ws4.fire.observed import ObservedFire, load_dogrib  # noqa: E402
from ws4.fire.observed_view import write_comparison_svg  # noqa: E402

SCENARIOS: tuple[str, ...] = ("base", "wind-27", "wind-43", "flat", "no-wind", "long-800")


def run_scenario(fire: ObservedFire, name: str) -> DogribCase:
    """Run one named sensitivity scenario.

    Parameters
    ----------
    fire : ObservedFire
        Dogrib observed fire.
    name : str
        Scenario name from ``SCENARIOS``.

    Returns
    -------
    DogribCase
        The simulated growth and comparison.
    """
    if name == "wind-27":
        return run_dogrib_case(fire, scenario=name, wind_kmh=27.0)
    if name == "wind-43":
        return run_dogrib_case(fire, scenario=name, wind_kmh=43.0)
    if name == "flat":
        return run_dogrib_case(fire, scenario=name, slope_percent=0.0)
    if name == "no-wind":
        return run_dogrib_case(fire, scenario=name, wind_kmh=0.0)
    if name == "long-800":
        return run_dogrib_case(fire, scenario=name, duration_min=800.0)
    return run_dogrib_case(fire, scenario=name)


def main() -> None:
    """Run the scenarios and write the evidence files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p157-dogrib-results.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "notes" / "reports" / "p157-dogrib-summary.json",
    )
    parser.add_argument(
        "--view",
        type=Path,
        default=ROOT / "notes" / "reports" / "p157-dogrib-view.svg",
    )
    args = parser.parse_args()
    fire = load_dogrib(ROOT / "tests" / "fixtures" / "fire" / "dogrib")
    rows: list[dict[str, object]] = []
    base_case: DogribCase | None = None
    for name in SCENARIOS:
        case = run_scenario(fire, name)
        if name == "base":
            base_case = case
        row: dict[str, object] = {
            "scenario": case.scenario,
            "duration_min": case.duration_min,
            "fuel_type": case.fuel_type,
            "ffmc": case.ffmc,
            "bui": case.bui,
            "wind_kmh": case.wind_kmh,
            "wind_direction_deg": case.wind_direction_deg,
            "slope_percent": case.slope_percent,
            "aspect_deg": case.aspect_deg,
            "start_cells": case.start_cells,
            "head_ros_m_min": case.growth.head_ros_m_min,
            "length_to_breadth": case.growth.length_to_breadth,
            "burned_area_ha": case.growth.burned_area_ha,
        }
        row.update({f"metric_{key}": value for key, value in case.metrics.to_dict().items()})
        rows.append(row)
    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    if base_case is not None:
        write_comparison_svg(fire, base_case, args.view)
    summary = {
        "fire": fire.to_dict(),
        "scenarios": rows,
        "view": str(args.view),
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    columns = [
        "scenario",
        "burned_area_ha",
        "metric_area_obs_ha",
        "metric_area_bias",
        "metric_perimeter_bias",
        "metric_centroid_distance_m",
        "metric_iou",
        "metric_sorensen",
        "metric_orientation_error_deg",
    ]
    print(frame[columns].to_string(index=False))


if __name__ == "__main__":
    main()
