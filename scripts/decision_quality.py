"""Compute decision-quality metrics from a long CSV matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from ws4.opt.decision_quality import evaluate_decisions


def main() -> None:
    """Read a decision matrix, evaluate it, and write artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--decision", default="decision")
    parser.add_argument("--scenario", default="scenario")
    parser.add_argument("--outcome", default="outcome")
    parser.add_argument("--feasible", default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.input)
    report = evaluate_decisions(
        frame,
        decision=args.decision,
        scenario=args.scenario,
        outcome=args.outcome,
        feasible=args.feasible,
    )
    report.write(args.output)
    print(json.dumps(report.summary(), indent=2))


if __name__ == "__main__":
    main()
