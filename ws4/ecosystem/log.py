"""The deterministic event log and its replay contract.

An event log is the auditable record of one landscape run: the ordered events, the scenario
and seed that produced them, and the package hashes that identify the process definitions.
Reading a log validates its schema, order, uniqueness, and digest. Replaying a log re-runs a
caller-supplied runner from the log's metadata and requires the same event sequence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .events import (
    EVENT_PHASES,
    Attribute,
    Event,
    EventError,
    _attributes,
    _integer,
    _text,
)
from .tape import TAPE_ALGORITHM

EVENT_LOG_SCHEMA_VERSION: Final[str] = "ws4.event-log.v1"

#: A runner that regenerates the events for a log's metadata.
ReplayRunner = Callable[["EventLogMetadata"], Sequence[Event]]

_LOG_FIELDS: Final[frozenset[str]] = frozenset(
    {"schema_version", "metadata", "events", "event_digest"}
)


class ReplayError(RuntimeError):
    """Raised when a replayed event stream differs from the logged stream."""


def _digest_hex(value: object, field: str) -> str:
    """Return a normalized 64-character SHA-256 hex digest.

    Parameters
    ----------
    value : object
        The candidate digest.
    field : str
        The field name, used in the error.

    Returns
    -------
    str
        The lower-case digest.

    Raises
    ------
    EventError
        If the value is not a 64-character hexadecimal string.
    """
    text = _text(value, field).lower()
    if len(text) != 64:
        raise EventError(f"{field} must be a 64-character SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as error:
        raise EventError(f"{field} must be hexadecimal") from error
    return text


def _package_hashes(value: object) -> tuple[tuple[str, str], ...]:
    """Return canonical, sorted package-hash entries.

    Parameters
    ----------
    value : object
        A mapping of package name to SHA-256 digest, or None.
    field : str
        The field name, used in the error.

    Returns
    -------
    tuple of (str, str) pairs
        The package names and digests, sorted by name.

    Raises
    ------
    EventError
        If the value is not a mapping or a digest is invalid.
    """
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise EventError("package_hashes must be a mapping")
    entries: list[tuple[str, str]] = []
    for raw_name, raw_digest in value.items():
        name = _text(raw_name, "package name")
        entries.append((name, _digest_hex(raw_digest, f"package {name!r} digest")))
    return tuple(sorted(entries))


def _digest(metadata: EventLogMetadata, events: Sequence[Event]) -> str:
    """Return the replay digest of a log's metadata and events.

    Parameters
    ----------
    metadata : EventLogMetadata
        The log metadata.
    events : sequence of Event
        The ordered events.

    Returns
    -------
    str
        The hex SHA-256 digest.
    """
    payload = {
        "metadata": metadata.to_dict(),
        "events": [event.to_dict() for event in events],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EventLogMetadata:
    """The scenario and provenance header of an event log.

    Parameters
    ----------
    scenario_id : str
        The scenario the log belongs to.
    scenario_seed : int or None, optional
        The non-negative seed of the random tape, when the log is stochastic.
    tape_algorithm : str, optional
        The tape algorithm identifier (default :data:`ws4.ecosystem.tape.TAPE_ALGORITHM`).
    package_hashes : tuple of (str, str) pairs, optional
        Package names mapped to SHA-256 digests.
    attributes : tuple of (str, scalar) pairs, optional
        Canonical provenance attributes.
    """

    scenario_id: str
    scenario_seed: int | None = None
    tape_algorithm: str = TAPE_ALGORITHM
    package_hashes: tuple[tuple[str, str], ...] = ()
    attributes: tuple[Attribute, ...] = ()

    def __post_init__(self) -> None:
        """Validate the metadata and canonicalize its maps."""
        scenario_id = _text(self.scenario_id, "scenario_id")
        scenario_seed = self.scenario_seed
        if scenario_seed is not None:
            scenario_seed = _integer(scenario_seed, "scenario_seed")
            if scenario_seed < 0:
                raise EventError("scenario_seed must be non-negative")
        tape_algorithm = _text(self.tape_algorithm, "tape_algorithm")
        if tape_algorithm != TAPE_ALGORITHM:
            raise EventError(f"tape_algorithm must be {TAPE_ALGORITHM!r}; got {tape_algorithm!r}")
        package_hashes = _package_hashes(dict(self.package_hashes))
        attributes = _attributes(self.attributes)
        object.__setattr__(self, "scenario_id", scenario_id)
        object.__setattr__(self, "scenario_seed", scenario_seed)
        object.__setattr__(self, "tape_algorithm", tape_algorithm)
        object.__setattr__(self, "package_hashes", package_hashes)
        object.__setattr__(self, "attributes", attributes)

    def to_dict(self) -> dict[str, object]:
        """Return the metadata as a JSON-serializable mapping.

        Returns
        -------
        dict
            The metadata fields, with package hashes and attributes as mappings.
        """
        return {
            "scenario_id": self.scenario_id,
            "scenario_seed": self.scenario_seed,
            "tape_algorithm": self.tape_algorithm,
            "package_hashes": dict(self.package_hashes),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> EventLogMetadata:
        """Validate and construct metadata from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`.

        Returns
        -------
        EventLogMetadata
            The validated metadata.

        Raises
        ------
        EventError
            If the mapping is not a mapping or a field is invalid.
        """
        if not isinstance(payload, Mapping):
            raise EventError("metadata must be a mapping")
        if "scenario_id" not in payload:
            raise EventError("metadata is missing scenario_id")
        return cls(
            scenario_id=_text(payload["scenario_id"], "scenario_id"),
            scenario_seed=(
                None
                if payload.get("scenario_seed") is None
                else _integer(payload["scenario_seed"], "scenario_seed")
            ),
            tape_algorithm=_text(payload.get("tape_algorithm", TAPE_ALGORITHM), "tape_algorithm"),
            package_hashes=_package_hashes(payload.get("package_hashes")),
            attributes=_attributes(payload.get("attributes")),
        )


@dataclass(frozen=True)
class EventLog:
    """An ordered, unique, replayable sequence of events for one scenario.

    Parameters
    ----------
    metadata : EventLogMetadata
        The scenario and provenance header.
    events : tuple of Event
        The events, in non-decreasing :attr:`Event.sort_key` order.
    """

    metadata: EventLogMetadata
    events: tuple[Event, ...]

    def __post_init__(self) -> None:
        """Validate the event sequence and its scenario identity."""
        events = tuple(self.events)
        for event in events:
            if not isinstance(event, Event):
                raise EventError("events must contain Event records")
        seen: set[str] = set()
        previous: tuple[float, int, int, int, str] | None = None
        for event in events:
            if event.scenario_id != self.metadata.scenario_id:
                raise EventError(
                    f"event {event.event_id!r} names scenario {event.scenario_id!r}, "
                    f"not {self.metadata.scenario_id!r}"
                )
            if event.event_id in seen:
                raise EventError(f"duplicate event id: {event.event_id!r}")
            seen.add(event.event_id)
            if previous is not None and event.sort_key < previous:
                raise EventError(f"event {event.event_id!r} is out of order")
            previous = event.sort_key
        object.__setattr__(self, "events", events)

    @classmethod
    def from_events(cls, events: Sequence[Event], metadata: EventLogMetadata) -> EventLog:
        """Sort events by their execution key and build a log.

        Parameters
        ----------
        events : sequence of Event
            The events to canonicalize.
        metadata : EventLogMetadata
            The scenario and provenance header.

        Returns
        -------
        EventLog
            The sorted, validated log.
        """
        ordered = sorted(events, key=lambda event: event.sort_key)
        return cls(metadata=metadata, events=tuple(ordered))

    @property
    def replay_token(self) -> str:
        """Return the SHA-256 digest of the metadata and ordered events.

        Returns
        -------
        str
            The hex replay digest.
        """
        return _digest(self.metadata, self.events)

    def summary(self) -> dict[str, object]:
        """Return a stable summary of the log.

        Returns
        -------
        dict
            The scenario, event counts, year range, area, processes, phases, first and last
            event ids, and the replay token.
        """
        years = [event.year for event in self.events]
        area = sum(event.area_ha for event in self.events if event.area_ha is not None)
        return {
            "schema_version": EVENT_LOG_SCHEMA_VERSION,
            "scenario_id": self.metadata.scenario_id,
            "scenario_seed": self.metadata.scenario_seed,
            "event_count": len(self.events),
            "year_min": min(years) if years else None,
            "year_max": max(years) if years else None,
            "area_ha": area,
            "processes": sorted({event.process_id for event in self.events}),
            "event_types": sorted({event.event_type for event in self.events}),
            "phases": sorted({event.phase for event in self.events}, key=EVENT_PHASES.index),
            "first_event_id": self.events[0].event_id if self.events else None,
            "last_event_id": self.events[-1].event_id if self.events else None,
            "replay_token": self.replay_token,
        }

    def write(self, path: Path) -> None:
        """Write the log as a JSON object with its replay digest.

        Parameters
        ----------
        path : Path
            Destination file. Parent directories are created.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": EVENT_LOG_SCHEMA_VERSION,
            "metadata": self.metadata.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "event_digest": self.replay_token,
        }
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def read(cls, path: Path) -> EventLog:
        """Read and validate a JSON event log.

        Parameters
        ----------
        path : Path
            The event-log file.

        Returns
        -------
        EventLog
            The validated log.

        Raises
        ------
        EventError
            If the file is missing, unreadable, malformed, has the wrong schema version,
            contains an invalid event, or its digest does not match.
        """
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise EventError("event logs must be JSON")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise EventError(f"cannot read event log {path}: {error}") from error
        if not isinstance(payload, Mapping):
            raise EventError("event log must be a JSON object")
        unknown = set(payload) - _LOG_FIELDS
        if unknown:
            raise EventError(f"unknown event-log fields: {', '.join(sorted(unknown))}")
        version = payload.get("schema_version")
        if version != EVENT_LOG_SCHEMA_VERSION:
            raise EventError(
                f"event-log schema_version must be {EVENT_LOG_SCHEMA_VERSION!r}; got {version!r}"
            )
        metadata_payload = payload.get("metadata")
        if not isinstance(metadata_payload, Mapping):
            raise EventError("event log is missing a metadata object")
        events_payload = payload.get("events")
        if not isinstance(events_payload, list):
            raise EventError("event log is missing an events list")
        events: list[Event] = []
        for index, item in enumerate(events_payload):
            if not isinstance(item, Mapping):
                raise EventError(f"event {index} is not a mapping")
            events.append(Event.from_dict(item))
        log = cls(metadata=EventLogMetadata.from_dict(metadata_payload), events=tuple(events))
        digest = payload.get("event_digest")
        if digest is None:
            raise EventError("event log is missing event_digest")
        expected = _digest_hex(digest, "event_digest")
        if expected != log.replay_token:
            raise EventError("event log digest does not match its contents")
        return log

    def verify_replay(self, runner: ReplayRunner) -> None:
        """Re-run a runner from the log metadata and require the same event sequence.

        Parameters
        ----------
        runner : ReplayRunner
            A callable that takes the log metadata and returns the regenerated events.

        Raises
        ------
        ReplayError
            If the runner returns a different scenario, a different event, or a different
            event count.
        """
        try:
            replayed = EventLog(
                metadata=self.metadata,
                events=tuple(runner(self.metadata)),
            )
        except EventError as error:
            raise ReplayError(f"replay is invalid: {error}") from error
        if replayed.replay_token == self.replay_token:
            return
        for index, expected in enumerate(self.events):
            if index >= len(replayed.events):
                raise ReplayError(f"replay ended after {index} events; expected {len(self.events)}")
            actual = replayed.events[index]
            if actual != expected:
                raise ReplayError(
                    f"replay diverges at event {index}: expected {expected.event_id!r}, "
                    f"got {actual.event_id!r}"
                )
        raise ReplayError(
            f"replay produced {len(replayed.events)} events; expected {len(self.events)}"
        )


class EventLogBuilder:
    """An append-only builder that enforces event order and uniqueness.

    Parameters
    ----------
    metadata : EventLogMetadata
        The scenario and provenance header the events must match.
    """

    def __init__(self, metadata: EventLogMetadata) -> None:
        """Retain the metadata and start an empty event sequence."""
        self.metadata = metadata
        self._events: list[Event] = []
        self._ids: set[str] = set()
        self._last_key: tuple[float, int, int, int, str] | None = None

    def __len__(self) -> int:
        """Return the number of events appended so far.

        Returns
        -------
        int
            The event count.
        """
        return len(self._events)

    def append(self, event: Event) -> None:
        """Append one event, enforcing scenario, uniqueness, and order.

        Parameters
        ----------
        event : Event
            The event to append.

        Raises
        ------
        EventError
            If the event is not an Event, names another scenario, repeats an id, or arrives
            out of order.
        """
        if not isinstance(event, Event):
            raise EventError("event must be an Event record")
        if event.scenario_id != self.metadata.scenario_id:
            raise EventError(
                f"event {event.event_id!r} names scenario {event.scenario_id!r}, "
                f"not {self.metadata.scenario_id!r}"
            )
        if event.event_id in self._ids:
            raise EventError(f"duplicate event id: {event.event_id!r}")
        if self._last_key is not None and event.sort_key < self._last_key:
            raise EventError(f"event {event.event_id!r} is out of order")
        self._events.append(event)
        self._ids.add(event.event_id)
        self._last_key = event.sort_key

    def extend(self, events: Sequence[Event]) -> None:
        """Append a sequence of events in order.

        Parameters
        ----------
        events : sequence of Event
            The events to append.

        Raises
        ------
        EventError
            If any event is invalid or out of order.
        """
        for event in events:
            self.append(event)

    def build(self) -> EventLog:
        """Return the immutable log of everything appended.

        Returns
        -------
        EventLog
            The validated log.
        """
        return EventLog(metadata=self.metadata, events=tuple(self._events))


__all__ = [
    "EVENT_LOG_SCHEMA_VERSION",
    "EventLog",
    "EventLogBuilder",
    "EventLogMetadata",
    "ReplayError",
    "ReplayRunner",
]
