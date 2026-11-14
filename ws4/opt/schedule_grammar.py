"""Deterministic add/remove mutations for process schedule candidates.

The P193 neighbourhood search takes a caller-supplied neighbour function. This module supplies
one over a fixed block universe, treatment set, and horizon. Candidate ids are derived from the
canonical schedule, so the same schedule always has the same id.

Only add and remove moves are implemented. Treatment windows, spatial constraints, and road
access belong to the estate model, not this grammar.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from .process_search import ProcessSearchCandidate

SCHEDULE_GRAMMAR_VERSION: Final[str] = "ws4.schedule-grammar.v1"


class ScheduleGrammarError(ValueError):
    """Raised when a schedule grammar or candidate schedule is invalid."""


def _canonical_schedule(
    schedule: Mapping[int, Sequence[tuple[str, int]]],
) -> dict[int, tuple[tuple[str, int], ...]]:
    """Return a validated, sorted schedule mapping.

    Parameters
    ----------
    schedule : mapping of int to sequence of (str, int)
        Block to treatment/offset entries.

    Returns
    -------
    dict
        Sorted block keys and sorted treatment/offset entries.

    Raises
    ------
    ScheduleGrammarError
        If a block, treatment, offset, or duplicate entry is invalid.
    """
    if not isinstance(schedule, Mapping):
        raise ScheduleGrammarError("schedule must be a mapping")
    result: dict[int, tuple[tuple[str, int], ...]] = {}
    for raw_block, raw_events in schedule.items():
        if isinstance(raw_block, bool) or not isinstance(raw_block, int) or raw_block <= 0:
            raise ScheduleGrammarError("block ids must be positive integers")
        if not isinstance(raw_events, Sequence):
            raise ScheduleGrammarError("block events must be a sequence")
        events: list[tuple[str, int]] = []
        for raw_treatment, raw_offset in raw_events:
            if not isinstance(raw_treatment, str) or not raw_treatment.strip():
                raise ScheduleGrammarError("treatment names must be non-empty strings")
            if isinstance(raw_offset, bool) or not isinstance(raw_offset, int) or raw_offset < 0:
                raise ScheduleGrammarError("offsets must be non-negative integers")
            events.append((raw_treatment.strip(), raw_offset))
        if len(set(events)) != len(events):
            raise ScheduleGrammarError(f"block {raw_block} has duplicate events")
        result[raw_block] = tuple(sorted(events, key=lambda item: (item[1], item[0])))
    return dict(sorted(result.items()))


def schedule_id(schedule: Mapping[int, Sequence[tuple[str, int]]]) -> str:
    """Return a stable id for a canonical schedule.

    Parameters
    ----------
    schedule : mapping of int to sequence of (str, int)
        Block to treatment/offset entries.

    Returns
    -------
    str
        A ``schedule-`` prefixed digest.
    """
    canonical = _canonical_schedule(schedule)
    payload = [
        [block, [[treatment, offset] for treatment, offset in events]]
        for block, events in canonical.items()
    ]
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"schedule-{digest}"


@dataclass(frozen=True)
class ScheduleMoveGrammar:
    """Add/remove neighbourhood over a fixed schedule universe.

    Parameters
    ----------
    blocks : sequence of int
        Block ids available to the grammar.
    treatments : sequence of str
        Treatment names available to the grammar.
    horizon_years : int
        Number of offsets, starting at zero.
    max_events_per_block : int, optional
        Maximum number of events in one block (default one).
    allow_offset_moves : bool, optional
        Whether to move an existing event to each other offset (default False).
    windows : mapping of int to (int, int) or None, optional
        Inclusive start and exclusive end offsets per block. Omitted blocks use the full
        horizon.
    """

    blocks: Sequence[int]
    treatments: Sequence[str]
    horizon_years: int
    max_events_per_block: int = 1
    allow_offset_moves: bool = False
    windows: Mapping[int, tuple[int, int]] | None = None

    def __post_init__(self) -> None:
        """Validate and canonicalize the grammar."""
        if isinstance(self.blocks, (str, bytes)) or not self.blocks:
            raise ScheduleGrammarError("blocks must be a non-empty sequence")
        blocks = tuple(sorted(int(block) for block in self.blocks))
        if len(set(blocks)) != len(blocks) or any(block <= 0 for block in blocks):
            raise ScheduleGrammarError("blocks must be unique positive integers")
        if isinstance(self.treatments, (str, bytes)) or not self.treatments:
            raise ScheduleGrammarError("treatments must be a non-empty sequence")
        treatments = tuple(sorted(str(treatment).strip() for treatment in self.treatments))
        if any(not treatment for treatment in treatments) or len(set(treatments)) != len(
            treatments
        ):
            raise ScheduleGrammarError("treatments must be unique non-empty strings")
        if (
            isinstance(self.horizon_years, bool)
            or not isinstance(self.horizon_years, int)
            or self.horizon_years <= 0
        ):
            raise ScheduleGrammarError("horizon_years must be a positive integer")
        if (
            isinstance(self.max_events_per_block, bool)
            or not isinstance(self.max_events_per_block, int)
            or self.max_events_per_block <= 0
        ):
            raise ScheduleGrammarError("max_events_per_block must be a positive integer")
        if not isinstance(self.allow_offset_moves, bool):
            raise ScheduleGrammarError("allow_offset_moves must be a boolean")
        windows: dict[int, tuple[int, int]] | None
        if self.windows is None:
            windows = None
        else:
            if not isinstance(self.windows, Mapping):
                raise ScheduleGrammarError("windows must be a mapping")
            windows = {}
            for raw_block, raw_window in self.windows.items():
                if raw_block not in blocks:
                    raise ScheduleGrammarError(f"window block {raw_block} is outside the grammar")
                if not isinstance(raw_window, tuple) or len(raw_window) != 2:
                    raise ScheduleGrammarError("windows must be (start, end) pairs")
                start, end = raw_window
                if (
                    isinstance(start, bool)
                    or isinstance(end, bool)
                    or not isinstance(start, int)
                    or not isinstance(end, int)
                    or start < 0
                    or end > self.horizon_years
                    or start >= end
                ):
                    raise ScheduleGrammarError(
                        "window bounds must satisfy 0 <= start < end <= horizon_years"
                    )
                windows[raw_block] = (start, end)
        object.__setattr__(self, "blocks", blocks)
        object.__setattr__(self, "treatments", treatments)
        object.__setattr__(self, "windows", windows)

    def _window(self, block: int) -> tuple[int, int]:
        """Return a block's allowed offset window.

        Parameters
        ----------
        block : int
            Block id.

        Returns
        -------
        tuple of (int, int)
            Inclusive start and exclusive end.
        """
        if self.windows is None:
            return (0, self.horizon_years)
        return self.windows.get(block, (0, self.horizon_years))

    def validate(self, schedule: Mapping[int, Sequence[tuple[str, int]]]) -> None:
        """Require every schedule entry to be inside the grammar universe.

        Parameters
        ----------
        schedule : mapping of int to sequence of (str, int)
            Candidate schedule.

        Raises
        ------
        ScheduleGrammarError
            If a block, treatment, offset, or event count is outside the grammar.
        """
        blocks = set(self.blocks)
        treatments = set(self.treatments)
        for block, events in schedule.items():
            if block not in blocks:
                raise ScheduleGrammarError(f"block {block} is outside the grammar")
            if len(events) > self.max_events_per_block:
                raise ScheduleGrammarError(f"block {block} exceeds max_events_per_block")
            start, end = self._window(block)
            for treatment, offset in events:
                if treatment not in treatments:
                    raise ScheduleGrammarError(f"treatment {treatment!r} is outside the grammar")
                if offset < start or offset >= end:
                    raise ScheduleGrammarError(f"offset {offset} is outside block {block}'s window")

    def neighbours(self, candidate: ProcessSearchCandidate) -> tuple[ProcessSearchCandidate, ...]:
        """Return deterministic add and remove neighbours.

        Parameters
        ----------
        candidate : ProcessSearchCandidate
            Candidate whose schedule is mutated.

        Returns
        -------
        tuple of ProcessSearchCandidate
            Neighbours in add-then-remove order, deduplicated by schedule id.

        Raises
        ------
        ScheduleGrammarError
            If the candidate schedule is outside the grammar universe.
        """
        current = _canonical_schedule(candidate.schedule)
        self.validate(current)
        neighbours: dict[str, ProcessSearchCandidate] = {}

        def add(schedule: Mapping[int, Sequence[tuple[str, int]]]) -> None:
            canonical = _canonical_schedule(schedule)
            identifier = schedule_id(canonical)
            neighbours.setdefault(identifier, ProcessSearchCandidate(identifier, canonical))

        for block in self.blocks:
            events = current.get(block, ())
            if len(events) >= self.max_events_per_block:
                continue
            start, end = self._window(block)
            for treatment in self.treatments:
                for offset in range(start, end):
                    item = (treatment, offset)
                    if item in events:
                        continue
                    updated = dict(current)
                    updated[block] = tuple(
                        sorted((*events, item), key=lambda value: (value[1], value[0]))
                    )
                    add(updated)

        for block in tuple(current):
            for item in current[block]:
                updated = dict(current)
                remaining = tuple(event for event in current[block] if event != item)
                if remaining:
                    updated[block] = remaining
                else:
                    del updated[block]
                add(updated)

        if self.allow_offset_moves:
            for block in tuple(current):
                events = current[block]
                start, end = self._window(block)
                for index, (treatment, offset) in enumerate(events):
                    for new_offset in range(start, end):
                        if new_offset == offset or (treatment, new_offset) in events:
                            continue
                        moved = list(events)
                        moved[index] = (treatment, new_offset)
                        updated = dict(current)
                        updated[block] = tuple(
                            sorted(moved, key=lambda value: (value[1], value[0]))
                        )
                        add(updated)

        return tuple(neighbours.values())
