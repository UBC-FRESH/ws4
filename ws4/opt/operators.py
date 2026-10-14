"""Neighbourhood operators for the schedule search.

A schedule maps a block to a chosen ``(treatment, year)``. Operators propose a
modified schedule, or ``None`` when they cannot move.
"""

from __future__ import annotations

import random
from typing import Protocol

Schedule = dict[int, tuple[str, int]]
Candidates = dict[int, list[tuple[str, int]]]


class Operator(Protocol):
    """A neighbourhood move."""

    name: str
    weight: float

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Return a modified schedule, or None if the operator cannot move."""


class ToggleOperator:
    """Assign a treatment to a block, or clear an assigned block."""

    name = "toggle"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Toggle one block."""
        blocks = [block for block, options in candidates.items() if options]
        if not blocks:
            return None
        block = rng.choice(blocks)
        result = dict(schedule)
        if block in result and rng.random() < 0.5:
            del result[block]
        else:
            result[block] = rng.choice(candidates[block])
        return result


class ShiftOperator:
    """Move an assigned block to a different year for the same treatment."""

    name = "shift"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Shift one block in time."""
        blocks = [
            block
            for block in schedule
            if len([o for o in candidates.get(block, []) if o[0] == schedule[block][0]]) > 1
        ]
        if not blocks:
            return None
        block = rng.choice(blocks)
        options = [o for o in candidates[block] if o[0] == schedule[block][0]]
        result = dict(schedule)
        result[block] = rng.choice(options)
        return result


class SwapOperator:
    """Exchange the assignments of two blocks."""

    name = "swap"

    def __init__(self, weight: float = 0.5) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Swap two assigned blocks."""
        blocks = list(schedule)
        if len(blocks) < 2:
            return None
        first, second = rng.sample(blocks, 2)
        result = dict(schedule)
        result[first], result[second] = result[second], result[first]
        return result


class OperatorRegistry:
    """A weighted set of operators."""

    def __init__(self, operators: list[Operator] | None = None) -> None:
        """Store the operators (a default set when none is given)."""
        self._operators: list[Operator] = (
            operators
            if operators is not None
            else [ToggleOperator(), ShiftOperator(), SwapOperator()]
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
