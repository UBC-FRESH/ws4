#!/usr/bin/env python3
"""Compare the batched GPU LNS prototype with the CPU LNS reference on c5.

Run on a compiled c5 dataset::

    python examples/gpu_effects/search_c5.py \
        --dataset /path/to/c5_compiled \
        --targets /path/to/targets_balanced_stock79.yaml \
        --seed-schedule /path/to/seed_stage1.csv \
        --blocks 2000 --rounds 500 --proposals 128 \
        --cpu-iterations 30000 --seeds 7 8 9 --out search_results.json

The CPU baseline is the current reference path: ``solve_sa_delta`` with the stock
``LnsOperator`` and the same 64-block cap.  The GPU prototype prices 128 independent
proposals per round and accepts the best one.  Both results are re-evaluated from scratch
with ``IncrementalObjective`` before they are reported, so a stale incremental state cannot
hide a wrong objective.
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
from ws4.opt.gpu_search import BatchedLnsSearch  # noqa: E402
from ws4.opt.incremental import IncrementalObjective  # noqa: E402
from ws4.opt.objective import load_targets  # noqa: E402
from ws4.opt.operators import LnsOperator, OperatorRegistry  # noqa: E402
from ws4.opt.solvers import solve_sa_delta  # noqa: E402


def main() -> None:
    """Run the GPU and CPU searches and write a JSON comparison."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path)
    parser.add_argument("--blocks", type=int, default=2000)
    parser.add_argument("--rounds", type=int, default=500)
    parser.add_argument("--proposals", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=1e8)
    parser.add_argument("--final-temperature", type=float, default=1e3)
    parser.add_argument("--cpu-iterations", type=int, default=30000)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 8, 9])
    parser.add_argument("--out", type=Path, default=Path("gpu_search_results.json"))
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available")

    cfg = OptimizeConfig(
        years=200,
        targets_path=str(args.targets),
        iterations=1,
        lns_max_destroy=64,
        threads=1,
    )
    optimizer = Optimizer.from_dataset(args.dataset, cfg)
    targets = load_targets(args.targets)
    evaluator = IncrementalObjective(optimizer, targets)
    candidates = optimizer.candidates()

    if args.seed_schedule is not None:
        seed_schedule = load_schedule_csv(args.seed_schedule)
        seed_blocks = [block for block in seed_schedule if block in candidates]
    else:
        seed_schedule = {}
        seed_blocks = []
    others = [block for block in sorted(candidates) if block not in set(seed_blocks)]
    random.Random(7).shuffle(others)
    blocks = (seed_blocks + others)[: args.blocks]
    if seed_schedule:
        initial = {block: chain for block, chain in seed_schedule.items() if block in set(blocks)}
    else:
        initial = {block: candidates[block][0] for block in blocks if candidates[block]}

    started = time.perf_counter()
    table_cpu = EffectTable.build(
        optimizer,
        evaluator,
        blocks,
        extra_pairs=list(initial.items()),
        candidates=candidates,
    )
    build_seconds = time.perf_counter() - started
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    table = table_cpu.to("cuda")
    torch.cuda.synchronize()
    upload_seconds = time.perf_counter() - started

    registry = OperatorRegistry([LnsOperator(weight=1.0, destroy_fraction=0.1, max_destroy=64)])
    cooling = (1.0 / 1000.0) ** (1.0 / max(1, args.cpu_iterations))
    runs: list[dict[str, object]] = []
    for seed in args.seeds:
        cpu_evaluator = IncrementalObjective(optimizer, targets)
        started = time.perf_counter()
        best, _objective = solve_sa_delta(
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
        cpu_verify.reset(best)

        search = BatchedLnsSearch(
            optimizer,
            evaluator,
            table,
            proposals=args.proposals,
            temperature=args.temperature,
            final_temperature=args.final_temperature,
            seed=seed,
        )
        result = search.run(initial, args.rounds)
        gpu_verify = IncrementalObjective(optimizer, targets)
        gpu_verify.reset(result.schedule)
        runs.append(
            {
                "seed": seed,
                "cpu_objective": cpu_verify.objective,
                "cpu_seconds": cpu_seconds,
                "gpu_objective": gpu_verify.objective,
                "gpu_seconds": result.seconds,
                "gpu_accepted": result.accepted,
                "gpu_proposals": result.proposals,
                "search_speedup": cpu_seconds / max(1e-9, result.seconds),
                "cost_including_build_speedup": cpu_seconds
                / max(1e-9, result.seconds + build_seconds + upload_seconds),
                "gpu_quality_at_least_cpu": gpu_verify.objective <= cpu_verify.objective,
            }
        )
        print(json.dumps(runs[-1]))

    results = {
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "dataset": str(args.dataset),
        "targets": str(args.targets),
        "blocks": len(blocks),
        "rows": table.rows,
        "nnz": table.nnz,
        "table_bytes": table.nbytes(),
        "build_seconds": build_seconds,
        "upload_seconds": upload_seconds,
        "vram_max_allocated_bytes": torch.cuda.max_memory_allocated(),
        "vram_max_reserved_bytes": torch.cuda.max_memory_reserved(),
        "rounds": args.rounds,
        "proposals_per_round": args.proposals,
        "temperature": args.temperature,
        "final_temperature": args.final_temperature,
        "cpu_iterations": args.cpu_iterations,
        "cooling": cooling,
        "runs": runs,
    }
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
