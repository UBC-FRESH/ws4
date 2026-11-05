"""Build an exact solution-space view from a target-weight portfolio.

A portfolio is a finite set of optimizer runs, one per weight vector and seed. The
archive that keeps downloadable schedules is deliberately bounded, so its front can
omit trade-offs that every successful member actually contains. This module rebuilds
the front from the member records themselves, normalizes each outcome to a common
0=worst, 1=best box for a 3D view, and labels near-front members without pretending
that they are Pareto.

The output is advisory: the grid and the search budget define the sample, and a point
on the front is nondominated only with respect to the declared metrics.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .archive import Elite, pareto_front

#: Metrics that are always minimized when a portfolio record does not name one.
_DEFAULT_DIRECTION = "max"
_OBJECTIVE = "objective"


def _member_key(member: Mapping[str, Any], index: int) -> str:
    """Return the stable identity of one portfolio member.

    Parameters
    ----------
    member : mapping
        One record from ``portfolio.json``.
    index : int
        The record's position, used when the record has no label.

    Returns
    -------
    str
        ``label:seed`` when both are present, otherwise a stable member label.
    """
    label = str(member.get("label", "") or f"member-{index:03d}")
    seed = member.get("seed")
    if seed is None:
        return label
    try:
        return f"{label}:{int(seed):03d}"
    except (TypeError, ValueError):
        return f"{label}:{seed}"


def _directions_for(metrics: Sequence[str], supplied: Mapping[str, Any] | None) -> dict[str, str]:
    """Return a validated direction per outcome metric.

    Parameters
    ----------
    metrics : sequence of str
        The outcome metrics, in display order.
    supplied : mapping or None
        A direction map from the portfolio report. Missing metrics maximize.

    Returns
    -------
    dict of str to str
        One ``"min"`` or ``"max"`` per metric.

    Raises
    ------
    ValueError
        When a supplied direction is not ``"min"`` or ``"max"``.
    """
    source = supplied or {}
    directions: dict[str, str] = {}
    for metric in metrics:
        direction = str(source.get(metric, _DEFAULT_DIRECTION))
        if direction not in {"min", "max"}:
            raise ValueError(f"metric {metric!r} has unknown direction {direction!r}")
        directions[metric] = direction
    return directions


def _numeric(value: object) -> float | None:
    """Return a finite float, or None when the value is missing or non-finite."""
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _successful_points(
    members: Sequence[Mapping[str, Any]],
    metrics: Sequence[str],
) -> list[dict[str, Any]]:
    """Return the members that carry every declared outcome metric.

    Parameters
    ----------
    members : sequence of mapping
        Records from ``portfolio.json``.
    metrics : sequence of str
        The outcome metrics.

    Returns
    -------
    list of dict
        One normalized point record per successful member.
    """
    points: list[dict[str, Any]] = []
    for index, member in enumerate(members):
        if str(member.get("status", "")) == "failed":
            continue
        objective = _numeric(member.get("objective"))
        raw_metrics = member.get("metrics")
        if objective is None or not isinstance(raw_metrics, Mapping):
            continue
        values: dict[str, float] = {}
        valid = True
        for metric in metrics:
            value = _numeric(raw_metrics.get(metric))
            if value is None:
                valid = False
                break
            values[metric] = value
        if not valid:
            continue
        points.append(
            {
                "key": _member_key(member, index),
                "label": str(member.get("label", "") or f"member-{index:03d}"),
                "seed": member.get("seed"),
                "objective": objective,
                "metrics": values,
                "factors": dict(member.get("factors", {}) or {}),
                "status": str(member.get("status", "ok")),
                "schedule": member.get("schedule"),
                "targets": member.get("targets"),
                "run_dir": member.get("run_dir"),
                "error": str(member.get("error", "")),
            }
        )
    return points


def _ideal_nadir(
    points: Sequence[dict[str, Any]], metrics: Sequence[str], directions: Mapping[str, str]
) -> tuple[dict[str, float], dict[str, float]]:
    """Return the best and worst value per metric."""
    ideal: dict[str, float] = {}
    nadir: dict[str, float] = {}
    for metric in metrics:
        values = [float(point["metrics"][metric]) for point in points]
        if directions[metric] == "min":
            ideal[metric] = min(values)
            nadir[metric] = max(values)
        else:
            ideal[metric] = max(values)
            nadir[metric] = min(values)
    return ideal, nadir


def _normalise(value: float, best: float, worst: float) -> float:
    """Map one value to 0=worst and 1=best, with a constant metric at 0.5."""
    span = best - worst
    if abs(span) <= 1e-12:
        return 0.5
    return max(0.0, min(1.0, (value - worst) / span))


def _distance_to_front(
    point: Mapping[str, float],
    front: Sequence[Mapping[str, float]],
    metrics: Sequence[str],
) -> float:
    """Return the Chebyshev distance from one point to the nearest front point.

    The distance is measured in the normalized outcome box, so it is comparable
    across metrics with different units. A point on the front has distance zero.
    """
    if not front:
        return 1.0
    return min(
        max(abs(float(point[metric]) - float(candidate[metric])) for metric in metrics)
        for candidate in front
    )


def build_solution_space(
    payload: Mapping[str, Any],
    *,
    near_front_epsilon: float = 0.0,
) -> dict[str, Any]:
    """Build the browser's exact solution-space payload from a portfolio report.

    Parameters
    ----------
    payload : mapping
        A parsed ``portfolio.json`` document.
    near_front_epsilon : float, optional
        The largest Chebyshev distance in the normalized outcome box that is still
        labelled near-front. ``0`` keeps only exact front members. The label is
        explicit; a near-front member is not called Pareto.

    Returns
    -------
    dict
        Dimensions, directions, ideal/nadir, exact front keys, points, and counts.

    Raises
    ------
    ValueError
        When no metrics are declared or a metric direction is unknown.
    """
    metrics = [str(metric) for metric in payload.get("metrics", [])]
    if not metrics:
        raise ValueError("the portfolio has no declared metrics")
    raw_directions = payload.get("directions")
    directions = _directions_for(
        metrics, raw_directions if isinstance(raw_directions, Mapping) else None
    )
    raw_members = payload.get("members", [])
    if not isinstance(raw_members, Sequence) or isinstance(raw_members, (str, bytes)):
        raw_members = []
    members = [item for item in raw_members if isinstance(item, Mapping)]
    points = _successful_points(members, metrics)
    failed = sum(1 for item in members if str(item.get("status", "")) == "failed")
    if not points:
        return {
            "dimensions": [*metrics, _OBJECTIVE],
            "metrics": metrics,
            "directions": {**directions, _OBJECTIVE: "min"},
            "ideal": {},
            "nadir": {},
            "front": [],
            "near_front": [],
            "front_size": 0,
            "near_front_size": 0,
            "near_front_epsilon": max(0.0, float(near_front_epsilon)),
            "points": [],
            "failed": failed,
        }
    ideal, nadir = _ideal_nadir(points, metrics, directions)
    objective_best = min(float(point["objective"]) for point in points)
    objective_worst = max(float(point["objective"]) for point in points)
    for point in points:
        point["normalized"] = {
            metric: _normalise(float(point["metrics"][metric]), ideal[metric], nadir[metric])
            for metric in metrics
        }
        point["normalized"][_OBJECTIVE] = _normalise(
            float(point["objective"]), objective_best, objective_worst
        )
    elites = [
        Elite(
            objective=float(point["objective"]),
            metrics={metric: float(point["metrics"][metric]) for metric in metrics},
            schedule={},
            source=str(point["key"]),
            seed=point.get("seed") if isinstance(point.get("seed"), int) else None,
        )
        for point in points
    ]
    front_elites = pareto_front(elites, directions)
    front_keys = {elite.source for elite in front_elites}
    front_points = [point for point in points if point["key"] in front_keys]
    epsilon = max(0.0, float(near_front_epsilon))
    for point in points:
        point["front"] = point["key"] in front_keys
        point["distance_to_front"] = _distance_to_front(
            point["normalized"], [candidate["normalized"] for candidate in front_points], metrics
        )
        point["near_front"] = bool(point["front"] or point["distance_to_front"] <= epsilon + 1e-12)
    near_keys = [point["key"] for point in points if point["near_front"]]
    dimensions = [*metrics, _OBJECTIVE]
    all_directions = {**directions, _OBJECTIVE: "min"}
    return {
        "dimensions": dimensions,
        "metrics": metrics,
        "directions": all_directions,
        "ideal": ideal,
        "nadir": nadir,
        "front": [point["key"] for point in front_points],
        "near_front": near_keys,
        "front_size": len(front_points),
        "near_front_size": len(near_keys),
        "near_front_epsilon": epsilon,
        "points": points,
        "failed": failed,
    }
