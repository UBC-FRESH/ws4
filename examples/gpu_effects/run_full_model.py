#!/usr/bin/env python3
"""Run the GPU population search on a full compiled model and verify it exactly.

This is the checked-in, reproducible counterpart to the full-model experiments.  It loads
the candidate map from a persistent cache, loads a lean effect table, runs the population,
writes the best schedule, and replays that schedule with a fresh
:class:`IncrementalObjective`.

The candidate cache is safe to reuse while its dataset fingerprint and candidate horizon
match.  Pass ``--rebuild-cache`` after changing either; the command refuses a stale cache
rather than silently mixing models.

Example::

    python examples/gpu_effects/run_full_model.py \
        --dataset /path/to/compiled_ft_econ \
        --targets /path/to/targets.yaml \
        --seed-schedule /path/to/seed.csv \
        --table /path/to/effects-lean.pt \
        --candidates-cache /path/to/candidates.pkl \
        --out /path/to/best.csv \
        --years 200 --population 64 --generations 1000 --seed 7
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ws4.opt.archive import write_schedule  # noqa: E402
from ws4.opt.candidate_cache import (  # noqa: E402
    load_or_build_candidates,
    load_or_build_simulator,
)
from ws4.opt.engine import OptimizeConfig, Optimizer, load_schedule_csv  # noqa: E402
from ws4.opt.gpu_effects import EffectTable  # noqa: E402
from ws4.opt.gpu_ga import GenomePopulation  # noqa: E402
from ws4.opt.incremental import IncrementalObjective  # noqa: E402
from ws4.opt.objective import load_targets  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Return the command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--seed-schedule", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--candidates-cache", type=Path, required=True)
    parser.add_argument("--simulator-cache", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--population", type=int, default=64)
    parser.add_argument("--generations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--islands", type=int, default=1)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--rebuild-cache", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Run one full-model population search and report its exact result."""
    args = parse_args()
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
    targets = load_targets(args.targets)
    seed = load_schedule_csv(args.seed_schedule)
    setup_done = time.perf_counter()
    if args.simulator_cache is not None:
        load_or_build_simulator(optimizer, args.simulator_cache, rebuild=args.rebuild_cache)
    simulator_done = time.perf_counter()
    candidates = load_or_build_candidates(
        optimizer, args.candidates_cache, rebuild=args.rebuild_cache
    )
    candidates_done = time.perf_counter()

    table = EffectTable.load(args.table, device=args.device)
    table_done = time.perf_counter()
    evaluator = IncrementalObjective(optimizer, targets)
    population = GenomePopulation(
        optimizer,
        evaluator,
        table,
        population=args.population,
        seed=args.seed,
        seed_schedule=seed,
        candidates=candidates,
        random_fraction=0.05,
        initial_mutation_rate=0.02,
        mutation_rate=0.002,
        islands=args.islands,
    )
    population_done = time.perf_counter()
    result = population.run(args.generations, check=1)
    search_done = time.perf_counter()

    write_schedule(args.out, result.schedule)
    verified = IncrementalObjective(optimizer, targets)
    verified.reset(result.schedule)
    verify_done = time.perf_counter()

    record = {
        "dataset": str(args.dataset),
        "targets": str(args.targets),
        "table": str(args.table),
        "candidates_cache": str(args.candidates_cache),
        "simulator_cache": None if args.simulator_cache is None else str(args.simulator_cache),
        "schedule": str(args.out),
        "population": args.population,
        "generations": args.generations,
        "seed": args.seed,
        "islands": args.islands,
        "initial_objective": result.initial_objective,
        "device_objective": result.objective,
        "verified_objective": verified.objective,
        "exact_match": math.isclose(
            verified.objective, result.objective, rel_tol=1e-9, abs_tol=1e-6
        ),
        "best_generation": result.best_generation,
        "evaluations": result.evaluations,
        "setup_s": setup_done - started,
        "simulator_s": simulator_done - setup_done,
        "candidates_s": candidates_done - simulator_done,
        "table_s": table_done - candidates_done,
        "population_s": population_done - table_done,
        "search_s": search_done - population_done,
        "verify_s": verify_done - search_done,
        "total_s": verify_done - started,
    }
    print(json.dumps(record, indent=2, sort_keys=True))
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
