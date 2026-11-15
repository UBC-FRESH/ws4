"""P222: gap-only round-robin dispatch feasibility."""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DropTask:
    """One drop assignment.

    Attributes
    ----------
    application : int
        Application index.
    cell : int
        Target gap cell.
    stack : int
        Drop stack on the cell.
    start_min : float
        Actual drop start time.
    """

    application: int
    cell: int
    stack: int
    start_min: float


def simulate_queue(
    *,
    aircraft: int,
    applications: int = 8,
    interval_min: float = 15.0,
    cycle_min: float = 4.25,
    cells: int = 5,
    drops_per_cell: int = 2,
) -> dict[str, object]:
    """Assign drops to the earliest available aircraft.

    Parameters
    ----------
    aircraft : int
        Number of identical aircraft.
    applications : int, optional
        Number of re-wetting applications (default 8).
    interval_min : float, optional
        Target interval between applications (default 15).
    cycle_min : float, optional
        Mean aircraft cycle (default 4.25).
    cells : int, optional
        Number of gap cells (default 5).
    drops_per_cell : int, optional
        Drops per cell per application (default 2).

    Returns
    -------
    dict
        Lateness, cell wet-event gaps and assignment rows.
    """
    if aircraft < 1 or applications < 1 or cells < 1:
        raise ValueError("aircraft, applications and cells must be positive")
    available = [0.0] * aircraft
    tasks: list[DropTask] = []
    application_ends: list[float] = []
    cell_times: dict[int, list[float]] = {cell: [] for cell in range(cells)}
    for application in range(applications):
        scheduled = application * interval_min
        app_times: list[float] = []
        # Interleave cells so every cell gets its first drop before the
        # second stack is placed.
        for stack in range(drops_per_cell):
            for cell in range(cells):
                index = min(range(aircraft), key=lambda item: available[item])
                start = max(scheduled, available[index])
                available[index] = start + cycle_min
                tasks.append(DropTask(application, cell, stack, start))
                cell_times[cell].append(start)
                app_times.append(start)
        application_ends.append(max(app_times))
    max_gap = 0.0
    for times in cell_times.values():
        ordered = sorted(times)
        max_gap = max(max_gap, max(b - a for a, b in itertools.pairwise(ordered)))
    start_lateness = [
        min(task.start_min for task in tasks if task.application == index) - index * interval_min
        for index in range(applications)
    ]
    end_lateness = [
        application_ends[index] - (index * interval_min + interval_min)
        for index in range(applications)
    ]
    return {
        "aircraft": aircraft,
        "applications": applications,
        "interval_min": interval_min,
        "cycle_min": cycle_min,
        "cells": cells,
        "drops_per_cell": drops_per_cell,
        "max_cell_gap_min": max_gap,
        "max_start_lateness_min": max(start_lateness),
        "max_end_lateness_min": max(end_lateness),
        "sustains_interval": max_gap <= interval_min + 1e-9,
        "feasible": max_gap <= interval_min + 1e-9 and max(end_lateness) <= 1e-9,
        "tasks": [asdict(task) for task in tasks],
    }


def main() -> None:
    """Run the queue simulation for several aircraft counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aircraft", default="3,4,5")
    parser.add_argument("--applications", type=int, default=8)
    parser.add_argument("--interval-min", type=float, default=15.0)
    parser.add_argument("--cycle-min", type=float, default=4.25)
    args = parser.parse_args()
    counts = [int(value) for value in args.aircraft.split(",") if value]
    results = {
        str(count): simulate_queue(
            aircraft=count,
            applications=args.applications,
            interval_min=args.interval_min,
            cycle_min=args.cycle_min,
        )
        for count in counts
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
