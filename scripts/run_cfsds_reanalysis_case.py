"""Run WS4 on the P166 CFSDS hourly-reanalysis case."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    """Run the case and write its metrics."""
    from ws4.fire.comparison import run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p166-reanalysis-case.json",
    )
    args = parser.parse_args()
    metadata = json.loads((args.fixture / "metadata.json").read_text(encoding="utf-8"))
    fire = load_cfsds_reanalysis_case(args.fixture)
    result = run_observed_case(
        fire,
        scenario="cfsds-reanalysis-uncalibrated",
        ffmc=float(metadata["ffmc"]),
        bui=float(metadata["bui"]),
        duration_min=float(metadata["duration_min"]),
    )
    payload = {
        "case": fire.fire_id,
        "weather_mode": metadata["weather_mode"],
        "ignition_mode": metadata["ignition_mode"],
        "event_start": metadata["event_start"],
        "event_end": metadata["event_end"],
        "ffmc": metadata["ffmc"],
        "bui": metadata["bui"],
        "result": result.to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics = result.metrics
    print(
        json.dumps(
            {
                "case": fire.fire_id,
                "iou": metrics.iou,
                "sorensen": metrics.sorensen,
                "area_sim_ha": metrics.area_sim_ha,
                "area_obs_ha": metrics.area_obs_ha,
                "area_bias": metrics.area_bias,
                "perimeter_bias": metrics.perimeter_bias,
                "centroid_distance_m": metrics.centroid_distance_m,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
