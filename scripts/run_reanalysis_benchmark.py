"""Run the P167 multi-case CFSDS reanalysis benchmark."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _summary(rows: list[dict[str, Any]]) -> dict[str, object]:
    """Return median, best, and worst metric summaries."""
    ious = [float(row["iou"]) for row in rows]
    area_biases = [float(row["area_bias"]) for row in rows]
    return {
        "case_count": len(rows),
        "median_iou": statistics.median(ious),
        "best_iou": max(ious),
        "worst_iou": min(ious),
        "median_area_bias": statistics.median(area_biases),
        "min_area_bias": min(area_biases),
        "max_area_bias": max(area_biases),
        "overpredicted_cases": sum(value > 0 for value in area_biases),
        "systematic_overprediction": all(value > 0 for value in area_biases),
    }


def main() -> None:
    """Run every fixture and write the distribution."""
    import pandas as pd
    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        nargs="+",
        required=True,
        help="One or more CFSDS reanalysis fixture directories.",
    )
    parser.add_argument(
        "--seed",
        choices=("point", "first-perimeter"),
        default="point",
        help="Ignition seeding mode.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p167-reanalysis-benchmark.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p167-reanalysis-benchmark.csv",
    )
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    for fixture in args.fixtures:
        metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
        fire = load_cfsds_reanalysis_case(fixture)
        initial_mask = observed_mask(fire, 0) if args.seed == "first-perimeter" else None
        result = run_observed_case(
            fire,
            scenario="cfsds-reanalysis-uncalibrated",
            ffmc=float(metadata["ffmc"]),
            bui=float(metadata["bui"]),
            duration_min=float(metadata["duration_min"]),
            initial_mask=initial_mask,
        )
        metrics = result.metrics
        rows.append(
            {
                "case": fire.fire_id,
                "seed": args.seed,
                "start_cells": result.start_cells,
                "event_start": metadata["event_start"],
                "duration_min": metadata["duration_min"],
                "area_obs_ha": metrics.area_obs_ha,
                "area_sim_ha": metrics.area_sim_ha,
                "area_bias": metrics.area_bias,
                "perimeter_bias": metrics.perimeter_bias,
                "iou": metrics.iou,
                "sorensen": metrics.sorensen,
                "centroid_distance_m": metrics.centroid_distance_m,
                "orientation_error_deg": metrics.orientation_error_deg,
            }
        )
    payload = {
        "protocol": f"uncalibrated CFSDS hourly reanalysis; seed={args.seed}",
        "model_skill": False,
        "cases": rows,
        "summary": _summary(rows),
        "limitations": (
            "Reanalysis weather, daily satellite perimeters, reconstructed ignition, and one "
            "fuel/terrain tile. No calibration was applied. This is event evidence, not "
            "operational validation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(args.csv, index=False)
    frame = pd.DataFrame(rows)
    print(
        frame[
            ["case", "iou", "sorensen", "area_bias", "perimeter_bias", "centroid_distance_m"]
        ].to_string(index=False)
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
