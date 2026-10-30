"""Move-based objective deltas.

A metaheuristic move changes one block, so the objective only changes where that block's
account values change. This module keeps the objective's *state* — the realized totals per
``(year, account)`` for the accounts the targets read — and prices a move by the difference
it makes, instead of recomputing the whole schedule.

The objective is separable across ``(year, account)`` cells: a target reads one cell, and the
penalty is a function of that cell's value. So the delta of a move is the sum, over the cells
the moved block touches, of ``penalty(after) - penalty(before)``. That is exact, and it costs
O(cells the block touches) rather than O(schedule x years x accounts).

Route accounts are additive and are priced the same way. Patch size-distribution
accounts are non-additive and are priced through a :class:`PatchModel`; the
opening, green-up and core-area penalties are priced through
:class:`SpatialPenaltyModel`. The optimizer falls back to whole-schedule
evaluation only for build-route, edge-contrast or spread accounts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

import pandas as pd

from .objective import Target, accumulates, flow_penalty, penalty, priority_total
from .operators import Candidates, Chain, Schedule
from .patch import PatchModel
from .spatial import SpatialPenaltyModel

if TYPE_CHECKING:
    from ..patch.accounts import PatchAccount
    from .engine import Optimizer

Cell = tuple[int, str]


class IncrementalObjective:
    """Exact objective deltas for single-block moves over raw account targets.

    The evaluator holds the running account totals, so a move is priced by its exact delta
    rather than by recomputing the whole schedule. Patch accounts are not additive, so they
    are priced separately through a :class:`PatchModel`; the spatial rules are priced
    through a :class:`SpatialPenaltyModel`.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer that owns the caches this evaluator reuses.
    targets : sequence of Target
        The goals.
    extra_accounts : sequence of str, optional
        Further accounts to track (for example, accounts a viewer displays); they do not
        affect the objective.
    patch_accounts : sequence of PatchAccount, optional
        Patch size-distribution accounts, priced by a patch model.

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
        self,
        optimizer: Optimizer,
        targets: Sequence[Target],
        extra_accounts: Sequence[str] = (),
        patch_accounts: Sequence[PatchAccount] = (),
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
        patch_accounts : sequence of PatchAccount, optional
            Patch size-distribution accounts, evaluated by a :class:`PatchModel` (they are
            non-additive, so they are priced separately).
        """
        self.optimizer = optimizer
        self.targets = [target for target in targets if target.active]
        self.patch = PatchModel(optimizer, patch_accounts) if patch_accounts else None
        self.spatial = SpatialPenaltyModel(optimizer)
        optimizer.set_active_patch_model(self.patch)
        patch_names = {account.name for account in patch_accounts}

        def is_patch(name: str) -> bool:
            return any(name == stem or name.startswith(f"{stem}.") for stem in patch_names)

        if self.patch is not None:
            # patch statistics are only needed where a patch target reads them (the accounting
            # points); the simulation is annual but the accounting is periodic
            self.patch.set_focus_years(
                sorted({target.end_offset() for target in self.targets if is_patch(target.account)})
            )

        self.accounts: set[str] = {
            target.account for target in self.targets if not is_patch(target.account)
        } | {name for name in extra_accounts if not is_patch(name)}
        self.totals: dict[Cell, float] = {}
        self.assignments: Schedule = {}
        self._contributions: dict[tuple[int, Chain], dict[Cell, float]] = {}
        self._pending_move: tuple[dict[Cell, float], list[int], Schedule] | None = None
        # A level — a patch account, or any feature — is a state of the map at one point in time,
        # so a target on one is read at its period's end (the accounting is periodic while the
        # simulation is annual), which is the reference's convention. An accumulating account sums
        # its period. A flow target aggregates whole periods across its window, so it tracks every
        # year of that window.
        horizon = optimizer.cfg.years

        def years_for(target: Target) -> tuple[int, ...]:
            if target.flow:
                stop = target.flow_end if target.flow_end is not None else horizon
                return tuple(range(target.flow_start, stop))
            if not accumulates(target.account):
                return (target.end_offset(),)
            return tuple(target.cell_offsets())

        self._target_offsets: list[tuple[int, ...]] = [years_for(target) for target in self.targets]
        self._targets_by_cell: dict[Cell, list[int]] = {}
        for index, target in enumerate(self.targets):
            for year in self._target_offsets[index]:
                self._targets_by_cell.setdefault((year, target.account), []).append(index)

    def reset(self, schedule: Schedule) -> None:
        """Set the state to the empty-schedule base plus the schedule's contributions.

        Parameters
        ----------
        schedule : dict of int to tuple of (str, int)
            The schedule to evaluate.
        """
        carbon_names = {name for name in self.accounts if name.startswith("carbon.")}
        carbon = self.optimizer.carbon_ledger() if carbon_names else None
        base = (
            self.optimizer._simulator_base_values()
            if self.optimizer.carbon_ledger() is not None
            else self.optimizer._base_values()
        )
        self.totals = {cell: value for cell, value in base.items() if cell[1] in self.accounts}
        self.assignments = dict(schedule)
        for block, assignment in schedule.items():
            if carbon is None:
                contribution = self.contribution(block, assignment)
            else:
                contribution = {
                    cell: value
                    for cell, value in self.optimizer._simulator_block_delta(
                        block, assignment
                    ).items()
                    if cell[1] in self.accounts and not cell[1].startswith("carbon.")
                }
                for cell, value in self.optimizer._block_route_delta(block, assignment).items():
                    if cell[1] in self.accounts:
                        contribution[cell] = contribution.get(cell, 0.0) + value
            for cell, value in contribution.items():
                self.totals[cell] = self.totals.get(cell, 0.0) + value
        if carbon is not None:
            for cell, value in carbon.schedule_values(schedule, carbon_names).items():
                self.totals[cell] = value
        if self.patch is not None:
            self.patch.reset(schedule)
            for cell, value in self.patch.cell_map().items():
                self.totals[cell] = self.totals.get(cell, 0.0) + value
        self.spatial.reset(schedule)

    def contribution(self, block: int, chain: Chain) -> dict[Cell, float]:
        """Return (and cache) a chain's tracked-cell contribution (feature, product, route).

        Parameters
        ----------
        block : int
            The block.
        chain : tuple of (str, int)
            The treatment chain.

        Returns
        -------
        dict of (int, str) to float
            The value this chain would add to each tracked cell, relative to leaving the block
            untreated. Cached, so a caller may ask repeatedly, which is what a schedule built by
            construction needs.
        """
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
                self.contribution(block, chain)

    def revert(self) -> None:
        """Undo a move's patch and spatial changes that were not committed."""
        if self.patch is not None:
            self.patch.revert()
        self.spatial.revert()

    def _pending(self, changed: Sequence[int], schedule: Schedule) -> dict[Cell, float]:
        """Return the per-cell change a move makes."""
        pending: dict[Cell, float] = {}
        for block in changed:
            old = self.assignments.get(block)
            new = schedule.get(block)
            if new is not None:
                for cell, value in self.contribution(block, new).items():
                    pending[cell] = pending.get(cell, 0.0) + value
            if old is not None:
                for cell, value in self.contribution(block, old).items():
                    pending[cell] = pending.get(cell, 0.0) - value
        if self.patch is not None:
            for cell, value in self.patch.pending(changed, schedule).items():
                pending[cell] = pending.get(cell, 0.0) + value
        return pending

    def _terms(self, totals: Mapping[Cell, float] | None = None) -> list[float]:
        """Return the current penalty per target.

        Parameters
        ----------
        totals : mapping of (int, str) to float or None, optional
            Account totals to price. Defaults to the evaluator's current totals.

        Returns
        -------
        list of float
            One normalized penalty per active target.
        """
        values = self.totals if totals is None else totals
        penalties: list[float] = []
        for index, target in enumerate(self.targets):
            if target.flow:
                penalties.append(flow_penalty(values, target, self.optimizer.cfg.years))
                continue
            value = sum(
                values.get((year, target.account), 0.0) for year in self._target_offsets[index]
            )
            penalties.append(penalty(value, target))
        return penalties

    @property
    def objective(self) -> float:
        """Return the objective for the current state (periods summed).

        Returns
        -------
        float
            The total weighted penalty.
        """
        return priority_total(self.targets, self._terms()) + self.spatial.objective

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
            return self.spatial.delta(changed, schedule)
        if len({target.priority for target in self.targets}) > 1:
            after_totals = dict(self.totals)
            for cell, value in pending.items():
                after_totals[cell] = after_totals.get(cell, 0.0) + value
            before_total = priority_total(self.targets, self._terms())
            after_total = priority_total(self.targets, self._terms(after_totals))
            return after_total - before_total + self.spatial.delta(changed, schedule)
        affected: set[int] = set()
        for cell in pending:
            affected.update(self._targets_by_cell.get(cell, ()))
        total = 0.0
        for index in affected:
            target = self.targets[index]
            if target.flow:
                horizon = self.optimizer.cfg.years
                before = flow_penalty(self.totals, target, horizon)
                after = flow_penalty(self.totals, target, horizon, pending)
                total += after - before
                continue
            if accumulates(target.account):
                before = sum(
                    self.totals.get((year, target.account), 0.0) for year in target.cell_offsets()
                )
                change = sum(
                    pending.get((year, target.account), 0.0) for year in target.cell_offsets()
                )
            else:
                before = self.totals.get((target.end_offset(), target.account), 0.0)
                change = pending.get((target.end_offset(), target.account), 0.0)
            total += penalty(before + change, target) - penalty(before, target)
        return total + self.spatial.delta(changed, schedule)

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
        if self.patch is not None:
            self.patch.commit(changed, schedule)
        self.spatial.apply(changed, schedule)

    def values_frame(self) -> pd.DataFrame:
        """Return the tracked account values as a frame (``offset``, ``account``, ``value``).

        Returns
        -------
        pandas.DataFrame
            One row per tracked ``(offset, account)`` cell.
        """
        rows = [
            {"offset": offset, "account": account, "value": value}
            for (offset, account), value in self.totals.items()
        ]
        return pd.DataFrame(rows, columns=["offset", "account", "value"])
