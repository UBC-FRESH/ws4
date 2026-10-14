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

from ..report import write_report
from ..sim.engine import Simulator
from .core import Problem
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


class Optimizer:
    """A simulated-annealing optimizer over a compiled dataset."""

    def __init__(self, dataset_dir: Path, cfg: OptimizeConfig) -> None:
        """Store the dataset directory and the run configuration."""
        self.dataset_dir = Path(dataset_dir)
        self.cfg = cfg
        self.registry = OperatorRegistry()

    @classmethod
    def from_dataset(cls, dataset_dir: Path, cfg: OptimizeConfig) -> Optimizer:
        """Build an optimizer that reads the given compiled dataset."""
        return cls(dataset_dir, cfg)

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

    def _evaluate(self, schedule: Schedule, targets: list[Target]) -> float:
        """Return the objective for a schedule."""
        simulator = Simulator.from_dataset(self.dataset_dir)
        values = simulator.simulate(self._schedule_frame(schedule), self.cfg.years)
        return objective(values, targets)

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
        if self.cfg.metaheuristic == "tabu":
            return solve_tabu(
                problem,
                rng,
                iterations=self.cfg.iterations,
                tenure=self.cfg.tenure,
                on_step=on_step,
            )
        if self.cfg.metaheuristic == "ils":
            return solve_ils(
                problem,
                rng,
                iterations=self.cfg.iterations,
                perturbation=self.cfg.perturbation,
                on_step=on_step,
            )
        return solve_sa(
            problem,
            rng,
            iterations=self.cfg.iterations,
            temperature=self.cfg.temperature,
            cooling=self.cfg.cooling,
            on_step=on_step,
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
        simulator = Simulator.from_dataset(self.dataset_dir)
        values = simulator.run(schedule_path, years=self.cfg.years, out_dir=out_dir)
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
        }
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
