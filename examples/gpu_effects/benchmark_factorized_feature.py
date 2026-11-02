#!/usr/bin/env python3
"""Benchmark a padded factorized feature account on the GPU.

This script never builds an all-account effects matrix. It loads the persisted
structural descriptor archive, pads only the small fragment/segment axes, builds a
single track/age lookup for one feature account, and evaluates a batch of genomes.

Example::

    python examples/gpu_effects/benchmark_factorized_feature.py \
        --dataset /path/to/compiled \
        --targets /path/to/targets.yaml \
        --artifact /path/to/tsa24-factorized.npz \
        --seed-schedule /path/to/seed.csv \
        --account feature.Volume --genomes 64 --period-width 10
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
    FactorizedEffectArrays,
    PaddedFactorizedTensors,
    build_feature_value_table,
)


def _available_memory_bytes() -> int:
    """Return Linux MemAvailable in bytes."""
    with Path("/proc/meminfo").open(encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    return 0


def _genome(
    blocks: np.ndarray,
    candidates: dict[int, list[tuple[tuple[str, int], ...]]],
    schedule: dict[int, tuple[tuple[str, int], ...]],
) -> np.ndarray:
    """Map one schedule to option positions in artifact block order."""
    genome = np.zeros(len(blocks), dtype=np.int64)
    for index, block in enumerate(blocks):
        chain = schedule.get(int(block))
        if chain is None:
            continue
        try:
            genome[index] = candidates[int(block)].index(chain)
        except ValueError:
            genome[index] = 0
    return genome


def _period_values(values: dict[int, float]) -> np.ndarray:
    """Return an ordered period array from a period-to-value mapping."""
    return np.asarray([values[index] for index in sorted(values)], dtype=np.float64)


def main() -> None:
    """Build the padded layout, verify one genome, and time a genome batch."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path)
    parser.add_argument("--account", default="feature.Volume")
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--period-width", type=int, default=10)
    parser.add_argument("--genomes", type=int, default=64)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out", type=Path, default=Path("factorized_feature_benchmark.json"))
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
    expected_blocks = np.asarray(sorted(candidates), dtype=np.int64)
    if not np.array_equal(arrays.blocks, expected_blocks):
        raise SystemExit("artifact block order does not match the candidate order")

    estimate = PaddedFactorizedTensors.estimated_bytes(arrays)
    available = _available_memory_bytes()
    required = int(estimate * 2.5) + 4_000_000_000
    if available and available < required:
        raise SystemExit(
            f"not enough host memory: need >= {required / 1e9:.1f} GB, "
            f"have {available / 1e9:.1f} GB"
        )
    options = arrays.option_count
    artifact_gb = arrays.nbytes() / 1e9
    print(
        f"options={options:,} artifact={artifact_gb:.2f} GB "
        f"padded_estimate={estimate / 1e9:.2f} GB available={available / 1e9:.1f} GB"
    )

    schedule = (
        load_schedule_csv(args.seed_schedule)
        if args.seed_schedule is not None
        else {
            int(block): candidates[int(block)][0]
            for block in expected_blocks
            if candidates[int(block)]
        }
    )
    genome_seed = _genome(expected_blocks, candidates, schedule)
    option_selection = {
        int(block): int(genome_seed[index]) for index, block in enumerate(expected_blocks)
    }
    started = time.perf_counter()
    expected = arrays.feature_period_values(
        args.account,
        option_selection,
        period_width=args.period_width,
        years=args.years,
        simulator=simulator,
    )
    exact_seconds = time.perf_counter() - started

    started = time.perf_counter()
    table = build_feature_value_table(
        arrays,
        simulator,
        args.account,
        years=args.years,
    )
    table_seconds = time.perf_counter() - started
    started = time.perf_counter()
    option_counts = np.diff(arrays.chain_offsets)[: len(expected_blocks)]
    padded = PaddedFactorizedTensors.from_arrays(arrays)
    build_seconds = time.perf_counter() - started
    del arrays

    rng = np.random.default_rng(7)
    genomes = np.zeros((args.genomes, len(expected_blocks)), dtype=np.int64)
    for block_index, count in enumerate(option_counts):
        genomes[:, block_index] = rng.integers(0, int(count), size=args.genomes)
    genomes[0] = genome_seed
    device_genomes = torch.as_tensor(genomes, dtype=torch.int64, device=args.device)
    device_table = torch.as_tensor(table, device=args.device)

    if args.device.startswith("cuda"):
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    padded = padded.to(args.device)
    if args.device.startswith("cuda"):
        torch.cuda.synchronize()
    upload_seconds = time.perf_counter() - started

    result = padded.feature_batch(
        device_genomes,
        device_table,
        years=args.years,
        period_width=args.period_width,
    )
    if args.device.startswith("cuda"):
        torch.cuda.synchronize()
    exact = result[0].double().cpu().numpy()
    expected_array = _period_values(expected)
    max_error = float(np.max(np.abs(exact - expected_array)))
    if max_error > 1e-3:
        raise SystemExit(f"padded feature result differs from exact evaluator: {max_error}")

    samples: list[float] = []
    for _ in range(args.repeats):
        if args.device.startswith("cuda"):
            torch.cuda.synchronize()
        started = time.perf_counter()
        padded.feature_batch(
            device_genomes,
            device_table,
            years=args.years,
            period_width=args.period_width,
        )
        if args.device.startswith("cuda"):
            torch.cuda.synchronize()
        samples.append(time.perf_counter() - started)
    batch_seconds = statistics.median(samples)
    peak_gpu_bytes = int(torch.cuda.max_memory_allocated()) if args.device.startswith("cuda") else 0
    record = {
        "account": args.account,
        "artifact": str(args.artifact),
        "artifact_gb": artifact_gb,
        "options": options,
        "genomes": args.genomes,
        "years": args.years,
        "period_width": args.period_width,
        "build_seconds": build_seconds,
        "table_seconds": table_seconds,
        "exact_seconds": exact_seconds,
        "upload_seconds": upload_seconds,
        "batch_seconds": batch_seconds,
        "evaluations_per_second": args.genomes / batch_seconds,
        "exact_max_error": max_error,
        "peak_gpu_bytes": peak_gpu_bytes,
    }
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
