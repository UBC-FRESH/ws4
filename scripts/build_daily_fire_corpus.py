"""Build the daily CFSDS breadth corpus and integrity manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from ws4.fire.daily_corpus import DailyCase


def _row(case: DailyCase) -> dict[str, object]:
    """Return one flat daily-case row.

    Parameters
    ----------
    case : DailyCase
        Corpus case.

    Returns
    -------
    dict
        Flat row.
    """
    return case.to_dict()


def main() -> None:
    """Build the corpus, write artifacts, and print the gate."""
    import pandas as pd
    from ws4.fire.daily_corpus import build_daily_corpus, daily_manifest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--years", default="2003,2009,2023")
    parser.add_argument("--quotas", default="7,6,7")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p165-daily-corpus.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p165-daily-corpus.csv",
    )
    args = parser.parse_args()
    years = tuple(int(value) for value in str(args.years).split(","))
    quotas = tuple(int(value) for value in str(args.quotas).split(","))
    cases, candidate_count, rejected_count = build_daily_corpus(
        args.data_root, years=years, quotas=quotas
    )
    data = daily_manifest(cases, candidate_count, rejected_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame([_row(case) for case in cases]).to_csv(args.csv, index=False)
    gate = data["gate"]
    if not isinstance(gate, dict):
        raise TypeError("gate must be a mapping")
    print(
        pd.DataFrame([_row(case) for case in cases])[
            ["case_id", "year", "days", "final_area_ha", "area_relative_error", "ecozone"]
        ].to_string(index=False)
    )
    print(json.dumps(gate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
