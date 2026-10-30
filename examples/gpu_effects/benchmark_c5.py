#!/usr/bin/env python3
"""Benchmark the sparse float64 effect table against the CPU contribution lookup.

Run on a compiled c5 dataset::

    python examples/gpu_effects/benchmark_c5.py \
        --dataset /path/to/c5_compiled \
        --targets /path/to/targets_balanced_stock79.yaml \
        --seed-schedule /path/to/seed_stage1.csv \
        --blocks 2000 --out results.json

The script does not change the optimizer.  It builds the effect rows through the existing
``Optimizer._block_deltas`` path, then times the same steady-state operations a search
would use: a single-row gather, a row difference, and a 64-block segmented delta.  The CPU
baseline is the warm ``IncrementalObjective.contribution`` dictionary plus a pending sum.
Both sides price the same rows; the CPU side is generous because it excludes the penalty
reduction and cold-cache prefetch.
"""

from __future__ import annotations

import argparse
import functools
import json
import random
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ws4.opt.engine import OptimizeConfig, Optimizer, load_schedule_csv  # noqa: E402
from ws4.opt.gpu_effects import EffectTable  # noqa: E402
from ws4.opt.incremental import IncrementalObjective  # noqa: E402
from ws4.opt.objective import load_targets  # noqa: E402

Cell = tuple[int, str]


def timed_cpu(call: Callable[[], None], repeats: int) -> float:
    """Return the median seconds per call on the CPU."""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        call()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def timed_cuda(call: Callable[[], None], repeats: int) -> float:
    """Return the median synchronized seconds per call on the GPU."""
    samples = []
    for _ in range(repeats):
        torch.cuda.synchronize()
        start = time.perf_counter()
        call()
        torch.cuda.synchronize()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def timed_events(call: Callable[[], None], repeats: int) -> float:
    """Return the amortized CUDA-event seconds per back-to-back call."""
    call()
    torch.cuda.synchronize()
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    start.record()
    for _ in range(repeats):
        call()
    end.record()
    end.synchronize()
    return start.elapsed_time(end) / 1000.0 / repeats


def pending_from_contributions(
    contributions: dict[tuple[int, tuple], dict[Cell, float]],
    new_rows: list[tuple[int, tuple]],
    old_rows: list[tuple[int, tuple]],
) -> dict[Cell, float]:
    """Return the CPU exact pending delta for the given signed rows."""
    pending: dict[Cell, float] = {}
    for pair in new_rows:
        for cell, value in contributions[pair].items():
            pending[cell] = pending.get(cell, 0.0) + value
    for pair in old_rows:
        for cell, value in contributions[pair].items():
            pending[cell] = pending.get(cell, 0.0) - value
    return pending


def cpu_single_calls(
    contributions: dict[tuple[int, tuple], dict[Cell, float]],
    specs: list[tuple[int, tuple, tuple]],
) -> None:
    """Price a batch of single-block moves with the CPU contribution lookup."""
    for block, new_chain, old_chain in specs:
        pending_from_contributions(contributions, [(block, new_chain)], [(block, old_chain)])


def cpu_lns_calls(
    contributions: dict[tuple[int, tuple], dict[Cell, float]],
    specs: list[tuple[list[tuple[int, tuple]], list[tuple[int, tuple]]]],
) -> None:
    """Price a batch of LNS moves with the CPU contribution lookup."""
    for new_rows, old_rows in specs:
        pending_from_contributions(contributions, new_rows, old_rows)


def dense_expected(
    pending: dict[Cell, float],
    cell_index: dict[Cell, int],
    columns: int,
) -> torch.Tensor:
    """Return a CPU float64 dense row for a pending delta."""
    out = torch.zeros(columns, dtype=torch.float64)
    for cell, value in pending.items():
        column = cell_index.get(cell)
        if column is not None:
            out[column] = value
    return out


def max_error(actual: torch.Tensor, expected: torch.Tensor) -> float:
    """Return the maximum absolute error."""
    return float((actual.double() - expected).abs().max()) if expected.numel() else 0.0


