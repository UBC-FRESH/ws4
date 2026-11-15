"""P227: seeded source-queue variability envelope."""

from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class Sample:
    """One source-queue sample."""

    refill_l_min: float
    seed: int
    max_cell_gap_min: float
    max_end_lateness_min: float
    max_source_wait_min: float
    feasible: bool


def simulate_sample(
    *,
    refill_l_min: float,
    seed: int,
    aircraft: int = 3,
    applications: int = 8,
    interval_min: float = 15.0,
    cycle_min: float = 4.25,
    cells: int = 5,
    drops_per_cell: int = 2,
    payload_l: float = 6000.0,
    service_jitter: float = 0.10,
    cycle_jitter: float = 0.05,
) -> Sample:
    """Run one seeded source-queue sample.

    Parameters
    ----------
    refill_l_min : float
        Nominal refill rate.
    seed : int
        Random seed.
    aircraft : int, optional
        Number of aircraft (default 3).
    applications : int, optional
        Applications (default 8).
    interval_min : float, optional
        Target interval (default 15).
    cycle_min : float, optional
        Nominal total cycle (default 4.25).
    cells : int, optional
        Gap cells (default 5).
    drops_per_cell : int, optional
        Drops per cell (default 2).
    payload_l : float, optional
        Litres per sortie (default 6000).
    service_jitter : float, optional
        Fractional service-time jitter (default 0.10).
    cycle_jitter : float, optional
        Fractional cycle jitter (default 0.05).

    Returns
    -------
    Sample
        Queue metrics and feasibility.
    """
    rng = random.Random(seed)
    source_free = 0.0
    aircraft_ready = [0.0] * aircraft
    cell_times = {cell: [] for cell in range(cells)}
    application_ends: list[float] = []
    max_source_wait = 0.0
    for application in range(applications):
        scheduled = application * interval_min
        app_times: list[float] = []
        for _stack in range(drops_per_cell):
            for cell in range(cells):
                index = min(range(aircraft), key=lambda item: aircraft_ready[item])
                start = max(scheduled, aircraft_ready[index])
                app_times.append(start)
                cell_times[cell].append(start)
                service = (payload_l / refill_l_min) * (
                    1.0 + rng.uniform(-service_jitter, service_jitter)
                )
                cycle = cycle_min * (1.0 + rng.uniform(-cycle_jitter, cycle_jitter))
                travel = max(0.0, cycle - service)
                arrival = start + travel
                service_start = max(arrival, source_free)
                max_source_wait = max(max_source_wait, service_start - arrival)
                source_free = service_start + service
                aircraft_ready[index] = source_free
        application_ends.append(max(app_times))
    max_gap = max(
        max(b - a for a, b in itertools.pairwise(sorted(times)))
        for times in cell_times.values()
    )
    lateness = max(
        application_ends[index] - (index * interval_min + interval_min)
        for index in range(applications)
    )
    return Sample(
        refill_l_min=refill_l_min,
        seed=seed,
        max_cell_gap_min=max_gap,
        max_end_lateness_min=lateness,
        max_source_wait_min=max_source_wait,
        feasible=max_gap <= interval_min + 1e-9 and lateness <= 1e-9,
    )


def percentile(values: list[float], fraction: float) -> float:
    """Return a simple nearest-rank percentile.

    Parameters
    ----------
    values : list of float
        Sample values.
    fraction : float
        Percentile in [0, 1].

    Returns
    -------
    float
        Percentile value.
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be in [0, 1]")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def aggregate(samples: list[Sample]) -> dict[str, float]:
    """Aggregate one source rate.

    Parameters
    ----------
    samples : list of Sample
        Samples for one rate.

    Returns
    -------
    dict
        Feasible fraction and p95 metrics.
    """
    gaps = [sample.max_cell_gap_min for sample in samples]
    lateness = [sample.max_end_lateness_min for sample in samples]
    waits = [sample.max_source_wait_min for sample in samples]
    return {
        "samples": len(samples),
        "feasible_fraction": sum(sample.feasible for sample in samples) / len(samples),
        "p95_cell_gap_min": percentile(gaps, 0.95),
        "p95_end_lateness_min": percentile(lateness, 0.95),
        "p95_source_wait_min": percentile(waits, 0.95),
        "mean_source_wait_min": mean(waits),
    }


def main() -> None:
    """Run the variability envelope and print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refill-l-min", default="3500,4235.294,5000,6000")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=227)
    args = parser.parse_args()
    rates = [float(value) for value in args.refill_l_min.split(",") if value]
    result = {}
    for rate_index, rate in enumerate(rates):
        samples = [
            simulate_sample(refill_l_min=rate, seed=args.seed + rate_index * 1000 + index)
            for index in range(args.samples)
        ]
        result[str(rate)] = aggregate(samples)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
