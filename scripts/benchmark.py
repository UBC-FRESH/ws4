#!/usr/bin/env python3
"""Benchmark the compile and simulate paths and report runtime and peak memory.

Command-line usage::

    python scripts/benchmark.py --fragments 20000
    python scripts/benchmark.py --fragments 20000 --profile

The benchmark builds a synthetic fragment inventory from the matrix regression fixture,
compiles it, and simulates an empty schedule. It prints the wall-clock seconds and the
peak resident memory of the process, so the same command records a scale result.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import resource
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.sim.engine import Simulator

DEFAULT_ROOT: Path = Path(__file__).resolve().parent.parent
FIXTURE: Path = DEFAULT_ROOT / "tests" / "fixtures" / "matrix"


def synthetic_fragments(count: int, blocks: int, seed: int) -> pd.DataFrame:
    """Build a synthetic fragment inventory.

    Parameters
    ----------
    count : int
        The number of fragments.
    blocks : int
        The number of blocks to spread the fragments over.
    seed : int
        The random seed.

    Returns
    -------
    pandas.DataFrame
        A fragment inventory with the columns the fixture recipe expects.
    """
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "BLOCK": rng.integers(1, blocks + 1, size=count),
            "AREA_HA": np.round(rng.uniform(0.5, 20.0, size=count), 3),
            "F_AGE": rng.integers(0, 140, size=count),
            "AU": rng.choice(["A", "B"], size=count),
            "IFM": rng.choice(["managed", "unmanaged"], size=count),
            "RETENTION": rng.choice([0.0, 0.25], size=count),
        }
    )


def peak_memory_mb() -> float:
    """Return the peak resident set size of this process, in MiB.

    Returns
    -------
    float
        The peak resident set size, in mebibytes.
    """
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def run_benchmark(
    count: int, blocks: int, years: int, seed: int, workdir: Path
) -> dict[str, float]:
    """Compile and simulate a synthetic landscape and return the timings.

    Parameters
    ----------
    count : int
        The number of fragments.
    blocks : int
        The number of blocks.
    years : int
        The simulation horizon.
    seed : int
        The random seed.
    workdir : Path
        A scratch directory.

    Returns
    -------
    dict of str to float
        ``fragments``, ``tracks``, ``build_seconds``, ``simulate_seconds``, and
        ``peak_memory_mb``.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    fragments = workdir / "fragments.csv"
    synthetic_fragments(count, blocks, seed).to_csv(fragments, index=False)

    started = time.perf_counter()
    dataset = build_canonical_dataset(FIXTURE / "recipe.xml", fragments, workdir / "compiled")
    build_seconds = time.perf_counter() - started

    schedule = workdir / "schedule.csv"
    schedule.write_text("block_id,treatment,period\n", encoding="utf-8")
    simulator = Simulator.from_dataset(dataset)
    started = time.perf_counter()
    simulator.run(schedule, years=years, out_dir=workdir / "run")
    simulate_seconds = time.perf_counter() - started

    return {
        "fragments": float(len(simulator.fragments)),
        "tracks": float(len(simulator.tracks)),
        "build_seconds": build_seconds,
        "simulate_seconds": simulate_seconds,
        "peak_memory_mb": peak_memory_mb(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark from the command line.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` on success.
    """
    parser = argparse.ArgumentParser(description="Benchmark the compile and simulate paths.")
    parser.add_argument("--fragments", type=int, default=20000)
    parser.add_argument("--blocks", type=int, default=0, help="defaults to one block per fragment")
    parser.add_argument("--years", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--workdir", type=Path, default=Path("tmp/benchmark"))
    parser.add_argument("--profile", action="store_true", help="profile the simulate step")
    args = parser.parse_args(argv)
    blocks = args.blocks or args.fragments

    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
        result = run_benchmark(args.fragments, blocks, args.years, args.seed, args.workdir)
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(12)
        print(stream.getvalue())
    else:
        result = run_benchmark(args.fragments, blocks, args.years, args.seed, args.workdir)

    for key, value in result.items():
        print(f"{key:<18}{value:>12.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
