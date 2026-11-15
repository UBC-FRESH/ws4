"""P232: source-distance and drawdown consistency for HWF113."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceMetrics:
    """One candidate source evaluated against the gap schedule.

    Parameters
    ----------
    object_id : int
        Source service object identifier.
    feature_type : str
        Alberta waterbody feature type.
    name : str or None
        Waterbody name, when present.
    area_ha : float
        Waterbody area in hectares.
    distance_km : float
        One-way distance from the gap in kilometres.
    drawdown_mm : float
        Equivalent depth removed by the full gap demand.
    required_speed_kmh : float
        Average speed needed to keep the gap cycle travel budget.
    """

    object_id: int
    feature_type: str
    name: str | None
    area_ha: float
    distance_km: float
    drawdown_mm: float
    required_speed_kmh: float


def travel_budget_min(
    *,
    cycle_min: float,
    payload_l: float,
    refill_l_min: float,
) -> float:
    """Return the travel time left after refilling one payload.

    Parameters
    ----------
    cycle_min : float
        Total aircraft cycle in minutes.
    payload_l : float
        Litres per sortie.
    refill_l_min : float
        Source refill rate in litres per minute.

    Returns
    -------
    float
        Travel budget in minutes.
    """
    service_min = payload_l / refill_l_min
    budget = cycle_min - service_min
    if budget <= 0.0:
        raise ValueError("refill time leaves no travel budget")
    return budget


def evaluate_sources(
    sources: list[dict[str, Any]],
    *,
    volume_l: float,
    budget_min: float,
) -> list[SourceMetrics]:
    """Evaluate source area and distance against the gap demand.

    Parameters
    ----------
    sources : list of dict
        Candidate source records with ``area_ha`` and ``distance_km``.
    volume_l : float
        Total water demand in litres.
    budget_min : float
        Travel budget per sortie in minutes.

    Returns
    -------
    list of SourceMetrics
        Candidates sorted by distance.
    """
    metrics: list[SourceMetrics] = []
    for source in sources:
        area_ha = float(source["area_ha"])
        distance_km = float(source["distance_km"])
        if area_ha <= 0.0:
            raise ValueError("source area must be positive")
        metrics.append(
            SourceMetrics(
                object_id=int(source["object_id"]),
                feature_type=str(source["feature_type"]),
                name=source.get("name"),
                area_ha=area_ha,
                distance_km=distance_km,
                drawdown_mm=volume_l / (area_ha * 10_000.0),
                required_speed_kmh=120.0 * distance_km / budget_min,
            )
        )
    return sorted(metrics, key=lambda metric: metric.distance_km)


def load_candidates(path: Path) -> list[dict[str, Any]]:
    """Load unique nearest candidates from a P229 screen artifact.

    Parameters
    ----------
    path : pathlib.Path
        P229 screen JSON.

    Returns
    -------
    list of dict
        Unique candidate records.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    nearest = payload.get("nearest_by_min_area")
    if not isinstance(nearest, dict):
        raise ValueError("input has no nearest_by_min_area mapping")
    unique: dict[int, dict[str, Any]] = {}
    for candidate in nearest.values():
        if not isinstance(candidate, dict):
            continue
        unique[int(candidate["object_id"])] = candidate
    return sorted(unique.values(), key=lambda item: float(item["distance_km"]))


def main() -> None:
    """Run the source consistency check and print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--volume-l", type=float, default=480_000.0)
    parser.add_argument("--cycle-min", type=float, default=4.25)
    parser.add_argument("--payload-l", type=float, default=6_000.0)
    parser.add_argument("--refill-l-min", type=float, default=4_235.294)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    budget = travel_budget_min(
        cycle_min=args.cycle_min,
        payload_l=args.payload_l,
        refill_l_min=args.refill_l_min,
    )
    sources = load_candidates(args.sources)
    metrics = evaluate_sources(sources, volume_l=args.volume_l, budget_min=budget)
    payload = {
        "parameters": {
            "volume_l": args.volume_l,
            "cycle_min": args.cycle_min,
            "payload_l": args.payload_l,
            "refill_l_min": args.refill_l_min,
            "travel_budget_min": budget,
        },
        "sources": [asdict(metric) for metric in metrics],
    }
    text = json.dumps(payload, indent=2)
    if args.output is None:
        print(text)
    else:
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
