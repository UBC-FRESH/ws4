"""An elite solution archive and a Pareto front over declared metrics.

The optimizer minimizes one weighted-goal penalty, but a decision-maker often needs the
trade-off between outcomes: volume against habitat, cost against patch size, or one
target's floor against another's ceiling. The archive keeps candidate schedules with
their realized metrics and filters a nondominated front under explicit max/min
directions.

The filter is deterministic: a candidate dominates another when it is no worse on every
metric and strictly better on at least one. Exact metric ties keep the candidate with the
lower scalar objective, which makes a portfolio reproducible when two weight vectors
happen to reach the same point.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .operators import Schedule

Direction = Literal["min", "max"]
_DIRECTIONS = {"min", "max"}


@dataclass(frozen=True)
class Elite:
    """One archived schedule and its outcomes.

    Attributes
    ----------
    objective : float
        The scalar weighted-goal penalty the search minimized.
    metrics : mapping of str to float
        The named outcomes the Pareto filter compares.
    schedule : Schedule
        The schedule's treatment chains per block.
    source : str, optional
        A label for where the candidate came from, such as a portfolio member.
    seed : int or None, optional
        The search seed, when known.
    iteration : int or None, optional
        The iteration that produced the candidate, when known.
    """

    objective: float
    metrics: Mapping[str, float]
    schedule: Schedule
    source: str = ""
    seed: int | None = None
    iteration: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready record without the schedule.

        Returns
        -------
        dict of str to object
            The objective, metrics, source, seed, iteration, and block count.
        """
        return {
            "objective": round(float(self.objective), 6),
            "metrics": {key: round(float(value), 6) for key, value in sorted(self.metrics.items())},
            "source": self.source,
            "seed": self.seed,
            "iteration": self.iteration,
            "blocks": len(self.schedule),
        }


def _check_directions(directions: Mapping[str, str], metrics: Mapping[str, float]) -> None:
    """Reject an unknown direction or a metric without one."""
    for metric in metrics:
        direction = directions.get(metric)
        if direction not in _DIRECTIONS:
            raise ValueError(f"metric {metric!r} needs a 'min' or 'max' direction")
    for metric, direction in directions.items():
        if direction not in _DIRECTIONS:
            raise ValueError(f"metric {metric!r} has unknown direction {direction!r}")


def dominates(left: Elite, right: Elite, directions: Mapping[str, str]) -> bool:
    """Return whether one candidate dominates another.

    Parameters
    ----------
    left : Elite
        The candidate tested as the dominator.
    right : Elite
        The candidate tested as the dominated one.
    directions : mapping of str to str
        The ``"min"`` or ``"max"`` direction per metric.

    Returns
    -------
    bool
        True when ``left`` is no worse on every metric and strictly better on at least one.

    Raises
    ------
    ValueError
        When the two candidates do not carry the same metrics or a direction is missing.
    """
    _check_directions(directions, left.metrics)
    _check_directions(directions, right.metrics)
    if set(left.metrics) != set(right.metrics):
        raise ValueError("candidates must carry the same metrics")
    better = False
    for metric, direction in directions.items():
        left_value = float(left.metrics[metric])
        right_value = float(right.metrics[metric])
        if direction == "min":
            if left_value > right_value:
                return False
            better = better or left_value < right_value
        else:
            if left_value < right_value:
                return False
            better = better or left_value > right_value
    return better


def pareto_front(elites: Sequence[Elite], directions: Mapping[str, str]) -> list[Elite]:
    """Return the nondominated candidates, stably ordered by objective.

    Parameters
    ----------
    elites : sequence of Elite
        The candidates to filter. Exact metric ties keep the lowest scalar objective and then
        the first candidate in the input order.
    directions : mapping of str to str
        The ``"min"`` or ``"max"`` direction per metric.

    Returns
    -------
    list of Elite
        One candidate per distinct metric vector, sorted by objective and source.

    Raises
    ------
    ValueError
        When a candidate has a metric without a direction.
    """
    unique: dict[tuple[float, ...], Elite] = {}
    for elite in elites:
        _check_directions(directions, elite.metrics)
        key = tuple(float(elite.metrics[metric]) for metric in directions)
        previous = unique.get(key)
        if previous is None or elite.objective < previous.objective:
            unique[key] = elite
    candidates = list(unique.values())
    front = [
        candidate
        for candidate in candidates
        if not any(
            dominates(other, candidate, directions)
            for other in candidates
            if other is not candidate
        )
    ]
    return sorted(front, key=lambda elite: (elite.objective, elite.source, elite.seed or -1))