def main() -> None:
    """Run the benchmark and write a JSON record."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path)
    parser.add_argument("--blocks", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--lns-width", type=int, default=64)
    parser.add_argument("--out", type=Path, default=Path("gpu_effects_results.json"))
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available")
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    cfg = OptimizeConfig(
        years=200,
        targets_path=str(args.targets),
        iterations=1,
        lns_max_destroy=args.lns_width,
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
    random.shuffle(others)
    blocks = (seed_blocks + others)[: args.blocks]

    started = time.perf_counter()
    table_cpu = EffectTable.build(optimizer, evaluator, blocks, candidates=candidates)
    build_seconds = time.perf_counter() - started
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    table = table_cpu.to("cuda")
    torch.cuda.synchronize()
    upload_seconds = time.perf_counter() - started

    cell_index = {cell: column for column, cell in enumerate(table.cells)}
    feature = cell_index.get((199, "feature.total.Yield"))
    conifer = [
        column
        for column, cell in enumerate(table.cells)
        if cell[1] == "product.Yield.managed.Conif"
    ]
    decid = [
        column
        for column, cell in enumerate(table.cells)
        if cell[1] == "product.Yield.managed.Decid"
    ]

    contributions: dict[tuple[int, tuple], dict[Cell, float]] = {}
    for block in blocks:
        for chain in candidates[block]:
            contributions[(block, chain)] = evaluator.contribution(block, chain)
    for block in blocks:
        contributions[(block, ())] = {}

    def row_id(block: int, chain: tuple) -> int:
        return 0 if not chain else table.row_index[(block, chain)]

    rng = random.Random(args.seed)
    single_specs = []
    for _ in range(4096):
        block = rng.choice(blocks)
        new_chain = rng.choice(candidates[block])
        old_chain = () if rng.random() < 0.25 else rng.choice(candidates[block] + [()])
        single_specs.append((block, new_chain, old_chain))
    single_new = torch.tensor(
        [row_id(block, chain) for block, chain, _old in single_specs],
        dtype=torch.int64,
        device="cuda",
    )
    single_old = torch.tensor(
        [row_id(_block, chain) for _block, _new, chain in single_specs],
        dtype=torch.int64,
        device="cuda",
    )
    single_gpu = table.move_deltas(single_new, single_old).cpu()
    single_errors = [
        max_error(
            single_gpu[index],
            dense_expected(
                pending_from_contributions(contributions, [(block, new)], [(block, old)]),
                cell_index,
                table.columns,
            ),
        )
        for index, (block, new, old) in enumerate(single_specs)
    ]

    lns_specs = []
    for _ in range(1024):
        chosen = rng.sample(blocks, args.lns_width)
        lns_specs.append(
            (
                [(block, rng.choice(candidates[block])) for block in chosen],
                [
                    (block, () if rng.random() < 0.25 else rng.choice(candidates[block] + [()]))
                    for block in chosen
                ],
            )
        )
    lns_new = torch.tensor(
        [[row_id(block, chain) for block, chain in new] for new, _old in lns_specs],
        dtype=torch.int64,
        device="cuda",
    )
    lns_old = torch.tensor(
        [[row_id(block, chain) for block, chain in old] for _new, old in lns_specs],
        dtype=torch.int64,
        device="cuda",
    )
    lns_gpu = table.lns_deltas(lns_new, lns_old).cpu()
    lns_errors = [
        max_error(
            lns_gpu[index],
            dense_expected(
                pending_from_contributions(contributions, new, old),
                cell_index,
                table.columns,
            ),
        )
        for index, (new, old) in enumerate(lns_specs)
    ]

    single_rows = []
    for moves in (1, 64, 1024, 4096):
        specs = single_specs[:moves]
        new = single_new[:moves]
        old = single_old[:moves]

        cpu_seconds = timed_cpu(functools.partial(cpu_single_calls, contributions, specs), 3)
        gpu_call = functools.partial(table.move_deltas, new, old)
        gpu_seconds = timed_cuda(gpu_call, 5)
        kernel_seconds = timed_events(gpu_call, max(5, 2000 // moves))
        single_rows.append(
            {
                "moves": moves,
                "rows": 2 * moves,
                "cpu_seconds": cpu_seconds,
                "gpu_seconds": gpu_seconds,
                "gpu_kernel_seconds": kernel_seconds,
                "cpu_moves_per_second": moves / cpu_seconds,
                "gpu_moves_per_second": moves / gpu_seconds,
                "gpu_kernel_moves_per_second": moves / kernel_seconds,
                "gpu_rows_per_second": 2 * moves / gpu_seconds,
                "gpu_kernel_rows_per_second": 2 * moves / kernel_seconds,
                "gpu_speedup": cpu_seconds / gpu_seconds,
                "gpu_kernel_speedup": cpu_seconds / kernel_seconds,
            }
        )

    lns_rows = []
    for moves in (1, 16, 64, 256, 1024):
        specs = lns_specs[:moves]
        new = lns_new[:moves]
        old = lns_old[:moves]

        cpu_seconds = timed_cpu(functools.partial(cpu_lns_calls, contributions, specs), 3)
        gpu_call = functools.partial(table.lns_deltas, new, old)
        gpu_seconds = timed_cuda(gpu_call, 5)
        kernel_seconds = timed_events(gpu_call, max(5, 1000 // moves))
        rows = 2 * args.lns_width * moves
        lns_rows.append(
            {
                "moves": moves,
                "blocks_per_move": args.lns_width,
                "rows": rows,
                "cpu_seconds": cpu_seconds,
                "gpu_seconds": gpu_seconds,
                "gpu_kernel_seconds": kernel_seconds,
                "cpu_moves_per_second": moves / cpu_seconds,
                "gpu_moves_per_second": moves / gpu_seconds,
                "gpu_kernel_moves_per_second": moves / kernel_seconds,
                "gpu_rows_per_second": rows / gpu_seconds,
                "gpu_kernel_rows_per_second": rows / kernel_seconds,
                "gpu_speedup": cpu_seconds / gpu_seconds,
                "gpu_kernel_speedup": cpu_seconds / kernel_seconds,
            }
        )

    results = {
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "dataset": str(args.dataset),
        "targets": str(args.targets),
        "blocks": len(blocks),
        "rows": table.rows,
        "nnz": table.nnz,
        "nnz_per_row": table.nnz / max(1, table.rows - 1),
        "target_cells": table.columns,
        "feature_stock_column": feature,
        "conifer_columns": len(conifer),
        "deciduous_columns": len(decid),
        "build_seconds": build_seconds,
        "build_rows_per_second": (table.rows - 1) / build_seconds,
        "upload_seconds": upload_seconds,
        "upload_bytes_per_second": table_cpu.nbytes() / max(1e-9, upload_seconds),
        "table_bytes": table.nbytes(),
        "dense_float64_bytes": table.rows * table.columns * 8,
        "vram_allocated_bytes": torch.cuda.memory_allocated(),
        "vram_max_allocated_bytes": torch.cuda.max_memory_allocated(),
        "vram_max_reserved_bytes": torch.cuda.max_memory_reserved(),
        "single_exactness": {
            "moves": len(single_specs),
            "max_abs_error": max(single_errors),
            "tolerance": {"atol": 1e-8},
            "pass": max(single_errors) <= 1e-8,
        },
        "lns_exactness": {
            "moves": len(lns_specs),
            "blocks_per_move": args.lns_width,
            "max_abs_error": max(lns_errors),
            "tolerance": {"atol": 1e-8},
            "pass": max(lns_errors) <= 1e-8,
        },
        "single_benchmark": single_rows,
        "lns_benchmark": lns_rows,
        "lns_1024_moves_64_blocks": lns_rows[-1],
        "all_exact": max(single_errors) <= 1e-8 and max(lns_errors) <= 1e-8,
    }
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
