"""Simulated-annealing optimizer over a treatment schedule.

The search starts from an empty schedule and applies neighbourhood moves
(toggle, shift, swap), accepting a worse move with the annealing probability. The
objective is the weighted-goal penalty from :mod:`ws4.opt.objective`. A run is
reproducible from its seed.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from ..model.schema import dataset_reference
from ..patch.accounts import PatchAccount, load_patch_accounts, load_patch_edges
from ..patch.constraints import core_area_penalty, schedule_years, spatial_penalty
from ..patch.edge import EdgeElement, load_edge_elements
from ..report import write_report
from ..roads.accounts import (
    DuplicateAccount,
    RouteAccount,
    RouteCostLedger,
    RouteModel,
    load_route_config,
    resolve_account_values,
)
from ..sim.engine import Simulator
from .core import Problem
from .incremental import IncrementalObjective
from .mip import bound_for
from .objective import Target, load_targets, objective
from .operators import (
    Candidates,
    Chain,
    ClusterOperator,
    LnsOperator,
    MergeOperator,
    OperatorRegistry,
    Schedule,
    ShiftOperator,
    SwapOperator,
    ToggleOperator,
)
from .patch import PatchModel
from .solvers import solve_ils, solve_sa, solve_sa_delta, solve_tabu
from .telemetry import RunLogger

_MAX_ROTATIONS = 3
_MAX_CHAINS = 320
_CHAIN_STEP = 10
_FRONTIER_CAP = 80
_ROTATION_SEEDS = 12


@dataclass
class OptimizeConfig:
    """Configuration for an optimization run."""

    threads: int = 1
    time_limit: str = "01:00:00"
    seed: int = 42
    targets_path: str = ""
    weights_path: str = ""
    years: int = 50
    iterations: int = 500
    temperature: float = 1000.0
    cooling: float = 0.99
    cooling_mode: str = "geometric"
    cooling_window: int = 64
    metaheuristic: str = "sa"
    tenure: int = 10
    perturbation: int = 2
    starts: int = 1
    workers: int = 1
    islands: int = 0
    episodes: int = 1
    warm_start: bool = False
    mip_bound: bool = False
    topology_path: str = ""
    route_config_path: str = ""
    edge_elements_path: str = ""
    max_opening_ha: float | None = None
    min_green_up_years: int | None = None
    core_buffer_m: float | None = None
    min_core_area_ha: float | None = None
    spatial_weight: float = 1.0
    allow_spatial_override: bool = False
    toggle_weight: float = 1.0
    shift_weight: float = 1.0
    swap_weight: float = 0.5
    lns_weight: float = 0.2
    lns_destroy: float = 0.1
    cluster_weight: float = 0.0
    cluster_size: int = 8
    warm_cache: bool = False
    patch_accounts_path: str = ""
    merge_weight: float = 0.0

    def __post_init__(self) -> None:
        """Reject an unknown temperature schedule before the search starts."""
        if self.cooling_mode not in {"geometric", "adaptive"}:
            raise ValueError(f"unknown cooling_mode: {self.cooling_mode!r}")


class Optimizer:
    """A simulated-annealing optimizer over a compiled dataset."""

    def __init__(self, dataset_dir: Path, cfg: OptimizeConfig) -> None:
        """Store the dataset directory and the run configuration."""
        self.dataset_dir = Path(dataset_dir)
        self.cfg = cfg
        self._graph_cache: list[tuple[int, int, float]] | None = None
        self._edges_by_block_cache: dict[int, list[tuple[int, int, float]]] | None = None
        self.registry = OperatorRegistry(
            [
                ToggleOperator(weight=cfg.toggle_weight),
                ShiftOperator(weight=cfg.shift_weight),
                SwapOperator(weight=cfg.swap_weight),
                LnsOperator(weight=cfg.lns_weight, destroy_fraction=cfg.lns_destroy),
                ClusterOperator(
                    weight=cfg.cluster_weight,
                    size=cfg.cluster_size,
                    neighbours=self._neighbours() if cfg.cluster_weight > 0.0 else {},
                ),
                MergeOperator(self, weight=cfg.merge_weight),
            ]
        )
        self._block_area_cache: dict[int, float] | None = None
        self._route_cache: (
            tuple[RouteModel | None, tuple[RouteAccount, ...], tuple[DuplicateAccount, ...]] | None
        ) = None
        self._edge_cache: tuple[EdgeElement, ...] | None = None
        self._simulator_cache: Simulator | None = None
        self._patch_cache: PatchModel | None = None
        self._active_patch: PatchModel | None = None
        self._patch_accounts_cache: tuple[PatchAccount, ...] | None = None
        self._base_cache: dict[tuple[int, str], float] | None = None
        self._product_delta_cache: dict[
            tuple[int, Chain, tuple[str, ...]], dict[tuple[int, str], float]
        ] = {}
        self._last_values: pd.DataFrame | None = None
        self._delta_cache: dict[tuple[int, Chain], dict[tuple[int, str], float]] = {}
        self._route_delta_cache: dict[tuple[int, Chain], dict[tuple[int, str], float]] = {}

    @classmethod
    def from_dataset(cls, dataset_dir: Path, cfg: OptimizeConfig) -> Optimizer:
        """Build an optimizer that reads the given compiled dataset."""
        return cls(dataset_dir, cfg)

    def route(
        self,
    ) -> tuple[RouteModel | None, tuple[RouteAccount, ...], tuple[DuplicateAccount, ...]]:
        """Return the route model, route accounts, and duplicate accounts, loaded once.

        Returns
        -------
        tuple
            ``(model, route_accounts, duplicate_accounts)``. The model is None when no
            route configuration is set.
        """
        if self._route_cache is None:
            if self.cfg.route_config_path:
                config = load_route_config(Path(self.cfg.route_config_path))
                self._route_cache = (
                    config.model,
                    config.route_accounts,
                    config.duplicate_accounts,
                )
            else:
                self._route_cache = (None, (), ())
        return self._route_cache

    def candidates(self) -> Candidates:
        """Return the possible treatment chains for each block.

        A block may be treated more than once. A chain is built by walking the track
        transitions: a treatment applies over an age window, so its schedule years are the
        years the block reaches that window; after a treatment the block moves to the
        successor track at the treatment's reset age, and the next rotation is read from
        there. The window start, midpoint, and end are taken per rotation, up to a rotation
        cap, and each block's chain list is capped.

        Returns
        -------
        dict of int to list of Chain
            The candidate treatment chains per block (single rotations first, earliest
            first, then multi-rotation chains).
        """
        simulator = Simulator.from_dataset(self.dataset_dir)
        by_track: dict[int, list[tuple[str, int, int, int, int]]] = {}
        for row in simulator.treatments.itertuples(index=False):
            by_track.setdefault(int(float(str(row.track_id))), []).append(
                (
                    str(row.treatment),
                    int(float(str(row.begin))),
                    int(float(str(row.end))),
                    int(float(str(row.new_track))),
                    int(float(str(row.offset))),
                )
            )
        grouped = simulator.fragments.groupby("block_id")
        track_of = grouped["track_id"].first().to_dict()
        age_of = grouped["age"].min().to_dict()
        options: Candidates = {}
        rotations = min(_MAX_ROTATIONS, max(1, self.cfg.years))
        for raw_block, raw_track in track_of.items():
            block_id = int(float(str(raw_block)))
            track_id = int(float(str(raw_track)))
            age = int(float(str(age_of[raw_block])))
            options[block_id] = self._chains(by_track, track_id, age, rotations)
        return options

    def _chains(
        self,
        by_track: dict[int, list[tuple[str, int, int, int, int]]],
        track: int,
        age: int,
        rotations: int,
    ) -> list[Chain]:
        """Return a block's feasible treatment chains, bounded.

        Parameters
        ----------
        by_track : dict
            The treatments per track, as ``(treatment, begin, end, new_track, offset)``.
        track : int
            The block's initial track.
        age : int
            The block's initial age.
        rotations : int
            The maximum number of treatments in a chain.

        Returns
        -------
        list of Chain
            The chains; a single rotation first (earliest first), then multi-rotation chains.
        """
        last_year = self.cfg.years - 1
        single: list[Chain] = []
        for label, begin, end, _, _ in by_track.get(track, []):
            start = max(0, begin - age)
            stop = last_year if end <= 0 else min(last_year, end - age)
            if start > stop:
                continue
            single.extend(((label, year),) for year in range(start, stop + 1))
        single.sort(key=lambda chain: chain[0][1])
        if rotations <= 1 or not single:
            return single[:_MAX_CHAINS]
        # Later rotations: seed from a sample of first-rotation years and step by the period,
        # so every operable age is a first-rotation candidate while the list stays bounded.
        stride = max(1, len(single) // _ROTATION_SEEDS)
        frontier: list[tuple[Chain, int, int, int]] = []
        for chain in single[::stride][:_ROTATION_SEEDS]:
            label, year = chain[0]
            transition = next((row for row in by_track.get(track, []) if row[0] == label), None)
            if transition is not None:
                frontier.append((chain, transition[3], transition[4], year))
        multi: list[Chain] = []
        for _ in range(rotations - 1):
            next_frontier: list[tuple[Chain, int, int, int]] = []
            for chain, current_track, current_age, current_year in frontier:
                for label, begin, end, new_track, new_age in by_track.get(current_track, []):
                    start = current_year + max(0, begin - current_age)
                    stop = last_year if end <= 0 else current_year + (end - current_age)
                    stop = min(stop, last_year)
                    if start > stop:
                        continue
                    years = list(range(start, stop + 1, _CHAIN_STEP))
                    if years[-1] != stop:
                        years.append(stop)
                    for year in years:
                        new_chain = (*chain, (label, year))
                        multi.append(new_chain)
                        next_frontier.append((new_chain, new_track, new_age, year))
            frontier = next_frontier[:_FRONTIER_CAP]
            if not frontier:
                break
        return (single + multi)[:_MAX_CHAINS]

    def _schedule_frame(self, schedule: Schedule) -> pd.DataFrame:
        """Render a schedule as a DataFrame (one row per treatment event)."""
        rows = [
            {"block_id": block, "treatment": treatment, "period": year}
            for block, chain in schedule.items()
            for treatment, year in chain
        ]
        return pd.DataFrame(rows, columns=["block_id", "treatment", "period"])

    def simulator(self) -> Simulator:
        """Return a reusable simulator, built once and reset before each use.

        Returns
        -------
        Simulator
            The simulator. Its mutable state is reset by :meth:`Simulator.reset` before
            each evaluation, so one dataset load serves the whole search.
        """
        if self._simulator_cache is None:
            self._simulator_cache = Simulator.from_dataset(self.dataset_dir)
        return self._simulator_cache

    def _evaluate(self, schedule: Schedule, targets: list[Target]) -> float:
        """Return the objective for a schedule, including any spatial penalty."""
        frame = self._schedule_frame(schedule)
        model, route_accounts, duplicate_accounts = self.route()
        # Feature account values are additive over blocks, so a schedule is the
        # empty-schedule base plus a per-block delta — exact and far cheaper than a full
        # re-simulation. Route accounts are additive too, except build (charged once per
        # segment across the schedule); edge contrast is not additive. Those configurations
        # fall back to the full evaluation.
        additive_routes = not route_accounts or (
            model is not None and all(account.kind != "build" for account in route_accounts)
        )
        if not self.edge_elements() and additive_routes:
            values = self._incremental_values(schedule, duplicate_accounts, route_accounts)
        else:
            values = self._full_values(schedule, model, route_accounts, duplicate_accounts)
        self._last_values = values
        patch = self.patch_model()
        if patch is not None:
            patch.reset(schedule)
            rows = [
                {"year": year, "account": account, "value": value}
                for (year, account), value in patch.cell_map().items()
            ]
            if rows:
                values = pd.concat(
                    [values, pd.DataFrame(rows, columns=["year", "account", "value"])],
                    ignore_index=True,
                )
                self._last_values = values
        return objective(values, targets) + self._spatial_penalty(frame)

    def last_account_values(self) -> pd.DataFrame:
        """Return the account values of the most recent objective evaluation.

        The objective computes an account-values frame for every schedule it scores; this
        returns the one from the latest call, so a caller can inspect what the optimizer
        last saw (for example, to watch the target window of an account).

        Returns
        -------
        pandas.DataFrame
            The account values, with ``year``, ``account``, and ``value`` columns, or an
            empty frame with those columns before any evaluation.
        """
        if self._last_values is None:
            return pd.DataFrame(columns=["year", "account", "value"])
        return self._last_values

    def patch_accounts(self) -> tuple[PatchAccount, ...]:
        """Return the configured patch accounts (empty when none).

        Returns
        -------
        tuple of PatchAccount
            The definitions.
        """
        if self._patch_cache is not None:
            return self._patch_cache.accounts
        if not self.cfg.patch_accounts_path:
            return ()
        if self._patch_accounts_cache is None:
            self._patch_accounts_cache = load_patch_accounts(Path(self.cfg.patch_accounts_path))
        return self._patch_accounts_cache

    def patch_model(self) -> PatchModel | None:
        """Return the patch model when patch accounts are configured, built once.

        Returns
        -------
        PatchModel or None
            The model, or None when no patch accounts are configured.
        """
        accounts = self.patch_accounts()
        if not accounts:
            return None
        if self._patch_cache is None:
            self._patch_cache = PatchModel(self, accounts)
        return self._patch_cache

    def active_patch_model(self) -> PatchModel | None:
        """Return the patch model the current evaluator is maintaining.

        Returns
        -------
        PatchModel or None
            The live model, or None when the run has no patch accounts or no evaluator yet.
        """
        return self._active_patch

    def set_active_patch_model(self, model: PatchModel | None) -> None:
        """Record the patch model the current evaluator is maintaining.

        Parameters
        ----------
        model : PatchModel or None
            The live model, or None.
        """
        self._active_patch = model

    def delta_evaluator(
        self, targets: Sequence[Target], extra_accounts: Sequence[str] = ()
    ) -> IncrementalObjective | None:
        """Return a move-based objective evaluator when the configuration supports one.

        The evaluator tracks only the accounts the targets read (plus any
        ``extra_accounts``), so it is used when the run has no route accounts, duplicate
        accounts, or edge contrast (each rewrites or extends the account values). When it
        returns None the caller falls back to whole-schedule evaluation.

        Parameters
        ----------
        targets : sequence of Target
            The goals.
        extra_accounts : sequence of str, optional
            Further accounts to track for display; they do not affect the objective.

        Returns
        -------
        IncrementalObjective or None
            The evaluator, or None when the configuration needs whole-schedule values.
        """
        model, route_accounts, duplicate_accounts = self.route()
        if duplicate_accounts or self.edge_elements():
            return None
        if route_accounts and (model is None or any(a.kind == "build" for a in route_accounts)):
            return None
        patch_accounts = self.patch_accounts()
        if patch_accounts and not self.cfg.topology_path:
            raise ValueError("patch accounts need a topology (set topology_path)")
        return IncrementalObjective(self, targets, extra_accounts, patch_accounts)

    def _full_values(
        self,
        schedule: Schedule,
        model: RouteModel | None,
        route_accounts: tuple[RouteAccount, ...],
        duplicate_accounts: tuple[DuplicateAccount, ...],
    ) -> pd.DataFrame:
        """Return the account values from a full re-simulation."""
        frame = self._schedule_frame(schedule)
        simulator = self.simulator()
        simulator.reset()
        ledger = RouteCostLedger(model.network, collect=False) if model is not None else None
        edges = self._graph() if self.cfg.topology_path else []
        values = simulator.simulate(
            frame,
            self.cfg.years,
            route_model=model,
            ledger=ledger,
            edge_elements=self.edge_elements(),
            edges=edges,
        )
        if ledger is not None and route_accounts:
            values = resolve_account_values(
                values, ledger.account_values(route_accounts), duplicate_accounts
            )
        elif duplicate_accounts:
            values = resolve_account_values(values, None, duplicate_accounts)
        return values

    def _base_values(self) -> dict[tuple[int, str], float]:
        """Return the empty-schedule account values as a mapping, computed once."""
        if self._base_cache is not None:
            return self._base_cache
        simulator = self.simulator()
        simulator.reset()
        empty = pd.DataFrame(
            {
                "block_id": pd.Series(dtype="int64"),
                "treatment": pd.Series(dtype="string"),
                "period": pd.Series(dtype="int64"),
            }
        )
        values = simulator.simulate(empty, self.cfg.years)
        simulator.reset()
        base = {
            (int(str(row.year)), str(row.account)): float(str(row.value))
            for row in values.itertuples(index=False)
        }
        self._base_cache = base
        return base

    def _block_delta(
        self, block: int, chain: Chain, accounts: set[str] | None = None
    ) -> dict[tuple[int, str], float]:
        """Return a block's account-value delta for a treatment chain, cached.

        Parameters
        ----------
        block : int
            The block.
        chain : tuple of (str, int)
            The block's treatment chain (events applied in year order).
        accounts : set of str or None, optional
            When given and the names are all product accounts, the delta is the products
            the chain makes, computed without stepping every year.

        Returns
        -------
        dict of (int, str) to float
            The account value per ``(year, account)`` cell (non-zero entries only).
        """
        if accounts is not None and all(name.startswith("product.") for name in accounts):
            product_key = (block, chain, tuple(sorted(accounts)))
            cached_product = self._product_delta_cache.get(product_key)
            if cached_product is not None:
                return cached_product
            products = self.simulator().block_chain_products(block, chain)
            product_delta = {cell: value for cell, value in products.items() if cell[1] in accounts}
            self._product_delta_cache[product_key] = product_delta
            return product_delta
        key = (block, chain)
        cached = self._delta_cache.get(key)
        if cached is not None:
            return cached
        simulator = self.simulator()
        treated = simulator.block_chain(block, chain, self.cfg.years)
        empty = simulator.block_chain(block, (), self.cfg.years)
        delta = {
            cell: treated.get(cell, 0.0) - empty.get(cell, 0.0)
            for cell in set(treated) | set(empty)
        }
        delta = {cell: value for cell, value in delta.items() if value != 0.0}
        self._delta_cache[key] = delta
        return delta

    def _block_route_delta(self, block: int, chain: Chain) -> dict[tuple[int, str], float]:
        """Return a block's route-account delta for a treatment chain, cached."""
        key = (block, chain)
        cached = self._route_delta_cache.get(key)
        if cached is not None:
            return cached
        model, route_accounts, _ = self.route()
        delta: dict[tuple[int, str], float] = {}
        if model is not None and route_accounts:
            delta = self.simulator().block_route_chain(
                block, chain, self.cfg.years, model, route_accounts
            )
            delta = {cell: value for cell, value in delta.items() if value != 0.0}
        self._route_delta_cache[key] = delta
        return delta

    @staticmethod
    def _values_frame(totals: dict[tuple[int, str], float]) -> pd.DataFrame:
        """Render a ``(year, account) -> value`` mapping as an account-values frame."""
        return pd.DataFrame(
            [
                {"year": year, "account": account, "value": value}
                for (year, account), value in totals.items()
            ],
            columns=["year", "account", "value"],
        )

    def _incremental_values(
        self,
        schedule: Schedule,
        duplicate_accounts: tuple[DuplicateAccount, ...] = (),
        route_accounts: tuple[RouteAccount, ...] = (),
    ) -> pd.DataFrame:
        """Return the account values from the base plus per-block feature and route deltas."""
        self.simulator().reset()
        totals = dict(self._base_values())
        route_totals: dict[tuple[int, str], float] = {}
        for block, chain in schedule.items():
            for cell, value in self._block_delta(block, chain).items():
                totals[cell] = totals.get(cell, 0.0) + value
            if route_accounts and chain:
                for cell, value in self._block_route_delta(block, chain).items():
                    route_totals[cell] = route_totals.get(cell, 0.0) + value
        values = self._values_frame(totals)
        if route_accounts:
            route = self._values_frame(route_totals) if route_totals else None
            return resolve_account_values(values, route, duplicate_accounts)
        if duplicate_accounts:
            return resolve_account_values(values, None, duplicate_accounts)
        return values

    def edge_elements(self) -> tuple[EdgeElement, ...]:
        """Return the edge contrast elements, loading them once.

        Returns
        -------
        tuple of EdgeElement
            The edge elements, or an empty tuple when none are configured.
        """
        if self._edge_cache is None:
            self._edge_cache = (
                load_edge_elements(Path(self.cfg.edge_elements_path))
                if self.cfg.edge_elements_path
                else ()
            )
        return self._edge_cache

    def _graph(self) -> list[tuple[int, int, float]]:
        """Return the cached topology graph ``(src, dst, shared_length)``."""
        if self._graph_cache is None:
            self._graph_cache = load_patch_edges(Path(self.cfg.topology_path))
        return self._graph_cache

    def _neighbours(self) -> dict[int, tuple[int, ...]]:
        """Return each block's topological neighbours (empty without a topology).

        Returns
        -------
        dict of int to tuple of int
            The neighbour blocks per block.
        """
        if not self.cfg.topology_path:
            return {}
        index: dict[int, list[int]] = {}
        for source, target, _ in self._graph():
            index.setdefault(source, []).append(target)
            index.setdefault(target, []).append(source)
        return {block: tuple(items) for block, items in index.items()}

    def _edges_by_block(self) -> dict[int, list[tuple[int, int, float]]]:
        """Return the cached adjacency index: each block to its incident edges."""
        if self._edges_by_block_cache is None:
            index: dict[int, list[tuple[int, int, float]]] = {}
            for source, target, length in self._graph():
                index.setdefault(source, []).append((source, target, length))
                index.setdefault(target, []).append((source, target, length))
            self._edges_by_block_cache = index
        return self._edges_by_block_cache

    def _incident_edges(self, blocks: set[int]) -> list[tuple[int, int, float]]:
        """Return the edges incident to any of ``blocks``, de-duplicated.

        Only an edge incident to a disturbed block can contribute to an opening, a
        perimeter, or a green-up violation, so scanning these instead of every edge keeps
        the spatial penalty proportional to the schedule, not the whole topology.
        """
        index = self._edges_by_block()
        seen: set[tuple[int, int, float]] = set()
        for block in blocks:
            seen.update(index.get(block, ()))
        return list(seen)

    def _block_area(self) -> dict[int, float]:
        """Return the cached block areas, loading them once."""
        if self._block_area_cache is None:
            simulator = Simulator.from_dataset(self.dataset_dir)
            self._block_area_cache = {
                int(float(str(block))): float(str(area))
                for block, area in simulator.fragments.groupby("block_id")["area_ha"].sum().items()
            }
        return self._block_area_cache

    def _spatial_penalty(self, schedule: pd.DataFrame) -> float:
        """Return the weighted spatial penalty for a schedule, or zero when disabled.

        The penalty is disabled by ``allow_spatial_override`` (the explicit override), and
        when no maximum opening size, green-up interval, or core-area rule is set.
        """
        if self.cfg.allow_spatial_override:
            return 0.0
        if (
            self.cfg.max_opening_ha is None
            and self.cfg.min_green_up_years is None
            and self.cfg.min_core_area_ha is None
        ):
            return 0.0
        block_area = self._block_area()
        pairs = [
            (int(float(str(row.block_id))), int(float(str(row.period))))
            for row in schedule.itertuples(index=False)
        ]
        selected_by_year, disturbance_years = schedule_years(pairs)
        # Only edges incident to a disturbed block can contribute; this keeps the penalty
        # proportional to the schedule rather than to the whole topology.
        incident = self._incident_edges(set(disturbance_years))
        incident_edges = [(source, target) for source, target, _ in incident]
        penalty = spatial_penalty(
            selected_by_year,
            disturbance_years,
            incident_edges,
            block_area,
            self.cfg.max_opening_ha,
            self.cfg.min_green_up_years,
        )
        if self.cfg.min_core_area_ha is not None and self.cfg.core_buffer_m is not None:
            penalty += core_area_penalty(
                selected_by_year,
                incident,
                block_area,
                self.cfg.core_buffer_m,
                self.cfg.min_core_area_ha,
            )
        return self.cfg.spatial_weight * penalty

    def _solve(
        self,
        seed: int,
        on_step: Callable[[int, float], None] | None = None,
        initial: Schedule | None = None,
    ) -> tuple[Schedule, float]:
        """Run one metaheuristic start with the given seed.

        Parameters
        ----------
        seed : int
            The seed for this start.
        on_step : callable or None, optional
            Called with ``(iteration, best_objective)`` each iteration.
        initial : Schedule or None, optional
            A starting schedule (for example a migrated elite). When omitted, the warm
            start seeds the search with each block's first candidate.

        Returns
        -------
        tuple of (Schedule, float)
            The best schedule and its objective.
        """
        targets = load_targets(Path(self.cfg.targets_path)) if self.cfg.targets_path else []
        candidates = self.candidates()
        problem = Problem(
            evaluate=lambda schedule: self._evaluate(schedule, targets),
            candidates=candidates,
            registry=self.registry,
        )
        rng = random.Random(seed)
        if initial is None and self.cfg.warm_start:
            initial = {block: options[0] for block, options in candidates.items() if options}
        if self.cfg.metaheuristic == "tabu":
            return solve_tabu(
                problem,
                rng,
                iterations=self.cfg.iterations,
                tenure=self.cfg.tenure,
                on_step=on_step,
                initial=initial,
            )
        if self.cfg.metaheuristic == "ils":
            return solve_ils(
                problem,
                rng,
                iterations=self.cfg.iterations,
                perturbation=self.cfg.perturbation,
                on_step=on_step,
                initial=initial,
            )
        evaluator = self.delta_evaluator(targets)
        if evaluator is not None:
            if self.cfg.warm_cache:
                evaluator.warm(candidates)
            return solve_sa_delta(
                evaluator,
                rng,
                iterations=self.cfg.iterations,
                temperature=self.cfg.temperature,
                cooling=self.cfg.cooling,
                candidates=candidates,
                registry=self.registry,
                initial=initial,
                on_step=on_step,
                adaptive=self.cfg.cooling_mode == "adaptive",
                cooling_window=self.cfg.cooling_window,
            )
        return solve_sa(
            problem,
            rng,
            iterations=self.cfg.iterations,
            temperature=self.cfg.temperature,
            cooling=self.cfg.cooling,
            on_step=on_step,
            initial=initial,
            adaptive=self.cfg.cooling_mode == "adaptive",
            cooling_window=self.cfg.cooling_window,
        )

    def _use_pool(self) -> bool:
        """Return whether the search should run across a process pool.

        True for the island model (more than one island and more than one worker) or for a
        parallel multi-start (more than one start and more than one worker).

        Returns
        -------
        bool
            Whether to use the process pool.
        """
        if self.cfg.workers <= 1:
            return False
        return (self.cfg.islands > 1) or (self.cfg.starts > 1)

    def search(self) -> tuple[Schedule, float, list[Target]]:
        """Run the search and return the incumbent.

        When ``islands`` is set (and there is more than one), the islands run in parallel
        for ``episodes`` rounds, and the global best schedule is migrated into every island
        as the next round's starting point. Otherwise the starts run independently (serially
        or across a process pool).

        Returns
        -------
        tuple of (Schedule, float, list of Target)
            The best schedule, its objective, and the targets.
        """
        targets = load_targets(Path(self.cfg.targets_path)) if self.cfg.targets_path else []
        if self.cfg.islands > 1 and self.cfg.workers > 1:
            best, best_obj = self._island_search()
            return best, best_obj, targets
        starts = max(1, self.cfg.starts)
        if self.cfg.workers > 1 and starts > 1:
            jobs = [
                (
                    str(self.dataset_dir),
                    replace(self.cfg, starts=1, workers=1),
                    self.cfg.seed + start,
                )
                for start in range(starts)
            ]
            with ProcessPoolExecutor(max_workers=self.cfg.workers) as pool:
                results = list(pool.map(_run_start, jobs))
            best, best_obj = min(results, key=lambda result: result[1])
        else:
            best, best_obj = {}, math.inf
            for start in range(starts):
                candidate, candidate_obj = self._solve(self.cfg.seed + start)
                if candidate_obj < best_obj:
                    best, best_obj = candidate, candidate_obj
        return best, best_obj, targets

    def _island_search(self) -> tuple[Schedule, float]:
        """Run the island model: parallel islands with elite migration.

        Returns
        -------
        tuple of (Schedule, float)
            The best schedule across all islands and episodes, and its objective.
        """
        islands = max(1, self.cfg.islands)
        episodes = max(1, self.cfg.episodes)
        island_config = replace(self.cfg, islands=1, starts=1, workers=1, episodes=1)
        seeds = [self.cfg.seed + index for index in range(islands)]
        best: Schedule = {}
        best_obj = math.inf
        for _episode in range(episodes):
            jobs = [
                (str(self.dataset_dir), island_config, seed, best if best else None)
                for seed in seeds
            ]
            with ProcessPoolExecutor(max_workers=islands) as pool:
                results = list(pool.map(_island_job, jobs))
            for candidate, candidate_obj in results:
                if candidate_obj < best_obj:
                    best, best_obj = candidate, candidate_obj
        return best, best_obj

    def run(self, out_dir: Path) -> dict[str, Any]:
        """Run the search and write the incumbent schedule and a summary.

        Parameters
        ----------
        out_dir : Path
            Directory to write the run outputs into.

        Returns
        -------
        dict of str to Any
            The run summary.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        logger = RunLogger(
            out_dir / "telemetry.jsonl",
            run_id=f"{self.cfg.metaheuristic}-{self.cfg.seed}",
            config=asdict(self.cfg),
        )
        if self._use_pool():
            best, best_obj, targets = self.search()
        else:
            best, best_obj = {}, math.inf
            for start in range(max(1, self.cfg.starts)):
                candidate, candidate_obj = self._solve(self.cfg.seed + start, on_step=logger.step)
                if candidate_obj < best_obj:
                    best, best_obj = candidate, candidate_obj
            targets = load_targets(Path(self.cfg.targets_path)) if self.cfg.targets_path else []
        logger.close()

        schedule_path = out_dir / "schedule.csv"
        self._schedule_frame(best).to_csv(schedule_path, index=False)
        model, route_accounts, duplicate_accounts = self.route()
        simulator = Simulator.from_dataset(self.dataset_dir)
        values = simulator.run(
            schedule_path,
            years=self.cfg.years,
            out_dir=out_dir,
            topology_csv=Path(self.cfg.topology_path) if self.cfg.topology_path else None,
            route_model=model,
            route_accounts=route_accounts,
            duplicate_accounts=duplicate_accounts,
            edge_elements=self.edge_elements(),
            core_buffer_m=self.cfg.core_buffer_m,
            min_core_area_ha=self.cfg.min_core_area_ha,
        )
        write_report(values, targets, out_dir)
        summary: dict[str, Any] = {
            "incumbent_objective": best_obj,
            "iterations": self.cfg.iterations,
            "seed": self.cfg.seed,
            "metaheuristic": self.cfg.metaheuristic,
            "starts": self.cfg.starts,
            "blocks_scheduled": len(best),
            "operators": self.registry.names(),
            "status": "ok",
            "dataset": dataset_reference(self.dataset_dir),
        }
        if self.cfg.mip_bound:
            bound = bound_for(
                self.dataset_dir,
                targets,
                self.candidates(),
                self.cfg.years,
                topology_path=Path(self.cfg.topology_path) if self.cfg.topology_path else None,
                max_opening_ha=self.cfg.max_opening_ha,
            )
            summary["bound"] = bound.objective
            summary["gap"] = best_obj - bound.objective
            summary["bound_status"] = bound.status
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary


def _run_start(job: tuple[str, OptimizeConfig, int]) -> tuple[Schedule, float]:
    """Run one start in a worker process.

    Top-level so it is picklable by the process pool.

    Parameters
    ----------
    job : tuple
        ``(dataset_dir, config, seed)``.

    Returns
    -------
    tuple of (Schedule, float)
        The best schedule and its objective for that start.
    """
    dataset_dir, cfg, seed = job
    return Optimizer.from_dataset(Path(dataset_dir), cfg)._solve(seed)


def _island_job(
    job: tuple[str, OptimizeConfig, int, Schedule | None],
) -> tuple[Schedule, float]:
    """Run one island episode in a worker process.

    Top-level so it is picklable by the process pool.

    Parameters
    ----------
    job : tuple
        ``(dataset_dir, config, seed, initial)``, where ``initial`` is the migrated elite
        (or None on the first episode).

    Returns
    -------
    tuple of (Schedule, float)
        The island's best schedule and its objective.
    """
    dataset_dir, cfg, seed, initial = job
    return Optimizer.from_dataset(Path(dataset_dir), cfg)._solve(seed, initial=initial)
