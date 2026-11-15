"""P226: source queue and refill feasibility for gap re-wetting."""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class QueueResult:
    """One source-queue simulation result."""

    aircraft: int
    sources: int
    refill_l_min: float
    applications: int
    interval_min: float
    cycle_min: float
    payload_l: float
    max_cell_gap_min: float
    max_end_lateness_min: float
    max_source_wait_min: float
    feasible: bool

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-serializable mapping."""
        return {
            "aircraft": self.aircraft,
            "sources": self.sources,
            "refill_l_min": self.refill_l_min,
            "applications": self.applications,
            "interval_min": self.interval_min,
            "cycle_min": self.cycle_min,
            "payload_l": self.payload_l,
            "max_cell_gap_min": self.max_cell_gap_min,
            "max_end_lateness_min": self.max_end_lateness_min,
            "max_source_wait_min": self.max_source_wait_min,
            "feasible": self.feasible,
        }


def simulate(
    *,
    aircraft: int = 3,
    sources: int = 1,
    refill_l_min: float,
    applications: int = 8,
    interval_min: float = 15.0,
    cycle_min: float = 4.25,
    cells: int = 5,
    drops_per_cell: int = 2,
    payload_l: float = 6000.0,
) -> QueueResult:
    """Simulate drops and refill at one or more sources.

    Parameters
    ----------
    aircraft : int, optional
        Number of aircraft (default 3).
    sources : int, optional
        Number of water sources (default 1).
    refill_l_min : float
        Refill rate per source.
    applications : int, optional
        Number of applications (default 8).
    interval_min : float, optional
        Target interval (default 15).
    cycle_min : float, optional
        Total aircraft cycle (default 4.25).
    cells : int, optional
        Gap cells (default 5).
    drops_per_cell : int, optional
        Drops per cell (default 2).
    payload_l : float, optional
        Litres per sortie (default 6000).

    Returns
    -------
    QueueResult
        Queue and wetness-gap metrics.
    """
    service_min = payload_l / refill_l_min
    travel_min = max(0.0, cycle_min - service_min)
    aircraft_ready = [0.0] * aircraft
    source_free = [0.0] * sources
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
                source_index = min(range(sources), key=lambda item: source_free[item])
                source_arrival = start + travel_min
                service_start = max(source_arrival, source_free[source_index])
                max_source_wait = max(max_source_wait, service_start - source_arrival)
                source_free[source_index] = service_start + service_min
                aircraft_ready[index] = source_free[source_index]
        application_ends.append(max(app_times))
    max_gap = max(
        max(b - a for a, b in itertools.pairwise(sorted(times)))
        for times in cell_times.values()
    )
    end_lateness = max(
        application_ends[index] - (index * interval_min + interval_min)
        for index in range(applications)
    )
    return QueueResult(
        aircraft=aircraft,
        sources=sources,
        refill_l_min=refill_l_min,
        applications=applications,
        interval_min=interval_min,
        cycle_min=cycle_min,
        payload_l=payload_l,
        max_cell_gap_min=max_gap,
        max_end_lateness_min=end_lateness,
        max_source_wait_min=max_source_wait,
        feasible=max_gap <= interval_min + 1e-9 and end_lateness <= 1e-9,
    )


def main() -> None:
    """Run source-queue cases and print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refill-l-min", default="4235.294,5000,6000")
    parser.add_argument("--applications", type=int, default=8)
    parser.add_argument("--sources", default="1")
    args = parser.parse_args()
    rates = [float(value) for value in args.refill_l_min.split(",") if value]
    sources = [int(value) for value in args.sources.split(",") if value]
    cases = [
        simulate(
            refill_l_min=rate,
            sources=count,
            applications=args.applications,
        ).to_dict()
        for count in sources
        for rate in rates
    ]
    print(json.dumps(cases, indent=2))


if __name__ == "__main__":
    main()
