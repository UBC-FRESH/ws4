#!/usr/bin/env python3
"""Compare completed ws4 runs over the same landscape.

Each ``--run label=path`` names a run directory. The report compares the objective, targets,
accounts, and constraint status, and can add a Pareto front over named metrics. The command
is read-only and reports missing artefacts as unavailable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ws4.opt.scenarios import compare_scenarios, parse_metric, parse_run_spec


def main(argv: list[str] | None = None) -> int:
    """Run the comparison from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when the report was written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        help="label=path to a completed run directory; repeat for each run",
    )
    parser.add_argument(
        "--metric",
        action="append",
        default=[],
        help="account[:min|max] for the Pareto front; repeat for more metrics",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    runs = [parse_run_spec(value) for value in args.run]
    metrics = dict(parse_metric(value) for value in args.metric)
    report = compare_scenarios(runs, args.out, metrics=metrics)
    print(str(report["markdown"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
