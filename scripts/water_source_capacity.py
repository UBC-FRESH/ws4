"""P224: water-source throughput lower bound for gap re-wetting."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SourceCapacity:
    """One water-source throughput calculation.

    Attributes
    ----------
    sorties_per_hour : float
        Aircraft sortie demand.
    payload_l : float
        Litres per sortie.
    refill_l_min : float
        Refill rate per source.
    sources : int
        Number of identical sources.
    """

    sorties_per_hour: float
    payload_l: float
    refill_l_min: float
    sources: int

    @property
    def required_l_per_hour(self) -> float:
        """Water demand in litres per hour.

        Returns
        -------
        float
            Demand in litres per hour.
        """
        return self.sorties_per_hour * self.payload_l

    @property
    def supplied_l_per_hour(self) -> float:
        """Water supply in litres per hour.

        Returns
        -------
        float
            Supply in litres per hour.
        """
        return self.refill_l_min * 60.0 * self.sources

    @property
    def source_limited_sorties_per_hour(self) -> float:
        """Sorties per hour the source can supply.

        Returns
        -------
        float
            Source-limited sortie rate.
        """
        return self.supplied_l_per_hour / self.payload_l

    @property
    def utilization(self) -> float:
        """Fraction of source capacity used.

        Returns
        -------
        float
            Demand divided by supply.
        """
        return self.required_l_per_hour / self.supplied_l_per_hour

    @property
    def feasible(self) -> bool:
        """Whether the source can meet the demand.

        Returns
        -------
        bool
            True when supply meets demand.
        """
        return self.supplied_l_per_hour >= self.required_l_per_hour

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-serializable mapping.

        Returns
        -------
        dict
            Capacity fields and derived values.
        """
        return {
            **asdict(self),
            "required_l_per_hour": self.required_l_per_hour,
            "supplied_l_per_hour": self.supplied_l_per_hour,
            "source_limited_sorties_per_hour": self.source_limited_sorties_per_hour,
            "utilization": self.utilization,
            "feasible": self.feasible,
        }


def minimum_refill_l_min(
    *,
    sorties_per_hour: float,
    payload_l: float,
    sources: int = 1,
) -> float:
    """Return the minimum refill rate per source.

    Parameters
    ----------
    sorties_per_hour : float
        Sortie demand.
    payload_l : float
        Litres per sortie.
    sources : int, optional
        Number of sources (default 1).

    Returns
    -------
    float
        Minimum refill rate in litres per minute.
    """
    if sources < 1:
        raise ValueError("sources must be positive")
    return sorties_per_hour * payload_l / (60.0 * sources)


def main() -> None:
    """Run the source-capacity cases and print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sorties-per-hour", type=float, default=40.0)
    parser.add_argument("--payload-l", type=float, default=6000.0)
    parser.add_argument("--sources", default="1,2")
    parser.add_argument("--refill-l-min", default="2000,3000,4000,5000")
    args = parser.parse_args()
    source_counts = [int(value) for value in args.sources.split(",") if value]
    refill_rates = [float(value) for value in args.refill_l_min.split(",") if value]
    cases = []
    for sources in source_counts:
        for refill in refill_rates:
            capacity = SourceCapacity(
                sorties_per_hour=args.sorties_per_hour,
                payload_l=args.payload_l,
                refill_l_min=refill,
                sources=sources,
            )
            cases.append(capacity.to_dict())
    minimums = {
        str(sources): minimum_refill_l_min(
            sorties_per_hour=args.sorties_per_hour,
            payload_l=args.payload_l,
            sources=sources,
        )
        for sources in source_counts
    }
    print(json.dumps({"minimum_refill_l_min": minimums, "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
