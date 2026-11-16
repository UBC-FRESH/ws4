"""Schedule-driven management events for the ecological cohort state.

This is the first management bridge: a block-level schedule is mapped to fragments, a
treatment emits one controlled harvest event per fragment, and applying the event removes a
fraction of the live cohorts and replaces that area with bare age-zero cohorts. It is a
simplified bridge, not a replacement for the compiled treatment semantics.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pandas as pd

from .events import Event
from .process import DecisionSource, ProcessContext
from .state import CohortState

MANAGEMENT_PROCESS_ID: Final[str] = "management"
MANAGEMENT_SOURCE: Final[str] = "ws4.ecosystem.management"
FRACTION_TOLERANCE: Final[float] = 1e-6


class ManagementError(RuntimeError):
    """Raised when a schedule or harvest event is invalid."""


def _probability(value: object, field: str) -> float:
    """Return a finite probability in [0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManagementError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ManagementError(f"{field} must be between 0 and 1")
    return number


def _track_key(value: object) -> int:
    """Return a non-negative integer track id from a table value."""
    if isinstance(value, bool):
        raise ManagementError("track_id must be a non-negative integer")
    try:
        number = float(str(value).strip())
    except ValueError as error:
        raise ManagementError("track_id must be a non-negative integer") from error
    if not math.isfinite(number) or not number.is_integer() or number < 0.0:
        raise ManagementError("track_id must be a non-negative integer")
    return int(number)


def load_schedule(path: str | Path) -> dict[int, tuple[tuple[str, int], ...]]:
    """Load a ``block_id,treatment,offset`` schedule CSV.

    Parameters
    ----------
    path : str or Path
        The schedule CSV.

    Returns
    -------
    dict
        Block id to ordered ``(treatment, offset)`` entries.

    Raises
    ------
    ManagementError
        If a required column is missing, a row is invalid, or a duplicate event exists.
    """
    source = Path(path)
    if not source.is_file():
        raise ManagementError(f"schedule does not exist: {source}")
    frame = pd.read_csv(source)
    required = {"block_id", "treatment", "offset"}
    missing = required - set(frame.columns)
    if missing:
        raise ManagementError(f"schedule is missing: {', '.join(sorted(missing))}")
    grouped: dict[int, list[tuple[str, int]]] = {}
    for row in frame.itertuples(index=False):
        block = int(str(row.block_id))
        treatment = str(row.treatment).strip()
        offset = int(str(row.offset))
        if block <= 0:
            raise ManagementError("block_id must be positive")
        if not treatment:
            raise ManagementError("treatment must be non-empty")
        if offset < 0:
            raise ManagementError("offset must be non-negative")
        grouped.setdefault(block, []).append((treatment, offset))
    result: dict[int, tuple[tuple[str, int], ...]] = {}
    for block, items in grouped.items():
        if len(set(items)) != len(items):
            raise ManagementError(f"block {block} has duplicate treatment events")
        result[block] = tuple(sorted(items, key=lambda item: (item[1], item[0])))
    return result


def load_block_fragments(path: str | Path) -> dict[int, tuple[int, ...]]:
    """Load a ``block_id,fragment_id`` mapping CSV.

    Parameters
    ----------
    path : str or Path
        The mapping CSV.

    Returns
    -------
    dict
        Block id to ordered fragment ids.

    Raises
    ------
    ManagementError
        If the mapping is missing, duplicated, or invalid.
    """
    source = Path(path)
    if not source.is_file():
        raise ManagementError(f"fragment mapping does not exist: {source}")
    frame = pd.read_csv(source)
    required = {"block_id", "fragment_id"}
    missing = required - set(frame.columns)
    if missing:
        raise ManagementError(f"fragment mapping is missing: {', '.join(sorted(missing))}")
    grouped: dict[int, list[int]] = {}
    seen: set[tuple[int, int]] = set()
    for row in frame.itertuples(index=False):
        block = int(str(row.block_id))
        fragment = int(str(row.fragment_id))
        if block <= 0 or fragment <= 0:
            raise ManagementError("block and fragment ids must be positive")
        pair = (block, fragment)
        if pair in seen:
            raise ManagementError(f"duplicate block/fragment pair: {pair}")
        seen.add(pair)
        grouped.setdefault(block, []).append(fragment)
    return {block: tuple(sorted(fragments)) for block, fragments in sorted(grouped.items())}


@dataclass(frozen=True)
class ScheduleSource(DecisionSource):
    """Emit and apply harvest events from a block-level schedule.

    Parameters
    ----------
    schedule : mapping of int to sequence of (str, int)
        Block to ordered treatment/offset entries.
    block_fragments : mapping of int to sequence of int
        Block to fragment ids.
    harvest_fraction : float, optional
        Fraction of each live cohort removed (default 1.0, a clearcut).
    scenario_id : str, optional
        Scenario id stamped on events.
    track_transitions : mapping of (int, str) to int, optional
        Compiled ``(source_track, treatment)`` to target track transitions. Newly created
        cohorts take the target track; survivors keep the source track.
    process_id : str
        Process id used by the executor.
    phases : tuple of str
        The executor phase this source participates in.
    state_reads, state_writes : frozenset of str
        Declared cohort-state variables.
    """

    schedule: Mapping[int, Sequence[tuple[str, int]]]
    block_fragments: Mapping[int, Sequence[int]]
    harvest_fraction: float = 1.0
    scenario_id: str = "management"
    track_transitions: Mapping[tuple[int, str], int] = field(default_factory=dict)

    process_id: str = MANAGEMENT_PROCESS_ID
    phases: tuple[str, ...] = ("treatment",)
    state_reads: frozenset[str] = frozenset(
        {"area_fraction", "biomass_t_ha", "fuel_t_ha", "snag_t_ha", "track_id"}
    )
    state_writes: frozenset[str] = frozenset(
        {"area_fraction", "age", "biomass_t_ha", "fuel_t_ha", "snag_t_ha", "track_id"}
    )

    def __post_init__(self) -> None:
        """Validate the schedule, mapping, fraction, and scenario."""
        if not self.scenario_id.strip():
            raise ManagementError("scenario_id must be non-empty")
        object.__setattr__(
            self, "harvest_fraction", _probability(self.harvest_fraction, "harvest_fraction")
        )
        cleaned: dict[int, tuple[tuple[str, int], ...]] = {}
        for block, items in self.schedule.items():
            if block <= 0:
                raise ManagementError("schedule block ids must be positive")
            events: list[tuple[str, int]] = []
            for treatment, offset in items:
                if not str(treatment).strip():
                    raise ManagementError("treatment must be non-empty")
                if int(offset) < 0:
                    raise ManagementError("offset must be non-negative")
                events.append((str(treatment).strip(), int(offset)))
            cleaned[int(block)] = tuple(sorted(events, key=lambda item: (item[1], item[0])))
        object.__setattr__(self, "schedule", cleaned)
        transitions: dict[tuple[int, str], int] = {}
        for (raw_track, raw_treatment), target in self.track_transitions.items():
            if isinstance(raw_track, bool) or not isinstance(raw_track, int) or raw_track < 0:
                raise ManagementError(
                    "track transition source tracks must be non-negative integers"
                )
            treatment = str(raw_treatment).strip()
            if not treatment:
                raise ManagementError("track transition treatments must be non-empty")
            if isinstance(target, bool) or not isinstance(target, int) or target < 0:
                raise ManagementError("track transition targets must be non-negative integers")
            transitions[(raw_track, treatment)] = target
        object.__setattr__(self, "track_transitions", transitions)
        mapping: dict[int, tuple[int, ...]] = {}
        for block, fragments in self.block_fragments.items():
            values = tuple(sorted(int(fragment) for fragment in fragments))
            if not values:
                raise ManagementError(f"block {block} has no fragments")
            if any(fragment <= 0 for fragment in values):
                raise ManagementError("fragment ids must be positive")
            mapping[int(block)] = values
        object.__setattr__(self, "block_fragments", mapping)
        unknown = sorted(set(cleaned) - set(mapping))
        if unknown:
            raise ManagementError(f"schedule blocks have no fragment mapping: {unknown}")

    def events(self, state: CohortState, context: ProcessContext) -> tuple[Event, ...]:
        """Emit harvest events scheduled for the current offset.

        Parameters
        ----------
        state : CohortState
            The current state; unused beyond validation.
        context : ProcessContext
            The annual context; ``year`` is the schedule offset.

        Returns
        -------
        tuple of Event
            Harvest events not already in the current year.
        """
        del state
        existing = {event.event_id for event in context.year_events}
        events: list[Event] = []
        for block, items in sorted(self.schedule.items()):
            for treatment, offset in items:
                if offset != context.year:
                    continue
                for fragment in self.block_fragments[block]:
                    event_id = f"harvest-{context.year}-{block}-{fragment}"
                    if event_id in existing:
                        continue
                    events.append(
                        Event(
                            event_id=event_id,
                            process_id=self.process_id,
                            event_type="harvest",
                            time=float(context.year) + 0.4,
                            year=context.year,
                            phase="treatment",
                            source=MANAGEMENT_SOURCE,
                            scenario_id=context.scenario_id,
                            fragment_ids=(fragment,),
                            block_ids=(block,),
                            attributes=(
                                ("treatment", treatment),
                                ("harvest_fraction", self.harvest_fraction),
                            ),
                        )
                    )
        return tuple(events)

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Remove a fraction of the fragment's live cohorts and create bare cohorts.

        Parameters
        ----------
        state : CohortState
            The current state.
        event : Event
            A harvest event.

        Returns
        -------
        CohortState
            The updated state; other event types are returned unchanged.
        """
        if event.event_type != "harvest" or not event.fragment_ids:
            return state
        fraction = self.harvest_fraction
        treatment = ""
        for key, value in event.attributes:
            if key == "harvest_fraction" and isinstance(value, (int, float)):
                fraction = float(value)
            elif key == "treatment" and isinstance(value, str):
                treatment = value.strip()
        fragment = event.fragment_ids[0]
        frame = state.cohorts.copy()
        group = frame[frame["fragment_id"] == fragment]
        if group.empty:
            return state
        has_track = "track_id" in frame.columns
        if self.track_transitions and not has_track:
            frame["track_id"] = 0
            group = frame[frame["fragment_id"] == fragment]
            has_track = True
        next_id = int(group["cohort_id"].max()) + 1
        drop: list[int] = []
        new_rows: list[dict[str, object]] = []
        for index, row in group.iterrows():
            area = float(row["area_fraction"])
            removed = area * fraction
            survivor = area - removed
            source_track = 0
            if has_track and pd.notna(row["track_id"]):
                source_track = _track_key(row["track_id"])
            new_track = self.track_transitions.get((source_track, treatment), source_track)
            if survivor > FRACTION_TOLERANCE:
                frame.at[index, "area_fraction"] = survivor
            else:
                drop.append(int(str(index)))
            if removed > FRACTION_TOLERANCE:
                new_rows.append(
                    {
                        "fragment_id": fragment,
                        "cohort_id": next_id,
                        "species": str(row["species"]),
                        "age": 0,
                        "area_fraction": removed,
                        "biomass_t_ha": 0.0,
                        "fuel_t_ha": 0.0,
                        "snag_t_ha": 0.0,
                        "attributes_json": "{}",
                        **({"track_id": new_track} if has_track else {}),
                    }
                )
                next_id += 1
        if drop:
            frame = frame.drop(index=drop)
        if new_rows:
            frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)
        return CohortState(
            cohorts=frame.reset_index(drop=True),
            schema=state.schema,
            fragment_areas=state.fragment_areas,
        )
