"""Diagnose daily growth trajectory and neighbor-radius sensitivity."""

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


def _ratio(simulated: float, observed: float) -> float:
    """Return a safe area ratio."""
    return simulated / observed if observed > 0 else 0.0


def _summary(rows: list[dict[str, Any]]) -> dict[str, object]:
    """Summarize trajectory and radius results."""
    ratios_r2 = [float(row["area_ratio_r2"]) for row in rows]
    ratios_r1 = [float(row["area_ratio_r1"]) for row in rows]
    day1 = [float(row["area_ratio_day1"]) for row in rows]
    return {
        "case_count": len(rows),
        "median_final_ratio_r2": statistics.median(ratios_r2),
        "median_final_ratio_r1": statistics.median(ratios_r1),
        "median_day1_ratio": statistics.median(day1),
        "cases_over_2x_at_day1": sum(value > 2.0 for value in day1),
        "cases_over_2x_final_r2": sum(value > 2.0 for value in ratios_r2),
        "cases_over_2x_final_r1": sum(value > 2.0 for value in ratios_r1),
        "radius1_fixes_bias": all(value <= 2.0 for value in ratios_r1),
    }


def main() -> None:
    """Run the six-case trajectory and radius diagnostic."""
    import pandas as pd
    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p169-growth-trajectory.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p169-growth-trajectory.csv",
    )
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    for fixture in args.fixtures:
        metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
        fire = load_cfsds_reanalysis_case(fixture)
        start = observed_mask(fire, 0)
        ffmc = float(metadata["ffmc"])
        bui = float(metadata["bui"])
        duration_min = float(metadata["duration_min"])
        daily = run_observed_case(
            fire,
            scenario="trajectory",
            ffmc=ffmc,
            bui=bui,
            duration_min=duration_min,
            initial_mask=start,
            snapshot_interval_min=1440.0,
            neighbor_radius=2,
        )
        final_r2 = run_observed_case(
            fire,
            scenario="radius-2",
            ffmc=ffmc,
            bui=bui,
            duration_min=duration_min,
            initial_mask=start,
            neighbor_radius=2,
        )
        final_r1 = run_observed_case(
            fire,
            scenario="radius-1",
            ffmc=ffmc,
            bui=bui,
            duration_min=duration_min,
            initial_mask=start,
            neighbor_radius=1,
        )
        observed = [float(value) for value in metadata["daily_cumuarea_ha"]]
        simulated = [snapshot.area_ha for snapshot in daily.growth.snapshots]
        ratios = [_ratio(simulated[index], observed[index]) for index in range(len(observed))]
        rows.append(
            {
                "case": fire.fire_id,
                "start_cells": daily.start_cells,
                "day_count": len(observed),
                "observed_final_ha": observed[-1],
                "simulated_final_ha": final_r2.growth.burned_area_ha,
                "area_ratio_r2": _ratio(final_r2.growth.burned_area_ha, observed[-1]),
                "area_ratio_r1": _ratio(final_r1.growth.burned_area_ha, observed[-1]),
                "area_ratio_day1": ratios[0],
                "area_ratio_day2": ratios[1] if len(ratios) > 1 else None,
                "first_day_over_2x": next(
                    (index + 1 for index, value in enumerate(ratios) if value > 2.0),
                    None,
                ),
                "daily_ratios": ratios,
                "iou_r2": final_r2.metrics.iou,
                "iou_r1": final_r1.metrics.iou,
            }
        )
    payload = {
        "protocol": "first-perimeter seed; hourly reanalysis weather; no calibration",
        "rows": rows,
        "summary": _summary(rows),
        "limitations": (
            "Daily observed cumulative area is from CFSDS, but the comparison uses a fixed "
            "13:00 event start and daily snapshots. This is diagnostic, not a calibration."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    frame = pd.DataFrame(rows)
    frame.to_csv(args.csv, index=False)
    print(
        frame[
            [
                "case",
                "area_ratio_day1",
                "area_ratio_r2",
                "area_ratio_r1",
                "first_day_over_2x",
                "iou_r1",
            ]
        ].to_string(index=False)
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
