#!/usr/bin/env python3
"""Run a target-weight portfolio and write a Pareto front.

The portfolio varies one or more targets' minimum and maximum weights, runs the
existing optimizer for every vector and seed, and reports the members that are not
dominated on the declared metrics. It is a finite, budgeted sample: advisory, not a
certified optimum.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ws4.opt.portfolio import parse_directions, parse_vary, run_portfolio


def _seeds(text: str) -> list[int]:
    """Parse a comma list of integer seeds."""
    values = [int(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise ValueError("expected at least one seed")
    return values


def _metrics(text: str | None, vary: dict[str, tuple[float, ...]]) -> list[str]:
    """Return the requested metrics, defaulting to the varied accounts."""
    if text:
        values = [item.strip() for item in text.split(",") if item.strip()]
        if not values:
            raise ValueError("expected at least one metric")
        return values
    return sorted({key.split("@", 1)[0] for key in vary})


def main(argv: list[str] | None = None) -> int:
    """Run the portfolio from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when every member ran, and ``1`` when a member failed.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--vary",
        required=True,
        help="account=factor,factor; a second group is separated by ';'",
    )
    parser.add_argument("--metrics", default=None, help="comma list; default: varied accounts")
    parser.add_argument("--directions", default=None, help="metric=min|max; separated by ';'")
    parser.add_argument("--seeds", default="1")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--years", type=int, default=50)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--engine", default="sa", choices=("sa", "tabu", "ils", "threshold"))
    parser.add_argument("--archive-size", type=int, default=20)
    parser.add_argument("--max-members", type=int, default=64)
    args = parser.parse_args(argv)
    vary = parse_vary(args.vary)
    metrics = _metrics(args.metrics, vary)
    directions = parse_directions(args.directions, metrics) if args.directions else None
    report = run_portfolio(
        dataset=args.dataset,
        targets=args.targets,
        out_dir=args.out,
        vary=vary,
        metrics=metrics,
        seeds=_seeds(args.seeds),
        iterations=args.iterations,
        years=args.years,
        threads=args.threads,
        metaheuristic=args.engine,
        directions=directions,
        archive_size=args.archive_size,
        max_members=args.max_members,
    )
    print(str(report["markdown"]))
    print(json.dumps({"front": report["front"], "failures": report["failures"]}, indent=2))
    return 0 if report["failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
