"""Move-based objective deltas.

A metaheuristic move changes one block, so the objective only changes where that block's
account values change. This module keeps the objective's *state* — the realized totals per
``(year, account)`` for the accounts the targets read — and prices a move by the difference
it makes, instead of recomputing the whole schedule.

The objective is separable across ``(year, account)`` cells: a target reads one cell, and the
penalty is a function of that cell's value. So the delta of a move is the sum, over the cells
the moved block touches, of ``penalty(after) - penalty(before)``. That is exact, and it costs
O(cells the block touches) rather than O(schedule x years x accounts).

Scope (M1): targets on raw feature/product accounts, with no route accounts, no duplicate
accounts, and no edge contrast. The optimizer falls back to whole-schedule evaluation for
anything else.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import pandas as pd

from .objective import Target, penalty
from .operators import Candidates, Chain, Schedule

if TYPE_CHECKING:
    from .engine import Optimizer

Cell = tuple[int, str]


class IncrementalObjective:
    """Exact objective deltas for single-block moves over raw account targets.

    Attributes
    ----------
    optimizer : Optimizer
        The optimizer that owns the caches this evaluator reuses.
    targets : list of Target
        The goals.
    accounts : set of str
        The account labels the targets read.
    totals : dict of (int, str) to float
        The realized total per ``(year, account)`` cell.
    assignments : dict of int to tuple of (str, int)
        The current schedule.
    """

    def __init__(
        self, optimizer: Optimizer, targets: Sequence[Target], extra_accounts: Sequence[str] = ()
    ) -> None:
        """Build the evaluator for a target set.

        Parameters
        ----------
        optimizer : Optimizer
            The optimizer (its block-delta cache is reused).
        targets : sequence of Target
            The goals.
        extra_accounts : sequence of str, optional
            Further accounts to track (for example, accounts a viewer displays); they do
            not affect the objective.
        """
        self.optimizer = optimizer
        self.targets = list(targets)
        self.accounts: set[str] = {target.account for target in self.targets} | set(extra_accounts)
        self.totals: dict[Cell, float] = {}
        self.assignments: Schedule = {}
        self._contributions: dict[tuple[int, Chain], dict[Cell, float]] = {}
        self._pending_move: tuple[dict[Cell, float], list[int], Schedule] | None = None
        self._targets_by_cell: dict[Cell, list[int]] = {}
        for index, target in enumerate(self.targets):
            for year in target.cell_years():
                self._targets_by_cell.setdefault((year, target.account), []).append(index)

    def reset(self, schedule: Schedule) -> None:
        """Set the state to the empty-schedule base plus the schedule's contributions.

        Parameters
        ----------
        schedule : dict of int to tuple of (str, int)
            The schedule to evaluate.
        """
        base = self.optimizer._base_values()
        self.totals = {cell: value for cell, value in base.items() if cell[1] in self.accounts}
        self.assignments = dict(schedule)
        for block, assignment in schedule.items():
            for cell, value in self._contribution(block, assignment).items():
                self.totals[cell] = self.totals.get(cell, 0.0) + value

    def _contribution(self, block: int, chain: Chain) -> dict[Cell, float]:
        """Return (and cache) a chain's tracked-cell contribution (feature, product, route)."""
        key = (block, chain)
        cached = self._contributions.get(key)
        if cached is not None:
            return cached
        contribution = {
            cell: value
            for cell, value in self.optimizer._block_delta(block, chain, self.accounts).items()
            if cell[1] in self.accounts and value != 0.0
        }
        for cell, value in self.optimizer._block_route_delta(block, chain).items():
            if cell[1] in self.accounts and value != 0.0:
                contribution[cell] = contribution.get(cell, 0.0) + value
        self._contributions[key] = contribution
        return contribution

    def warm(self, candidates: Candidates) -> None:
        """Precompute every candidate chain's contribution.

        The search then has no contribution misses, which suits long runs (the one-off cost
        is paid once instead of as misses scattered through the search).

        Parameters
        ----------
        candidates : dict of int to list of Chain
            The candidate chains per block.
        """
        for block, chains in candidates.items():
            for chain in chains:
                self._contribution(block, chain)

    def _pending(self, changed: Sequence[int], schedule: Schedule) -> dict[Cell, float]:
        """Return the per-cell change a move makes."""
        pending: dict[Cell, float] = {}
        for block in changed:
            old = self.assignments.get(block)
            new = schedule.get(block)
            if new is not None:
                for cell, value in self._contribution(block, new).items():
                    pending[cell] = pending.get(cell, 0.0) + value
            if old is not None:
                for cell, value in self._contribution(block, old).items():
                    pending[cell] = pending.get(cell, 0.0) - value
        return pending

    @property
    def objective(self) -> float:
        """Return the objective for the current state (periods summed)."""
        total = 0.0
        for target in self.targets:
            value = sum(
                self.totals.get((year, target.account), 0.0) for year in target.cell_years()
            )
            total += penalty(value, target)
        return total

    def delta(self, changed: Sequence[int], schedule: Schedule) -> float:
        """Return the exact objective change a move would make, without applying it.

        Parameters
        ----------
        changed : sequence of int
            The blocks the move changes.
        schedule : dict of int to tuple of (str, int)
            The schedule after the move.

        Returns
        -------
        float
            The objective after minus the objective before.
        """
        pending = self._pending(changed, schedule)
        self._pending_move = (pending, list(changed), schedule)
        if not pending:
            return 0.0
        affected: set[int] = set()
        for cell in pending:
            affected.update(self._targets_by_cell.get(cell, ()))
        total = 0.0
        for index in affected:
            target = self.targets[index]
            before = sum(
                self.totals.get((year, target.account), 0.0) for year in target.cell_years()
            )
            change = sum(pending.get((year, target.account), 0.0) for year in target.cell_years())
            total += penalty(before + change, target) - penalty(before, target)
        return total

    def apply(self, changed: Sequence[int], schedule: Schedule) -> None:
        """Apply a move to the state.

        Parameters
        ----------
        changed : sequence of int
            The blocks the move changes.
        schedule : dict of int to tuple of (str, int)
            The schedule after the move.
        """
        stored = self._pending_move
        if stored is not None and stored[2] is schedule and stored[1] == list(changed):
            pending, changed_blocks, _ = stored
        else:
            pending, changed_blocks = self._pending(changed, schedule), list(changed)
        self._pending_move = None
        for cell, value in pending.items():
            self.totals[cell] = self.totals.get(cell, 0.0) + value
        for block in changed_blocks:
            assignment = schedule.get(block)
            if assignment is None:
                self.assignments.pop(block, None)
            else:
                self.assignments[block] = assignment

    def values_frame(self) -> pd.DataFrame:
        """Return the tracked account values as a frame (``year``, ``account``, ``value``)."""
        rows = [
            {"year": year, "account": account, "value": value}
            for (year, account), value in self.totals.items()
        ]
        return pd.DataFrame(rows, columns=["year", "account", "value"])
