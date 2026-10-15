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
import functools
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
from ws4.build.legacy import ingest_legacy_matrix
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target
from ws4.patch.accounts import PatchAccount, load_patch_edges
from ws4.patch.edge import EdgeElement
from ws4.roads.accounts import RouteCostLedger, RouteModel
from ws4.roads.network import RouteNetwork
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


def build_c5_dataset(sample_dir: Path, workdir: Path) -> Path:
    """Ingest the C5 sample's compiled matrix into the WS4 schema.

    Parameters
    ----------
    sample_dir : Path
        The sample directory (with ``tracks/`` and ``roads/``).
    workdir : Path
        A scratch directory.

    Returns
    -------
    Path
        The compiled dataset directory.
    """
    tracks = Path(sample_dir) / "tracks"
    blocks = pd.read_csv(tracks / "blocks.csv")
    fragments = pd.DataFrame(
        {
            "BLOCK": blocks["BLOCK"].astype(int),
            "AREA_HA": blocks["AREA"].astype(float),
            "F_AGE": blocks["OFFSET"].astype(int),
        }
    )
    fragments_path = workdir / "c5_fragments.csv"
    fragments.to_csv(fragments_path, index=False)
    return ingest_legacy_matrix(tracks, fragments_path, workdir / "c5_compiled")


def c5_schedule(dataset: Path, limit: int) -> pd.DataFrame:
    """Build a schedule that harvests each of the first ``limit`` blocks once.

    Parameters
    ----------
    dataset : Path
        The compiled dataset.
    limit : int
        The maximum number of blocks to schedule.

    Returns
    -------
    pandas.DataFrame
        A schedule with ``block_id``, ``treatment``, and ``period`` columns.
    """
    simulator = Simulator.from_dataset(dataset)
    blocks = pd.read_parquet(dataset / "blocks.parquet")
    merged = simulator.treatments.merge(
        blocks[["block_id", "track_id"]], on="track_id", how="inner"
    )
    picks = merged.drop_duplicates("block_id").head(limit)
    return pd.DataFrame(picks.loc[:, ["block_id", "treatment"]]).assign(period=0)


def _route_config(workdir: Path, sample_dir: Path) -> Path:
    """Write a route configuration for the sample and return its path."""
    roads = Path(sample_dir) / "roads"
    config = workdir / "route.yaml"
    config.write_text(
        "route:\n"
        f"  segments: {roads / 'segments.csv'}\n"
        f"  destinations: {roads / 'destinations.csv'}\n"
        f"  linkages: {roads / 'linkages.csv'}\n"
        "route_accounts:\n"
        "  - {destination: destination.MILL1, kind: haul, account: route.Mill1.haul}\n"
        "duplicate_accounts:\n"
        "  - {master: route.Mill1.haul, target: route.Total.haul}\n",
        encoding="utf-8",
    )
    return config


def run_spatial_benchmark(
    sample_dir: Path, workdir: Path, years: int, route_blocks: int, spatial_years: int
) -> dict[str, float]:
    """Time the C5 spatial and route components.

    Parameters
    ----------
    sample_dir : Path
        The sample directory (with ``tracks/``, ``roads/``, and ``blocks/``).
    workdir : Path
        A scratch directory.
    years : int
        The simulation horizon, in years.
    route_blocks : int
        The number of blocks to schedule for the routing benchmark.
    spatial_years : int
        The horizon for the patch-account benchmark.

    Returns
    -------
    dict of str to float
        Per-component timings, in seconds.
    """
    sample_dir = Path(sample_dir)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    started = time.perf_counter()
    dataset = build_c5_dataset(sample_dir, workdir)
    timings["ingest_seconds"] = time.perf_counter() - started

    schedule = c5_schedule(dataset, route_blocks)
    schedule.to_csv(workdir / "c5_schedule.csv", index=False)
    empty = schedule.head(0)

    started = time.perf_counter()
    Simulator.from_dataset(dataset).simulate(empty, years)
    timings["simulate_base_seconds"] = time.perf_counter() - started

    topology = sample_dir / "blocks" / "topology_blocks_200r.csv"
    edges = load_patch_edges(topology)
    elements = (
        EdgeElement("feature.Edge.OldYoung", "feature.Seral.old", "feature.Seral.young", 1.0),
    )
    started = time.perf_counter()
    Simulator.from_dataset(dataset).simulate(empty, years, edge_elements=elements, edges=edges)
    timings["simulate_edge_seconds"] = time.perf_counter() - started

    network = RouteNetwork.from_tables(
        pd.read_csv(sample_dir / "roads" / "segments.csv"),
        pd.read_csv(sample_dir / "roads" / "destinations.csv"),
        pd.read_csv(sample_dir / "roads" / "linkages.csv"),
    )
    started = time.perf_counter()
    ledger = RouteCostLedger(network)
    Simulator.from_dataset(dataset).simulate(
        schedule, years, route_model=RouteModel(network), ledger=ledger
    )
    timings["simulate_routing_seconds"] = time.perf_counter() - started

    account = PatchAccount(name="patch.disturbance", criteria="feature.Seral.young", threshold=0.5)
    started = time.perf_counter()
    Simulator.from_dataset(dataset).write_patch_metrics(
        empty,
        spatial_years,
        topology,
        (5.0, 10.0, 50.0),
        workdir / "spatial",
        patch_accounts=[account],
    )
    timings["patch_accounts_seconds"] = time.perf_counter() - started

    config = OptimizeConfig(
        years=years,
        iterations=0,
        topology_path=str(topology),
        route_config_path=str(_route_config(workdir, sample_dir)),
    )
    optimizer = Optimizer.from_dataset(dataset, config)
    targets = [Target("feature.Seral.young", 0, minimum=0.0)]
    started = time.perf_counter()
    optimizer._evaluate({}, targets)  # the objective evaluation is the workload
    timings["optimizer_eval_seconds"] = time.perf_counter() - started

    timings["fragments"] = float(len(pd.read_parquet(dataset / "fragments.parquet")))
    timings["peak_memory_mb"] = peak_memory_mb()
    return timings


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
    parser.add_argument("--scenario", choices=["synthetic", "c5"], default="synthetic")
    parser.add_argument("--sample-dir", type=Path, default=None, help="the C5 sample directory")
    parser.add_argument("--fragments", type=int, default=20000)
    parser.add_argument("--blocks", type=int, default=0, help="defaults to one block per fragment")
    parser.add_argument("--years", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--workdir", type=Path, default=Path("tmp/benchmark"))
    parser.add_argument("--route-blocks", type=int, default=300, help="blocks to schedule (c5)")
    parser.add_argument("--spatial-years", type=int, default=1, help="patch-account horizon (c5)")
    parser.add_argument("--profile", action="store_true", help="profile the simulate step")
    args = parser.parse_args(argv)

    if args.scenario == "c5":
        if args.sample_dir is None:
            parser.error("--scenario c5 needs --sample-dir")
        sample_dir = args.sample_dir
        workload = functools.partial(
            run_spatial_benchmark,
            sample_dir,
            args.workdir,
            args.years,
            args.route_blocks,
            args.spatial_years,
        )
    else:
        blocks = args.blocks or args.fragments
        workload = functools.partial(
            run_benchmark, args.fragments, blocks, args.years, args.seed, args.workdir
        )

    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
        result = workload()
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(12)
        print(stream.getvalue())
    else:
        result = workload()

    for key, value in result.items():
        print(f"{key:<28}{value:>12.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
