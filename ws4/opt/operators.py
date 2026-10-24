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
    """A neighbourhood move.

    Operators are selected by weight, so a registry turns a mix of operators into a single
    proposal distribution. A move that cannot be made returns None and is not counted.

    Attributes
    ----------
    name : str
        The operator name, as it appears in the run summary.
    weight : float
        The relative probability of selecting the operator.
    """

    name: str
    weight: float

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Mutate the schedule and return the previous chains, or None to move.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The previous chain per touched block (None means the block was absent), or None
            when the operator cannot move.
        """

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Return a modified copy and the blocks it changed, or None.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to copy and modify.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        tuple or None
            ``(schedule, changed)``, or None when the operator cannot move.
        """

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Return a modified copy, or None if the operator cannot move.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to copy and modify.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The modified copy, or None when the operator cannot move.
        """


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
    """Assign a candidate chain to a block, or clear an assigned block.

    The block is drawn uniformly from the assignable blocks. An assigned block is cleared
    with probability one half, otherwise it takes a randomly chosen candidate chain.

    Parameters
    ----------
    weight : float, optional
        The operator's selection weight. Defaults to 1.0.
    """

    name = "toggle"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Toggle one block in place.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The previous chain of the touched block, or None when no block can be assigned.
        """
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
    """Rechoose a block's chain (a different rotation sequence).

    Only blocks with more than one candidate chain can move. The block is drawn from the
    assignable blocks, retrying a bounded number of times before falling back to a block
    that is already assigned.

    Parameters
    ----------
    weight : float, optional
        The operator's selection weight. Defaults to 1.0.
    """

    name = "shift"

    def __init__(self, weight: float = 1.0) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Rechoose one assigned block's chain, in place.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The previous chain of the touched block, or None when no block can be rechosen.
        """
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
    """Exchange the chains of two blocks.

    Both blocks must already be assigned, so the move leaves the set of assigned blocks
    unchanged and only exchanges their chains.

    Parameters
    ----------
    weight : float, optional
        The operator's selection weight. Defaults to 0.5.
    """

    name = "swap"

    def __init__(self, weight: float = 0.5) -> None:
        """Set the operator's selection weight."""
        self.weight = weight

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Exchange two assigned blocks' chains, in place.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The previous chain of each exchanged block, or None when two assigned blocks
            cannot be found.
        """
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

    Parameters
    ----------
    weight : float, optional
        The operator's selection weight. Defaults to 0.2.
    destroy_fraction : float, optional
        The fraction of the assigned blocks to destroy and repair. Defaults to 0.1.
    """

    name = "lns"

    def __init__(self, weight: float = 0.2, destroy_fraction: float = 0.1) -> None:
        """Set the operator's selection weight and the fraction destroyed."""
        self.weight = weight
        self.destroy_fraction = destroy_fraction

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Rechoose a fraction of the schedule in place.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The previous chain per destroyed block, or None when the schedule is empty.
        """
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

    Parameters
    ----------
    weight : float, optional
        The operator's selection weight. Defaults to 0.5.
    size : int, optional
        The maximum number of blocks in the cluster. Defaults to 8.
    neighbours : mapping of int to tuple of int, optional
        The topological neighbours per block. An empty map leaves every cluster a single
        block, so the move degrades to a rechoose.
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
        """Rechoose a connected cluster of blocks, in place.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The previous chain per touched block, or None when no block can be assigned.
        """
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


class CoalesceOperator(_OperatorBase):
    """Align a connected cluster onto one treatment year, within an area band.

    The cluster and merge operators change which blocks are assigned, but a large
    opening also needs its blocks treated in the **same year** and its total area
    inside the policy band. This operator grows a connected cluster until its
    criterion-weighted area reaches ``min_area_ha`` (without exceeding
    ``max_area_ha``), takes a target year from the seed block, and rechooses every
    member onto a candidate chain that treats it in that year.

    Parameters
    ----------
    optimizer : PatchSource
        The optimizer, used to read the active patch criterion and block areas.
    weight : float, optional
        The operator's selection weight. Defaults to 0.2.
    size : int, optional
        The maximum number of blocks in the cluster. Defaults to 8.
    min_area_ha : float, optional
        The smallest opening area the move will build. Defaults to 5 ha.
    max_area_ha : float, optional
        The largest opening area the move will build. Defaults to 40 ha.
    neighbours : mapping of int to tuple of int, optional
        The topological neighbours per block. An empty map leaves every cluster a
        single block, so the move is unavailable.
    """

    name = "coalesce"

    def __init__(
        self,
        optimizer: PatchSource,
        *,
        weight: float = 0.2,
        size: int = 8,
        min_area_ha: float = 5.0,
        max_area_ha: float = 40.0,
        neighbours: Mapping[int, tuple[int, ...]] | None = None,
    ) -> None:
        """Set the optimizer, weight, cluster size, area band and neighbours."""
        if min_area_ha < 0.0 or max_area_ha <= min_area_ha:
            raise ValueError("coalesce requires 0 <= min_area_ha < max_area_ha")
        self.optimizer = optimizer
        self.weight = weight
        self.size = size
        self.min_area_ha = min_area_ha
        self.max_area_ha = max_area_ha
        self.neighbours = neighbours or {}

    def _area(
        self,
        block: int,
        chain: Chain,
        label: str | None,
        year: int,
        block_area: Mapping[int, float],
        model: object | None,
    ) -> float:
        """Return the criterion-weighted area a chain contributes in a year."""
        area = float(block_area.get(block, 0.0))
        if label is None or model is None:
            return area
        value = model.value(block, chain, label, year)  # type: ignore[attr-defined]
        return max(0.0, area * float(value))

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Align a connected cluster to one treatment year, in place.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The previous chain per touched block, or None when no opening in the area
            band can be built.
        """
        assignable = [block for block, options in candidates.items() if options]
        if not assignable:
            return None
        model = self.optimizer.active_patch_model()
        labels = tuple(getattr(model, "labels", ())) if model is not None else ()
        label = labels[0] if labels else None
        block_area = self.optimizer._block_area()  # type: ignore[attr-defined]

        seed = rng.choice(assignable)
        seed_chain = schedule.get(seed)
        if seed_chain:
            target_year = int(seed_chain[0][1])
        else:
            seed_options = [chain for chain in candidates.get(seed, ()) if chain]
            if not seed_options:
                return None
            target_year = int(rng.choice(seed_options)[0][1])

        def options_at_year(block: int) -> list[Chain]:
            return [
                chain
                for chain in candidates.get(block, ())
                if chain and any(int(year) == target_year for _, year in chain)
            ]

        seed_options = options_at_year(seed)
        if not seed_options:
            return None
        chosen: dict[int, Chain] = {seed: rng.choice(seed_options)}
        total = self._area(seed, chosen[seed], label, target_year, block_area, model)
        if total > self.max_area_ha:
            return None
        seen = {seed}
        frontier = list(self.neighbours.get(seed, ()))
        while total < self.min_area_ha and frontier and len(chosen) < self.size:
            block = frontier.pop(rng.randrange(len(frontier)))
            if block in seen or block in chosen:
                continue
            seen.add(block)
            options = options_at_year(block)
            if not options:
                continue
            choice = rng.choice(options)
            area = self._area(block, choice, label, target_year, block_area, model)
            if area <= 0.0 or total + area > self.max_area_ha:
                continue
            chosen[block] = choice
            total += area
            frontier.extend(other for other in self.neighbours.get(block, ()) if other not in seen)
        if total < self.min_area_ha:
            return None

        undo: Undo = {}
        for block, choice in chosen.items():
            if schedule.get(block) == choice:
                continue
            undo[block] = schedule.get(block)
            schedule[block] = choice
        if not undo:
            return None
        return undo


