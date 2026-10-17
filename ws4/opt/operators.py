"""Neighbourhood operators for the schedule search.

A schedule maps a block to its **chain**: the ordered treatments applied to it over the
horizon (a block may be treated more than once, as rotations). Each event is a
``(treatment, year)`` pair. An empty chain means the block is not treated.

Operators propose a move **in place**: they mutate the schedule and return the previous
chain of each block they touched, so the caller can undo a rejected move without copying
the whole schedule. A copying :meth:`propose` is provided on top for callers that want a
new schedule.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

Event = tuple[str, int]
Chain = tuple[Event, ...]
Schedule = dict[int, Chain]
Candidates = dict[int, list[Chain]]
Undo = dict[int, "Chain | None"]

_OptionIndex = tuple[tuple[int, ...], dict[int, tuple[Chain, ...]]]
_INDEX_CACHE: dict[int, tuple[Candidates, _OptionIndex]] = {}


def _index(candidates: Candidates) -> _OptionIndex:
    """Return (and cache) the assignable blocks and the rechoosable chains per block.

    ``blocks`` is every block with at least one candidate chain; ``rechoosable`` maps a
    block with more than one candidate chain to its chains. The cache is keyed by the
    identity of ``candidates`` (kept alive so the id cannot be reused).

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


def restore(schedule: Schedule, undo: Undo) -> None:
    """Undo an in-place move, restoring each touched block's previous chain.

    Parameters
    ----------
    schedule : dict of int to Chain
        The mutated schedule.
    undo : dict of int to Chain or None
        The previous chain per touched block (None means the block was absent).
    """
    for block, previous in undo.items():
        if previous is None:
            schedule.pop(block, None)
        else:
            schedule[block] = previous


class Operator(Protocol):
    """A neighbourhood move."""

    name: str
    weight: float

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Mutate the schedule and return the previous chains, or None to move."""

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a modified copy and the blocks it changed, or None."""

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Return a modified copy, or None if the operator cannot move."""


class _OperatorBase:
    """Shared plumbing: a copying ``propose``/``apply`` on top of an in-place move."""

    name = ""
    weight = 1.0

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:  # pragma: no cover - overridden
        """Mutate the schedule and return the previous chains, or None."""
        raise NotImplementedError

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a modified copy and the blocks it changed, or None."""
        result = dict(schedule)
        undo = self.propose_inplace(result, rng, candidates)
        return None if undo is None else (result, tuple(undo))

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Return a modified copy, or None if the operator cannot move."""
        proposal = self.propose(schedule, rng, candidates)
        return None if proposal is None else proposal[0]


class ToggleOperator(_OperatorBase):
    """Assign a candidate chain to a block, or clear an assigned block."""

    name = "toggle"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Toggle one block in place."""
        blocks, _ = _index(candidates)
        if not blocks:
            return None
        block = rng.choice(blocks)
        undo: Undo = {block: schedule.get(block)}
        if block in schedule and rng.random() < 0.5:
            del schedule[block]
        else:
            schedule[block] = rng.choice(candidates[block])
        return undo


class ShiftOperator(_OperatorBase):
    """Rechoose a block's chain (a different rotation sequence)."""

    name = "shift"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Rechoose one assigned block's chain, in place."""
        if not schedule:
            return None
        blocks, rechoosable = _index(candidates)
        for _ in range(12):
            block = rng.choice(blocks)
            current = schedule.get(block)
            if current and block in rechoosable:
                schedule[block] = rng.choice(rechoosable[block])
                return {block: current}
        assigned = [block for block, chain in schedule.items() if chain and block in rechoosable]
        if not assigned:
            return None
        block = rng.choice(assigned)
        current = schedule[block]
        schedule[block] = rng.choice(rechoosable[block])
        return {block: current}


class SwapOperator(_OperatorBase):
    """Exchange the chains of two blocks."""

    name = "swap"

    def __init__(self, weight: float = 0.5) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Exchange two assigned blocks' chains, in place."""
        if len(schedule) < 2:
            return None
        blocks, _ = _index(candidates)
        first: int | None = None
        second: int | None = None
        for _ in range(24):
            block = rng.choice(blocks)
            if block not in schedule:
                continue
            if first is None:
                first = block
            elif block != first:
                second = block
                break
        if first is None or second is None:
            return None
        first_chain = schedule[first]
        schedule[first], schedule[second] = schedule[second], first_chain
        return {first: first_chain, second: schedule[first]}


