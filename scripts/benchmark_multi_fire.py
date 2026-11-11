"""Run the available public observed-fire event benchmark.

Only Dogrib and Hay River are in the repository. The result is a two-fire distribution, not a
regional validation. Hay River is saturated and is retained as a failure case, not excluded.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from ws4.fire.comparison import DogribCase


def _row(case: DogribCase, name: str) -> dict[str, object]:
    """Return one event-benchmark row."""
    metrics = case.metrics
    return {
        "case": name,
        "area_sim_ha": metrics.area_sim_ha,
        "area_obs_ha": metrics.area_obs_ha,
        "area_bias": metrics.area_bias,
        "perimeter_bias": metrics.perimeter_bias,
        "centroid_distance_m": metrics.centroid_distance_m,
        "iou": metrics.iou,
        "sorensen": metrics.sorensen,
        "orientation_error_deg": metrics.orientation_error_deg,
    }


def _as_float(row: dict[str, object], key: str) -> float:
    """Return one numeric row field."""
    value = row[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"row field {key!r} is not numeric")
    return float(value)


def main() -> None:
    """Run the fixed two-fire event benchmark and write artifacts."""
    from ws4.fire.comparison import (
        dogrib_burning_conditions,
        run_dogrib_case,
        run_observed_case,
    )
    from ws4.fire.observed import load_dogrib, load_hay_river
    from ws4.fire.validation import ValidationTier, classify_against_published

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "notes" / "reports" / "p164-multi-fire.csv"
    )
    parser.add_argument(
        "--summary", type=Path, default=ROOT / "notes" / "reports" / "p164-multi-fire.json"
    )
    args = parser.parse_args()
    dogrib = load_dogrib(ROOT / "tests" / "fixtures" / "fire" / "dogrib")
    hay = load_hay_river(ROOT / "tests" / "fixtures" / "fire" / "hay_river_2023")
    cases = {
        "dogrib-2b": run_dogrib_case(
            dogrib,
            scenario="dogrib-2b",
            heterogeneous=True,
            hourly_weather=True,
            weather_patches=True,
            point_ignition=True,
            fuel_break_start=True,
            duration_min=402.0,
            burning_conditions=dogrib_burning_conditions(),
        ),
        "hay-river-full": run_observed_case(
            hay,
            scenario="hay-river-full",
            ffmc=92.92,
            bui=73.28,
            duration_min=9360.0,
        ),
    }
    rows = [_row(case, name) for name, case in cases.items()]
    for row in rows:
        row["published_jaccard_position"] = classify_against_published(
            ValidationTier.EVENT, "jaccard", _as_float(row, "iou")
        )
    ious = [_as_float(row, "iou") for row in rows]
    sorensens = [_as_float(row, "sorensen") for row in rows]
    summary = {
        "case_count": len(rows),
        "cases": rows,
        "median_iou": statistics.median(ious),
        "worst_iou": min(ious),
        "best_iou": max(ious),
        "median_sorensen": statistics.median(sorensens),
        "worst_sorensen": min(sorensens),
        "published_event_envelope": "Jaccard 0.15-0.30; context, not a pass mark",
        "limitations": (
            "Only two public observed-fire fixtures exist. Hay River is saturated and is retained "
            "as a failure case. This is not a regional validation."
        ),
    }
    import pandas as pd

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        pd.DataFrame(rows)[
            ["case", "iou", "sorensen", "area_bias", "perimeter_bias", "published_jaccard_position"]
        ].to_string(index=False)
    )
    print(
        json.dumps(
            {
                key: summary[key]
                for key in ("median_iou", "worst_iou", "median_sorensen", "limitations")
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
