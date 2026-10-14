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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ..sim.engine import Simulator
from .objective import Target, load_targets, objective
from .operators import Candidates, OperatorRegistry, Schedule


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

    def run(self, out_dir: Path) -> dict[str, Any]:
        """Run the search and write the incumbent schedule and a summary.

        Parameters
        ----------
        out_dir : Path
            Directory to write ``schedule.csv``, ``account_values.csv``, and
            ``summary.json`` into.

        Returns
        -------
        dict of str to Any
            The run summary.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        targets = load_targets(Path(self.cfg.targets_path)) if self.cfg.targets_path else []
        candidates = self.candidates()
        rng = random.Random(self.cfg.seed)

        current: Schedule = {}
        current_obj = self._evaluate(current, targets)
        best, best_obj = dict(current), current_obj
        temperature = self.cfg.temperature
        for _ in range(self.cfg.iterations):
            move = self.registry.pick(rng).apply(current, rng, candidates)
            if move is None:
                continue
            move_obj = self._evaluate(move, targets)
            if move_obj <= current_obj or rng.random() < math.exp(
                (current_obj - move_obj) / max(temperature, 1e-9)
            ):
                current, current_obj = move, move_obj
                if move_obj < best_obj:
                    best, best_obj = dict(move), move_obj
            temperature *= self.cfg.cooling

        schedule_path = out_dir / "schedule.csv"
        self._schedule_frame(best).to_csv(schedule_path, index=False)
        simulator = Simulator.from_dataset(self.dataset_dir)
        simulator.run(schedule_path, years=self.cfg.years, out_dir=out_dir)
        summary: dict[str, Any] = {
            "incumbent_objective": best_obj,
            "iterations": self.cfg.iterations,
            "seed": self.cfg.seed,
            "blocks_scheduled": len(best),
            "operators": self.registry.names(),
            "status": "ok",
        }
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary
