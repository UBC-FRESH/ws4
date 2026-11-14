"""P204: rain-driven fire-stopping pilot on 2003_96."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ws4.fire.comparison import DogribCase

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _row(*, case_id: str, member: dict[str, object], result: DogribCase) -> dict[str, object]:
    from run_freeburn_ensemble import _time_to_observed_area

    return {
        "case": case_id,
        "member": member["name"],
        "wind_scale": member["wind_scale"],
        "rh_offset": member["rh_offset"],
        "threshold_mm": 12.7,
        "window_min": 7200.0,
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


def main() -> None:
    """Run the rain-stopping pilot and write JSON and CSV artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ws4-root", type=Path, required=True)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="defaults to <ws4-root>/tests/fixtures/fire/large_2003_96",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes/reports/p204-rain-stopping.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes/reports/p204-rain-stopping.csv",
    )
    args = parser.parse_args()
    fixture = args.fixture or args.ws4_root / "tests/fixtures/fire/large_2003_96"
    sys.path.insert(0, str(args.ws4_root))
    sys.path.insert(0, str(SCRIPTS))

    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    from run_freeburn_ensemble import MEMBERS, _weather_member

    fire = load_cfsds_reanalysis_case(fixture)
    metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
    start = observed_mask(fire, 0)
    rows: list[dict[str, object]] = []
    for member in MEMBERS:
        perturbed = _weather_member(
            fire,
            wind_scale=float(member["wind_scale"]),
            rh_offset=float(member["rh_offset"]),
        )
        result = run_observed_case(
            perturbed,
            scenario=f"rain-stop-{member['name']}",
            ffmc=float(metadata["ffmc"]),
            bui=float(metadata["bui"]),
            duration_min=float(metadata["duration_min"]),
            initial_mask=start,
            snapshot_interval_min=60.0,
            neighbor_radius=2,
            fire_stopping_precipitation_mm=12.7,
            fire_stopping_window_min=7200.0,
        )
        rows.append(_row(case_id=str(metadata["case_id"]), member=member, result=result))

    payload = {
        "proof": "P204 rain-driven fire stopping",
        "case_id": metadata["case_id"],
        "fixture": str(fixture),
        "criterion": (
            "Latham and Rothermel (1993): at least 0.5 inch (~12.7 mm) accumulated "
            "over 5 days or fewer"
        ),
        "rows": rows,
        "limitations": [
            "Expert-opinion fire-stopping criterion, not a calibrated physical threshold.",
            "Hard stop: no reignition after the threshold is reached.",
            "One case and five weather members.",
            "No water, retardant, crews or suppression resources.",
            "No calibration and no operational claim.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with args.csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(
            f"{row['member']:<9} area={row['area_sim_ha']:.0f} "
            f"bias={row['area_bias']:.2f} iou={row['iou']:.3f}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
