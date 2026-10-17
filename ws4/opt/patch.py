"""Patch size-distribution accounts for the optimizer, maintained incrementally.

Patch accounts are **non-additive**: a patch is a connected set of adjacent member blocks, so a
move changes the patches around the block it touches. This model keeps one
:class:`~ws4.opt.patch_state.PatchGroupYear` per criterion group and year — the components,
their areas and perimeters, and the per-size-class sums — and a move sets the changed blocks'
criterion values there, so only the affected years' aggregates move.

Each block's criterion series is cached per ``(block, chain)`` (it depends only on that
block's own chain), and the adjacency is indexed by block.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from ..patch.accounts import PatchAccount, load_patch_edges_detailed
from .operators import Chain, Schedule
from .patch_state import PatchGroupYear

if TYPE_CHECKING:
    from .engine import Optimizer

Cell = tuple[int, str]
GroupKey = tuple[str, float, float | None]

# A move changing more blocks than this rebuilds the affected years instead of updating each
# block in place (an LNS move touches hundreds).
_REBUILD_ABOVE = 8


class PatchModel:
    """The patch size-distribution accounts of an optimizer.

    Attributes
    ----------
    optimizer : Optimizer
        The optimizer (its topology and simulator are reused).
    accounts : tuple of PatchAccount
        The definitions.
    """

    def __init__(self, optimizer: Optimizer, accounts: Sequence[PatchAccount]) -> None:
        """Build the model: index the adjacency and group the accounts."""
        self.optimizer = optimizer
        self.accounts = tuple(accounts)
        self.years = optimizer.cfg.years
        self.area = optimizer._block_area()
        self.blocks = tuple(self.area)
        self._detailed = load_patch_edges_detailed(Path(optimizer.cfg.topology_path))
        self._adjacency: dict[float | None, dict[int, tuple[tuple[int, float], ...]]] = {}
        grouped: dict[tuple[str, float, float | None], list[PatchAccount]] = {}
        for account in self.accounts:
            key = (account.criteria, account.threshold, account.search_distance)
            grouped.setdefault(key, []).append(account)
        self.groups: dict[tuple[str, float, float | None], tuple[PatchAccount, ...]] = {
            key: tuple(value) for key, value in grouped.items()
        }
        self.labels = sorted({account.criteria for account in self.accounts})
        self._series: dict[tuple[int, Chain], dict[str, dict[int, float]]] = {}
        self.assignments: Schedule = {}
        self.focus_years: tuple[int, ...] = ()
        self.states: dict[tuple[GroupKey, int], PatchGroupYear] = {}
        self.values: dict[int, dict[str, float]] = {}
        self._undo_values: dict[int, dict[str, float]] = {}
        self._undo: list[tuple[PatchGroupYear, int, float | None]] = []
        self._untouched: dict[int, dict[str, float]] = {}

    def series(self, block: int, chain: Chain | None) -> dict[str, dict[int, float]]:
        """Return (and cache) a block chain's criterion series per label.

        An untreated block (``chain`` is None) keeps its inventory series, so the empty chain
        is a real, cacheable state rather than a zero.

        Parameters
        ----------
        block : int
            The block.
        chain : tuple or None
            The treatment chain, or None for an untreated block.

        Returns
        -------
        dict of str to dict of int to float
            The criterion value per label and year.
        """
        events: Chain = chain if chain is not None else ()
        key = (block, events)
        cached = self._series.get(key)
        if cached is None:
            simulator = self.optimizer.simulator()
            cached = {
                label: simulator.block_criteria_series(block, events, label, self.years)
                for label in self.labels
            }
            self._series[key] = cached
        return cached

    def _value(self, block: int, chain: Chain | None, label: str, year: int) -> float:
        """Return a block's criterion value in a year under a chain (None is untreated)."""
        return self.series(block, chain)[label].get(year, 0.0)

    def adjacency(self, search_distance: float | None) -> dict[int, tuple[tuple[int, float], ...]]:
        """Return (and cache) the block adjacency within a topology search distance.

        Only edges no longer than ``search_distance`` metres join blocks, so a patch stays
        within the neighbourhood the account defines.

        Parameters
        ----------
        search_distance : float or None
            The search distance, in metres; None keeps every edge.

        Returns
        -------
        dict of int to tuple of (int, float)
            The ``(neighbour, shared_length)`` pairs per block.
        """
        cached = self._adjacency.get(search_distance)
        if cached is None:
            index: dict[int, list[tuple[int, float]]] = {}
            for source, target, length, distance in self._detailed:
                if search_distance is not None and distance > search_distance:
                    continue
                index.setdefault(source, []).append((target, length))
                index.setdefault(target, []).append((source, length))
            cached = {block: tuple(items) for block, items in index.items()}
            self._adjacency[search_distance] = cached
        return cached

    def _state(self, key: GroupKey, year: int) -> PatchGroupYear:
        """Return (building once) a group's state for a year."""
        state = self.states.get((key, year))
        if state is None:
            state = PatchGroupYear(self.groups[key], key[1], self.adjacency(key[2]), self.area)
            self.states[(key, year)] = state
        return state

    def _cells(self, year: int) -> dict[str, float]:
        """Return a year's patch cells from the group states."""
        out: dict[str, float] = {}
        for key in self.groups:
            out.update(self._state(key, year).cells())
        return out

    def reset(self, schedule: Schedule) -> None:
        """Set the state to the schedule's patch accounts.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule.
        """
        self.assignments = dict(schedule)
        self.states = {}
        self.values = {}
        self._undo = []
        self._undo_values = {}
        self._untouched = {}
        series_by_block = {block: self.series(block, schedule.get(block)) for block in self.blocks}
        for year in range(self.years):
            for key in self.groups:
                label = key[0]
                threshold = key[1]
                members: dict[int, float] = {}
                for block in self.blocks:
                    value = series_by_block[block][label].get(year, 0.0)
                    if value > threshold:
                        members[block] = value
                self._state(key, year).rebuild(members)
            self.values[year] = self._cells(year)

    def _affected(self, changed: Sequence[int], schedule: Schedule) -> set[int]:
        """Return the years where a changed block's criterion differs."""
        affected: set[int] = set()
        for block in changed:
            old_series = self.series(block, self.assignments.get(block))
            new_series = self.series(block, schedule.get(block))
            for label in self.labels:
                old_values = old_series[label]
                new_values = new_series[label]
                for year in range(self.years):
                    if old_values.get(year, 0.0) != new_values.get(year, 0.0):
                        affected.add(year)
        return affected

    def _local_cells(
        self,
        year: int,
        changed: Sequence[int],
        schedule: Schedule,
        series_by_block: Mapping[int, dict[str, dict[int, float]]] | None = None,
    ) -> dict[str, float]:
        """Update a year's states for the changed blocks only, and return its cells."""
        if series_by_block is None:
            series_by_block = {block: self.series(block, schedule.get(block)) for block in changed}
        for key in self.groups:
            label = key[0]
            state = self._state(key, year)
            new_values = {block: series_by_block[block][label].get(year, 0.0) for block in changed}
            state.rebuild_local(changed, new_values)
        return self._cells(year)

    def set_focus_years(self, years: Sequence[int]) -> None:
        """Record the years the objective reads, so gap moves target them.

        Parameters
        ----------
        years : sequence of int
            The years the targets are accounted in.
        """
        self.focus_years = tuple(sorted(set(years)))

    def value(self, block: int, chain: Chain | None, label: str, year: int) -> float:
        """Return a block's criterion value in a year under a chain (None is untreated).

        Parameters
        ----------
        block : int
            The block.
        chain : tuple or None
            The treatment chain, or None for an untreated block.
        label : str
            The criterion feature label.
        year : int
            The year.

        Returns
        -------
        float
            The criterion value.
        """
        return self._value(block, chain, label, year)

    def find_gap(
        self, year: int, rng: random.Random, *, samples: int = 8
    ) -> tuple[int, str, float] | None:
        """Return ``(block, label, threshold)`` for a gap in ``year``, or None.

        A gap is a non-member block whose member-neighbours span two or more components, so treating
        it would join those patches. Sampling a few blocks keeps a proposal O(1) rather than a scan
        of the whole forest.

        Parameters
        ----------
        year : int
            The year to look in.
        rng : random.Random
            The random source.
        samples : int, optional
            The number of blocks to test. Defaults to 8.

        Returns
        -------
        tuple of (int, str, float) or None
            The gap block, the criterion label, and the threshold, or None if none was found.
        """
        if not self.groups or not self.blocks:
            return None
        for key in self.groups:
            label, threshold, _ = key
            state = self._state(key, year)
            blocks = state.blocks
            for _ in range(samples):
                block = blocks[rng.randrange(len(blocks))]
                if state.is_gap(state.index[block]):
                    return block, label, threshold
        return None

    def pending(self, changed: Sequence[int], schedule: Schedule) -> dict[Cell, float]:
        """Apply a move to the states and return the patch-cell change.

        The change can be undone with :meth:`revert` (until :meth:`commit`). A small move
        updates each changed block's value in place; a large one (an LNS move) rebuilds the
        affected years, which is cheaper than hundreds of local updates.

        Parameters
        ----------
        changed : sequence of int
            The blocks the move changes.
        schedule : dict of int to Chain
            The schedule after the move.

        Returns
        -------
        dict of (int, str) to float
            The change per ``(year, account)`` cell.
        """
        self._undo = []
        self._undo_values = {}
        self._rebuilt = []
        self._changed = list(changed)
        self._affected_years = sorted(self._affected(changed, schedule))
        merged: dict[Cell, float] = {}
        bulk = len(changed) > _REBUILD_ABOVE
        # the new chain's series is the same for every affected year, so look it up once
        series_by_block = {block: self.series(block, schedule.get(block)) for block in changed}
        for year in self._affected_years:
            if bulk:
                cells = self._local_cells(year, changed, schedule, series_by_block)
                self._rebuilt.append(year)
            else:
                for key in self.groups:
                    label = key[0]
                    state = self._state(key, year)
                    for block in changed:
                        previous = state.value_of(block)
                        self._undo.append((state, block, previous))
                        state.set_value(block, series_by_block[block][label].get(year, 0.0))
                cells = self._cells(year)
            previous_cells = self.values.get(year, {})
            self._undo_values[year] = previous_cells
            for name in set(previous_cells) | set(cells):
                difference = cells.get(name, 0.0) - previous_cells.get(name, 0.0)
                if difference:
                    merged[(year, name)] = difference
            self.values[year] = cells
        return merged

    def revert(self) -> None:
        """Undo a :meth:`pending` move that was not committed."""
        for state, block, previous in self._undo:
            state.set_value(block, previous)
        for year in self._rebuilt:
            self._local_cells(year, self._changed, self.assignments)
        for year, cells in self._undo_values.items():
            self.values[year] = cells
        self._undo = []
        self._rebuilt = []
        self._undo_values = {}

    def commit(self, changed: Sequence[int], schedule: Schedule) -> None:
        """Apply a move to the model.

        Parameters
        ----------
        changed : sequence of int
            The blocks the move changes.
        schedule : dict of int to Chain
            The schedule after the move.
        """
        for block in changed:
            assignment = schedule.get(block)
            if assignment is None:
                self.assignments.pop(block, None)
            else:
                self.assignments[block] = assignment
        self._undo = []
        self._undo_values = {}
        self._untouched = {}

    def cell_map(self) -> dict[Cell, float]:
        """Return the current patch cells as a ``(year, account) -> value`` mapping."""
        result: dict[Cell, float] = {}
        for year, cells in self.values.items():
            for account, value in cells.items():
                result[(year, account)] = value
        return result
