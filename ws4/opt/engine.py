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
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from ..model.schema import dataset_reference
from ..patch.accounts import load_patch_edges
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
from .mip import bound_for
from .objective import Target, load_targets, objective
from .operators import Candidates, OperatorRegistry, Schedule
from .solvers import solve_ils, solve_sa, solve_tabu
from .telemetry import RunLogger


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
    metaheuristic: str = "sa"
    tenure: int = 10
    perturbation: int = 2
    starts: int = 1
    workers: int = 1
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


class Optimizer:
    """A simulated-annealing optimizer over a compiled dataset."""

    def __init__(self, dataset_dir: Path, cfg: OptimizeConfig) -> None:
        """Store the dataset directory and the run configuration."""
        self.dataset_dir = Path(dataset_dir)
        self.cfg = cfg
        self.registry = OperatorRegistry()
        self._spatial_cache: tuple[list[tuple[int, int]], dict[int, float]] | None = None
        self._route_cache: (
            tuple[RouteModel | None, tuple[RouteAccount, ...], tuple[DuplicateAccount, ...]] | None
        ) = None
        self._edge_cache: tuple[EdgeElement, ...] | None = None
        self._graph_cache: list[tuple[int, int, float]] | None = None
        self._simulator_cache: Simulator | None = None
        self._base_cache: dict[tuple[int, str], float] | None = None
        self._delta_cache: dict[tuple[int, str, int], dict[tuple[int, str], float]] = {}

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
        """Return the possible ``(treatment, year)`` options for each block.

        A block's options are the treatments offered by its track, at the start, the
        midpoint, and the end of each treatment's eligible age window.
        """
        simulator = Simulator.from_dataset(self.dataset_dir)
        grouped = simulator.fragments.groupby("block_id")
        track_of = grouped["track_id"].first().to_dict()
        age_of = grouped["age"].min().to_dict()
        options: Candidates = {}
        for raw_block, raw_track in track_of.items():
            block_id = int(float(str(raw_block)))
            track_id = int(float(str(raw_track)))
            age = int(float(str(age_of[raw_block])))
            rows = simulator.treatments[simulator.treatments["track_id"] == track_id]
            block_options: list[tuple[str, int]] = []
            for _, treatment in rows.iterrows():
                # The treatment's window is an age window; the schedule year is when the
                # block reaches that age.
                begin = max(0, int(treatment["begin"]) - age)
                raw_end = int(treatment["end"])
                end = self.cfg.years - 1 if raw_end <= 0 else min(self.cfg.years - 1, raw_end - age)
                if begin > end:
                    continue
                label = str(treatment["treatment"])
                for year in sorted({begin, (begin + end) // 2, end}):
                    block_options.append((label, year))
            options[block_id] = block_options
        return options

    def _schedule_frame(self, schedule: Schedule) -> pd.DataFrame:
        """Render a schedule as a DataFrame."""
        rows = [
            {"block_id": block, "treatment": treatment, "period": year}
            for block, (treatment, year) in schedule.items()
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
        # re-simulation. Edge contrast and route accounts are not additive over blocks, so
        # those configurations fall back to the full evaluation.
        if not self.edge_elements() and not route_accounts:
            values = self._incremental_values(schedule, duplicate_accounts)
        else:
            values = self._full_values(schedule, model, route_accounts, duplicate_accounts)
        return objective(values, targets) + self._spatial_penalty(frame)

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

    def _block_delta(self, block: int, treatment: str, year: int) -> dict[tuple[int, str], float]:
        """Return a block's account-value delta for an assignment, cached."""
        key = (block, treatment, year)
        cached = self._delta_cache.get(key)
        if cached is not None:
            return cached
        simulator = self.simulator()
        treated = simulator.block_trajectory(block, treatment, year, self.cfg.years)
        empty = simulator.block_trajectory(block, None, year, self.cfg.years)
        delta = {
            cell: treated.get(cell, 0.0) - empty.get(cell, 0.0)
            for cell in set(treated) | set(empty)
        }
        delta = {cell: value for cell, value in delta.items() if value != 0.0}
        self._delta_cache[key] = delta
        return delta

    def _incremental_values(
        self, schedule: Schedule, duplicate_accounts: tuple[DuplicateAccount, ...]
    ) -> pd.DataFrame:
        """Return the account values from the base plus per-block deltas."""
        self.simulator().reset()
        totals = dict(self._base_values())
        for block, (treatment, year) in schedule.items():
            for cell, value in self._block_delta(block, treatment, year).items():
                totals[cell] = totals.get(cell, 0.0) + value
        values = pd.DataFrame(
            [
                {"year": year, "account": account, "value": value}
                for (year, account), value in totals.items()
            ],
            columns=["year", "account", "value"],
        )
        if duplicate_accounts:
            values = resolve_account_values(values, None, duplicate_accounts)
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

    def _spatial(self) -> tuple[list[tuple[int, int]], dict[int, float]]:
        """Return the cached topology edges and block areas, loading them once."""
        if self._spatial_cache is None:
            edges = [(source, target) for source, target, _ in self._graph()]
            simulator = Simulator.from_dataset(self.dataset_dir)
            block_area = {
                int(float(str(block))): float(str(area))
                for block, area in simulator.fragments.groupby("block_id")["area_ha"].sum().items()
            }
            self._spatial_cache = (edges, block_area)
        return self._spatial_cache

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
        edges, block_area = self._spatial()
        pairs = [
            (int(float(str(row.block_id))), int(float(str(row.period))))
            for row in schedule.itertuples(index=False)
        ]
        selected_by_year, harvest_year = schedule_years(pairs)
        penalty = spatial_penalty(
            selected_by_year,
            harvest_year,
            edges,
            block_area,
            self.cfg.max_opening_ha,
            self.cfg.min_green_up_years,
        )
        if self.cfg.min_core_area_ha is not None and self.cfg.core_buffer_m is not None:
            penalty += core_area_penalty(
                selected_by_year,
                self._graph(),
                block_area,
                self.cfg.core_buffer_m,
                self.cfg.min_core_area_ha,
            )
        return self.cfg.spatial_weight * penalty

    def _solve(
        self, seed: int, on_step: Callable[[int, float], None] | None = None
    ) -> tuple[Schedule, float]:
        """Run one metaheuristic start with the given seed.

        Parameters
        ----------
        seed : int
            The seed for this start.
        on_step : callable or None, optional
            Called with ``(iteration, best_objective)`` each iteration.

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
        # A warm start seeds the search with each block's first candidate.
        initial: Schedule | None = (
            {block: options[0] for block, options in candidates.items() if options}
            if self.cfg.warm_start
            else None
        )
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
        return solve_sa(
            problem,
            rng,
            iterations=self.cfg.iterations,
            temperature=self.cfg.temperature,
            cooling=self.cfg.cooling,
            on_step=on_step,
            initial=initial,
        )

    def search(self) -> tuple[Schedule, float, list[Target]]:
        """Run the search (serial or parallel multi-start) and return the incumbent.

        Returns
        -------
        tuple of (Schedule, float, list of Target)
            The best schedule, its objective, and the targets.
        """
        targets = load_targets(Path(self.cfg.targets_path)) if self.cfg.targets_path else []
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
        if self.cfg.workers > 1 and self.cfg.starts > 1:
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
            bound = bound_for(self.dataset_dir, targets, self.candidates(), self.cfg.years)
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
