"""Extract measured FFS treatment effects from open data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from ws4.fire.treatment_effects import pair_pre_post, summarize_effects, surface_fuel_total


def main() -> None:
    """Read FFS tables, summarize effects, and write JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vegetation", type=Path, required=True)
    parser.add_argument("--trees", type=Path, required=True)
    parser.add_argument("--fuels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    vegetation = pd.read_csv(args.vegetation, low_memory=False)
    trees = pd.read_csv(args.trees, low_memory=False)
    fuels = pd.read_csv(args.fuels, low_memory=False)
    fuels["SURFACE_FUEL_TOTAL"] = surface_fuel_total(fuels)
    metrics = {
        "canopy_cover_pct_change": summarize_effects(
            pair_pre_post(vegetation, "CANOPY_COVER_VERT_PROJECTION")
        ),
        "live_basal_area_pct_change": summarize_effects(
            pair_pre_post(trees, "LIVE_TREE_BASAL_AREA")
        ),
        "surface_fuel_pct_change": summarize_effects(pair_pre_post(fuels, "SURFACE_FUEL_TOTAL")),
    }
    payload = {
        "dataset": "National Fire and Fire Surrogate study, RDS-2016-0009",
        "archive_sha256": "6a31b026ff6f7248556eab4ba2e4f6694f75e6f769f5d1c53378c679e73321ff",
        "method": "pre (-1) and first post (1) treatment unit values; percent change",
        "metrics": {name: frame.to_dict(orient="records") for name, frame in metrics.items()},
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
