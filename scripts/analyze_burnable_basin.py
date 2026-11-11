"""Compare simulated and observed area with the connected burnable basin."""

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


def _load_reports(paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Load per-case rows from report JSON files."""
    cases: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("cases", []):
            cases[str(row["case"])] = row
    return cases


def main() -> None:
    """Compute basin fractions and write the diagnostic."""
    import pandas as pd
    from ws4.fire.observed import load_cfsds_reanalysis_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, nargs="+", required=True)
    parser.add_argument("--reports", type=Path, nargs="*", default=[])
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p176-burnable-basin.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p176-burnable-basin.csv",
    )
    args = parser.parse_args()
    reports = _load_reports(args.reports)
    rows: list[dict[str, Any]] = []
    for fixture in args.fixtures:
        metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
        fire = load_cfsds_reanalysis_case(fixture)
        fuel = fire.fbp_fuel_grid()
        burnable_cells = sum(value is not None for value in fuel.ravel())
        burnable_ha = burnable_cells * fire.grid.cell_size_m**2 / 10_000.0
        observed_ha = float(metadata["daily_cumuarea_ha"][-1])
        report = reports.get(fire.fire_id, {})
        simulated_ha = report.get("area_sim_ha")
        rows.append(
            {
                "case": fire.fire_id,
                "cell_size_m": fire.grid.cell_size_m,
                "burnable_ha": burnable_ha,
                "observed_ha": observed_ha,
                "simulated_ha": simulated_ha,
                "sim_burnable": None if simulated_ha is None else simulated_ha / burnable_ha,
                "observed_burnable": observed_ha / burnable_ha,
            }
        )
    sim_ratios = [float(row["sim_burnable"]) for row in rows if row["sim_burnable"] is not None]
    obs_ratios = [float(row["observed_burnable"]) for row in rows]
    payload = {
        "summary": {
            "case_count": len(rows),
            "median_sim_burnable": statistics.median(sim_ratios) if sim_ratios else None,
            "median_observed_burnable": statistics.median(obs_ratios),
            "cases_sim_over_95pct_basin": sum(value >= 0.95 for value in sim_ratios),
            "cases_observed_under_50pct_basin": sum(value <= 0.5 for value in obs_ratios),
        },
        "rows": rows,
        "interpretation": (
            "When simulated area approaches burnable area while observed area is much smaller, "
            "the model lacks a stopping/containment mechanism."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(args.csv, index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
