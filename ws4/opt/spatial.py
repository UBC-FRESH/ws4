"""Move-based spatial penalties over the block topology.

The opening, green-up and core-area rules are not separable per ``(year, account)``
cell: an opening is a connected component of blocks disturbed in one year, and
green-up is a property of an adjacent pair. This module keeps the schedule's
disturbance state and prices a move by the exact local change:

* opening and core-area penalties are recomputed only for the years the moved
  blocks enter or leave;
* green-up is recomputed only on the edges incident to the moved blocks.

That is the spatial counterpart of :mod:`ws4.opt.incremental`, and the optimizer
uses it through the same move-based evaluator when the topology and rules are
configured.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING

from ..patch.constraints import core_area_penalty, spatial_penalty
from ..patch.metrics import connected_patches
from .operators import Schedule

if TYPE_CHECKING:
    from .engine import Optimizer

Edge = tuple[int, int]


class SpatialPenaltyModel:
    """The spatial part of the move-based objective.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer whose configuration and topology the model reads. The model reads
        block areas and the topology once and keeps the current disturbance state.
    """

    def __init__(self, optimizer: Optimizer) -> None:
        """Build the model and load the topology only when a spatial rule is active."""
        cfg = optimizer.cfg
        self.enabled = not cfg.allow_spatial_override and (
            cfg.max_opening_ha is not None
            or cfg.min_green_up_years is not None
            or (cfg.min_core_area_ha is not None and cfg.core_buffer_m is not None)
        )
        self.weight = float(cfg.spatial_weight)
        self.max_opening_ha = cfg.max_opening_ha
        self.min_green_up_years = cfg.min_green_up_years
        self.min_core_area_ha = cfg.min_core_area_ha
        self.core_buffer_m = cfg.core_buffer_m
        self.block_area: dict[int, float] = {}
        self.edges: list[tuple[int, int, float]] = []
        self.adjacency: list[Edge] = []
        self.edges_by_block: dict[int, list[tuple[int, int, float]]] = {}
        self.selected_by_year: dict[int, set[int]] = {}
        self.disturbance_years: dict[int, tuple[int, ...]] = {}
        self.assignments: Schedule = {}
        self._value = 0.0
        self._pending_value: float | None = None
        self._pending_assignments: Schedule | None = None
        self._pending_changed: tuple[int, ...] = ()
        if not self.enabled:
            return
        self.block_area = optimizer._block_area()
        if cfg.topology_path:
            self.edges = list(optimizer._graph())
            self.adjacency = [(source, target) for source, target, _ in self.edges]
            self.edges_by_block = optimizer._edges_by_block()

    @property
    def objective(self) -> float:
        """Return the current weighted spatial penalty.

        Returns
        -------
        float
            The weighted opening, green-up and core-area penalty.
        """
        return self._value

    def reset(self, schedule: Schedule) -> None:
        """Replace the model's state with ``schedule``.

        Parameters
        ----------
        schedule : dict of int to tuple of (str, int)
            The schedule to adopt as the current state.
        """
        self.assignments = dict(schedule)
        self.selected_by_year, self.disturbance_years = _state_for(schedule)
        self._value = self._value_for(self.selected_by_year, self.disturbance_years)
        self._clear_pending()

    def delta(self, changed: Sequence[int], schedule: Schedule) -> float:
        """Return the exact spatial penalty change a move would make.

        Parameters
        ----------
        changed : sequence of int
            The blocks the move changes.
        schedule : dict of int to tuple of (str, int)
            The schedule after the move.

        Returns
        -------
        float
            The weighted spatial penalty after minus before.
        """
        if not self.enabled:
            return 0.0
        changed = tuple(int(block) for block in changed)
        affected_years: set[int] = set()
        for block in changed:
            affected_years.update(self.disturbance_years.get(block, ()))
            affected_years.update(year for _, year in schedule.get(block, ()))
        after_selected = {year: set(self.selected_by_year.get(year, ())) for year in affected_years}
        after_years = {
            block: tuple(sorted({year for _, year in schedule.get(block, ())})) for block in changed
        }
        for block in changed:
            for year in self.disturbance_years.get(block, ()):
                after_selected.setdefault(year, set()).discard(block)
            for year in after_years[block]:
                after_selected.setdefault(year, set()).add(block)

        before = sum(
            self._year_penalty(year, self.selected_by_year.get(year, set()))
            for year in affected_years
        )
        after = sum(
            self._year_penalty(year, after_selected.get(year, set())) for year in affected_years
        )
        if self.min_green_up_years is not None:
            for source, target in self._incident_edges(changed):
                before += self._green_up_penalty(source, target, self.disturbance_years)
                source_years = (
                    after_years.get(source)
                    if source in after_years
                    else self.disturbance_years.get(source)
                )
                target_years = (
                    after_years.get(target)
                    if target in after_years
                    else self.disturbance_years.get(target)
                )
                after += self._green_up_penalty_from_years(source_years, target_years)
        total = self.weight * (after - before)
        self._pending_value = self._value + total
        self._pending_assignments = dict(schedule)
        self._pending_changed = changed
        return total

    def apply(self, changed: Sequence[int], schedule: Schedule) -> None:
        """Commit a move's spatial state.

        Parameters
        ----------
        changed : sequence of int
            The blocks the move changed.
        schedule : dict of int to tuple of (str, int)
            The schedule after the move.
        """
        if not self.enabled:
            return
        changed = tuple(int(block) for block in changed)
        if self._pending_assignments is not None and self._pending_changed == changed:
            self._value = float(self._pending_value or 0.0)
        else:
            self._value += self.delta(changed, schedule)
        for block in changed:
            for year in self.disturbance_years.get(block, ()):
                selected = self.selected_by_year.get(year)
                if selected is not None:
                    selected.discard(block)
                    if not selected:
                        self.selected_by_year.pop(year, None)
            years = tuple(sorted({year for _, year in schedule.get(block, ())}))
            if years:
                for year in years:
                    self.selected_by_year.setdefault(year, set()).add(block)
                self.disturbance_years[block] = years
            else:
                self.disturbance_years.pop(block, None)
        self.assignments = dict(schedule)
        if self._pending_assignments is None:
            self._value = self._value_for(self.selected_by_year, self.disturbance_years)
        self._clear_pending()

    def revert(self) -> None:
        """Discard a pending move's spatial changes."""
        self._clear_pending()

    def _clear_pending(self) -> None:
        """Clear the pending move state."""
        self._pending_value = None
        self._pending_assignments = None
        self._pending_changed = ()

    def _value_for(
        self,
        selected_by_year: Mapping[int, set[int]],
        disturbance_years: Mapping[int, tuple[int, ...]],
    ) -> float:
        """Return the weighted spatial penalty for a complete state."""
        if not self.enabled:
            return 0.0
        penalty = spatial_penalty(
            selected_by_year,
            disturbance_years,
            self.adjacency,
            self.block_area,
            self.max_opening_ha,
            self.min_green_up_years,
        )
        if self.min_core_area_ha is not None and self.core_buffer_m is not None:
            penalty += core_area_penalty(
                selected_by_year,
                self.edges,
                self.block_area,
                self.core_buffer_m,
                self.min_core_area_ha,
            )
        return self.weight * penalty

    def _year_penalty(self, year: int, selected: set[int]) -> float:
        """Return the opening and core-area penalty for one year's selected blocks."""
        if not selected:
            return 0.0
        penalty = 0.0
        if self.max_opening_ha is not None:
            for patch in connected_patches(selected, self.adjacency):
                area = sum(self.block_area.get(block, 0.0) for block in patch)
                if area > self.max_opening_ha:
                    penalty += area - self.max_opening_ha
        if self.min_core_area_ha is not None and self.core_buffer_m is not None:
            penalty += core_area_penalty(
                {year: selected},
                self.edges,
                self.block_area,
                self.core_buffer_m,
                self.min_core_area_ha,
            )
        return penalty

    def _incident_edges(self, blocks: Iterable[int]) -> set[Edge]:
        """Return the undirected adjacency edges incident to any of ``blocks``."""
        edges: set[Edge] = set()
        for block in blocks:
            for source, target, _ in self.edges_by_block.get(block, ()):
                edges.add((min(source, target), max(source, target)))
        return edges

    def _green_up_penalty(
        self,
        source: int,
        target: int,
        disturbance_years: Mapping[int, Sequence[int]],
    ) -> float:
        """Return the green-up penalty for one edge under ``disturbance_years``."""
        return self._green_up_penalty_from_years(
            disturbance_years.get(source),
            disturbance_years.get(target),
        )

    def _green_up_penalty_from_years(
        self,
        source_years: Sequence[int] | None,
        target_years: Sequence[int] | None,
    ) -> float:
        """Return the green-up penalty for one edge from its two disturbance lists."""
        if self.min_green_up_years is None or not source_years or not target_years:
            return 0.0
        gap = min(abs(int(a) - int(b)) for a in source_years for b in target_years)
        return max(0.0, float(self.min_green_up_years - gap))


def _state_for(schedule: Schedule) -> tuple[dict[int, set[int]], dict[int, tuple[int, ...]]]:
    """Return the selected blocks per year and disturbance years per block."""
    selected: dict[int, set[int]] = defaultdict(set)
    years: dict[int, list[int]] = defaultdict(list)
    for block, chain in schedule.items():
        for _, year in chain:
            selected[int(year)].add(int(block))
            years[int(block)].append(int(year))
    return (
        {year: set(blocks) for year, blocks in selected.items()},
        {block: tuple(sorted(set(items))) for block, items in years.items()},
    )
