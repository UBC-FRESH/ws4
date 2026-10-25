#!/usr/bin/env python3
"""Profile a full route evaluation on a real schedule.

Opt-in: this is a measurement tool, not a CI gate. It loads the compiled dataset,
targets, route config, and a run's schedule, warms the optimizer, then profiles
repeated full value evaluations.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import pstats
from pathlib import Path

import pandas as pd
from ws4.opt.engine import OptimizeConfig, Optimizer


def load_schedule(path: Path) -> dict[int, tuple[tuple[str, int], ...]]:
    """Return a block -> treatment chain mapping from a run's schedule CSV.

    Parameters
    ----------
    path : Path
        The run's ``schedule.csv``.

    Returns
    -------
    dict of int to tuple of (str, int)
        The sorted treatment chains by block.
    """
    frame = pd.read_csv(path)
    chains: dict[int, list[tuple[str, int]]] = {}
    for row in frame.itertuples(index=False):
        block = int(str(row.block_id))
        chains.setdefault(block, []).append((str(row.treatment), int(str(row.offset))))
    return {
        block: tuple(sorted(events, key=lambda event: event[1])) for block, events in chains.items()
    }


def profile(
    *,
    dataset: Path,
    targets: Path,
    route_config: Path,
    schedule: Path,
    years: int,
    repeats: int,
) -> dict[str, object]:  # pragma: no cover - opt-in profiler
    """Return timing and the top cumulative functions for a full route evaluation.

    Parameters
    ----------
    dataset : Path
        Compiled dataset.
    targets : Path
        Targets YAML.
    route_config : Path
        Route configuration YAML.
    schedule : Path
        A run's schedule CSV.
    years : int
        Simulation horizon.
    repeats : int
        Number of profiled evaluations.

    Returns
    -------
    dict of str to object
        Timings, counts, and the top cumulative functions.
    """
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            targets_path=str(targets),
            route_config_path=str(route_config),
            years=years,
            iterations=1,
            seed=1,
        ),
    )
    chains = load_schedule(schedule)
    model, route_accounts, duplicates = optimizer.route()
    if model is None:
        raise ValueError("the route config did not load a route model")
    optimizer._full_values(chains, model, route_accounts, duplicates)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeats):
        optimizer._full_values(chains, model, route_accounts, duplicates)
    profiler.disable()
    stats = pstats.Stats(profiler)
    # pstats stubs omit these internal attributes.
    raw_stats = stats.stats  # type: ignore[attr-defined]
    total_tt = float(stats.total_tt)  # type: ignore[attr-defined]
    rows = [
        {"function": function, "cumulative": round(values[3], 6), "calls": values[1]}
        for function, values in raw_stats.items()
    ]
    rows.sort(key=lambda row: row["cumulative"], reverse=True)
    return {
        "dataset": str(dataset),
        "route_config": str(route_config),
        "schedule": str(schedule),
        "blocks": len(chains),
        "route_accounts": len(route_accounts),
        "repeats": repeats,
        "seconds": round(total_tt, 6),
        "seconds_per_eval": round(total_tt / repeats, 6),
        "top_cumulative": rows[:15],
    }


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - opt-in profiler
    """Run the route profile from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` after writing the report.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--route-config", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--years", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = profile(
        dataset=args.dataset,
        targets=args.targets,
        route_config=args.route_config,
        schedule=args.schedule,
        years=args.years,
        repeats=max(1, args.repeats),
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
