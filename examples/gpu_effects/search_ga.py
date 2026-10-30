#!/usr/bin/env python3
"""Compare the GPU population search with CPU SA/LNS and batched GPU LNS on c5.

Run on a compiled dataset::

    python examples/gpu_effects/search_ga.py \
        --dataset /path/to/c5_compiled \
        --targets /path/to/targets_balanced_stock79.yaml \
        --seed-schedule /path/to/seed_stage1.csv \
        --blocks 2000 --population 256 --generations 500 \
        --cpu-iterations 30000 --seeds 7 8 9 --out ga_results.json

The CPU baseline is the current reference path, ``solve_sa_delta`` with the stock
``LnsOperator``.  The batched GPU LNS prototype keeps one schedule and accepts the best of
each proposal batch.  The population search evaluates one full genome per block and breeds
with elitism, tournament selection, uniform crossover, and mutation.  Every result is
re-evaluated from scratch with ``IncrementalObjective`` before it is reported, and the
population's device fitness is checked against the exact evaluator on its first
generation.
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
from ws4.opt.gpu_search import BatchedLnsSearch  # noqa: E402
from ws4.opt.incremental import IncrementalObjective  # noqa: E402
from ws4.opt.objective import load_targets  # noqa: E402
from ws4.opt.operators import LnsOperator, OperatorRegistry  # noqa: E402
from ws4.opt.solvers import solve_sa_delta  # noqa: E402


def _slice(
    candidates: dict[int, list[tuple[tuple[str, int], ...]]],
    seed_schedule: dict[int, tuple[tuple[str, int], ...]],
    blocks: int,
) -> tuple[list[int], dict[int, tuple[tuple[str, int], ...]]]:
    """Return the seed-first block slice and its initial schedule."""
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


def main() -> None:
    """Run the CPU and GPU searches and write a JSON comparison."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path)
    parser.add_argument("--blocks", type=int, default=2000)
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--population", type=int, default=256)
    parser.add_argument("--generations", type=int, default=500)
    parser.add_argument("--random-fraction", type=float, default=0.15)
    parser.add_argument("--initial-mutation-rate", type=float, default=0.05)
    parser.add_argument("--mutation-rate", type=float, default=0.002)
    parser.add_argument("--elite-fraction", type=float, default=0.1)
    parser.add_argument("--tournament-size", type=int, default=3)
    parser.add_argument("--islands", type=int, default=1)
    parser.add_argument("--exchange", choices=["ring", "agrp"], default="ring")
    parser.add_argument("--migration-interval", type=int, default=0)
    parser.add_argument("--migrants", type=int, default=1)
    parser.add_argument("--cpu-iterations", type=int, default=30000)
    parser.add_argument("--lns-proposals", type=int, default=0)
    parser.add_argument("--lns-rounds", type=int, default=0)
    parser.add_argument("--check", type=int, default=8)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 8, 9])
    parser.add_argument("--skip-cpu", action="store_true")
    parser.add_argument("--skip-lns", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("ga_results.json"))
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available")

    cfg = OptimizeConfig(
        years=args.years,
        targets_path=str(args.targets),
        iterations=1,
        lns_max_destroy=64,
        threads=1,
    )
    optimizer = Optimizer.from_dataset(args.dataset, cfg)
    targets = load_targets(args.targets)
    evaluator = IncrementalObjective(optimizer, targets)
    candidates = optimizer.candidates()

    seed_schedule = load_schedule_csv(args.seed_schedule) if args.seed_schedule is not None else {}
    blocks, initial = _slice(candidates, seed_schedule, args.blocks)
    extras = [
        (block, chain) for block, chain in initial.items() if chain not in candidates.get(block, ())
    ]

    started = time.perf_counter()
    table_cpu = EffectTable.build(
        optimizer,
        evaluator,
        blocks,
        extra_pairs=extras,
        candidates=candidates,
    )
    build_seconds = time.perf_counter() - started
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    table = table_cpu.to("cuda")
    torch.cuda.synchronize()
    upload_seconds = time.perf_counter() - started

    lns_proposals = args.population if args.lns_proposals <= 0 else args.lns_proposals
    lns_rounds = args.generations if args.lns_rounds <= 0 else args.lns_rounds
    registry = OperatorRegistry([LnsOperator(weight=1.0, destroy_fraction=0.1, max_destroy=64)])
    cooling = (1.0 / 1000.0) ** (1.0 / max(1, args.cpu_iterations))
    runs: list[dict[str, object]] = []
    for seed in args.seeds:
        record: dict[str, object] = {"seed": seed}
        if not args.skip_cpu:
            cpu_evaluator = IncrementalObjective(optimizer, targets)
            started = time.perf_counter()
            cpu_best, _objective = solve_sa_delta(
                cpu_evaluator,
                random.Random(seed),
                iterations=args.cpu_iterations,
                temperature=1000.0,
                cooling=cooling,
                initial=initial,
                candidates=candidates,
                registry=registry,
            )
            cpu_seconds = time.perf_counter() - started
            cpu_verify = IncrementalObjective(optimizer, targets)
            cpu_verify.reset(cpu_best)
            record.update(
                cpu_objective=cpu_verify.objective,
                cpu_seconds=cpu_seconds,
                cpu_iterations=args.cpu_iterations,
            )

        if not args.skip_lns:
            lns = BatchedLnsSearch(
                optimizer,
                evaluator,
                table,
                proposals=lns_proposals,
                temperature=1e8,
                final_temperature=1e3,
                seed=seed,
            )
            lns_result = lns.run(initial, lns_rounds, check=1 if args.check > 0 else 0)
            lns_verify = IncrementalObjective(optimizer, targets)
            lns_verify.reset(lns_result.schedule)
            record.update(
                lns_objective=lns_verify.objective,
                lns_seconds=lns_result.seconds,
                lns_evaluations=lns_result.proposals,
                lns_accepted=lns_result.accepted,
                lns_rounds=lns_rounds,
                lns_proposals_per_round=lns_proposals,
            )

        population = GenomePopulation(
            optimizer,
            evaluator,
            table,
            population=args.population,
            seed=seed,
            seed_schedule=initial,
            candidates=candidates,
            random_fraction=args.random_fraction,
            initial_mutation_rate=args.initial_mutation_rate,
            mutation_rate=args.mutation_rate,
            elite_fraction=args.elite_fraction,
            tournament_size=args.tournament_size,
            islands=args.islands,
            exchange=args.exchange,
            migration_interval=args.migration_interval,
            migrants=args.migrants,
        )
        ga_started = time.perf_counter()
        ga_result = population.run(args.generations, check=args.check)
        ga_seconds = time.perf_counter() - ga_started
        ga_verify = IncrementalObjective(optimizer, targets)
        ga_verify.reset(ga_result.schedule)
        record.update(
            ga_objective=ga_verify.objective,
            ga_seconds=ga_seconds,
            ga_evaluations=ga_result.evaluations,
            ga_generations=ga_result.generations,
            ga_best_generation=ga_result.best_generation,
            ga_best_island=ga_result.best_island,
            ga_initial_objective=ga_result.initial_objective,
            ga_objective_gain=ga_result.objective_gain,
            ga_history=ga_result.history,
        )

        if "cpu_objective" in record:
            cpu_objective = float(record["cpu_objective"])
            cpu_seconds = float(record["cpu_seconds"])
            record["ga_speedup"] = cpu_seconds / max(1e-9, ga_seconds)
            record["ga_quality_at_least_cpu"] = float(record["ga_objective"]) <= cpu_objective
            if "lns_objective" in record:
                record["lns_speedup"] = cpu_seconds / max(1e-9, float(record["lns_seconds"]))
                record["lns_quality_at_least_cpu"] = float(record["lns_objective"]) <= cpu_objective
        record["ga_cost_including_build_speedup"] = (
            float(record["cpu_seconds"]) / max(1e-9, ga_seconds + build_seconds + upload_seconds)
            if "cpu_seconds" in record
            else None
        )
        runs.append(record)
        print(json.dumps({key: value for key, value in record.items() if key != "ga_history"}))
        print(
            json.dumps(
                {
                    "seed": seed,
                    "ga_history_head": ga_result.history[:5],
                    "ga_history_tail": ga_result.history[-5:],
                }
            )
        )

    results = {
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "dataset": str(args.dataset),
        "targets": str(args.targets),
        "blocks": len(blocks),
        "extra_seed_chains": len(extras),
        "rows": table.rows,
        "nnz": table.nnz,
        "target_cells": table.columns,
        "table_bytes": table.nbytes(),
        "build_seconds": build_seconds,
        "upload_seconds": upload_seconds,
        "vram_max_allocated_bytes": torch.cuda.max_memory_allocated(),
        "vram_max_reserved_bytes": torch.cuda.max_memory_reserved(),
        "population": args.population,
        "generations": args.generations,
        "islands": args.islands,
        "exchange": args.exchange,
        "migration_interval": args.migration_interval,
        "migrants": args.migrants,
        "cpu_iterations": args.cpu_iterations,
        "lns_rounds": lns_rounds,
        "lns_proposals_per_round": lns_proposals,
        "check": args.check,
        "runs": runs,
    }
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
