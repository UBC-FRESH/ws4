"""The versioned event record shared by controlled and uncontrolled WS4 events.

An event is one state transition at a known time and place. A treatment is an event; so is a
fire, a windthrow, a regeneration, or a salvage decision. The record is deliberately wider than
the ``femic.disturbance.v1`` consumer row: it carries the scenario, process, phase, priority,
and provenance the unified executor needs, and the disturbance row is accepted as a subset by
:meth:`Event.from_disturbance_row`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

EVENT_SCHEMA_VERSION: Final[str] = "ws4.event.v1"

#: The canonical event phases, in execution order. A phase is part of the record, not a free
#: label, so a new phase is a schema-version change rather than a silent reordering.
EVENT_PHASES: Final[tuple[str, ...]] = (
    "forcing",
    "ignition",
    "propagation",
    "effect",
    "growth",
    "treatment",
    "regeneration",
    "accounting",
)

#: A JSON scalar is the only value an event attribute may carry.
JsonScalar = str | int | float | bool | None

#: One canonical attribute entry: a key and a JSON scalar.
Attribute = tuple[str, JsonScalar]


class EventError(RuntimeError):
    """Raised when an event or a list of events is invalid."""


def _text(value: object, field: str) -> str:
    """Return a non-empty, stripped string.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    str
        The stripped string.

    Raises
    ------
    EventError
        If the value is not a non-empty string.
    """
    if not isinstance(value, str) or not value.strip():
        raise EventError(f"{field} must be a non-empty string")
    return value.strip()


def _integer(value: object, field: str) -> int:
    """Return an integer, rejecting booleans and non-integers.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    int
        The integer.

    Raises
    ------
    EventError
        If the value is not an integer.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise EventError(f"{field} must be an integer")
    return value


