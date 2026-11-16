"""Preview an explicit treatment prescription on open BC VRI stands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ws4.fire.prescription import (
    apply_stand_prescription,
    prescription_from_ffs,
    stand_from_vri_feature,
)


def main() -> None:
    """Read a VRI GeoJSON file, apply a prescription, and write JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--treatment",
        choices=("thin-only", "burn-only", "thin-burn"),
        required=True,
    )
    parser.add_argument("--fuel-type", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("input has no feature list")
    stands = [stand for feature in features if (stand := stand_from_vri_feature(feature))]
    prescription = prescription_from_ffs(args.treatment, fuel_type=args.fuel_type)
    rows = [apply_stand_prescription(stand, prescription).to_dict() for stand in stands]
    result = {
        "source": "BC VRI 2025 Rank 1, Open Government Licence - British Columbia",
        "treatment": args.treatment,
        "post_fuel_type": prescription.fuel_type,
        "stand_count": len(rows),
        "stands": rows,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
