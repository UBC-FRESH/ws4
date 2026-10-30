#!/usr/bin/env python3
"""Compare the fixed round-robin portfolio with the best single GPU method on c5.

Run on a compiled c5 dataset with a CUDA device::

    python examples/gpu_effects/portfolio_c5.py \
        --dataset /path/to/c5_compiled \
        --targets examples/c5_base/targets_balanced_stock79.yaml \
        --seed-schedule examples/c5_base/seed_stage1.csv \
        --blocks 2000 --seconds 15 --seeds 7 8 9 --out portfolio_results.json

The portfolio and the single GA receive the same search wall-clock budget.  The effect
table build is shared and is not charged to either search.  Every reported objective is a
fresh ``IncrementalObjective`` evaluation of the returned schedule; a portfolio worker
that claims a different objective raises instead of being reported.

This is a slice prototype, not a full-model or production claim.  The fixed allocation is
two SA workers, one tabu worker, one ILS worker, one GA worker, one CPU LNS worker, and one
diverse-restart SA worker.  The GA slot is the P83.8 GPU population search.  The benchmark
is bounded; use ``--seeds`` to repeat it, and report a negative result when the single
method is better.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ws4.opt.engine import OptimizeConfig, Optimizer, load_schedule_csv  # noqa: E402
from ws4.opt.gpu_effects import EffectTable  # noqa: E402
from ws4.opt.gpu_ga import GenomePopulation  # noqa: E402
from ws4.opt.incremental import IncrementalObjective  # noqa: E402
from ws4.opt.meta_portfolio import MetaPortfolio, WorkerSpec  # noqa: E402
from ws4.opt.objective import load_targets  # noqa: E402


def exact(
    optimizer: Optimizer,
    targets: list[object],
    schedule: dict[int, tuple[tuple[str, int], ...]],
) -> float:
    """Return a fresh exact incremental objective for a schedule."""
    evaluator = IncrementalObjective(optimizer, targets)
    evaluator.reset(schedule)
    return evaluator.objective


def slice_schedule(
    optimizer: Optimizer, seed_schedule: dict[int, tuple[tuple[str, int], ...]], blocks: int
) -> tuple[list[int], dict[int, tuple[tuple[str, int], ...]]]:
    """Return the seed-first block slice and its initial schedule."""
    candidates = optimizer.candidates()
    seed_blocks = [block for block in seed_schedule if block in candidates]
    seen = set(seed_blocks)
    others = [block for block in sorted(candidates) if block not in seen]
    random.Random(7).shuffle(others)
    chosen = (seed_blocks + others)[:blocks]
    chosen_set = set(chosen)
    initial = {block: chain for block, chain in seed_schedule.items() if block in chosen_set}
    if not initial:
        initial = {block: candidates[block][0] for block in chosen if candidates[block]}
    return chosen, initial


def portfolio_workers(seed: int) -> tuple[WorkerSpec, ...]:
    """Return the fixed seven-slot allocation for one benchmark seed."""
    return (
        WorkerSpec("sa-1", "sa", 400, seed + 1),
        WorkerSpec("sa-2", "sa", 400, seed + 2),
        WorkerSpec("tabu-1", "tabu", 10, seed + 3),
        WorkerSpec("ils-1", "ils", 20, seed + 4),
        WorkerSpec("ga-1", "ga", 200, seed),
        WorkerSpec("lns-1", "lns", 400, seed + 5),
        WorkerSpec("restart-1", "sa", 400, seed + 6, diverse=True),
    )


def main() -> None:
    """Run the portfolio and single-GA comparison and write a JSON report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path)
    parser.add_argument("--blocks", type=int, default=2000)
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--population", type=int, default=224)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7])
    parser.add_argument("--out", type=Path, default=Path("portfolio_results.json"))
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available")
    if args.seconds <= 0.0:
        raise SystemExit("--seconds must be positive")

    cfg = OptimizeConfig(
        years=args.years,
        targets_path=str(args.targets),
        iterations=1,
        lns_max_destroy=64,
        threads=1,
    )
    optimizer = Optimizer.from_dataset(args.dataset, cfg)
    targets = load_targets(args.targets)
    candidates = optimizer.candidates()
    seed_schedule = load_schedule_csv(args.seed_schedule) if args.seed_schedule is not None else {}
    blocks, initial = slice_schedule(optimizer, seed_schedule, args.blocks)
    chosen = set(blocks)
    slice_candidates = {block: candidates[block] for block in blocks if block in candidates}

    started = time.perf_counter()
    table_cpu = EffectTable.build(
        optimizer,
        IncrementalObjective(optimizer, targets),
        blocks=blocks,
        extra_pairs=list(initial.items()),
        candidates=candidates,
    )
    build_seconds = time.perf_counter() - started
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    table = table_cpu.to("cuda")
    torch.cuda.synchronize()
    upload_seconds = time.perf_counter() - started
    seed_objective = exact(optimizer, targets, initial)

    results: list[dict[str, object]] = []
    for seed in args.seeds:
        portfolio = MetaPortfolio(
            optimizer,
            targets,
            initial=initial,
            candidates=slice_candidates,
            table=table,
            workers=portfolio_workers(seed),
            rounds=1000,
            temperature=1000.0,
            cooling=0.99,
            tenure=10,
            tabu_samples=2,
            perturbation=2,
            ga_population=args.population,
            ga_random_fraction=0.15,
            ga_mutation_rate=0.002,
        )
        started = time.perf_counter()
        portfolio_result = portfolio.run(time_limit=args.seconds)
        portfolio_seconds = time.perf_counter() - started

        started = time.perf_counter()
        single = GenomePopulation(
            optimizer,
            IncrementalObjective(optimizer, targets),
            table,
            population=args.population,
            seed=seed,
            seed_schedule=initial,
            candidates=slice_candidates,
            random_fraction=0.15,
            mutation_rate=0.002,
        )
        single_result = single.run(10**9, deadline=started + args.seconds)
        single_seconds = time.perf_counter() - started

        record = {
            "seed": seed,
            "seed_objective": seed_objective,
            "portfolio_objective": exact(optimizer, targets, portfolio_result.schedule),
            "portfolio_seconds": portfolio_seconds,
            "portfolio_rounds": portfolio_result.rounds,
            "portfolio_migrations": len(portfolio_result.migrations),
            "portfolio_evaluations": portfolio_result.evaluations,
            "portfolio_contributions": portfolio_result.as_dict()["contributions"],
            "single_objective": exact(optimizer, targets, single_result.schedule),
            "single_seconds": single_seconds,
            "single_generations": single_result.generations,
            "single_evaluations": single_result.evaluations,
            "portfolio_better": portfolio_result.objective <= single_result.objective,
        }
        results.append(record)
        print(json.dumps(record))

    report = {
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "dataset": str(args.dataset),
        "targets": str(args.targets),
        "blocks": len(chosen),
        "rows": table.rows,
        "nnz": table.nnz,
        "table_bytes": table.nbytes(),
        "build_seconds": build_seconds,
        "upload_seconds": upload_seconds,
        "vram_max_allocated_bytes": torch.cuda.max_memory_allocated(),
        "vram_max_reserved_bytes": torch.cuda.max_memory_reserved(),
        "seconds_budget": args.seconds,
        "population": args.population,
        "runs": results,
    }
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
