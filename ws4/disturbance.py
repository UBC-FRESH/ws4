"""Read and report ``femic.disturbance.v1`` events.

WS4 is a consumer of the FEMIC disturbance contract. This module reads the flat
consumer rows (or the full event records) and reports them without changing the
compiled dataset, the simulator, or the optimizer.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

DISTURBANCE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "fire",
        "insect",
        "disease",
        "drought",
        "wind",
        "flood",
        "partial_mortality",
        "harvest",
        "salvage",
        "other",
    }
)
DISTURBANCE_SEVERITY_CLASSES: frozenset[str] = frozenset(
    {"low", "moderate", "high", "very_high", "unknown"}
)
DISTURBANCE_MIN_YEAR = 1900
DISTURBANCE_MAX_YEAR = 2300


class DisturbanceError(RuntimeError):
    """Raised when a disturbance table cannot be consumed."""


def _require_mapping(value: object, field: str) -> Mapping[str, object]:
    """Return a mapping, or raise a consumer error."""
    if not isinstance(value, Mapping):
        raise DisturbanceError(f"{field} must be a mapping")
    return value


def _require_text(value: object, field: str) -> str:
    """Return a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise DisturbanceError(f"{field} must be a non-empty string")
    return value.strip()


def _require_int(value: object, field: str) -> int:
    """Return an integer, rejecting booleans and non-integers."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DisturbanceError(f"{field} must be an integer")
    return value


def _require_number(value: object, field: str) -> float:
    """Return a finite number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DisturbanceError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise DisturbanceError(f"{field} must be finite")
    return number


def _require_probability(value: object, field: str) -> float:
    """Return a number in the closed interval [0, 1]."""
    number = _require_number(value, field)
    if number < 0 or number > 1:
        raise DisturbanceError(f"{field} must be between 0 and 1")
    return number