def _number(value: object, field: str) -> float:
    """Return a finite float, normalizing negative zero.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    float
        The finite number.

    Raises
    ------
    EventError
        If the value is not a finite number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EventError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise EventError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


def _probability(value: object, field: str) -> float:
    """Return a probability in the closed interval [0, 1].

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    float
        The probability.

    Raises
    ------
    EventError
        If the value is not a probability.
    """
    number = _number(value, field)
    if number < 0.0 or number > 1.0:
        raise EventError(f"{field} must be between 0 and 1")
    return number


def _optional_text(value: object, field: str) -> str | None:
    """Return an optional non-empty string.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    str or None
        The string, or None.

    Raises
    ------
    EventError
        If the value is present but not a non-empty string.
    """
    return None if value is None else _text(value, field)


def _optional_number(value: object, field: str) -> float | None:
    """Return an optional finite number.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    float or None
        The number, or None.

    Raises
    ------
    EventError
        If the value is present but not finite.
    """
    return None if value is None else _number(value, field)


def _optional_probability(value: object, field: str) -> float | None:
    """Return an optional probability.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    float or None
        The probability, or None.

    Raises
    ------
    EventError
        If the value is present but not a probability.
    """
    return None if value is None else _probability(value, field)


def _ids(value: object, field: str) -> tuple[int, ...]:
    """Return a sorted tuple of unique positive integer ids.

    Parameters
    ----------
    value : object
        A sequence of ids, or None.
    field : str
        The field name, used in the error.

    Returns
    -------
    tuple of int
        The canonical ids.

    Raises
    ------
    EventError
        If the value is not a sequence of unique positive integers.
    """
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise EventError(f"{field} must be a sequence of ids or null")
    ids: list[int] = []
    for item in value:
        identifier = _integer(item, field)
        if identifier <= 0:
            raise EventError(f"{field} ids must be positive")
        ids.append(identifier)
    if len(set(ids)) != len(ids):
        raise EventError(f"{field} ids must be unique")
    return tuple(sorted(ids))


def _attribute_value(value: object, field: str) -> JsonScalar:
    """Return a JSON scalar, rejecting non-finite numbers and unsupported values.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    str, int, float, bool, or None
        The scalar.

    Raises
    ------
    EventError
        If the value is not a JSON scalar.
    """
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _number(value, field)
    raise EventError(f"{field} must be a JSON scalar")


def _attributes(value: object) -> tuple[Attribute, ...]:
    """Return canonical, sorted attribute entries.

    Parameters
    ----------
    value : object
        A mapping, a sequence of pairs, or None.
    field : str
        The field name, used in the error.

    Returns
    -------
    tuple of (str, scalar) pairs
        The attributes, sorted by key.

    Raises
    ------
    EventError
        If the value is not a mapping or a sequence of pairs with unique string keys.
    """
    if value is None:
        return ()
    if isinstance(value, Mapping):
        items: Sequence[tuple[object, object]] = list(value.items())
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        pairs: list[tuple[object, object]] = []
        for item in value:
            if isinstance(item, (str, bytes)) or not isinstance(item, Sequence) or len(item) != 2:
                raise EventError("attributes must be a mapping or a sequence of pairs")
            pairs.append((item[0], item[1]))
        items = pairs
    else:
        raise EventError("attributes must be a mapping or a sequence of pairs")
    seen: set[str] = set()
    entries: list[Attribute] = []
    for key, raw in items:
        name = _text(key, "attribute key")
        if name in seen:
            raise EventError(f"attribute keys must be unique; {name!r} repeats")
        seen.add(name)
        entries.append((name, _attribute_value(raw, f"attribute {name!r}")))
    return tuple(sorted(entries, key=lambda entry: entry[0]))


@dataclass(frozen=True)
class Event:
    """One controlled or uncontrolled state transition.

    Parameters
    ----------
    event_id : str
        Stable identifier, unique within an event log.
    process_id : str
        The source that produced the event, such as ``fire`` or ``schedule``.
    event_type : str
        The event type, such as ``fire``, ``harvest``, or ``regeneration``.
    time : float
        Absolute simulation time in years. ``year`` must equal ``floor(time)``.
    year : int
        The annual accounting year the event belongs to.
    phase : str
        One of :data:`EVENT_PHASES`, the execution phase within the year.
    source : str
        Provenance identifier for the producer, such as ``ws4.disturbance.v1``.
    scenario_id : str, optional
        The scenario the event belongs to (default ``default``).
    priority : int, optional
        Ordering priority within a phase (default 0; lower runs first).
    fragment_ids : tuple of int, optional
        Fragments touched by the event.
    site_ids : tuple of int, optional
        Sites touched by the event.
    block_ids : tuple of int, optional
        Blocks touched by the event.
    severity_class : str or None, optional
        Categorical severity, such as ``low`` or ``high``.
    severity_value : float or None, optional
        Continuous severity in [0, 1].
    magnitude : float or None, optional
        A process-specific magnitude, such as wind speed or mortality fraction.
    area_ha : float or None, optional
        The event area in hectares.
    parent_event_id : str or None, optional
        The event that caused this one, when the log is a causal chain.
    confidence : float or None, optional
        Confidence or detection probability in [0, 1].
    attributes : tuple of (str, scalar) pairs, optional
        Canonical, sorted event attributes.
    """

    event_id: str
    process_id: str
    event_type: str
    time: float
    year: int
    phase: str
    source: str
    scenario_id: str = "default"
    priority: int = 0
    fragment_ids: tuple[int, ...] = ()
    site_ids: tuple[int, ...] = ()
    block_ids: tuple[int, ...] = ()
    severity_class: str | None = None
    severity_value: float | None = None
    magnitude: float | None = None
    area_ha: float | None = None
    parent_event_id: str | None = None
    confidence: float | None = None
    attributes: tuple[Attribute, ...] = ()

    def __post_init__(self) -> None:
        """Validate the record and canonicalize its ids and attributes."""
        event_id = _text(self.event_id, "event_id")
        process_id = _text(self.process_id, "process_id")
        event_type = _text(self.event_type, "event_type")
        phase = _text(self.phase, "phase")
        if phase not in EVENT_PHASES:
            allowed = ", ".join(EVENT_PHASES)
            raise EventError(f"phase must be one of: {allowed}; got {phase!r}")
        source = _text(self.source, "source")
        scenario_id = _text(self.scenario_id, "scenario_id")
        time = _number(self.time, "time")
        if time < 0.0:
            raise EventError("time must be non-negative")
        year = _integer(self.year, "year")
        if year < 0:
            raise EventError("year must be non-negative")
        if math.floor(time) != year:
            raise EventError("year must equal floor(time)")
        priority = _integer(self.priority, "priority")
        fragment_ids = _ids(self.fragment_ids, "fragment_ids")
        site_ids = _ids(self.site_ids, "site_ids")
        block_ids = _ids(self.block_ids, "block_ids")
        severity_class = _optional_text(self.severity_class, "severity_class")
        severity_value = _optional_probability(self.severity_value, "severity_value")
        magnitude = _optional_number(self.magnitude, "magnitude")
        area_ha = _optional_number(self.area_ha, "area_ha")
        if area_ha is not None and area_ha < 0.0:
            raise EventError("area_ha must be non-negative")
        parent_event_id = _optional_text(self.parent_event_id, "parent_event_id")
        confidence = _optional_probability(self.confidence, "confidence")
        attributes = _attributes(self.attributes)
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "process_id", process_id)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "time", time)
        object.__setattr__(self, "year", year)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "scenario_id", scenario_id)
        object.__setattr__(self, "priority", priority)
        object.__setattr__(self, "fragment_ids", fragment_ids)
        object.__setattr__(self, "site_ids", site_ids)
        object.__setattr__(self, "block_ids", block_ids)
        object.__setattr__(self, "severity_class", severity_class)
        object.__setattr__(self, "severity_value", severity_value)
        object.__setattr__(self, "magnitude", magnitude)
        object.__setattr__(self, "area_ha", area_ha)
        object.__setattr__(self, "parent_event_id", parent_event_id)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "attributes", attributes)

    @property
    def spatial_id(self) -> int:
        """Return the smallest spatial id named by the event, or 0 when it names none.

        Returns
        -------
        int
            The ordering tie-breaker for the event's spatial location.
        """
        ids = self.fragment_ids + self.site_ids + self.block_ids
        return min(ids) if ids else 0

    @property
    def sort_key(self) -> tuple[float, int, int, int, str]:
        """Return the deterministic execution-order key.

        Returns
        -------
        tuple
            ``(time, phase rank, priority, spatial id, event id)``.
        """
        return (
            self.time,
            EVENT_PHASES.index(self.phase),
            self.priority,
            self.spatial_id,
            self.event_id,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the event as a JSON-serializable mapping.

        Returns
        -------
        dict
            The event fields, with ids as lists and attributes as a mapping.
        """
        return {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_id": self.event_id,
            "scenario_id": self.scenario_id,
            "process_id": self.process_id,
            "event_type": self.event_type,
            "time": self.time,
            "year": self.year,
            "phase": self.phase,
            "priority": self.priority,
            "fragment_ids": list(self.fragment_ids),
            "site_ids": list(self.site_ids),
            "block_ids": list(self.block_ids),
            "severity_class": self.severity_class,
            "severity_value": self.severity_value,
            "magnitude": self.magnitude,
            "area_ha": self.area_ha,
            "parent_event_id": self.parent_event_id,
            "source": self.source,
            "confidence": self.confidence,
            "attributes": dict(self.attributes),
        }

    def to_disturbance_dict(self, start_year: int = 1900) -> dict[str, object]:
        """Return the event as a ``femic.disturbance.v1`` consumer row.

        The row uses ``source_id`` rather than ``source`` and fills categorical defaults the
        disturbance contract requires. The event's own type must be one the disturbance
        contract accepts; the caller is responsible for exporting only those events.

        Parameters
        ----------
        start_year : int, optional
            The calendar year of simulation offset 0 (default 1900). The consumer row's
            ``year`` is ``start_year + event.year``.

        Returns
        -------
        dict
            The consumer row fields.
        """
        if isinstance(start_year, bool) or not isinstance(start_year, int) or start_year < 0:
            raise EventError("start_year must be a non-negative integer")
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "year": start_year + self.year,
            "severity_class": self.severity_class or "unknown",
            "severity_value": self.severity_value,
            "confidence": 1.0 if self.confidence is None else self.confidence,
            "source_id": self.source,
            "fragment_ids": list(self.fragment_ids),
            "block_ids": list(self.block_ids),
            "area_ha": self.area_ha,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> Event:
        """Validate and construct an event from a mapping.

        Parameters
        ----------
        payload : mapping of str to object
            A mapping in the shape produced by :meth:`to_dict`. A ``schema_version`` field is
            checked when present. Extra fields are ignored.

        Returns
        -------
        Event
            The validated event.

        Raises
        ------
        EventError
            If a required field is missing or a field is invalid.
        """
        if not isinstance(payload, Mapping):
            raise EventError("event must be a mapping")
        version = payload.get("schema_version")
        if version is not None and version != EVENT_SCHEMA_VERSION:
            raise EventError(
                f"event schema_version must be {EVENT_SCHEMA_VERSION!r}; got {version!r}"
            )
        required = ("event_id", "process_id", "event_type", "time", "year", "phase", "source")
        missing = [field for field in required if field not in payload]
        if missing:
            raise EventError(f"missing event fields: {', '.join(missing)}")
        return cls(
            event_id=_text(payload["event_id"], "event_id"),
            process_id=_text(payload["process_id"], "process_id"),
            event_type=_text(payload["event_type"], "event_type"),
            time=_number(payload["time"], "time"),
            year=_integer(payload["year"], "year"),
            phase=_text(payload["phase"], "phase"),
            source=_text(payload["source"], "source"),
            scenario_id=_text(payload.get("scenario_id", "default"), "scenario_id"),
            priority=_integer(payload.get("priority", 0), "priority"),
            fragment_ids=_ids(payload.get("fragment_ids"), "fragment_ids"),
            site_ids=_ids(payload.get("site_ids"), "site_ids"),
            block_ids=_ids(payload.get("block_ids"), "block_ids"),
            severity_class=_optional_text(payload.get("severity_class"), "severity_class"),
            severity_value=_optional_probability(payload.get("severity_value"), "severity_value"),
            magnitude=_optional_number(payload.get("magnitude"), "magnitude"),
            area_ha=_optional_number(payload.get("area_ha"), "area_ha"),
            parent_event_id=_optional_text(payload.get("parent_event_id"), "parent_event_id"),
            confidence=_optional_probability(payload.get("confidence"), "confidence"),
            attributes=_attributes(payload.get("attributes")),
        )

    @classmethod
    def from_disturbance_row(cls, payload: Mapping[str, object]) -> Event:
        """Adapt a ``femic.disturbance.v1`` consumer row to an event.

        The row is the subset WS4 already consumes. Missing unified fields receive stable
        defaults: ``scenario_id`` is ``default``, ``process_id`` is the row's ``source_id``,
        ``time`` is the row's ``year``, ``phase`` is ``treatment`` for harvest and salvage and
        ``effect`` otherwise, and ``priority`` is 0.

        Parameters
        ----------
        payload : mapping of str to object
            A disturbance consumer row.

        Returns
        -------
        Event
            The adapted event.

        Raises
        ------
        EventError
            If the row is not a mapping or a required field is invalid.
        """
        if not isinstance(payload, Mapping):
            raise EventError("disturbance row must be a mapping")
        year = _integer(payload.get("year"), "year")
        source_id = _text(payload.get("source_id", "femic.disturbance.v1"), "source_id")
        event_type = _text(payload.get("event_type"), "event_type")
        phase = "treatment" if event_type in {"harvest", "salvage"} else "effect"
        unified = dict(payload)
        unified.setdefault("scenario_id", "default")
        unified.setdefault("process_id", source_id)
        unified.setdefault("time", float(year))
        unified.setdefault("phase", phase)
        unified.setdefault("priority", 0)
        unified.setdefault("source", source_id)
        return cls.from_dict(unified)
