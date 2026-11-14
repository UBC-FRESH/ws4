"""P205: crew line-construction rate pilot on 2003_96."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ws4.fire.comparison import DogribCase

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def build_construction_schedule(
    *,
    rows: int,
    cols: int,
    barrier_col: int,
    cell_size_m: float,
    rate_m_h: float,
    start_row: int = 0,
) -> np.ndarray:
    """Return closure times for a crew building from ``start_row`` at ``rate_m_h``.

    Parameters
    ----------
    rows, cols : int
        Grid shape.
    barrier_col : int
        Column occupied by the constructed line.
    cell_size_m : float
        Cell size in metres.
    rate_m_h : float
        Construction rate in metres per hour.
    start_row : int, optional
        Row where construction starts (default 0).

    Returns
    -------
    numpy.ndarray
        Per-cell closure times; infinity off the barrier.
    """
    if not 0 <= barrier_col < cols:
        raise ValueError("barrier_col must be inside the grid")
    if rate_m_h <= 0.0:
        raise ValueError("rate_m_h must be positive")
    if not 0 <= start_row < rows:
        raise ValueError("start_row must be inside the grid")
    speed_m_min = rate_m_h / 60.0
    closure = np.full((rows, cols), np.inf, dtype=float)
    for row in range(rows):
        distance_m = abs(row - start_row) * cell_size_m
        closure[row, barrier_col] = distance_m / speed_m_min
    return closure


def main() -> None:
    """Run the line-construction pilot and write JSON and CSV artifacts."""
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
        default=ROOT / "notes/reports/p205-line-construction.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes/reports/p205-line-construction.csv",
    )
    parser.add_argument("--rates", default="20,40,80")
    args = parser.parse_args()
    fixture = args.fixture or args.ws4_root / "tests/fixtures/fire/large_2003_96"
    sys.path.insert(0, str(args.ws4_root))
    sys.path.insert(0, str(SCRIPTS))

    from ws4.fire.comparison import observed_mask, run_observed_case
    from ws4.fire.observed import load_cfsds_reanalysis_case

    from run_firebreak_gap_2003_96 import _oracle_barrier_column
    from run_freeburn_ensemble import MEMBERS, _time_to_observed_area, _weather_member

    fire = load_cfsds_reanalysis_case(fixture)
    metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
    start = observed_mask(fire, 0)
    observed = observed_mask(fire, -1)
    barrier_col = _oracle_barrier_column(start, observed)
    rates = [float(value) for value in args.rates.split(",") if value]

    rows: list[dict[str, object]] = []
    for rate in rates:
        closure = build_construction_schedule(
            rows=fire.grid.nrows,
            cols=fire.grid.ncols,
            barrier_col=barrier_col,
            cell_size_m=fire.grid.cell_size_m,
            rate_m_h=rate,
        )
        for member in MEMBERS:
            perturbed = _weather_member(
                fire,
                wind_scale=float(member["wind_scale"]),
                rh_offset=float(member["rh_offset"]),
            )
            result: DogribCase = run_observed_case(
                perturbed,
                scenario=f"line-{rate:g}-{member['name']}",
                ffmc=float(metadata["ffmc"]),
                bui=float(metadata["bui"]),
                duration_min=float(metadata["duration_min"]),
                initial_mask=start,
                containment_start_min=closure,
                snapshot_interval_min=60.0,
                neighbor_radius=2,
            )
            ignition = result.growth.ignition_time_min
            east = int(np.count_nonzero(np.isfinite(ignition[:, barrier_col + 1 :])))
            rows.append(
                {
                    "case": metadata["case_id"],
                    "member": member["name"],
                    "wind_scale": member["wind_scale"],
                    "rh_offset": member["rh_offset"],
                    "rate_m_h": rate,
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
            )

    payload = {
        "proof": "P205 crew line-construction rate",
        "case_id": metadata["case_id"],
        "fixture": str(fixture),
        "barrier": {
            "column": barrier_col,
            "start_row": 0,
            "rates_m_h": rates,
            "placement": "oracle-assisted: 60% from mean start column to eastern observed extent",
        },
        "rows": rows,
        "limitations": [
            "Synthetic barrier geometry and construction schedule.",
            "No pumps, hose lays, water or crew fatigue.",
            "Construction starts at row 0 and proceeds monotonically.",
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
            f"rate={row['rate_m_h']:>4.0f} {row['member']:<9} "
            f"area={row['area_sim_ha']:.0f} east={row['east_of_barrier_burned_cells']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
