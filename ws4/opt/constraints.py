"""Hard-feasibility policies for the spatial rules.

The optimizer's default is **penalize**: a spatial violation adds a weighted penalty to
the objective, so the search can trade it against the targets. Two opt-in policies make a
violation hard:

* **reject** refuses a move that would leave the schedule infeasible;
* **repair** first tries to keep the feasible part of the move — drop added blocks, restore
  removed ones — and rejects the move if the result is still infeasible.

The guard wraps the operator registry, so every engine sees the same policy. It counts
proposed, feasible, rejected, and repaired moves for the run summary. Feasibility is
evaluated over the full schedule, which is exact for a constrained subproblem; the default
``penalize`` policy remains the scalable path for a whole landscape.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from ..patch.constraints import (
    core_area_penalty,
    green_up_violations,
    opening_violations,
    schedule_years,
    spatial_penalty,
)
from ..patch.metrics import connected_patches, core_area, patch_perimeter
from .operators import Candidates, Operator, OperatorRegistry, Schedule, restore

if TYPE_CHECKING:
    from .engine import Optimizer


class ConstraintGuard:
    """Apply a hard-feasibility policy to every proposed operator move.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer whose configuration, topology, and block areas the guard reads.
    """

    def __init__(self, optimizer: Optimizer) -> None:
        """Build the guard and load the topology when a hard policy is active."""
        cfg = optimizer.cfg
        self.strategy = cfg.constraint_strategy
        self.max_opening_ha = cfg.max_opening_ha
        self.min_green_up_years = cfg.min_green_up_years
        self.min_core_area_ha = cfg.min_core_area_ha
        self.core_buffer_m = cfg.core_buffer_m
        self.enabled = (
            self.strategy != "penalize"
            and not cfg.allow_spatial_override
            and bool(cfg.topology_path)
            and (
                self.max_opening_ha is not None
                or self.min_green_up_years is not None
                or (self.min_core_area_ha is not None and self.core_buffer_m is not None)
            )
        )
        self.stats: Counter[str] = Counter(
            {"proposed": 0, "feasible": 0, "rejected": 0, "repaired": 0}
        )
        self.initial_removed = 0
        self.initial_repairs = 0
        self._block_area: dict[int, float] = {}
        self._edges: list[tuple[int, int, float]] = []
        self._adjacency: list[tuple[int, int]] = []
        self._edge_by_pair: dict[tuple[int, int], float] = {}
        self._edges_by_block: dict[int, list[tuple[int, int, float]]] = {}
        if not self.enabled:
            return
        self._block_area = optimizer._block_area()
        self._edges = list(optimizer._graph())
        self._adjacency = [(source, target) for source, target, _ in self._edges]
        self._edge_by_pair = {
            (min(source, target), max(source, target)): length
            for source, target, length in self._edges
        }
        self._edges_by_block = optimizer._edges_by_block()

    def wrap(self, registry: OperatorRegistry) -> OperatorRegistry:
        """Return a registry whose operators obey the guard.

        Parameters
        ----------
        registry : OperatorRegistry
            The base registry.

        Returns
        -------
        OperatorRegistry
            The wrapped registry, or the original when the policy is the default.
        """
        if not self.enabled:
            return registry
        return OperatorRegistry(
            [GuardedOperator(operator, self) for operator in registry.operators]
        )

    def consider(
        self, before: Mapping[int, Any], proposed: Mapping[int, Any], changed: Sequence[int]
    ) -> Schedule | None:
        """Return the accepted schedule for a proposal, or None when it is rejected.

        Parameters
        ----------
        before : mapping of int to chain
            The feasible schedule before the move.
        proposed : mapping of int to chain
            The schedule the operator proposed.
        changed : sequence of int
            The blocks the operator touched.

        Returns
        -------
        dict of int to chain or None
            The feasible proposal or repair, or None when the move is rejected.
        """
        if not self.enabled:
            return dict(proposed)
        self.stats["proposed"] += 1
        if self.feasible(proposed):
            self.stats["feasible"] += 1
            return dict(proposed)
        if self.strategy == "reject":
            self.stats["rejected"] += 1
            return None
        repaired = self._repair(before, proposed, changed)
        if repaired is None:
            self.stats["rejected"] += 1
            return None
        self.stats["repaired"] += 1
        return repaired

    def _repair(
        self, before: Mapping[int, Any], proposed: Mapping[int, Any], changed: Sequence[int]
    ) -> Schedule | None:
        """Try a one-block local repair.

        Each candidate removes one addition, restores one removal, or restores one
        modification. The first feasible candidate that differs from the prior schedule is
        the repair. Removing every change would just reproduce the prior schedule, which is a
        rejection rather than a repair.
        """
        additions = [
            block
            for block in changed
            if before.get(block) is None and proposed.get(block) is not None
        ]
        removals = [
            block
            for block in changed
            if before.get(block) is not None and proposed.get(block) is None
        ]
        modifications = [
            block
            for block in changed
            if before.get(block) is not None
            and proposed.get(block) is not None
            and before[block] != proposed[block]
        ]
        candidates: list[Schedule] = []
        for block in additions:
            candidate = dict(proposed)
            candidate.pop(block, None)
            candidates.append(candidate)
        for block in removals:
            candidate = dict(proposed)
            candidate[block] = before[block]
            candidates.append(candidate)
        for block in modifications:
            candidate = dict(proposed)
            candidate[block] = before[block]
            candidates.append(candidate)
        for candidate in candidates:
            if candidate != before and self.feasible(candidate):
                return candidate
        return None

    def prepare(self, schedule: Schedule | None) -> Schedule:
        """Return a feasible starting schedule.

        An infeasible seed is repaired by removing every block in a violating patch or
        green-up pair, repeating until the schedule is feasible. The empty schedule is
        feasible, so this terminates.

        Parameters
        ----------
        schedule : dict of int to chain or None
            The proposed starting schedule.

        Returns
        -------
        dict of int to chain
            A feasible schedule.
        """
        current: Schedule = dict(schedule or {})
        if not self.enabled:
            return current
        for _ in range(len(current) + 1):
            if self.feasible(current):
                return current
            blocks = self.violating_blocks(current)
            if not blocks:
                return {}
            for block in blocks:
                current.pop(block, None)
            self.initial_removed += len(blocks)
            self.initial_repairs += 1
        return {}

    def feasible(self, schedule: Mapping[int, Any]) -> bool:
        """Return whether a schedule satisfies every active spatial rule.

        Parameters
        ----------
        schedule : mapping of int to chain
            The schedule to check.

        Returns
        -------
        bool
            True when the spatial penalty is zero within tolerance.
        """
        if not self.enabled:
            return True
        return self.penalty(schedule) <= 1e-9

    def penalty(self, schedule: Mapping[int, Any]) -> float:
        """Return the spatial penalty for a schedule.

        Parameters
        ----------
        schedule : mapping of int to chain
            The schedule to check.

        Returns
        -------
        float
            The opening, green-up, and core-area penalty.
        """
        if not self.enabled:
            return 0.0
        selected, disturbance = self._state(schedule)
        if not disturbance:
            return 0.0
        incident = self._incident_edges(disturbance)
        penalty = spatial_penalty(
            selected,
            disturbance,
            [(source, target) for source, target, _ in incident],
            self._block_area,
            self.max_opening_ha,
            self.min_green_up_years,
        )
        if self.min_core_area_ha is not None and self.core_buffer_m is not None:
            penalty += core_area_penalty(
                selected,
                incident,
                self._block_area,
                self.core_buffer_m,
                self.min_core_area_ha,
            )
        return penalty

    def violations(self, schedule: Mapping[int, Any]) -> list[dict[str, object]]:
        """Return the final spatial violation records.

        Parameters
        ----------
        schedule : mapping of int to chain
            The schedule to inspect.

        Returns
        -------
        list of dict
            Opening, green-up, and core-area records.
        """
        if not self.enabled:
            return []
        selected, disturbance = self._state(schedule)
        incident = self._incident_edges(disturbance)
        records: list[dict[str, object]] = []
        if self.max_opening_ha is not None:
            records.extend(
                opening_violations(
                    selected,
                    [(source, target) for source, target, _ in incident],
                    self._block_area,
                    self.max_opening_ha,
                )
            )
        if self.min_green_up_years is not None:
            records.extend(
                green_up_violations(
                    disturbance,
                    [(source, target) for source, target, _ in incident],
                    self.min_green_up_years,
                )
            )
        if self.min_core_area_ha is not None and self.core_buffer_m is not None:
            records.extend(self._core_violations(selected, incident))
        return records

    def violating_blocks(self, schedule: Mapping[int, Any]) -> set[int]:
        """Return the blocks involved in any spatial violation.

        Parameters
        ----------
        schedule : mapping of int to chain
            The schedule to inspect.

        Returns
        -------
        set of int
            The block identifiers to remove for a feasible seed.
        """
        if not self.enabled:
            return set()
        selected, disturbance = self._state(schedule)
        blocks: set[int] = set()
        if self.max_opening_ha is not None:
            for chosen in selected.values():
                for patch in connected_patches(chosen, self._adjacency):
                    area = sum(self._block_area.get(block, 0.0) for block in patch)
                    if area > self.max_opening_ha:
                        blocks.update(patch)
        if self.min_green_up_years is not None:
            for record in green_up_violations(
                disturbance,
                self._adjacency,
                self.min_green_up_years,
            ):
                blocks.add(int(str(record["block_a"])))
                blocks.add(int(str(record["block_b"])))
        if self.min_core_area_ha is not None and self.core_buffer_m is not None:
            for chosen in selected.values():
                for patch in connected_patches(chosen, self._adjacency):
                    area = sum(self._block_area.get(block, 0.0) for block in patch)
                    perimeter = patch_perimeter(patch, self._edges)
                    if core_area(area, perimeter, self.core_buffer_m) < self.min_core_area_ha:
                        blocks.update(patch)
        return blocks

    def summary(self) -> dict[str, object]:
        """Return the strategy and counts for the run summary.

        Returns
        -------
        dict of str to object
            The strategy, enabled flag, move counts, and initial repairs.
        """
        return {
            "strategy": self.strategy,
            "enabled": self.enabled,
            "proposed": self.stats["proposed"],
            "feasible": self.stats["feasible"],
            "rejected": self.stats["rejected"],
            "repaired": self.stats["repaired"],
            "initial_removed": self.initial_removed,
            "initial_repairs": self.initial_repairs,
        }

    def _state(
        self, schedule: Mapping[int, Any]
    ) -> tuple[dict[int, set[int]], dict[int, tuple[int, ...]]]:
        """Return selected blocks per year and disturbance years per block."""
        pairs = [(int(block), int(year)) for block, chain in schedule.items() for _, year in chain]
        selected, years = schedule_years(pairs)
        return selected, {block: tuple(items) for block, items in years.items()}

    def _incident_edges(
        self, disturbance_years: Mapping[int, Sequence[int]]
    ) -> list[tuple[int, int, float]]:
        """Return the deduplicated edges incident to a disturbed block."""
        found: dict[tuple[int, int], float] = {}
        for block in disturbance_years:
            for source, target, length in self._edges_by_block.get(int(block), ()):
                pair = (min(int(source), int(target)), max(int(source), int(target)))
                found[pair] = length
        return [(source, target, found[(source, target)]) for source, target in sorted(found)]

    def _core_violations(
        self, selected: Mapping[int, set[int]], edges: Sequence[tuple[int, int, float]]
    ) -> list[dict[str, object]]:
        """Return core-area records for the final report."""
        records: list[dict[str, object]] = []
        for year, chosen in selected.items():
            for patch in connected_patches(
                chosen, [(source, target) for source, target, _ in edges]
            ):
                area = sum(self._block_area.get(block, 0.0) for block in patch)
                perimeter = patch_perimeter(patch, edges)
                core = core_area(area, perimeter, float(self.core_buffer_m or 0.0))
                if core < float(self.min_core_area_ha or 0.0):
                    records.append(
                        {
                            "kind": "core_area",
                            "year": int(year),
                            "area_ha": core,
                            "limit": self.min_core_area_ha,
                            "block_a": -1,
                            "block_b": -1,
                            "years": 0,
                        }
                    )
        return records


class GuardedOperator:
    """An operator that applies a :class:`ConstraintGuard` to every proposal.

    Parameters
    ----------
    operator : Operator
        The wrapped operator.
    guard : ConstraintGuard
        The feasibility policy.
    """

    def __init__(self, operator: Operator, guard: ConstraintGuard) -> None:
        """Store the wrapped operator and guard."""
        self._operator = operator
        self._guard = guard
        self.name = operator.name
        self.weight = operator.weight

    def propose_inplace(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> dict[int, Any] | None:
        """Apply the guard to an in-place proposal.

        Parameters
        ----------
        schedule : dict of int to chain
            The schedule to mutate.
        rng : random.Random
            The random source.
        candidates : dict of int to list of chain
            The candidate chains per block.

        Returns
        -------
        dict of int to chain or None
            The previous chains for the touched blocks, or None when rejected.
        """
        before = dict(schedule)
        undo = self._operator.propose_inplace(schedule, rng, candidates)
        if undo is None:
            return None
        changed = list(undo)
        accepted = self._guard.consider(before, schedule, changed)
        if accepted is None:
            restore(schedule, undo)
            return None
        schedule.clear()
        schedule.update(accepted)
        return {block: before.get(block) for block in changed}

    def propose(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> tuple[Schedule, tuple[int, ...]] | None:
        """Apply the guard to a copying proposal.

        Parameters
        ----------
        schedule : dict of int to chain
            The schedule to copy.
        rng : random.Random
            The random source.
        candidates : dict of int to list of chain
            The candidate chains per block.

        Returns
        -------
        tuple or None
            The accepted schedule and changed blocks, or None when rejected.
        """
        proposal = self._operator.propose(schedule, rng, candidates)
        if proposal is None:
            return None
        proposed, changed = proposal
        accepted = self._guard.consider(schedule, proposed, changed)
        if accepted is None:
            return None
        touched = tuple(
            block
            for block in set(schedule) | set(accepted)
            if schedule.get(block) != accepted.get(block)
        )
        return accepted, touched

    def apply(
        self, schedule: Schedule, rng: random.Random, candidates: Candidates
    ) -> Schedule | None:
        """Apply the guard to a copying move.

        Parameters
        ----------
        schedule : dict of int to chain
            The schedule to copy.
        rng : random.Random
            The random source.
        candidates : dict of int to list of chain
            The candidate chains per block.

        Returns
        -------
        dict of int to chain or None
            The accepted schedule, or None when rejected.
        """
        proposal = self._operator.apply(schedule, rng, candidates)
        if proposal is None:
            return None
        changed = [
            block
            for block in set(schedule) | set(proposal)
            if schedule.get(block) != proposal.get(block)
        ]
        return self._guard.consider(schedule, proposal, changed)
