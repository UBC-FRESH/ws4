"""Run the P162 Hay River calibration-sensitivity diagnostic.

This is not a calibration fit. It asks whether three registered parameter points change the
result at one-day, three-day, and full-event windows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from ws4.fire.calibration import CalibrationParameters
    from ws4.fire.comparison import DogribCase

# Window label, duration in minutes, matching observed-perimeter index.
WINDOWS = (
    ("day-1", 660.0, 0),
    ("day-3", 3540.0, 2),
    ("full", 9360.0, 6),
)
POINTS = (
    ("baseline", 1.00, 1.00),
    ("low", 0.70, 0.50),
    ("high", 1.30, 1.50),
)


def _row(
    case: DogribCase,
    parameters: CalibrationParameters,
    *,
    window: str,
    duration_min: float,
    observed_index: int,
) -> dict[str, object]:
    """Return one flat diagnostic row."""
    from ws4.fire.calibration import calibration_score

    score = calibration_score(case.metrics)
    return {
        "window": window,
        "duration_min": duration_min,
        "observed_index": observed_index,
        "wind_multiplier": parameters.wind_multiplier,
        "head_ros_multiplier": parameters.head_ros_multiplier,
        "score": score.total,
        "score_area": score.area,
        "score_perimeter": score.perimeter,
        "score_centroid": score.centroid,
        "score_iou": score.iou,
        "score_sorensen": score.sorensen,
        "score_orientation": score.orientation,
        **case.metrics.to_dict(),
    }


def _as_float(row: dict[str, object], key: str) -> float:
    """Return one numeric row field."""
    value = row[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"row field {key!r} is not numeric")
    return float(value)


def _unique_signature(row: dict[str, object]) -> tuple[object, ...]:
    """Return the fields that must change for a window to be sensitive."""
    return (
        row["area_sim_ha"],
        row["perimeter_sim_m"],
        row["iou"],
        row["sorensen"],
        row["centroid_distance_m"],
        row["orientation_error_deg"],
        row["score"],
    )


def main() -> None:
    """Run the fixed diagnostic and write CSV/JSON artifacts."""
    from ws4.fire.calibration import CalibrationParameters
    from ws4.fire.comparison import run_observed_case
    from ws4.fire.observed import load_hay_river

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p162-sensitivity.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "notes" / "reports" / "p162-sensitivity.json",
    )
    args = parser.parse_args()
    fire = load_hay_river(ROOT / "tests" / "fixtures" / "fire" / "hay_river_2023")
    rows: list[dict[str, object]] = []
    for window, duration, observed_index in WINDOWS:
        for label, wind, head in POINTS:
            parameters = CalibrationParameters(wind, head)
            case = run_observed_case(
                fire,
                scenario=f"hay-{window}-{label}",
                ffmc=92.92,
                bui=73.28,
                duration_min=duration,
                observed_index=observed_index,
                wind_multiplier=wind,
                head_ros_multiplier=head,
            )
            rows.append(
                _row(
                    case,
                    parameters,
                    window=window,
                    duration_min=duration,
                    observed_index=observed_index,
                )
            )
    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    sensitivity = {}
    for window, _duration, _index in WINDOWS:
        window_rows = [row for row in rows if row["window"] == window]
        signatures = {_unique_signature(row) for row in window_rows}
        sensitivity[window] = {
            "unique_results": len(signatures),
            "sensitive": len(signatures) > 1,
            "max_area_ha": max(_as_float(row, "area_sim_ha") for row in window_rows),
            "min_area_ha": min(_as_float(row, "area_sim_ha") for row in window_rows),
            "max_iou": max(_as_float(row, "iou") for row in window_rows),
            "min_iou": min(_as_float(row, "iou") for row in window_rows),
        }
    summary = {
        "windows": [
            {"name": name, "duration_min": duration, "observed_index": index}
            for name, duration, index in WINDOWS
        ],
        "points": [
            {"name": name, "wind_multiplier": wind, "head_ros_multiplier": head}
            for name, wind, head in POINTS
        ],
        "sensitivity": sensitivity,
        "any_sensitive": any(item["sensitive"] for item in sensitivity.values()),
        "rows": rows,
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    columns = [
        "window",
        "wind_multiplier",
        "head_ros_multiplier",
        "score",
        "area_sim_ha",
        "area_obs_ha",
        "area_bias",
        "perimeter_bias",
        "iou",
        "sorensen",
        "centroid_distance_m",
        "orientation_error_deg",
    ]
    print(frame[columns].to_string(index=False))
    print("\nsensitivity", json.dumps(sensitivity, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
