"""Build the public fire-corpus manifest and inventory CSV."""

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
    from ws4.fire.corpus import FireCase


def _row(case: FireCase) -> dict[str, object]:
    """Return one flat inventory row.

    Parameters
    ----------
    case : FireCase
        Corpus case.

    Returns
    -------
    dict
        Flat row with input flags and joined missing inputs.
    """
    data = case.to_dict()
    inputs = data.pop("inputs")
    if not isinstance(inputs, dict):
        raise TypeError("case inputs must be a mapping")
    missing = data.pop("missing_inputs")
    if not isinstance(missing, tuple):
        raise TypeError("case missing_inputs must be a tuple")
    return {
        "case_id": data["case_id"],
        "name": data["name"],
        "region": data["region"],
        "year": data["year"],
        "tier": data["tier"],
        "status": data["status"],
        "source": data["source"],
        "licence": data["licence"],
        **inputs,
        "missing_inputs": ",".join(str(item) for item in missing),
        "duplicate_of": data["duplicate_of"],
        "independent": data["independent"],
        "notes": data["notes"],
    }


def main() -> None:
    """Write the manifest JSON and inventory CSV."""
    import pandas as pd
    from ws4.fire.corpus import CASES, manifest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p165-corpus-manifest.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "notes" / "reports" / "p165-corpus-inventory.csv",
    )
    args = parser.parse_args()
    data = manifest(CASES)
    rows = [_row(case) for case in CASES]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(args.csv, index=False)
    gate = data["gate"]
    if not isinstance(gate, dict):
        raise TypeError("gate must be a mapping")
    print(
        pd.DataFrame(rows)[["case_id", "tier", "status", "missing_inputs"]].to_string(index=False)
    )
    print(json.dumps(gate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
