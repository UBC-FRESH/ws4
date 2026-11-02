#!/usr/bin/env python3
"""Benchmark mixed feature/product target-cell switching on the factorized basis.

The script builds both padded layouts once, then prices a small mixed cell set for a
batch of genomes. It does not build or save an all-account matrix.
"""

from __future__ import annotations

import argparse
import json
import statistics
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
    PaddedFactorizedEvents,
    PaddedFactorizedTensors,
)


def _available_memory_bytes() -> int:
    """Return Linux MemAvailable in bytes."""
    with Path("/proc/meminfo").open(encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    return 0


def _options(
    blocks: np.ndarray,
    candidates: dict[int, list[tuple[tuple[str, int], ...]]],
    schedule: dict[int, tuple[tuple[str, int], ...]],
) -> dict[int, int]:
    """Map a schedule to candidate positions."""
    options: dict[int, int] = {}
    for block in blocks:
        chain = schedule.get(int(block))
        if chain is None:
            continue
        try:
            options[int(block)] = candidates[int(block)].index(chain)
        except ValueError:
            options[int(block)] = 0
    return options


def main() -> None:
    """Build the account set, verify mixed cells, and time the batch."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path)
    parser.add_argument("--feature", default="feature.Volume")
    parser.add_argument("--product", default="product.Yield.managed.Total")
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--genomes", type=int, default=64)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out", type=Path, default=Path("factorized_switch_benchmark.json"))
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
    simulator = optimizer.simulator()
    arrays = FactorizedEffectArrays.load(args.artifact)
    blocks = np.asarray(sorted(candidates), dtype=np.int64)
    if not np.array_equal(arrays.blocks, blocks):
        raise SystemExit("artifact block order does not match the candidate order")
    estimate = PaddedFactorizedTensors.estimated_bytes(
        arrays
    ) + PaddedFactorizedEvents.estimated_bytes(arrays)
    available = _available_memory_bytes()
    required = int(estimate * 2.5) + 4_000_000_000
    if available and available < required:
        raise SystemExit(
            f"not enough host memory: need >= {required / 1e9:.1f} GB, "
            f"have {available / 1e9:.1f} GB"
        )
    print(
        f"options={arrays.option_count:,} padded_estimate={estimate / 1e9:.2f} GB "
        f"available={available / 1e9:.1f} GB"
    )

    schedule = (
        load_schedule_csv(args.seed_schedule)
        if args.seed_schedule is not None
        else {int(block): candidates[int(block)][0] for block in blocks if candidates[int(block)]}
    )
    options = _options(blocks, candidates, schedule)
    seed_genome = np.asarray([options[int(block)] for block in blocks], dtype=np.int64)
    feature_periods = arrays.feature_period_values(
        args.feature,
        options,
        period_width=10,
        years=args.years,
        simulator=simulator,
    )
    product_years = arrays.product_period_values(
        args.product,
        options,
        period_width=1,
        years=args.years,
        simulator=simulator,
    )
    cells = [
        (9, args.feature),
        (9, args.product),
        (19, args.feature),
        (19, args.product),
    ]
    expected = np.asarray(
        [
            feature_periods[1],
            product_years[10],
            feature_periods[2],
            product_years[20],
        ],
        dtype=np.float64,
    )

    started = time.perf_counter()
    accounts = FactorizedAccountSet.from_arrays(
        arrays,
        simulator,
        years=args.years,
        device=args.device,
    )
    build_seconds = time.perf_counter() - started
    del arrays

    option_counts = np.diff(accounts.segments.chain_offsets.cpu().numpy())[: len(blocks)]
    rng = np.random.default_rng(23)
    genomes = np.zeros((args.genomes, len(blocks)), dtype=np.int64)
    for block_index, count in enumerate(option_counts):
        genomes[:, block_index] = rng.integers(0, int(count), size=args.genomes)
    genomes[0] = seed_genome
    device_genomes = torch.as_tensor(genomes, dtype=torch.int64, device=args.device)
    result = accounts.totals(device_genomes, cells)
    if args.device.startswith("cuda"):
        torch.cuda.synchronize()
    exact = result[0].cpu().numpy()
    max_error = float(np.max(np.abs(exact - expected)))
    if max_error > 1e-3:
        raise SystemExit(f"mixed factorized cells differ from exact evaluator: {max_error}")

    samples: list[float] = []
    for _ in range(args.repeats):
        if args.device.startswith("cuda"):
            torch.cuda.synchronize()
        started = time.perf_counter()
        accounts.totals(device_genomes, cells)
        if args.device.startswith("cuda"):
            torch.cuda.synchronize()
        samples.append(time.perf_counter() - started)
    batch_seconds = statistics.median(samples)
    record = {
        "feature": args.feature,
        "product": args.product,
        "cells": cells,
        "genomes": args.genomes,
        "build_seconds": build_seconds,
        "batch_seconds": batch_seconds,
        "evaluations_per_second": args.genomes / batch_seconds,
        "exact_max_error": max_error,
        "peak_gpu_bytes": (
            int(torch.cuda.max_memory_allocated()) if args.device.startswith("cuda") else 0
        ),
    }
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
