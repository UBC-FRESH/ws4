#!/usr/bin/env python3
"""Compare two carbon run directories for parity.

Usage::

    python scripts/carbon_parity.py --left out/ws3 --right out/ws4 --out parity.md

The two runs must write ``carbon_pools.csv`` and ``carbon_flux.csv`` in the WS4 carbon
format. The script compares the numeric columns on ``(timestep, identifier)`` and exits
nonzero when a table is outside the requested tolerance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if TYPE_CHECKING:
    from ws4.carbon.parity import FrameComparison


def _parse_args() -> argparse.Namespace:
    """Parse the command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True, help="Left carbon run")
    parser.add_argument("--right", type=Path, required=True, help="Right carbon run")
    parser.add_argument("--atol", type=float, default=1e-6, help="Absolute tolerance")
    parser.add_argument("--rtol", type=float, default=1e-6, help="Relative tolerance")
    parser.add_argument("--out", type=Path, default=None, help="Optional report path")
    return parser.parse_args()


def _compare(name: str, left: Path, right: Path, args: argparse.Namespace) -> FrameComparison:
    """Compare one table pair."""
    from ws4.carbon.parity import compare_frames

    left_frame = pd.read_csv(left / name)
    right_frame = pd.read_csv(right / name)
    return compare_frames(left_frame, right_frame, atol=args.atol, rtol=args.rtol)


def main() -> int:
    """Run the comparison and write the report.

    Returns
    -------
    int
        Zero when both tables pass, one otherwise.
    """
    args = _parse_args()
    left = args.left
    right = args.right
    pools = _compare("carbon_pools.csv", left, right, args)
    flux = _compare("carbon_flux.csv", left, right, args)
    report = {
        "left": str(left),
        "right": str(right),
        "atol": args.atol,
        "rtol": args.rtol,
        "pools": pools.__dict__,
        "flux": flux.__dict__,
        "ok": bool(pools.ok and flux.ok),
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
