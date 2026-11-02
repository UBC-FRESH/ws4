#!/usr/bin/env python3
"""Run a mixed-target factorized population on a full compiled model.

This is the P89.1 end-to-end check: the sparse table keeps its original cells, while a
feature and a second product account are priced from the P88 factorized basis.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ws4.opt.engine import OptimizeConfig, Optimizer, load_schedule_csv  # noqa: E402
from ws4.opt.factorized_effects import (  # noqa: E402
    FactorizedAccountSet,
    FactorizedEffectArrays,
)
from ws4.opt.gpu_effects import EffectTable  # noqa: E402
from ws4.opt.gpu_ga import GenomePopulation  # noqa: E402
from ws4.opt.incremental import IncrementalObjective  # noqa: E402
from ws4.opt.objective import Target  # noqa: E402


def _seed(
    blocks: np.ndarray,
    candidates: dict[int, list[tuple[tuple[str, int], ...]]],
    schedule_path: Path | None,
) -> dict[int, tuple[tuple[str, int], ...]]:
    """Return a seed schedule whose chains are all candidate rows."""
    payload = load_schedule_csv(schedule_path) if schedule_path is not None else {}
    seed: dict[int, tuple[tuple[str, int], ...]] = {}
    for block in blocks:
        chains = candidates[int(block)]
        if not chains:
            continue
        chain = payload.get(int(block), chains[0])
        if chain not in chains:
            chain = chains[0]
        seed[int(block)] = chain
    return seed


def main() -> None:
    """Run the mixed-target population and record exact replay and memory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path)
    parser.add_argument("--feature", default="feature.Yield.managed.Total")
    parser.add_argument("--product", default="product.Yield.managed.Total")
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--period-width", type=int, default=10)
    parser.add_argument("--population", type=int, default=64)
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--check", type=int, default=0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out", type=Path, default=Path("factorized_mixed_population.json"))
    args = parser.parse_args()

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("CUDA is not available")

    cfg = OptimizeConfig(
        years=args.years,
        targets_path=str(args.targets),
        iterations=1,
        threads=1,
    )
    optimizer = Optimizer.from_dataset(args.dataset, cfg)
    candidates = optimizer.candidates()
    blocks = np.asarray(sorted(candidates), dtype=np.int64)
    table = EffectTable.load(args.table)
    if not np.array_equal(table.blocks, blocks):
        raise SystemExit("effect table block order does not match candidates")
    arrays = FactorizedEffectArrays.load(args.artifact)
    if not np.array_equal(arrays.blocks, blocks):
        raise SystemExit("factorized artifact block order does not match candidates")

    table_account = table.cells[0][1]
    initial_targets = [Target(table_account, period=1, period_width=args.period_width, minimum=1.0)]
    initial = IncrementalObjective(optimizer, initial_targets)
    mixed_targets = [
        Target(
            table_account,
            period=1,
            period_width=args.period_width,
            flow="even",
            minimum=-5.0,
            maximum=5.0,
            min_weight=1.0,
            max_weight=1.0,
        ),
        Target(
            args.feature,
            period=20,
            period_width=args.period_width,
            minimum=100_000_000.0,
        ),
        Target(
            args.product,
            period=20,
            period_width=args.period_width,
            minimum=1_000_000.0,
        ),
    ]

    started = time.perf_counter()
    accounts = FactorizedAccountSet.from_arrays(
        arrays,
        optimizer.simulator(),
        years=args.years,
        device=args.device,
    )
    build_seconds = time.perf_counter() - started
    del arrays

    seed = _seed(blocks, candidates, args.seed_schedule)
    started = time.perf_counter()
    population = GenomePopulation(
        optimizer,
        initial,
        table,
        population=args.population,
        seed=7,
        seed_schedule=seed,
        candidates=candidates,
        factorized=accounts,
    )
    population_seconds = time.perf_counter() - started
    initial_cells = len(population.table.cells)

    started = time.perf_counter()
    population.update_targets(mixed_targets)
    switch_seconds = time.perf_counter() - started
    switched_cells = len(population.table.cells)
    if switched_cells != initial_cells:
        raise SystemExit("mixed target switch changed the effect-table cell count")

    started = time.perf_counter()
    result = population.run(args.generations, check=args.check)
    run_seconds = time.perf_counter() - started

    exact = IncrementalObjective(optimizer, mixed_targets)
    exact.reset(result.schedule)
    exact_objective = exact.objective
    error = abs(result.objective - exact_objective)

    record = {
        "table_account": table_account,
        "feature": args.feature,
        "product": args.product,
        "population": args.population,
        "generations": args.generations,
        "table_cells": initial_cells,
        "switched_table_cells": switched_cells,
        "factorized_cells": [list(cell) for cell in population._extra_cells],
        "factorized_build_seconds": build_seconds,
        "population_seconds": population_seconds,
        "switch_seconds": switch_seconds,
        "run_seconds": run_seconds,
        "evaluations_per_second": result.evaluations / run_seconds,
        "evaluations": result.evaluations,
        "best_objective": result.objective,
        "exact_objective": exact_objective,
        "objective_error": error,
        "best_generation": result.best_generation,
        "gpu_peak_bytes": (
            int(torch.cuda.max_memory_allocated()) if args.device.startswith("cuda") else 0
        ),
    }
    if error > 1e-3:
        raise SystemExit(f"mixed population objective differs from exact: {error}")
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
