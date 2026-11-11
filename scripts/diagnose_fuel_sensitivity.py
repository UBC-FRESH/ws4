"""Compare per-cell fuel with homogeneous dominant fuel on the six cases."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ratio(simulated: float, observed: float) -> float:
    """Return a safe area ratio."""
    return simulated / observed if observed > 0 else 0.0


def main() -> None:
    """Run per-cell vs dominant-fuel sensitivity."""
    import pandas as pd
    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p172-fuel-sensitivity.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p172-fuel-sensitivity.csv",
    )
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    for fixture in args.fixtures:
        metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
        fire = load_cfsds_reanalysis_case(fixture)
        start = observed_mask(fire, 0)
        fuel = fire.fbp_fuel_grid()
        counts = Counter(value for value in fuel.ravel() if value is not None)
        dominant = counts.most_common(1)[0][0]
        ffmc = float(metadata["ffmc"])
        bui = float(metadata["bui"])
        duration_min = float(metadata["duration_min"])
        per_cell = run_observed_case(
            fire,
            scenario="per-cell",
            ffmc=ffmc,
            bui=bui,
            duration_min=duration_min,
            initial_mask=start,
            neighbor_radius=2,
        )
        homogeneous = run_observed_case(
            fire,
            scenario="dominant",
            ffmc=ffmc,
            bui=bui,
            duration_min=duration_min,
            initial_mask=start,
            neighbor_radius=2,
            fuel_override=dominant,
        )
        rows.append(
            {
                "case": fire.fire_id,
                "dominant_fuel": dominant,
                "burnable_cells": int(fuel.size - sum(value is None for value in fuel.ravel())),
                "observed_final_ha": per_cell.metrics.area_obs_ha,
                "per_cell_area_ha": per_cell.metrics.area_sim_ha,
                "homogeneous_area_ha": homogeneous.metrics.area_sim_ha,
                "per_cell_ratio": _ratio(
                    per_cell.metrics.area_sim_ha, per_cell.metrics.area_obs_ha
                ),
                "homogeneous_ratio": _ratio(
                    homogeneous.metrics.area_sim_ha, per_cell.metrics.area_obs_ha
                ),
                "per_cell_iou": per_cell.metrics.iou,
                "homogeneous_iou": homogeneous.metrics.iou,
            }
        )
    ratios_per_cell = [float(row["per_cell_ratio"]) for row in rows]
    ratios_homogeneous = [float(row["homogeneous_ratio"]) for row in rows]
    payload = {
        "protocol": "first-perimeter seed; hourly reanalysis; fuel override diagnostic",
        "summary": {
            "case_count": len(rows),
            "median_per_cell_ratio": statistics.median(ratios_per_cell),
            "median_homogeneous_ratio": statistics.median(ratios_homogeneous),
            "homogeneous_reduces_ratio_cases": sum(
                float(row["homogeneous_ratio"]) < float(row["per_cell_ratio"]) for row in rows
            ),
            "fuel_explains_bias": all(value < 2.0 for value in ratios_homogeneous),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(args.csv, index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
