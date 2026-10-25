#!/usr/bin/env python3
"""Measure cached route events against the full route simulation.

Opt-in measurement: loads a compiled dataset, production route config, targets, and a
run's schedule; reports full, cold-cache, and warm-cache evaluation times plus a cell-by-
cell parity check.
"""

from __future__ import annotations

import argparse
import json
import time
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
        chains.setdefault(int(str(row.block_id)), []).append(
            (str(row.treatment), int(str(row.offset)))
        )
    return {
        block: tuple(sorted(events, key=lambda event: event[1])) for block, events in chains.items()
    }


def _parity(left: pd.DataFrame, right: pd.DataFrame) -> float:
    """Return the largest absolute cell difference between two value frames."""
    joined = (
        left.set_index(["offset", "account"])["value"]
        .to_frame("left")
        .join(right.set_index(["offset", "account"])["value"].to_frame("right"), how="outer")
        .fillna(0.0)
    )
    return float((joined["left"] - joined["right"]).abs().max())


def benchmark(
    *,
    dataset: Path,
    targets: Path,
    route_config: Path,
    schedule: Path,
    years: int,
    repeats: int,
) -> dict[str, object]:  # pragma: no cover - opt-in benchmark
    """Return full/cached timings and parity for one dataset and schedule.

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
        Number of warm evaluations.

    Returns
    -------
    dict of str to object
        Counts, timings, and the largest parity difference.
    """
    chains = load_schedule(schedule)
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
    model, route_accounts, duplicates = optimizer.route()
    if model is None:
        raise ValueError("the route config did not load a route model")

    cold_start = time.perf_counter()
    incremental = optimizer._incremental_values(chains, duplicates, route_accounts)
    cold_seconds = time.perf_counter() - cold_start

    warm_start = time.perf_counter()
    for _ in range(repeats):
        optimizer._incremental_values(chains, duplicates, route_accounts)
    warm_seconds = (time.perf_counter() - warm_start) / repeats

    full_start = time.perf_counter()
    full = optimizer._full_values(chains, model, route_accounts, duplicates)
    full_seconds = time.perf_counter() - full_start

    event_count = sum(
        len(optimizer._block_route_events(block, chain)) for block, chain in chains.items()
    )
    return {
        "dataset": str(dataset),
        "route_config": str(route_config),
        "schedule": str(schedule),
        "blocks": len(chains),
        "events": event_count,
        "route_accounts": len(route_accounts),
        "years": years,
        "full_seconds": round(full_seconds, 6),
        "cold_seconds": round(cold_seconds, 6),
        "warm_seconds": round(warm_seconds, 6),
        "cold_speedup": round(full_seconds / cold_seconds, 2) if cold_seconds else None,
        "warm_speedup": round(full_seconds / warm_seconds, 2) if warm_seconds else None,
        "max_cell_difference": _parity(incremental, full),
    }


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - opt-in benchmark
    """Run the route-event benchmark from the command line.

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
    report = benchmark(
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
