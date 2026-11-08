#!/usr/bin/env python3
"""Build a persisted factorized archive and padded feature cache.

The factorized basis stores structural option descriptors once. GPU targets can then
switch between feature and product accounts without extending the sparse harvest-effect
table. This is the reusable build used for large target-coupled instances such as TSA 29.

Example:

    python examples/gpu_effects/build_factorized.py \
        --dataset /path/to/build/compiled \
        --targets /path/to/targets.yaml \
        --cache-dir /path/to/runtime/gpu-cache \
        --out /path/to/runtime/factorized/tsa29-factorized.npz \
        --padded /path/to/runtime/factorized/tsa29-factorized.padded.pt \
        --workers 8
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ws4.opt.candidate_cache import load_or_build_candidates, load_or_build_simulator  # noqa: E402
from ws4.opt.engine import OptimizeConfig, Optimizer  # noqa: E402
from ws4.opt.factorized_effects import (  # noqa: E402
    FactorizedAccountSet,
    FactorizedEffectArrays,
)


def main() -> int:
    """Build the structural archive and padded cache."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Structural .npz archive")
    parser.add_argument("--padded", type=Path, required=True, help="Padded .pt cache")
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--chunk-blocks", type=int, default=512)
    parser.add_argument("--worker-memory-gb", type=float, default=12.0)
    args = parser.parse_args()
    started = time.perf_counter()
    optimizer = Optimizer.from_dataset(
        args.dataset,
        OptimizeConfig(
            years=args.years,
            targets_path=str(args.targets),
            iterations=1,
            threads=1,
        ),
    )
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    load_or_build_simulator(optimizer, args.cache_dir / "simulator.pkl")
    candidates = load_or_build_candidates(optimizer, args.cache_dir / "candidates.pkl")
    print(f"loaded model and candidates in {time.perf_counter() - started:.1f}s", flush=True)
    arrays = FactorizedEffectArrays.build_parallel(
        optimizer,
        candidates,
        years=args.years,
        workers=max(1, args.workers),
        chunk_blocks=max(32, args.chunk_blocks),
        worker_memory_bytes=int(args.worker_memory_gb * 1_000_000_000),
    )
    print(
        f"structural build {time.perf_counter() - started:.1f}s options={arrays.option_count}",
        flush=True,
    )
    arrays.save(args.out)
    print(f"saved {args.out} {args.out.stat().st_size} bytes", flush=True)
    accounts = FactorizedAccountSet.from_artifact(
        args.out,
        optimizer.simulator(),
        years=args.years,
        cache=args.padded,
    )
    del accounts
    print(
        f"padded build {time.perf_counter() - started:.1f}s {args.padded.stat().st_size} bytes",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
