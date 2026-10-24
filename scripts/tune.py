#!/usr/bin/env python3
"""Tune a small optimizer parameter space with grid or random search.

Every candidate runs the existing optimizer on the same dataset, targets, seeds, and
iteration budget. The report ranks candidates by best and median objective and names
the winner. The result is advisory: it compares a finite budget on a stochastic search.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ws4.opt.tune import run_tuning


def _seeds(text: str) -> list[int]:
    """Parse a comma list of integer seeds."""
    values = [int(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise ValueError("expected at least one seed")
    return values


def main(argv: list[str] | None = None) -> int:
    """Run the tuner from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when at least one candidate ran, and ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--space", type=Path, required=True, help="JSON field -> values")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", default="grid", choices=("grid", "random"))
    parser.add_argument("--budget", type=int, default=16)
    parser.add_argument("--seeds", default="1")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--years", type=int, default=50)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--max-candidates", type=int, default=64)
    args = parser.parse_args(argv)
    raw = json.loads(args.space.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("the parameter space must be a JSON object")
    report = run_tuning(
        dataset=args.dataset,
        targets=args.targets,
        out_dir=args.out,
        space=raw,
        mode=args.mode,
        budget=args.budget,
        seeds=_seeds(args.seeds),
        iterations=args.iterations,
        years=args.years,
        threads=args.threads,
        random_seed=args.random_seed,
        max_candidates=args.max_candidates,
    )
    print(str(report["markdown"]))
    print(json.dumps({"winner": report["winner"], "failures": report["failures"]}, indent=2))
    return 0 if report["winner"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
