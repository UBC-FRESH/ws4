"""Compare DEM terrain with flat terrain on the six reanalysis cases."""

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


def main() -> None:
    """Run DEM-vs-flat sensitivity."""
    import pandas as pd
    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p171-terrain-sensitivity.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p171-terrain-sensitivity.csv",
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
        dem = run_observed_case(
            fire,
            scenario="dem",
            ffmc=ffmc,
            bui=bui,
            duration_min=duration_min,
            initial_mask=start,
            neighbor_radius=2,
            flat_terrain=False,
        )
        flat = run_observed_case(
            fire,
            scenario="flat",
            ffmc=ffmc,
            bui=bui,
            duration_min=duration_min,
            initial_mask=start,
            neighbor_radius=2,
            flat_terrain=True,
        )
        rows.append(
            {
                "case": fire.fire_id,
                "observed_final_ha": dem.metrics.area_obs_ha,
                "dem_area_ha": dem.metrics.area_sim_ha,
                "flat_area_ha": flat.metrics.area_sim_ha,
                "dem_area_ratio": _ratio(dem.metrics.area_sim_ha, dem.metrics.area_obs_ha),
                "flat_area_ratio": _ratio(flat.metrics.area_sim_ha, flat.metrics.area_obs_ha),
                "dem_iou": dem.metrics.iou,
                "flat_iou": flat.metrics.iou,
            }
        )
    ratios_dem = [float(row["dem_area_ratio"]) for row in rows]
    ratios_flat = [float(row["flat_area_ratio"]) for row in rows]
    payload = {
        "protocol": "first-perimeter seed; hourly reanalysis; terrain sensitivity only",
        "summary": {
            "case_count": len(rows),
            "median_dem_ratio": statistics.median(ratios_dem),
            "median_flat_ratio": statistics.median(ratios_flat),
            "flat_reduces_ratio_cases": sum(
                float(row["flat_area_ratio"]) < float(row["dem_area_ratio"]) for row in rows
            ),
            "terrain_explains_bias": all(value < 2.0 for value in ratios_flat),
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
