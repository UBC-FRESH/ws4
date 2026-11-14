"""P203: time-dependent containment-closure pilot on 2003_96."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

if TYPE_CHECKING:
    from ws4.fire.comparison import DogribCase


def _row(
    *,
    member: dict[str, object],
    closure_min: float,
    barrier_col: int,
    result: DogribCase,
    ignition: np.ndarray,
) -> dict[str, object]:
    from run_freeburn_ensemble import _time_to_observed_area

    east = int(np.count_nonzero(np.isfinite(ignition[:, barrier_col + 1 :])))
    return {
        "case": "2003_96",
        "member": member["name"],
        "wind_scale": member["wind_scale"],
        "rh_offset": member["rh_offset"],
        "closure_min": closure_min,
        "barrier_col": barrier_col,
        "area_obs_ha": result.metrics.area_obs_ha,
        "area_sim_ha": result.metrics.area_sim_ha,
        "area_bias": result.metrics.area_bias,
        "iou": result.metrics.iou,
        "sorensen": result.metrics.sorensen,
        "east_of_barrier_burned_cells": east,
        "time_to_observed_area_min": _time_to_observed_area(
            result.growth.snapshots,
            result.metrics.area_obs_ha,
        ),
    }


def main() -> None:
    """Run the closure-time pilot and write JSON and CSV artifacts."""
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
        default=ROOT / "notes/reports/p203-containment-closure.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes/reports/p203-containment-closure.csv",
    )
    parser.add_argument("--gap-cells", type=int, default=5)
    parser.add_argument("--closures", default="0,1440,2880,4320")
    args = parser.parse_args()
    fixture = args.fixture or args.ws4_root / "tests/fixtures/fire/large_2003_96"
    sys.path.insert(0, str(args.ws4_root))

    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    sys.path.insert(0, str(SCRIPTS))
    from run_firebreak_gap_2003_96 import _oracle_barrier_column, build_gap_barrier
    from run_freeburn_ensemble import MEMBERS, _weather_member

    fire = load_cfsds_reanalysis_case(fixture)
    metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
    start = observed_mask(fire, 0)
    observed = observed_mask(fire, -1)
    barrier_col = _oracle_barrier_column(start, observed)
    observed_rows = np.argwhere(observed)[:, 0]
    gap_center_row = round(float(np.median(observed_rows)))
    barrier = build_gap_barrier(
        rows=fire.grid.nrows,
        cols=fire.grid.ncols,
        barrier_col=barrier_col,
        gap_center_row=gap_center_row,
        gap_cells=args.gap_cells,
    )
    closures = [float(value) for value in args.closures.split(",") if value]

    rows: list[dict[str, object]] = []
    for closure_min in closures:
        closure_grid = np.full(barrier.shape, np.inf, dtype=float)
        gap_rows = np.flatnonzero(~barrier[:, barrier_col])
        closure_grid[gap_rows, barrier_col] = closure_min
        for member in MEMBERS:
            perturbed = _weather_member(
                fire,
                wind_scale=float(member["wind_scale"]),
                rh_offset=float(member["rh_offset"]),
            )
            result = run_observed_case(
                perturbed,
                scenario=f"closure-{closure_min:g}-{member['name']}",
                ffmc=float(metadata["ffmc"]),
                bui=float(metadata["bui"]),
                duration_min=float(metadata["duration_min"]),
                initial_mask=start,
                containment_mask=barrier,
                containment_start_min=closure_grid,
                snapshot_interval_min=60.0,
                neighbor_radius=2,
            )
            rows.append(
                _row(
                    member=member,
                    closure_min=closure_min,
                    barrier_col=barrier_col,
                    result=result,
                    ignition=result.growth.ignition_time_min,
                )
            )

    payload = {
        "proof": "P203 time-dependent containment closure",
        "case_id": metadata["case_id"],
        "fixture": str(fixture),
        "barrier": {
            "column": barrier_col,
            "gap_center_row": gap_center_row,
            "gap_cells": args.gap_cells,
            "closures_min": closures,
            "placement": "oracle-assisted: 60% from mean start column to eastern observed extent",
        },
        "rows": rows,
        "limitations": [
            "Closure is permanent once a cell reaches its closure time.",
            "Synthetic, oracle-assisted barrier geometry.",
            "No water, retardant, crew or suppression-resource model.",
            "No calibration and no operational claim.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with args.csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"barrier column {barrier_col}, gap centre row {gap_center_row}")
    for row in rows:
        print(
            f"closure={row['closure_min']:>6.0f} {row['member']:<9} "
            f"area={row['area_sim_ha']:.0f} east={row['east_of_barrier_burned_cells']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
