"""P201: synthetic firebreak-gap sensitivity pilot on 2003_96."""

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

if TYPE_CHECKING:
    from ws4.fire.comparison import DogribCase


def build_gap_barrier(
    *,
    rows: int,
    cols: int,
    barrier_col: int,
    gap_center_row: int,
    gap_cells: int,
) -> np.ndarray:
    """Return a full-height barrier with a row gap.

    Parameters
    ----------
    rows, cols : int
        Grid shape.
    barrier_col : int
        Column occupied by the barrier.
    gap_center_row : int
        Centre row of the open gap.
    gap_cells : int
        Number of open rows; zero creates a closed barrier.

    Returns
    -------
    numpy.ndarray
        Boolean containment mask, True on non-burnable barrier cells.
    """
    if not 0 <= barrier_col < cols:
        raise ValueError("barrier_col must be inside the grid")
    if gap_cells < 0:
        raise ValueError("gap_cells must be non-negative")
    mask = np.zeros((rows, cols), dtype=bool)
    gap_start = gap_center_row - (gap_cells - 1) // 2
    gap_stop = gap_start + gap_cells
    for row in range(rows):
        if not gap_start <= row < gap_stop:
            mask[row, barrier_col] = True
    return mask


def _oracle_barrier_column(start: np.ndarray, observed: np.ndarray) -> int:
    start_cols = np.argwhere(start)[:, 1]
    observed_cols = np.argwhere(observed)[:, 1]
    if not len(start_cols) or not len(observed_cols):
        raise ValueError("start and observed masks must be non-empty")
    start_col = float(np.mean(start_cols))
    east_col = float(np.max(observed_cols))
    return round(start_col + 0.6 * (east_col - start_col))


def _row(
    *,
    member: dict[str, object],
    gap_cells: int,
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
        "gap_cells": gap_cells,
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
    """Run the gap pilot and write JSON and CSV artifacts."""
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
        default=ROOT / "notes/reports/p201-firebreak-gap.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes/reports/p201-firebreak-gap.csv",
    )
    parser.add_argument("--gap-widths", default="0,5,10")
    args = parser.parse_args()
    fixture = args.fixture or args.ws4_root / "tests/fixtures/fire/large_2003_96"
    sys.path.insert(0, str(SCRIPTS))
    from run_freeburn_ensemble import MEMBERS, _weather_member

    sys.path.insert(0, str(args.ws4_root))

    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    fire = load_cfsds_reanalysis_case(fixture)
    metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
    start = observed_mask(fire, 0)
    observed = observed_mask(fire, -1)
    barrier_col = _oracle_barrier_column(start, observed)
    observed_rows = np.argwhere(observed)[:, 0]
    gap_center_row = round(float(np.median(observed_rows)))
    gap_widths = [int(value) for value in args.gap_widths.split(",") if value]

    rows: list[dict[str, object]] = []
    for gap_cells in gap_widths:
        mask = build_gap_barrier(
            rows=fire.grid.nrows,
            cols=fire.grid.ncols,
            barrier_col=barrier_col,
            gap_center_row=gap_center_row,
            gap_cells=gap_cells,
        )
        for member in MEMBERS:
            perturbed = _weather_member(
                fire,
                wind_scale=float(member["wind_scale"]),
                rh_offset=float(member["rh_offset"]),
            )
            result = run_observed_case(
                perturbed,
                scenario=f"firebreak-gap-{gap_cells}-{member['name']}",
                ffmc=float(metadata["ffmc"]),
                bui=float(metadata["bui"]),
                duration_min=float(metadata["duration_min"]),
                initial_mask=start,
                containment_mask=mask,
                snapshot_interval_min=60.0,
                neighbor_radius=2,
            )
            rows.append(
                _row(
                    member=member,
                    gap_cells=gap_cells,
                    barrier_col=barrier_col,
                    result=result,
                    ignition=result.growth.ignition_time_min,
                )
            )

    payload = {
        "proof": "P201 synthetic firebreak-gap pilot",
        "case_id": metadata["case_id"],
        "fixture": str(fixture),
        "barrier": {
            "column": barrier_col,
            "gap_center_row": gap_center_row,
            "gap_widths": gap_widths,
            "placement": "oracle-assisted: 60% from mean start column to eastern observed extent",
        },
        "rows": rows,
        "limitations": [
            "Synthetic barrier geometry, not a surveyed firebreak.",
            "Barrier placement uses the observed final extent as a diagnostic guide.",
            "Weather perturbations are a sensitivity envelope, not an operational ensemble.",
            "No calibration was applied.",
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
            f"gap={row['gap_cells']:>2} {row['member']:<9} "
            f"area={row['area_sim_ha']:.0f} east={row['east_of_barrier_burned_cells']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