class LnsOperator(_OperatorBase):
    """Large-neighbourhood search: rechoose a fraction of the schedule in one move.

    The destroyed blocks are sampled by rejection from the candidate blocks, so the move
    costs O(blocks touched) rather than O(schedule).
    """

    name = "lns"

    def __init__(self, weight: float = 0.2, destroy_fraction: float = 0.1) -> None:
        """Set the operator's selection weight and the fraction destroyed."""
        self.weight = weight
        self.destroy_fraction = destroy_fraction

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Rechoose a fraction of the schedule in place."""
        if not schedule:
            return None
        blocks, _ = _index(candidates)
        count = max(1, int(len(schedule) * self.destroy_fraction))
        chosen: set[int] = set()
        limit = count * 4 + 8
        tries = 0
        while len(chosen) < count and tries < limit:
            tries += 1
            block = rng.choice(blocks)
            if block in schedule:
                chosen.add(block)
        undo: Undo = {}
        for block in chosen:
            undo[block] = schedule.get(block)
            chains = candidates.get(block)
            if chains:
                schedule[block] = rng.choice(chains)
            else:
                schedule.pop(block, None)
        return undo


class ClusterOperator(_OperatorBase):
    """Rechoose a connected cluster of blocks — a patch-shaped move.

    Instead of scattering single blocks (toggle/shift) or random blocks (LNS), this grows a
    small connected set from a seed block along the topology and rechooses every block in it.
    Openings and patches are the decision objects in the harvest-adjacency literature, so a
    move along the topology explores coherent patch changes.
    """

    name = "cluster"

    def __init__(
        self,
        weight: float = 0.5,
        size: int = 8,
        neighbours: Mapping[int, tuple[int, ...]] | None = None,
    ) -> None:
        """Set the weight, the cluster size, and the topological neighbours per block."""
        self.weight = weight
        self.size = size
        self.neighbours = neighbours or {}

    def _grow(self, seed: int, rng: random.Random) -> list[int]:
        """Return a connected set of at most ``size`` blocks, grown from ``seed``."""
        chosen = [seed]
        seen = {seed}
        frontier = [seed]
        while frontier and len(chosen) < self.size:
            block = frontier.pop(rng.randrange(len(frontier)))
            options = list(self.neighbours.get(block, ()))
            rng.shuffle(options)
            for other in options:
                if other in seen:
                    continue
                seen.add(other)
                chosen.append(other)
                frontier.append(other)
                if len(chosen) >= self.size:
                    break
        return chosen

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Rechoose a connected cluster of blocks, in place."""
        blocks, _ = _index(candidates)
        if not blocks:
            return None
        seed = rng.choice(blocks)
        undo: Undo = {}
        for block in self._grow(seed, rng):
            options = candidates.get(block)
            if not options:
                continue
            undo[block] = schedule.get(block)
            schedule[block] = rng.choice(options)
        return undo or None


if TYPE_CHECKING:
    from .patch import PatchModel


class PatchSource(Protocol):
    """The patch state a move operator can consult."""

    def active_patch_model(self) -> PatchModel | None:
        """Return the patch model the current evaluator is maintaining."""


class MergeOperator(_OperatorBase):
    """Treat a gap block — the negative space between two patches — to join them."""

    name = "merge"

    def __init__(
        self,
        optimizer: PatchSource,
        *,
        weight: float = 0.3,
        samples: int = 6,
        chains: int = 8,
    ) -> None:
        """Set the weight, the gap sampling, and how many chains to try.

        Parameters
        ----------
        optimizer : PatchSource
            The optimizer, used to reach the live patch model.
        weight : float, optional
            The operator's selection weight. Defaults to 0.3.
        samples : int, optional
            The number of blocks to test for a gap per proposal. Defaults to 6.
        chains : int, optional
            The number of candidate chains to try per gap. Defaults to 8.
        """
        self.optimizer = optimizer
        self.weight = weight
        self.samples = samples
        self.chains = chains

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Assign a gap block a chain that makes it a member, in place."""
        model = self.optimizer.active_patch_model()
        if model is None or not model.groups or model.years <= 0:
            return None
        years = model.focus_years or tuple(range(model.years))
        year = years[rng.randrange(len(years))]
        gap = model.find_gap(year, rng, samples=self.samples)
        if gap is None:
            return None
        block, label, threshold = gap
        options = candidates.get(block)
        if not options:
            return None
        for chain in rng.sample(options, min(self.chains, len(options))):
            if model.value(block, chain, label, year) > threshold:
                undo: Undo = {block: schedule.get(block)}
                schedule[block] = chain
                return undo
        return None


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


__all__ = [
    "Candidates",
    "Chain",
    "ClusterOperator",
    "Event",
    "LnsOperator",
    "MergeOperator",
    "Operator",
    "OperatorRegistry",
    "PatchSource",
    "Schedule",
    "ShiftOperator",
    "SwapOperator",
    "ToggleOperator",
    "Undo",
    "restore",
]
