"""P225: source service-time utilization for gap re-wetting."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SourceService:
    """One source service-time calculation.

    Attributes
    ----------
    aircraft : int
        Number of aircraft.
    cycle_min : float
        Mean aircraft cycle in minutes.
    payload_l : float
        Litres per sortie.
    refill_l_min : float
        Refill rate per source.
    sources : int
        Number of identical sources.
    """

    aircraft: int
    cycle_min: float
    payload_l: float
    refill_l_min: float
    sources: int

    @property
    def service_min(self) -> float:
        """Source service time per sortie.

        Returns
        -------
        float
            Refill duration in minutes.
        """
        return self.payload_l / self.refill_l_min

    @property
    def utilization(self) -> float:
        """Fraction of source service capacity used.

        Returns
        -------
        float
            Aircraft demand divided by source service capacity.
        """
        return self.aircraft * self.service_min / (self.cycle_min * self.sources)

    @property
    def feasible(self) -> bool:
        """Whether source service can keep up.

        Returns
        -------
        bool
            True when utilization is at or below 1.
        """
        return self.utilization <= 1.0 + 1e-12

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-serializable mapping.

        Returns
        -------
        dict
            Service time, utilization and feasibility.
        """
        return {
            **asdict(self),
            "service_min": self.service_min,
            "utilization": self.utilization,
            "feasible": self.feasible,
        }


def minimum_refill_l_min(
    *,
    aircraft: int,
    cycle_min: float,
    payload_l: float,
    sources: int = 1,
) -> float:
    """Return the minimum refill rate per source.

    Parameters
    ----------
    aircraft : int
        Number of aircraft.
    cycle_min : float
        Mean aircraft cycle in minutes.
    payload_l : float
        Litres per sortie.
    sources : int, optional
        Number of sources (default 1).

    Returns
    -------
    float
        Minimum refill rate in litres per minute.
    """
    if aircraft < 1 or sources < 1:
        raise ValueError("aircraft and sources must be positive")
    return aircraft * payload_l / (cycle_min * sources)


def main() -> None:
    """Run the source-service cases and print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aircraft", type=int, default=3)
    parser.add_argument("--cycle-min", type=float, default=4.25)
    parser.add_argument("--payload-l", type=float, default=6000.0)
    parser.add_argument("--sources", default="1,2")
    parser.add_argument("--refill-l-min", default="2000,3000,4000,5000")
    args = parser.parse_args()
    source_counts = [int(value) for value in args.sources.split(",") if value]
    refill_rates = [float(value) for value in args.refill_l_min.split(",") if value]
    cases = [
        SourceService(
            aircraft=args.aircraft,
            cycle_min=args.cycle_min,
            payload_l=args.payload_l,
            refill_l_min=rate,
            sources=sources,
        ).to_dict()
        for sources in source_counts
        for rate in refill_rates
    ]
    minimums = {
        str(sources): minimum_refill_l_min(
            aircraft=args.aircraft,
            cycle_min=args.cycle_min,
            payload_l=args.payload_l,
            sources=sources,
        )
        for sources in source_counts
    }
    print(json.dumps({"minimum_refill_l_min": minimums, "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
