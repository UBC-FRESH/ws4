"""Run the P164.8 training-only regime calibration on a potential sample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.fire.regime_calibration import (  # noqa: E402
    gate_results,
    load_potential_records,
    search_training,
    validate,
)


def run(
    potential: Path,
    *,
    output: Path,
    seed: int,
    candidates: int,
    validation: Path | None = None,
) -> dict[str, object]:
    """Search the training sample and optionally evaluate a frozen validation sample.

    Parameters
    ----------
    potential : Path
        Training potential-record JSON.
    output : Path
        Output JSON destination.
    seed : int
        Fixed search seed.
    candidates : int
        Number of pre-registered candidates.
    validation : Path or None, optional
        Validation potential-record JSON.

    Returns
    -------
    dict
        Training result and optional validation metrics.
    """
    records = load_potential_records(potential)
    result = search_training(records, seed=seed, count=candidates)
    payload: dict[str, object] = {
        "protocol": "P164.8",
        "seed": seed,
        "candidates": candidates,
        "training": result.to_dict(),
    }
    if validation is not None:
        metrics = validate(result.parameters, load_potential_records(validation), seed=seed + 1)
        payload["validation"] = {
            "metrics": metrics.to_dict(),
            "gates": gate_results(metrics),
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    """Run the calibration CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--potential", type=Path, required=True)
    parser.add_argument("--validation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--candidates", type=int, default=1_500)
    args = parser.parse_args()
    payload = run(
        args.potential,
        output=args.output,
        seed=args.seed,
        candidates=args.candidates,
        validation=args.validation,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