def _optional_ids(value: object, field: str) -> tuple[int, ...]:
    """Validate an optional list of positive integer ids."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise DisturbanceError(f"{field} must be a list or null")
    ids: list[int] = []
    for item in value:
        identifier = _require_int(item, field)
        if identifier <= 0:
            raise DisturbanceError(f"{field} ids must be positive")
        ids.append(identifier)
    if len(set(ids)) != len(ids):
        raise DisturbanceError(f"{field} ids must be unique")
    return tuple(ids)


@dataclass(frozen=True)
class DisturbanceEvent:
    """One event from a ``femic.disturbance.v1`` consumer row.

    Attributes
    ----------
    event_id : str
        Stable event identifier.
    event_type : str
        Canonical event type.
    year : int
        Calendar year the event began.
    severity_class : str
        Categorical severity.
    confidence : float
        Attribution or detection confidence in [0, 1].
    source_id : str
        Upstream source identifier.
    severity_value : float | None, optional
        Optional continuous severity in [0, 1].
    fragment_ids : tuple[int, ...], optional
        FEMIC fragment ids touched by the event.
    block_ids : tuple[int, ...], optional
        WS4 block ids touched by the event.
    area_ha : float | None, optional
        Event area in hectares.
    """

    event_id: str
    event_type: str
    year: int
    severity_class: str
    confidence: float
    source_id: str
    severity_value: float | None = None
    fragment_ids: tuple[int, ...] = ()
    block_ids: tuple[int, ...] = ()
    area_ha: float | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the flat consumer-row shape.

        Returns
        -------
        dict[str, object]
            The event fields ws4 consumes, with ids as lists.
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "year": self.year,
            "severity_class": self.severity_class,
            "severity_value": self.severity_value,
            "confidence": self.confidence,
            "fragment_ids": list(self.fragment_ids),
            "block_ids": list(self.block_ids),
            "area_ha": self.area_ha,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> DisturbanceEvent:
        """Validate and construct an event from a consumer row or full record.

        Parameters
        ----------
        payload : mapping[str, object]
            A ``consumer_rows()`` row or a full ``femic.disturbance.v1``
            record. Extra fields are ignored.

        Returns
        -------
        DisturbanceEvent
            The validated event.

        Raises
        ------
        DisturbanceError
            If a required field is missing or invalid.
        """
        if not isinstance(payload, Mapping):
            raise DisturbanceError("disturbance event must be a mapping")
        required = (
            "event_id",
            "event_type",
            "year",
            "severity_class",
            "confidence",
            "source_id",
        )
        missing = [field for field in required if field not in payload]
        if missing:
            raise DisturbanceError(f"missing disturbance fields: {', '.join(missing)}")
        event_type = _require_text(payload["event_type"], "event_type")
        if event_type not in DISTURBANCE_EVENT_TYPES:
            supported = ", ".join(sorted(DISTURBANCE_EVENT_TYPES))
            raise DisturbanceError(f"event_type must be one of: {supported}; got {event_type!r}")
        year = _require_int(payload["year"], "year")
        if year < DISTURBANCE_MIN_YEAR or year > DISTURBANCE_MAX_YEAR:
            raise DisturbanceError(
                f"year must be between {DISTURBANCE_MIN_YEAR} and {DISTURBANCE_MAX_YEAR}"
            )
        severity_class = _require_text(payload["severity_class"], "severity_class")
        if severity_class not in DISTURBANCE_SEVERITY_CLASSES:
            supported = ", ".join(sorted(DISTURBANCE_SEVERITY_CLASSES))
            raise DisturbanceError(
                f"severity_class must be one of: {supported}; got {severity_class!r}"
            )
        severity_value = payload.get("severity_value")
        area_ha = payload.get("area_ha")
        area_value = None if area_ha is None else _require_number(area_ha, "area_ha")
        if area_value is not None and area_value < 0:
            raise DisturbanceError("area_ha must be non-negative")
        return cls(
            event_id=_require_text(payload["event_id"], "event_id"),
            event_type=event_type,
            year=year,
            severity_class=severity_class,
            confidence=_require_probability(payload["confidence"], "confidence"),
            source_id=_require_text(payload["source_id"], "source_id"),
            severity_value=(
                None
                if severity_value is None
                else _require_probability(severity_value, "severity_value")
            ),
            fragment_ids=_optional_ids(payload.get("fragment_ids"), "fragment_ids"),
            block_ids=_optional_ids(payload.get("block_ids"), "block_ids"),
            area_ha=area_value,
        )


def _validate_unique_events(events: Sequence[DisturbanceEvent]) -> None:
    """Reject duplicate event ids in a table."""
    ids = [event.event_id for event in events]
    if len(set(ids)) != len(ids):
        duplicates = sorted({event_id for event_id in ids if ids.count(event_id) > 1})
        raise DisturbanceError(f"duplicate event ids: {', '.join(duplicates)}")


def load_disturbance_events(path: Path) -> tuple[DisturbanceEvent, ...]:
    """Read a ``femic.disturbance.v1`` JSON table.

    Parameters
    ----------
    path : pathlib.Path
        JSON file containing a list of events, an object with an ``events``
        list, or a single event object.

    Returns
    -------
    tuple[DisturbanceEvent, ...]
        The validated events in file order.

    Raises
    ------
    DisturbanceError
        If the suffix is unsupported, the file is empty, an event is invalid,
        or two events share an id.
    """
    if path.suffix.lower() != ".json":
        raise DisturbanceError("disturbance tables must be JSON")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        events_payload = payload.get("events")
        if events_payload is None and "event_id" in payload:
            events_payload = [payload]
        payload = events_payload
    if not isinstance(payload, list):
        raise DisturbanceError(f"{path} must contain a list of events or an object with 'events'")
    events = tuple(
        DisturbanceEvent.from_dict(event) for event in payload if isinstance(event, Mapping)
    )
    if len(events) != len(payload):
        raise DisturbanceError(f"{path} contains a non-mapping event")
    if not events:
        raise DisturbanceError(f"{path} contains no disturbance events")
    _validate_unique_events(events)
    return events


def events_for_block(
    events: Sequence[DisturbanceEvent], block_id: int
) -> tuple[DisturbanceEvent, ...]:
    """Return events that name a block directly.

    Parameters
    ----------
    events : sequence[DisturbanceEvent]
        Validated events.
    block_id : int
        Block id to select.

    Returns
    -------
    tuple[DisturbanceEvent, ...]
        Events whose ``block_ids`` contains ``block_id``. Fragment-to-block
        resolution belongs to the caller.
    """
    if block_id <= 0:
        raise DisturbanceError("block_id must be positive")
    return tuple(event for event in events if block_id in event.block_ids)


def summarize_disturbance_events(
    events: Sequence[DisturbanceEvent],
) -> dict[str, object]:
    """Return a stable summary of a disturbance table.

    Parameters
    ----------
    events : sequence[DisturbanceEvent]
        Validated events.

    Returns
    -------
    dict[str, object]
        Counts, event types, severity classes, year range, total area, affected
        blocks and fragments, sources, and confidence range.

    Raises
    ------
    DisturbanceError
        If the table is empty.
    """
    if not events:
        raise DisturbanceError("disturbance table must contain at least one event")
    _validate_unique_events(events)
    blocks: set[int] = set()
    fragments: set[int] = set()
    for event in events:
        blocks.update(event.block_ids)
        fragments.update(event.fragment_ids)
    return {
        "event_count": len(events),
        "event_types": sorted({event.event_type for event in events}),
        "severity_classes": sorted({event.severity_class for event in events}),
        "year_min": min(event.year for event in events),
        "year_max": max(event.year for event in events),
        "total_area_ha": sum(event.area_ha for event in events if event.area_ha is not None),
        "affected_blocks": sorted(blocks),
        "affected_fragments": sorted(fragments),
        "sources": sorted({event.source_id for event in events}),
        "confidence_min": min(event.confidence for event in events),
        "confidence_max": max(event.confidence for event in events),
    }
