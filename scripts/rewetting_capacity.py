"""P218: re-wetting sortie and fleet capacity lower bound."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Capacity:
    """One capacity calculation.

    Attributes
    ----------
    line_cells : int
        Number of cells treated per application.
    drops_per_cell : int
        Drops per cell per application.
    interval_min : float
        Re-wetting interval in minutes.
    cycle_min : float
        Mean aircraft cycle in minutes.
    payload_l : float
        Payload per sortie in litres.
    """

    line_cells: int
    drops_per_cell: int
    interval_min: float
    cycle_min: float
    payload_l: float

    @property
    def sorties_per_application(self) -> int:
        """Sorties in one complete application.

        Returns
        -------
        int
            Cell count times drops per cell.
        """
        return self.line_cells * self.drops_per_cell

    @property
    def sorties_per_hour(self) -> float:
        """Sorties per hour at the requested interval.

        Returns
        -------
        float
            Sorties per hour.
        """
        return self.sorties_per_application * 60.0 / self.interval_min

    @property
    def aircraft_lower_bound(self) -> int:
        """Perfect-dispatch aircraft lower bound.

        Returns
        -------
        int
            Minimum aircraft under continuous perfect dispatch.
        """
        return math.ceil(self.sorties_per_hour * self.cycle_min / 60.0)

    @property
    def water_l_per_hour(self) -> float:
        """Water delivered per hour.

        Returns
        -------
        float
            Litres per hour.
        """
        return self.sorties_per_hour * self.payload_l

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-serializable mapping.

        Returns
        -------
        dict
            Capacity fields and derived values.
        """
        return {
            **asdict(self),
            "sorties_per_application": self.sorties_per_application,
            "sorties_per_hour": self.sorties_per_hour,
            "aircraft_lower_bound": self.aircraft_lower_bound,
            "water_l_per_hour": self.water_l_per_hour,
        }


def main() -> None:
    """Run the capacity calculation and print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-cells", type=int, default=5)
    parser.add_argument("--full-line-cells", type=int, default=75)
    parser.add_argument("--drops-per-cell", type=int, default=2)
    parser.add_argument("--interval-min", type=float, default=15.0)
    parser.add_argument("--cycle-min", type=float, default=4.25)
    parser.add_argument("--payload-l", type=float, default=6000.0)
    args = parser.parse_args()
    gap = Capacity(
        line_cells=args.gap_cells,
        drops_per_cell=args.drops_per_cell,
        interval_min=args.interval_min,
        cycle_min=args.cycle_min,
        payload_l=args.payload_l,
    )
    full = Capacity(
        line_cells=args.full_line_cells,
        drops_per_cell=args.drops_per_cell,
        interval_min=args.interval_min,
        cycle_min=args.cycle_min,
        payload_l=args.payload_l,
    )
    print(json.dumps({"gap": gap.to_dict(), "full_line": full.to_dict()}, indent=2))


if __name__ == "__main__":
    main()
