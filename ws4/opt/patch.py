"""Patch size-distribution accounts for the optimizer, maintained incrementally.

Patch accounts are **non-additive**: a patch is a connected set of adjacent member blocks, so
a move changes the patches around the block it touches. This model keeps, per year, the
member set and the patch sub-account values, and a move recomputes only the years where a
changed block's criterion differs.

Two things make that affordable:

- each block's criterion series is cached per ``(block, chain)`` — it depends only on that
  block's own chain, never on the rest of the schedule;
- the adjacency is indexed by block, so a period costs O(members x degree) instead of a
  full scan of the topology's edges.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..patch.accounts import PatchAccount, patch_account_values_indexed
from .operators import Chain, Schedule

if TYPE_CHECKING:
    from .engine import Optimizer

Cell = tuple[int, str]


@dataclass
class _Pending:
    """A move's affected years and the recomputed cells for each."""

    years: set[int] = field(default_factory=set)
    cells: dict[int, dict[str, float]] = field(default_factory=dict)


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
        neighbours: dict[int, list[tuple[int, float]]] = {}
        for source, target, length in optimizer._graph():
            neighbours.setdefault(source, []).append((target, length))
            neighbours.setdefault(target, []).append((source, length))
        self.neighbours = {block: tuple(items) for block, items in neighbours.items()}
        self.groups: dict[tuple[str, float], list[PatchAccount]] = {}
        for account in self.accounts:
            self.groups.setdefault((account.criteria, account.threshold), []).append(account)
        self.labels = sorted({account.criteria for account in self.accounts})
        self._series: dict[tuple[int, Chain], dict[str, dict[int, float]]] = {}
        self.assignments: Schedule = {}
        self.members: dict[int, frozenset[int]] = {}
        self.values: dict[int, dict[str, float]] = {}
        self._pending: _Pending | None = None

    def series(self, block: int, chain: Chain) -> dict[str, dict[int, float]]:
        """Return (and cache) a block chain's criterion series per label."""
        key = (block, chain)
        cached = self._series.get(key)
        if cached is None:
            simulator = self.optimizer.simulator()
            cached = {
                label: simulator.block_criteria_series(block, chain, label, self.years)
                for label in self.labels
            }
            self._series[key] = cached
        return cached

    def _year(self, year: int, assignments: Schedule) -> tuple[frozenset[int], dict[str, float]]:
        """Compute one year's member set and patch cells."""
        cells: dict[str, float] = {}
        members: set[int] = set()
        for (label, threshold), accounts in self.groups.items():
            values: dict[int, float] = {}
            for block, chain in assignments.items():
                value = self.series(block, chain)[label].get(year, 0.0)
                if value > threshold:
                    values[block] = value
                    members.add(block)
            for account in accounts:
                for key, value in patch_account_values_indexed(
                    account, values, self.neighbours, self.area
                ).items():
                    cells[f"{account.name}.{key}"] = value
        return frozenset(members), cells

    def reset(self, schedule: Schedule) -> None:
        """Set the state to the schedule's patch accounts.

        Parameters
        ----------
        schedule : dict of int to Chain
            The schedule.
        """
        self.assignments = dict(schedule)
        self.members = {}
        self.values = {}
        for year in range(self.years):
            members, cells = self._year(year, self.assignments)
            self.members[year] = members
            self.values[year] = cells
        self._pending = None

    def _affected(self, changed: Sequence[int], schedule: Schedule) -> set[int]:
        """Return the years where a changed block's criterion differs."""
        affected: set[int] = set()
        for block in changed:
            old = self.assignments.get(block)
            new = schedule.get(block)
            old_series = self.series(block, old) if old is not None else None
            new_series = self.series(block, new) if new is not None else None
            for label in self.labels:
                old_values = old_series[label] if old_series is not None else {}
                new_values = new_series[label] if new_series is not None else {}
                for year in range(self.years):
                    if old_values.get(year, 0.0) != new_values.get(year, 0.0):
                        affected.add(year)
        return affected

    def pending(self, changed: Sequence[int], schedule: Schedule) -> dict[Cell, float]:
        """Return the patch-cell change a move makes, without applying it.

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
        pending = _Pending()
        merged: dict[Cell, float] = {}
        for year in self._affected(changed, schedule):
            members, cells = self._year(year, schedule)
            pending.years.add(year)
            pending.cells[year] = cells
            old = self.values.get(year, {})
            for key in set(old) | set(cells):
                difference = cells.get(key, 0.0) - old.get(key, 0.0)
                if difference:
                    merged[(year, key)] = difference
            del members
        self._pending = pending
        return merged

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
        pending = self._pending
        if pending is None:
            self.pending(changed, schedule)
            pending = self._pending
        assert pending is not None
        for year in pending.years:
            self.values[year] = pending.cells[year]
        self._pending = None

    def cell_map(self) -> dict[Cell, float]:
        """Return the current patch cells as a ``(year, account) -> value`` mapping."""
        result: dict[Cell, float] = {}
        for year, cells in self.values.items():
            for account, value in cells.items():
                result[(year, account)] = value
        return result
