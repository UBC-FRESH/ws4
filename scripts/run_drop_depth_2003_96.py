"""P208: single drop-depth pilot on 2003_96."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ws4.fire.comparison import DogribCase

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def ellipse_coverage(
    *,
    center_x: float,
    center_y: float,
    length_m: float,
    width_m: float,
    cell_x: float,
    cell_y: float,
    cell_size_m: float,
    samples: int = 50,
) -> float:
    """Return the fraction of a cell centre area inside an axis-aligned ellipse.

    Parameters
    ----------
    center_x, center_y : float
        Ellipse centre in projected metres.
    length_m, width_m : float
        Ellipse axes in metres.
    cell_x, cell_y : float
        Cell centre in projected metres.
    cell_size_m : float
        Cell size in metres.
    samples : int, optional
        Number of samples per axis (default 50).

    Returns
    -------
    float
        Fraction of the cell inside the ellipse.
    """
    half_l = length_m / 2.0
    half_w = width_m / 2.0
    if half_l <= 0.0 or half_w <= 0.0:
        raise ValueError("drop axes must be positive")
    inside = 0
    for i in range(samples):
        for j in range(samples):
            x = cell_x - cell_size_m / 2.0 + (i + 0.5) * cell_size_m / samples
            y = cell_y - cell_size_m / 2.0 + (j + 0.5) * cell_size_m / samples
            if ((x - center_x) / half_l) ** 2 + ((y - center_y) / half_w) ** 2 <= 1.0:
                inside += 1
    return inside / (samples * samples)


def build_depth_grid(
    *,
    rows: int,
    cols: int,
    xll: float,
    yll: float,
    cell_size_m: float,
    gap_cells: list[tuple[int, int]],
    drops_per_cell: int,
    volume_l: float,
    length_m: float,
    width_m: float,
) -> np.ndarray:
    """Build cell-mean depth in millimetres for a set of drop centres.

    Parameters
    ----------
    rows, cols : int
        Grid shape.
    xll, yll : float
        Grid lower-left coordinates in projected metres.
    cell_size_m : float
        Cell size in metres.
    gap_cells : list of tuple
        Drop-centre cells as ``(row, col)`` pairs.
    drops_per_cell : int
        Number of identical drops per centre.
    volume_l : float
        Volume per drop in litres.
    length_m, width_m : float
        Drop ellipse axes in metres.

    Returns
    -------
    numpy.ndarray
        Cell-mean depth in millimetres.
    """
    depth = np.zeros((rows, cols), dtype=float)
    ellipse_area_m2 = math.pi * (length_m / 2.0) * (width_m / 2.0)
    nominal_mm = volume_l / ellipse_area_m2
    for row, col in gap_cells:
        center_x = xll + (col + 0.5) * cell_size_m
        center_y = yll + (rows - 1 - row + 0.5) * cell_size_m
        for _ in range(drops_per_cell):
            for r in range(rows):
                for c in range(cols):
                    x = xll + (c + 0.5) * cell_size_m
                    y = yll + (rows - 1 - r + 0.5) * cell_size_m
                    depth[r, c] += nominal_mm * ellipse_coverage(
                        center_x=center_x,
                        center_y=center_y,
                        length_m=length_m,
                        width_m=width_m,
                        cell_x=x,
                        cell_y=y,
                        cell_size_m=cell_size_m,
                    )
    return depth


def main() -> None:
    """Run the drop-depth pilot and write JSON and CSV artifacts."""
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
        default=ROOT / "notes/reports/p208-drop-depth.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes/reports/p208-drop-depth.csv",
    )
    parser.add_argument("--drop-times", default="12000,13000,14000")
    args = parser.parse_args()
    fixture = args.fixture or args.ws4_root / "tests/fixtures/fire/large_2003_96"
    sys.path.insert(0, str(args.ws4_root))
    sys.path.insert(0, str(SCRIPTS))

    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    from run_firebreak_gap_2003_96 import _oracle_barrier_column, build_gap_barrier
    from run_freeburn_ensemble import MEMBERS, _time_to_observed_area, _weather_member

    fire = load_cfsds_reanalysis_case(fixture)
    metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
    start = observed_mask(fire, 0)
    observed = observed_mask(fire, -1)
    barrier_col = _oracle_barrier_column(start, observed)
    gap_center_row = round(float(np.median(np.argwhere(observed)[:, 0])))
    barrier = build_gap_barrier(
        rows=fire.grid.nrows,
        cols=fire.grid.ncols,
        barrier_col=barrier_col,
        gap_center_row=gap_center_row,
        gap_cells=5,
    )
    gap_cells = [(int(row), barrier_col) for row in np.flatnonzero(~barrier[:, barrier_col])]
    depth = build_depth_grid(
        rows=fire.grid.nrows,
        cols=fire.grid.ncols,
        xll=fire.grid.xll,
        yll=fire.grid.yll,
        cell_size_m=fire.grid.cell_size_m,
        gap_cells=gap_cells,
        drops_per_cell=2,
        volume_l=6000.0,
        length_m=100.0,
        width_m=50.0,
    )
    gap_mean_depth = float(
        np.mean([depth[row, barrier_col] for row in np.flatnonzero(~barrier[:, barrier_col])])
    )
    drop_times = [float(value) for value in args.drop_times.split(",") if value]

    rows: list[dict[str, object]] = []
    for drop_time in drop_times:
        for member in MEMBERS:
            perturbed = _weather_member(
                fire,
                wind_scale=float(member["wind_scale"]),
                rh_offset=float(member["rh_offset"]),
            )
            result: DogribCase = run_observed_case(
                perturbed,
                scenario=f"drop-{drop_time:g}-{member['name']}",
                ffmc=float(metadata["ffmc"]),
                bui=float(metadata["bui"]),
                duration_min=float(metadata["duration_min"]),
                initial_mask=start,
                containment_mask=barrier,
                wet_depth_mm=depth,
                wet_start_min=drop_time,
                wet_decay_min=60.0,
                wet_required_mm=0.75,
                snapshot_interval_min=60.0,
                neighbor_radius=2,
            )
            ignition = result.growth.ignition_time_min
            east = int(np.count_nonzero(np.isfinite(ignition[:, barrier_col + 1 :])))
            rows.append(
                {
                    "case": metadata["case_id"],
                    "member": member["name"],
                    "drop_time_min": drop_time,
                    "barrier_col": barrier_col,
                    "gap_mean_depth_mm": gap_mean_depth,
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
            )

    payload = {
        "proof": "P208 single drop-depth pilot",
        "case_id": metadata["case_id"],
        "fixture": str(fixture),
        "barrier": {
            "column": barrier_col,
            "gap_center_row": gap_center_row,
            "gap_cells": 5,
            "drop_times_min": drop_times,
            "placement": "oracle-assisted: 60% from mean start column to eastern observed extent",
        },
        "drops": {
            "drops_per_cell": 2,
            "volume_l": 6000.0,
            "length_m": 100.0,
            "width_m": 50.0,
            "decay_min": 60.0,
            "required_depth_mm": 0.75,
        },
        "rows": rows,
        "limitations": [
            "Cell-center ellipse sampling, not a surveyed drop contour.",
            "Two drops per gap cell, no overlap/dispatch sequence.",
            "No tanker, helicopter, refill or queue model.",
            "Synthetic, oracle-assisted barrier geometry.",
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
            f"drop={row['drop_time_min']:>6.0f} {row['member']:<9} "
            f"area={row['area_sim_ha']:.0f} east={row['east_of_barrier_burned_cells']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
