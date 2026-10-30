#!/usr/bin/env python3
"""Run several full-model seeds in one resident GPU population session.

The simulator, candidate map, lean effect table, and population option map are loaded and
built once.  Each requested seed resets only the random stream, population, and incumbent
before its search.  Every returned schedule is replayed with a fresh exact evaluator.

Example::

    python examples/gpu_effects/run_full_model_session.py \
        --dataset /path/to/compiled_ft_econ \
        --targets /path/to/targets.yaml \
        --seed-schedule /path/to/seed.csv \
        --table /path/to/effects-lean.pt \
        --candidates-cache /path/to/candidates.pkl \
        --simulator-cache /path/to/simulator-cache.pkl \
        --out-dir /path/to/schedules \
        --seeds 7 8 9 --years 200 --population 64 --generations 1000
"""

from __future__ import annotations

import argparse
import json
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
from ws4.opt.engine import (  # noqa: E402
    OptimizeConfig,
    Optimizer,
    load_schedule_csv,
)
from ws4.opt.gpu_effects import EffectTable  # noqa: E402
from ws4.opt.gpu_session import GpuSearchSession  # noqa: E402
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
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--population", type=int, default=64)
    parser.add_argument("--generations", type=int, default=1000)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    """Build one resident session and run every requested seed."""
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
    seed_schedule = load_schedule_csv(args.seed_schedule)
    if args.simulator_cache is not None:
        load_or_build_simulator(optimizer, args.simulator_cache, rebuild=args.rebuild_cache)
    candidates = load_or_build_candidates(
        optimizer, args.candidates_cache, rebuild=args.rebuild_cache
    )
    table = EffectTable.load(args.table, device=args.device)
    session = GpuSearchSession(
        optimizer,
        IncrementalObjective(optimizer, targets),
        table,
        candidates=candidates,
        seed_schedule=seed_schedule,
        population=args.population,
        initial_seed=args.seeds[0],
        random_fraction=0.05,
        initial_mutation_rate=0.02,
        mutation_rate=0.002,
        islands=1,
    )
    session_started = time.perf_counter()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    last_done = session_started
    for seed in args.seeds:
        result = session.run(seed, args.generations, check=1)
        search_done = time.perf_counter()
        schedule_path = args.out_dir / f"seed-{seed}.csv"
        write_schedule(schedule_path, result.schedule)
        verifier = IncrementalObjective(optimizer, targets)
        verifier.reset(result.schedule)
        verify_done = time.perf_counter()
        records.append(
            {
                "seed": seed,
                "schedule": str(schedule_path),
                "initial_objective": result.initial_objective,
                "device_objective": result.objective,
                "verified_objective": verifier.objective,
                "exact_match": verifier.objective == result.objective,
                "best_generation": result.best_generation,
                "evaluations": result.evaluations,
                "search_s": search_done - last_done,
                "verify_s": verify_done - search_done,
            }
        )
        last_done = verify_done
        print(json.dumps(records[-1], sort_keys=True), flush=True)

    payload = {
        "session_build_s": session_started - started,
        "total_s": time.perf_counter() - started,
        "runs": records,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