if TYPE_CHECKING:
    from .patch import PatchModel


class PatchSource(Protocol):
    """The patch state a move operator can consult.

    The patch model is owned by the evaluator, not by the operator, so an operator reaches it
    through this narrow interface rather than holding a reference to a mutable model.
    """

    def active_patch_model(self) -> PatchModel | None:
        """Return the patch model the current evaluator is maintaining.

        Returns
        -------
        PatchModel or None
            The live model, or None when no patch account is being evaluated.
        """


class MergeOperator(_OperatorBase):
    """Treat a gap block — the negative space between two patches — to join them.

    The negative space between two proximal patches is where a patch target is cheapest to
    improve: a block that is one criterion short of membership joins two patches instead of
    scattering harvest. The operator asks the live patch model for such a gap block and tries
    a bounded number of candidate chains that push it over the membership threshold.

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
        """Assign a gap block a chain that makes it a member, in place.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block.

        Returns
        -------
        dict of int to Chain or None
            The previous chain of the gap block, or None when no gap or chain is found.
        """
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


class SplitOperator(_OperatorBase):
    """Untreat an articulation block, splitting its patch.

    An articulation point sits between two parts of a patch, so clearing it separates them
    and can move area out of an over-large size class. The operator walks the live patch
    model for such a block and clears it. The default weight is zero, so the operator ships
    disabled until a configuration enables it.

    Parameters
    ----------
    optimizer : PatchSource
        The optimizer, used to reach the live patch model.
    weight : float, optional
        The operator's selection weight. Defaults to 0.0.
    samples : int, optional
        The number of blocks to test for an articulation point. Defaults to 6.
    """

    name = "split"

    def __init__(
        self,
        optimizer: PatchSource,
        *,
        weight: float = 0.0,
        samples: int = 6,
    ) -> None:
        """Set the weight and how many blocks to test per proposal.

        Parameters
        ----------
        optimizer : PatchSource
            The optimizer, used to reach the live patch model.
        weight : float, optional
            The operator's selection weight. Defaults to 0.0.
        samples : int, optional
            The number of blocks to test for an articulation point. Defaults to 6.
        """
        self.optimizer = optimizer
        self.weight = weight
        self.samples = samples

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Undo | None:
        """Untreat a block that will split its patch, in place.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule to mutate in place.
        rng : random.Random
            The random source.
        candidates : dict of int to list of Chain
            The candidate chains per block (unused: the move clears an assignment).

        Returns
        -------
        dict of int to Chain or None
            The previous chain of the articulation block, or None when none is found.
        """
        model = self.optimizer.active_patch_model()
        if model is None or not model.groups or model.years <= 0:
            return None
        years = model.focus_years or tuple(range(model.years))
        year = years[rng.randrange(len(years))]
        for key in model.groups:
            state = model._state(key, year)
            blocks = state.blocks
            for _ in range(self.samples):
                block = blocks[rng.randrange(len(blocks))]
                if block not in schedule:
                    continue
                if state.is_cut(state.index[block]):
                    undo: Undo = {block: schedule.get(block)}
                    schedule.pop(block, None)
                    return undo
        return None


class OperatorRegistry:
    """A weighted set of operators.

    Parameters
    ----------
    operators : list of Operator, optional
        The operators to choose between. When None, a default set of toggle, shift, swap and
        LNS is used.
    """

    def __init__(self, operators: list[Operator] | None = None) -> None:
        """Store the operators (a default set when none is given)."""
        self._operators: list[Operator] = (
            operators
            if operators is not None
            else [ToggleOperator(), ShiftOperator(), SwapOperator(), LnsOperator()]
        )

    @property
    def operators(self) -> list[Operator]:
        """Return the registered operators in selection order.

        Returns
        -------
        list of Operator
            A copy of the operator list.
        """
        return list(self._operators)

    def names(self) -> list[str]:
        """Return the operator names.

        Returns
        -------
        list of str
            The names, in registration order.
        """
        return [operator.name for operator in self._operators]

    def weights(self) -> dict[str, float]:
        """Return the operator weights by name.

        Returns
        -------
        dict of str to float
            The selection weight per operator name.
        """
        return {operator.name: operator.weight for operator in self._operators}

    def pick(self, rng: random.Random) -> Operator:
        """Return a weighted-random operator.

        Parameters
        ----------
        rng : random.Random
            The random source.

        Returns
        -------
        Operator
            The chosen operator.
        """
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
    "SplitOperator",
    "SwapOperator",
    "ToggleOperator",
    "Undo",
    "restore",
]
