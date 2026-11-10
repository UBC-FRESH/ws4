"""Run the pre-registered P161 Hay River calibration grid and Dogrib holdout."""

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

HAY_FFMC = 92.92
HAY_BUI = 73.28
HAY_DURATION_MIN = 9360.0


def _row(case: DogribCase, parameters: CalibrationParameters, fire: str) -> dict[str, object]:
    """Return one flat result row."""
    from ws4.fire.calibration import calibration_score

    score = calibration_score(case.metrics)
    return {
        "fire": fire,
        "scenario": case.scenario,
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
    """Return one numeric row field, rejecting a missing or non-numeric value."""
    value = row[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"row field {key!r} is not numeric")
    return float(value)


def _sort_key(row: dict[str, object]) -> tuple[float, float, float, float, float]:
    """Return the pre-registered tie-break key."""
    return (
        _as_float(row, "score"),
        abs(_as_float(row, "area_bias")),
        abs(_as_float(row, "perimeter_bias")),
        -_as_float(row, "iou"),
        _as_float(row, "centroid_distance_m"),
    )


def main() -> None:
    """Run the grid, print it, and write CSV/JSON artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p161-calibration-grid.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "notes" / "reports" / "p161-calibration-grid.json",
    )
    args = parser.parse_args()

    from ws4.fire.calibration import CalibrationParameters, calibration_score, parameter_grid
    from ws4.fire.comparison import (
        dogrib_burning_conditions,
        run_dogrib_case,
        run_observed_case,
    )
    from ws4.fire.observed import load_dogrib, load_hay_river

    hay = load_hay_river(ROOT / "tests" / "fixtures" / "fire" / "hay_river_2023")
    dogrib = load_dogrib(ROOT / "tests" / "fixtures" / "fire" / "dogrib")
    rows: list[dict[str, object]] = []
    for parameters in parameter_grid():
        case = run_observed_case(
            hay,
            scenario=f"hay-{parameters.wind_multiplier:.2f}-{parameters.head_ros_multiplier:.2f}",
            ffmc=HAY_FFMC,
            bui=HAY_BUI,
            duration_min=HAY_DURATION_MIN,
            wind_multiplier=parameters.wind_multiplier,
            head_ros_multiplier=parameters.head_ros_multiplier,
        )
        rows.append(_row(case, parameters, "hay_river"))
    best_row = min(rows, key=_sort_key)
    best = CalibrationParameters(
        wind_multiplier=_as_float(best_row, "wind_multiplier"),
        head_ros_multiplier=_as_float(best_row, "head_ros_multiplier"),
    )

    dogrib_baseline = run_dogrib_case(
        dogrib,
        scenario="dogrib-baseline",
        heterogeneous=True,
        hourly_weather=True,
        weather_patches=True,
        point_ignition=True,
        fuel_break_start=True,
        duration_min=402.0,
        burning_conditions=dogrib_burning_conditions(),
    )
    dogrib_holdout = run_dogrib_case(
        dogrib,
        scenario="dogrib-holdout",
        heterogeneous=True,
        hourly_weather=True,
        weather_patches=True,
        point_ignition=True,
        fuel_break_start=True,
        duration_min=402.0,
        burning_conditions=dogrib_burning_conditions(),
        wind_multiplier=best.wind_multiplier,
        head_ros_multiplier=best.head_ros_multiplier,
    )
    rows.append(_row(dogrib_baseline, CalibrationParameters(), "dogrib"))
    rows.append(_row(dogrib_holdout, best, "dogrib"))

    hay_rows = [row for row in rows if row["fire"] == "hay_river"]
    hay_burnable = sum(1 for row in hay.fbp_fuel_grid() for value in row if value is not None)
    baseline_hay = next(
        row
        for row in hay_rows
        if row["wind_multiplier"] == 1.0 and row["head_ros_multiplier"] == 1.0
    )
    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    summary = {
        "protocol": "notes/design/ws4-fire-calibration-protocol.md",
        "best": best.to_dict(),
        "best_hay_river": best_row,
        "baseline_hay_river": baseline_hay,
        "hay_burnable_cells": hay_burnable,
        "hay_unique_scores": len({row["score"] for row in hay_rows}),
        "dogrib_baseline": rows[-2],
        "dogrib_holdout": rows[-1],
        "rows": rows,
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    columns = [
        "fire",
        "scenario",
        "wind_multiplier",
        "head_ros_multiplier",
        "score",
        "area_bias",
        "perimeter_bias",
        "centroid_distance_m",
        "iou",
        "sorensen",
        "orientation_error_deg",
    ]
    print(frame[columns].to_string(index=False))
    print("\nbest", best.to_dict())
    print("dogrib baseline score", calibration_score(dogrib_baseline.metrics).total)
    print("dogrib holdout score", calibration_score(dogrib_holdout.metrics).total)


if __name__ == "__main__":
    main()
