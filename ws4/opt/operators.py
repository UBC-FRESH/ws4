"""Neighbourhood operators for the schedule search.

A schedule maps a block to its **chain**: the ordered treatments applied to it over the
horizon (a block may be treated more than once, as rotations). Each event is a
``(treatment, year)`` pair. An empty chain means the block is not treated. Operators
propose a modified schedule, or ``None`` when they cannot move.
"""

from __future__ import annotations

import random
from typing import Protocol

Event = tuple[str, int]
Chain = tuple[Event, ...]
Schedule = dict[int, Chain]
Candidates = dict[int, list[Chain]]

_OptionIndex = tuple[tuple[int, ...], dict[int, tuple[Chain, ...]]]
_INDEX_CACHE: dict[int, tuple[Candidates, _OptionIndex]] = {}


def _index(candidates: Candidates) -> _OptionIndex:
    """Return (and cache) the assignable blocks and the rechoosable chains per block.

    ``blocks`` is every block with at least one candidate chain; ``rechoosable`` maps a
    block with more than one candidate chain to its chains, so the shift operator does no
    per-call scan. The cache is keyed by the identity of ``candidates`` (kept alive so the
    id cannot be reused).

    Parameters
    ----------
    candidates : dict of int to list of Chain
        The per-block candidate chains.

    Returns
    -------
    tuple
        ``(blocks, rechoosable)``.
    """
    cached = _INDEX_CACHE.get(id(candidates))
    if cached is not None and cached[0] is candidates:
        return cached[1]
    blocks = tuple(block for block, chains in candidates.items() if chains)
    rechoosable = {block: tuple(chains) for block, chains in candidates.items() if len(chains) > 1}
    result = (blocks, rechoosable)
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
    """Assign a candidate chain to a block, or clear an assigned block."""

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
        if result.get(block) and rng.random() < 0.5:
            result[block] = ()
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
    """Rechoose a block's chain (a different rotation sequence)."""

    name = "shift"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a schedule with one block's chain rechoosing, and the block.

        A rechoosable block is sampled by drawing a candidate block and testing it, rather
        than scanning the schedule, so the move is O(1) when most assigned blocks have more
        than one chain.
        """
        if not schedule:
            return None
        blocks, rechoosable = _index(candidates)
        for _ in range(12):
            block = rng.choice(blocks)
            if schedule.get(block) and block in rechoosable:
                result = dict(schedule)
                result[block] = rng.choice(rechoosable[block])
                return result, (block,)
        assigned = [block for block in schedule if schedule[block] and block in rechoosable]
        if not assigned:
            return None
        block = rng.choice(assigned)
        result = dict(schedule)
        result[block] = rng.choice(rechoosable[block])
        return result, (block,)

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Rechoose one block's chain."""
        proposal = self.propose(schedule, rng, candidates)
        return None if proposal is None else proposal[0]


class SwapOperator:
    """Exchange the chains of two blocks."""

    name = "swap"

    def __init__(self, weight: float = 0.5) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a schedule with two blocks' chains exchanged, and the two blocks."""
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

    A destroy-repair move clears a random fraction of the assigned blocks and reassigns
    them to random candidate chains, exploring a large neighbourhood in one step.
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
            chains = candidates.get(block)
            if chains:
                result[block] = rng.choice(chains)
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

    def weights(self) -> dict[str, float]:
        """Return the operator weights by name."""
        return {operator.name: operator.weight for operator in self._operators}

    def pick(self, rng: random.Random) -> Operator:
        """Return a weighted-random operator."""
        total = sum(operator.weight for operator in self._operators)
        threshold = rng.random() * total
        for operator in self._operators:
            threshold -= operator.weight
            if threshold <= 0:
                return operator
        return self._operators[-1]
