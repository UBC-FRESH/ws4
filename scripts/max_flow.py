#!/usr/bin/env python3
"""Binary-search the highest feasible constant flow floor.

The command replaces the volume account's targets with a constant per-period minimum,
then probes the existing optimizer at each level. A probe passes when every period meets
the level within a relative tolerance and the run reports no spatial violations. The
result is the highest verified level, its schedule, and the probe log.

The ceiling is advisory: the high bound is an additive envelope over block options and
each probe is a finite search, so this is not a certified maximum.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ws4.opt.max_flow import run_max_flow


def main(argv: list[str] | None = None) -> int:
    """Run the flow-ceiling search from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when the report was written, including the advisory zero-ceiling case.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--years", type=int, default=100)
    parser.add_argument("--period-width", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--engine", default="sa", choices=("sa", "tabu", "ils", "threshold"))
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--probes", type=int, default=8)
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--high", type=float, default=None)
    parser.add_argument("--topology", type=Path, default=None)
    parser.add_argument("--max-opening-ha", type=float, default=None)
    parser.add_argument("--min-green-up-years", type=int, default=None)
    parser.add_argument("--core-buffer-m", type=float, default=None)
    parser.add_argument("--min-core-area-ha", type=float, default=None)
    parser.add_argument(
        "--constraint-strategy",
        default="reject",
        choices=("penalize", "reject", "repair"),
    )
    parser.add_argument(
        "--flow",
        default="",
        choices=("", "ndy", "even"),
        help="Also require non-declining or even flow in every probe",
    )
    parser.add_argument(
        "--flow-tolerance",
        type=float,
        default=0.0,
        help="Allowed percent change for the flow condition",
    )
    args = parser.parse_args(argv)
    report = run_max_flow(
        dataset=args.dataset,
        targets=args.targets,
        account=args.account,
        out_dir=args.out,
        years=args.years,
        period_width=args.period_width,
        iterations=args.iterations,
        seed=args.seed,
        metaheuristic=args.engine,
        threads=args.threads,
        probes=args.probes,
        tolerance=args.tolerance,
        high=args.high,
        topology=args.topology,
        max_opening_ha=args.max_opening_ha,
        min_green_up_years=args.min_green_up_years,
        core_buffer_m=args.core_buffer_m,
        min_core_area_ha=args.min_core_area_ha,
        constraint_strategy=args.constraint_strategy,
        flow=args.flow,
        flow_tolerance=args.flow_tolerance,
    )
    print(str(report["markdown"]))
    print(
        json.dumps(
            {"ceiling": report["ceiling"], "feasible": report["feasible"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
