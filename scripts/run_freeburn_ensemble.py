"""Run a documented weather-perturbation ensemble on free-burn large fires."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from ws4.fire.observed import ObservedFire

MEMBERS: tuple[dict[str, Any], ...] = (
    {"name": "baseline", "wind_scale": 1.0, "rh_offset": 0.0},
    {"name": "wind-low", "wind_scale": 0.8, "rh_offset": 0.0},
    {"name": "wind-high", "wind_scale": 1.2, "rh_offset": 0.0},
    {"name": "rh-dry", "wind_scale": 1.0, "rh_offset": -10.0},
    {"name": "rh-moist", "wind_scale": 1.0, "rh_offset": 10.0},
)


def _weather_member(fire: ObservedFire, wind_scale: float, rh_offset: float) -> ObservedFire:
    """Return a fire with perturbed wind and relative humidity."""
    weather = fire.weather.copy()
    weather["wind_speed_kmh"] = weather["wind_speed_kmh"].astype(float) * wind_scale
    weather["relative_humidity_percent"] = (
        weather["relative_humidity_percent"].astype(float) + rh_offset
    ).clip(1.0, 100.0)
    return replace(fire, weather=weather)


def _spread(values: list[float]) -> dict[str, float]:
    """Return the min, median, max and range of one metric."""
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "range": max(values) - min(values),
    }


def _time_to_observed_area(
    snapshots: tuple[Any, ...],
    observed_area_ha: float,
) -> float | None:
    """Return the first snapshot time at or above the observed area."""
    if observed_area_ha <= 0.0:
        return None
    for snapshot in snapshots:
        if float(snapshot.area_ha) >= observed_area_ha:
            return float(snapshot.time_min)
    return None


def _summary(rows: list[dict[str, Any]]) -> dict[str, object]:
    """Summarize overall and per-case ensemble spread."""
    biases = [float(row["area_bias"]) for row in rows]
    ious = [float(row["iou"]) for row in rows]
    times = [
        float(row["time_to_observed_area_min"])
        for row in rows
        if row["time_to_observed_area_min"] is not None
    ]
    cases = sorted({str(row["case"]) for row in rows})
    per_case: dict[str, object] = {}
    for case in cases:
        case_rows = [row for row in rows if str(row["case"]) == case]
        case_times = [
            float(row["time_to_observed_area_min"])
            for row in case_rows
            if row["time_to_observed_area_min"] is not None
        ]
        per_case[case] = {
            "run_count": len(case_rows),
            "area_bias": _spread([float(row["area_bias"]) for row in case_rows]),
            "iou": _spread([float(row["iou"]) for row in case_rows]),
            "time_to_observed_area_min": (_spread(case_times) if case_times else None),
        }
    return {
        "run_count": len(rows),
        "case_count": len(cases),
        "median_area_bias": statistics.median(biases),
        "min_area_bias": min(biases),
        "max_area_bias": max(biases),
        "median_iou": statistics.median(ious),
        "min_iou": min(ious),
        "max_iou": max(ious),
        "time_to_observed_area_min": _spread(times) if times else None,
        "per_case": per_case,
    }


def main() -> None:
    """Run the ensemble and write artifacts."""
    import pandas as pd
    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p178-freeburn-ensemble.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p178-freeburn-ensemble.csv",
    )
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    for fixture in args.fixtures:
        metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
        fire = load_cfsds_reanalysis_case(fixture)
        start = observed_mask(fire, 0)
        for member in MEMBERS:
            perturbed = _weather_member(
                fire,
                wind_scale=float(member["wind_scale"]),
                rh_offset=float(member["rh_offset"]),
            )
            result = run_observed_case(
                perturbed,
                scenario=f"freeburn-{member['name']}",
                ffmc=float(metadata["ffmc"]),
                bui=float(metadata["bui"]),
                duration_min=float(metadata["duration_min"]),
                initial_mask=start,
                snapshot_interval_min=60.0,
                neighbor_radius=2,
            )
            rows.append(
                {
                    "case": fire.fire_id,
                    "member": member["name"],
                    "wind_scale": member["wind_scale"],
                    "rh_offset": member["rh_offset"],
                    "area_obs_ha": result.metrics.area_obs_ha,
                    "area_sim_ha": result.metrics.area_sim_ha,
                    "area_bias": result.metrics.area_bias,
                    "iou": result.metrics.iou,
                    "sorensen": result.metrics.sorensen,
                    "time_to_observed_area_min": _time_to_observed_area(
                        result.growth.snapshots,
                        result.metrics.area_obs_ha,
                    ),
                }
            )
    payload = {
        "protocol": "free-burn large fires; first-perimeter seed; weather perturbation envelope",
        "model_skill": False,
        "members": list(MEMBERS),
        "summary": _summary(rows),
        "rows": rows,
        "limitations": (
            "Weather perturbations are a sensitivity envelope, not an operational ensemble. "
            "Small suppressed fires are excluded. No calibration was applied."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    frame = pd.DataFrame(rows)
    frame.to_csv(args.csv, index=False)
    print(
        frame[["case", "member", "area_bias", "iou", "time_to_observed_area_min"]].to_string(
            index=False
        )
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
