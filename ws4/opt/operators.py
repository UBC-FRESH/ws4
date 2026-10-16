"""Neighbourhood operators for the schedule search.

A schedule maps a block to a chosen ``(treatment, year)``. Operators propose a
modified schedule, or ``None`` when they cannot move.
"""

from __future__ import annotations

import random
from typing import Protocol

Schedule = dict[int, tuple[str, int]]
Candidates = dict[int, list[tuple[str, int]]]

_OptionIndex = tuple[tuple[int, ...], dict[tuple[int, str], tuple[tuple[str, int], ...]]]
_INDEX_CACHE: dict[int, tuple[Candidates, _OptionIndex]] = {}


def _index(candidates: Candidates) -> _OptionIndex:
    """Return (and cache) the assignable blocks and the shiftable options per block.

    ``blocks`` is every block with at least one option; ``shiftable`` maps a
    ``(block, treatment)`` to its more-than-one years, so the shift operator does no
    per-call scan of the options. The cache is keyed by the identity of ``candidates``
    (kept alive so the id cannot be reused).

    Parameters
    ----------
    candidates : dict of int to list of tuple of (str, int)
        The per-block options.

    Returns
    -------
    tuple
        ``(blocks, shiftable)``.
    """
    cached = _INDEX_CACHE.get(id(candidates))
    if cached is not None and cached[0] is candidates:
        return cached[1]
    blocks = tuple(block for block, options in candidates.items() if options)
    shiftable: dict[tuple[int, str], tuple[tuple[str, int], ...]] = {}
    for block, options in candidates.items():
        grouped: dict[str, list[tuple[str, int]]] = {}
        for option in options:
            grouped.setdefault(option[0], []).append(option)
        for treatment, group in grouped.items():
            if len(group) > 1:
                shiftable[(block, treatment)] = tuple(group)
    result = (blocks, shiftable)
    _INDEX_CACHE[id(candidates)] = (candidates, result)
    return result


class Operator(Protocol):
    """A neighbourhood move."""

    name: str
    weight: float

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Return a modified schedule, or None if the operator cannot move."""

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a modified schedule and the blocks it changed, or None."""


class ToggleOperator:
    """Assign a treatment to a block, or clear an assigned block."""

    name = "toggle"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a toggled schedule and the block that changed."""
        blocks, _ = _index(candidates)
        if not blocks:
            return None
        block = rng.choice(blocks)
        result = dict(schedule)
        if block in result and rng.random() < 0.5:
            del result[block]
        else:
            result[block] = rng.choice(candidates[block])
        return result, (block,)

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Toggle one block."""
        proposal = self.propose(schedule, rng, candidates)
        return None if proposal is None else proposal[0]


class ShiftOperator:
    """Move an assigned block to a different year for the same treatment."""

    name = "shift"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a shifted schedule and the block that changed.

        A shiftable block is sampled by drawing a candidate block and testing it, rather
        than scanning the schedule, so the move is O(1) when most assigned blocks can
        shift. A full scan is the fallback when the sample fails.
        """
        if not schedule:
            return None
        blocks, shiftable = _index(candidates)
        for _ in range(12):
            block = rng.choice(blocks)
            assignment = schedule.get(block)
            if assignment is not None and (block, assignment[0]) in shiftable:
                result = dict(schedule)
                result[block] = rng.choice(shiftable[(block, assignment[0])])
                return result, (block,)
        candidates_blocks = [
            block for block, (treatment, _) in schedule.items() if (block, treatment) in shiftable
        ]
        if not candidates_blocks:
            return None
        block = rng.choice(candidates_blocks)
        result = dict(schedule)
        result[block] = rng.choice(shiftable[(block, schedule[block][0])])
        return result, (block,)

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Shift one block in time."""
        proposal = self.propose(schedule, rng, candidates)
        return None if proposal is None else proposal[0]


class SwapOperator:
    """Exchange the assignments of two blocks."""

    name = "swap"

    def __init__(self, weight: float = 0.5) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a swapped schedule and the two blocks that changed."""
        blocks = list(schedule)
        if len(blocks) < 2:
            return None
        first, second = rng.sample(blocks, 2)
        result = dict(schedule)
        result[first], result[second] = result[second], result[first]
        return result, (first, second)

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Swap two assigned blocks."""
        proposal = self.propose(schedule, rng, candidates)
        return None if proposal is None else proposal[0]


class LnsOperator:
    """Large-neighbourhood search: destroy a fraction of the schedule and repair it.

    A destroy-repair move clears a random fraction of the assigned blocks and
    reassigns them, exploring a large neighbourhood in one step.
    """

    name = "lns"

    def __init__(self, weight: float = 0.2, destroy_fraction: float = 0.1) -> None:
        """Set the operator's selection weight and the fraction destroyed."""
        self.weight = weight
        self.destroy_fraction = destroy_fraction

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Destroy a fraction of the schedule, repair it, and report the changed blocks."""
        if not schedule:
            return None
        blocks = list(schedule)
        count = max(1, int(len(blocks) * self.destroy_fraction))
        destroyed = set(rng.sample(blocks, count))
        result = {block: value for block, value in schedule.items() if block not in destroyed}
        repaired: list[int] = []
        for block in destroyed:
            options = candidates.get(block)
            if options:
                result[block] = rng.choice(options)
            repaired.append(block)
        return result, tuple(repaired)

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Destroy a fraction of the schedule and repair it."""
        proposal = self.propose(schedule, rng, candidates)
        return None if proposal is None else proposal[0]


class OperatorRegistry:
    """A weighted set of operators."""

    def __init__(self, operators: list[Operator] | None = None) -> None:
        """Store the operators (a default set when none is given)."""
        self._operators: list[Operator] = (
            operators
            if operators is not None
            else [ToggleOperator(), ShiftOperator(), SwapOperator(), LnsOperator()]
        )

    def names(self) -> list[str]:
        """Return the operator names."""
        return [operator.name for operator in self._operators]

    def pick(self, rng: random.Random) -> Operator:
        """Return a weighted-random operator."""
        total = sum(operator.weight for operator in self._operators)
        threshold = rng.random() * total
        for operator in self._operators:
            threshold -= operator.weight
            if threshold <= 0:
                return operator
        return self._operators[-1]