@dataclass
class EliteArchive:
    """A bounded set of elite schedules.

    Parameters
    ----------
    capacity : int, optional
        The most candidates to retain. When the archive is over capacity, the highest scalar
        objective is dropped first, so the cap is a practical memory bound rather than an exact
        Pareto guarantee.
    directions : mapping of str to str, optional
        The direction per metric. Every added candidate must carry all of them.
    """

    capacity: int = 20
    directions: Mapping[str, str] = field(default_factory=dict)
    _elites: list[Elite] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        """Reject a capacity below one."""
        if self.capacity < 1:
            raise ValueError("capacity must be at least one")

    @property
    def elites(self) -> list[Elite]:
        """Return the retained candidates, lowest objective first.

        Returns
        -------
        list of Elite
            A copy of the retained list.
        """
        return list(self._elites)

    def add(self, elite: Elite) -> bool:
        """Consider one candidate for the archive.

        A candidate dominated by a retained member is rejected. A candidate that dominates
        retained members replaces them. An exact metric tie keeps the lower objective.

        Parameters
        ----------
        elite : Elite
            The candidate.

        Returns
        -------
        bool
            True when the candidate was retained.

        Raises
        ------
        ValueError
            When its metrics do not match the archive directions.
        """
        _check_directions(self.directions, elite.metrics)
        if set(elite.metrics) != set(self.directions):
            raise ValueError("candidate metrics must match the archive directions")
        for existing in self._elites:
            if existing.metrics == elite.metrics:
                if elite.objective < existing.objective:
                    self._elites.remove(existing)
                    break
                return False
        for existing in self._elites:
            if dominates(existing, elite, self.directions):
                return False
        self._elites = [
            existing for existing in self._elites if not dominates(elite, existing, self.directions)
        ]
        self._elites.append(elite)
        self._elites.sort(key=lambda item: (item.objective, item.source, item.seed or -1))
        if len(self._elites) > self.capacity:
            self._elites = self._elites[: self.capacity]
        return elite in self._elites

    def front(self) -> list[Elite]:
        """Return the nondominated subset of the retained candidates.

        Returns
        -------
        list of Elite
            The front, ordered by scalar objective.
        """
        return pareto_front(self._elites, self.directions)

    def write(self, directory: Path) -> dict[str, Path]:
        """Write the archive manifest and one schedule CSV per retained candidate.

        Parameters
        ----------
        directory : Path
            Destination directory. It is created when missing.

        Returns
        -------
        dict of str to Path
            The manifest and the schedule files keyed by candidate index.
        """
        directory.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        manifest: dict[str, Any] = {
            "capacity": self.capacity,
            "directions": dict(sorted(self.directions.items())),
            "elites": [],
        }
        for index, elite in enumerate(self._elites):
            record = elite.as_dict()
            schedule_path = directory / f"elite-{index:03d}.csv"
            write_schedule(schedule_path, elite.schedule)
            record["schedule"] = schedule_path.name
            manifest["elites"].append(record)
            paths[f"elite-{index:03d}"] = schedule_path
        manifest_path = directory / "archive.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        paths["manifest"] = manifest_path
        return paths


def write_schedule(path: Path, schedule: Schedule) -> None:
    """Write a schedule as a ``block_id,treatment,offset`` CSV.

    Parameters
    ----------
    path : Path
        Destination CSV.
    schedule : Schedule
        The treatment chains per block.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["block_id", "treatment", "offset"])
        for block in sorted(schedule):
            for treatment, offset in schedule[block]:
                writer.writerow([block, treatment, offset])


def metrics_from_records(
    records: Sequence[Mapping[str, Any]], names: Sequence[str]
) -> dict[str, float]:
    """Read named account values from a report-targets style record list.

    Parameters
    ----------
    records : sequence of mapping
        Records with ``account``, optional ``period``, and ``value`` keys.
    names : sequence of str
        The metric names. A name is an account, optionally suffixed with ``@<period>`` to select
        one period.

    Returns
    -------
    dict of str to float
        The value per requested name. A missing name is an error rather than a silent zero.

    Raises
    ------
    ValueError
        When a requested account or period is absent.
    """
    index: dict[tuple[str, int | None], float] = {}
    for record in records:
        account = str(record["account"])
        raw_period = record.get("period")
        period = int(raw_period) if raw_period is not None else None
        index[(account, period)] = float(record["value"])
    values: dict[str, float] = {}
    for name in names:
        account, separator, period_text = name.partition("@")
        period = int(period_text) if separator else None
        if (account, period) in index:
            values[name] = index[(account, period)]
            continue
        if separator and (account, None) in index:
            values[name] = index[(account, None)]
            continue
        matches = [value for (key, _), value in index.items() if key == account]
        if len(matches) == 1:
            values[name] = matches[0]
            continue
        raise ValueError(f"metric {name!r} was not found in the target report")
    return values
