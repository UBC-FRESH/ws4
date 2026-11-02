#!/usr/bin/env python3
"""Compare LTSY target formulations on one resident GPU population.

Each scenario reuses the same seed schedule, population size, random seed, effect table,
candidate store, and factorized padded cache. The only difference is the target YAML.

Example::

    python examples/gpu_effects/compare_ltsy_scenarios.py \
        --dataset /path/to/compiled \
        --table /path/to/effects-lean.pt \
        --factorized /path/to/tsa24-factorized.npz \
        --factorized-cache /path/to/tsa24-factorized.padded.pt \
        --cache-dir /path/to/runtime/gpu-cache \
        --seed-schedule /path/to/seed.csv \
        --scenario baseline=/path/to/evenflow_tsa24_ltsy.yaml \
        --scenario allperiod5_stock=/path/to/evenflow_tsa24_allperiods5_stock90.yaml \
        --scenario allperiod5_nostock=/path/to/evenflow_tsa24_allperiods5.yaml \
        --generations 5000 --out-dir /path/to/archive/scenarios
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ws4.opt.archive import write_schedule  # noqa: E402
from ws4.opt.candidate_cache import CompactCandidates, load_or_build_candidates  # noqa: E402
from ws4.opt.engine import OptimizeConfig, Optimizer, load_schedule_csv  # noqa: E402
from ws4.opt.factorized_effects import (  # noqa: E402
    FactorizedAccountSet,
    FactorizedEffectArrays,
)
from ws4.opt.gpu_effects import EffectTable  # noqa: E402
from ws4.opt.gpu_ga import GenomePopulation  # noqa: E402
from ws4.opt.incremental import IncrementalObjective  # noqa: E402
from ws4.opt.objective import load_targets  # noqa: E402


def _scenario(value: str) -> tuple[str, Path]:
    """Parse ``name=path`` from the command line."""
    name, _, raw = value.partition("=")
    if not name or not raw:
        raise argparse.ArgumentTypeError("scenario must be name=path")
    return name, Path(raw)


def _seed_schedule(
    blocks: np.ndarray,
    candidates: CompactCandidates,
    path: Path | None,
) -> dict[int, tuple[tuple[str, int], ...]]:
    """Return a candidate-only seed schedule."""
    requested = load_schedule_csv(path) if path is not None else {}
    seed: dict[int, tuple[tuple[str, int], ...]] = {}
    for block in blocks:
        count = candidates.option_count(int(block))
        if count <= 0:
            continue
        chain = requested.get(int(block), candidates.chain_at(int(block), 0))
        if candidates.index_of(int(block), chain) is None:
            chain = candidates.chain_at(int(block), 0)
        seed[int(block)] = chain
    return seed


def main() -> None:
    """Run all named scenarios and write schedules plus a JSON result table."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--factorized", type=Path, required=True)
    parser.add_argument("--factorized-cache", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path)
    parser.add_argument("--scenario", action="append", type=_scenario, required=True)
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--population", type=int, default=64)
    parser.add_argument("--generations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("CUDA is not available")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    table = EffectTable.load(args.table, device=args.device)
    arrays = FactorizedEffectArrays.load(args.factorized)
    blocks = np.asarray(table.blocks, dtype=np.int64)
    if not np.array_equal(arrays.blocks, blocks):
        raise SystemExit("factorized artifact blocks do not match the effect table")
    cfg = OptimizeConfig(
        years=args.years,
        iterations=1,
        threads=1,
    )
    optimizer = Optimizer.from_dataset(args.dataset, cfg)
    candidates_path = args.cache_dir / "candidates-compact.npz"
    candidates: Any
    if candidates_path.is_file():
        candidates = CompactCandidates.load(candidates_path)
    else:
        candidates = load_or_build_candidates(optimizer, args.cache_dir / "candidates.pkl")
    accounts = FactorizedAccountSet.from_artifact(
        args.factorized,
        optimizer.simulator(),
        years=args.years,
        device=args.device,
        cache=args.factorized_cache,
    )
    seed = _seed_schedule(blocks, candidates, args.seed_schedule)
    population = GenomePopulation(
        optimizer,
        IncrementalObjective(optimizer, []),
        table,
        population=args.population,
        seed=args.seed,
        seed_schedule=seed,
        candidates=candidates,
        factorized=accounts,
        random_fraction=0.05,
        initial_mutation_rate=0.02,
        mutation_rate=0.002,
    )
    initial_cells = len(population.table.cells)

    records: list[dict[str, object]] = []
    for name, target_path in args.scenario:
        targets = load_targets(target_path)
        started = time.perf_counter()
        population.reset(seed, seed=args.seed)
        population.update_targets(targets)
        result = population.run(args.generations, check=0)
        seconds = time.perf_counter() - started
        schedule_path = args.out_dir / f"{name}.csv"
        write_schedule(schedule_path, result.schedule)
        exact = IncrementalObjective(optimizer, targets)
        exact.reset(result.schedule)
        records.append(
            {
                "name": name,
                "targets": str(target_path),
                "schedule": str(schedule_path),
                "objective": result.objective,
                "exact_objective": exact.objective,
                "objective_error": abs(result.objective - exact.objective),
                "generations": result.generations,
                "evaluations": result.evaluations,
                "seconds": seconds,
                "table_cells": len(population.table.cells),
                "factorized_cells": [
                    [int(offset), str(account)] for offset, account in population._extra_cells
                ],
            }
        )
        print(json.dumps(records[-1], sort_keys=True))

    if len(population.table.cells) != initial_cells:
        raise SystemExit("a scenario changed the sparse effect-table cell count")
    (args.out_dir / "results.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
