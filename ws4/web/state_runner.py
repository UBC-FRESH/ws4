"""Run the resident-state search and materialize a web-readable run directory.

The web UI starts this module rather than importing the optimizer into the request
process. The module runs ``ws4 state-watch`` for the search, then ``ws4 simulate``
over the returned schedule so the ordinary readers (map, accounts, reports) have
their usual artefacts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd


def _schedule_with_offsets(path: Path) -> Path:
    """Return a normalised ``offset`` schedule.

    Older instance seeds use ``period`` rather than the state watcher's ``offset``
    (years after the simulation start). Convert in place beside the generated run.
    """
    frame = pd.read_csv(path)
    if "offset" in frame.columns:
        return path
    if "period" not in frame.columns:
        raise ValueError(f"{path} needs an offset or period column")
    frame = frame.copy()
    width = 10
    # A legacy period 0 is the pre-simulation snapshot, not a treatment slot.
    frame["offset"] = frame["period"].astype(int) * width
    target = path.with_name("initial-schedule-offset.csv")
    frame.to_csv(target, index=False)
    return target


def _candidate_index(dataset: Path, targets: Path, years: int, destination: Path) -> Path:
    from ws4.opt.engine import OptimizeConfig, Optimizer
    from ws4.opt.model2_index import CandidateIndex

    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(years=years, targets_path=str(targets), iterations=1, threads=1),
    )
    index = CandidateIndex.build(optimizer.candidates())
    index.save(destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidate-index", type=Path)
    parser.add_argument("--candidate-cache", type=Path)
    parser.add_argument("--initial-schedule", type=Path)
    parser.add_argument("--seed-state", type=Path)
    parser.add_argument("--period-width", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=1_000_000_000)
    parser.add_argument("--max-seconds", type=float, default=60.0)
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--accounts", default="")
    parser.add_argument("--lns-weight", type=float, default=0.2)
    parser.add_argument("--lns-destroy", type=float, default=0.1)
    parser.add_argument("--lns-max-destroy", type=int, default=64)
    parser.add_argument("--topology", type=Path)
    parser.add_argument("--patch-accounts", type=Path)
    parser.add_argument("--spread-accounts", type=Path)
    parser.add_argument("--block-coordinates", type=Path)
    parser.add_argument("--route-config", type=Path)
    args = parser.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    candidate_index = args.candidate_index
    candidate_cache = args.candidate_cache
    if candidate_index is not None and not candidate_index.is_file():
        candidate_index.parent.mkdir(parents=True, exist_ok=True)
        candidate_index = _candidate_index(
            args.dataset, args.targets, args.years, candidate_index
        )
    elif not candidate_index and not candidate_cache:
        candidate_index = _candidate_index(
            args.dataset, args.targets, args.years, out / "candidates.npz"
        )

    initial = args.initial_schedule
    if initial is not None:
        initial = _schedule_with_offsets(initial)

    seed_state = args.seed_state
    write_seed = None
    if seed_state is not None and not seed_state.is_file():
        seed_state.parent.mkdir(parents=True, exist_ok=True)
        write_seed = seed_state
    elif seed_state is None:
        seed_state = out / "seed-state.npz"
        write_seed = seed_state

    command = [
        sys.executable,
        "-m",
        "ws4.cli",
        "state-watch",
        "--dataset",
        str(args.dataset),
        "--targets",
        str(args.targets),
        "--iterations",
        str(args.iterations),
        "--max-seconds",
        str(args.max_seconds),
        "--years",
        str(args.years),
        "--period-width",
        str(args.period_width),
        "--plain",
        "--telemetry",
        str(out / "telemetry.jsonl"),
        "--schedule-out",
        str(out / "schedule.csv"),
        "--lns-weight",
        str(args.lns_weight),
        "--lns-destroy",
        str(args.lns_destroy),
        "--lns-max-destroy",
        str(args.lns_max_destroy),
    ]
    if candidate_index is not None:
        command.extend(["--candidate-index", str(candidate_index)])
    else:
        command.extend(["--candidate-cache", str(candidate_cache)])
    if initial is not None:
        command.extend(["--initial-schedule", str(initial)])
    if write_seed is not None:
        command.extend(["--write-seed-state", str(write_seed)])
    else:
        command.extend(["--seed-state", str(seed_state)])
    if args.accounts:
        command.extend(["--accounts", args.accounts])

    completed = subprocess.run(command, cwd=Path.cwd())
    if completed.returncode != 0:
        return completed.returncode
    if not (out / "schedule.csv").is_file():
        print("state-watch completed without writing schedule.csv", file=sys.stderr)
        return 1

    simulate = [
        sys.executable,
        "-m",
        "ws4.cli",
        "simulate",
        "--dataset",
        str(args.dataset),
        "--schedule",
        str(out / "schedule.csv"),
        "--years",
        str(args.years),
        "--out",
        str(out),
    ]
    for flag, path in (
        ("--topology", args.topology),
        ("--patch-accounts", args.patch_accounts),
        ("--spread-accounts", args.spread_accounts),
        ("--block-coordinates", args.block_coordinates),
        ("--route-config", args.route_config),
    ):
        if path is not None:
            simulate.extend([flag, str(path)])
    completed = subprocess.run(simulate, cwd=Path.cwd())
    if completed.returncode != 0:
        return completed.returncode

    # Preserve the search metadata alongside the simulator summary. The web
    # reader uses summary.json as the completed-run signal, so write a small
    # state-run summary even though the browser reads accounts from the CSV.
    objective = None
    iterations_run = 0
    telemetry = out / "telemetry.jsonl"
    if telemetry.is_file():
        for line in telemetry.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") == "step":
                try:
                    iterations_run = max(iterations_run, int(record.get("iteration", 0)))
                except (TypeError, ValueError):
                    pass
                if isinstance(record.get("objective"), (int, float)):
                    objective = float(record["objective"])
    try:
        blocks_scheduled = int(pd.read_csv(out / "schedule.csv")["block_id"].nunique())
    except Exception:
        blocks_scheduled = 0
    metadata = {
        "engine": "ws4 state-watch",
        "iterations": iterations_run,
        "iteration_limit": args.iterations,
        "years": args.years,
        "period_width": args.period_width,
        "accounts": args.accounts,
        "status": "complete",
        "objective": objective,
    }
    (out / "state_search.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(
            {
                "incumbent_objective": objective,
                "iterations": iterations_run,
                "iteration_limit": args.iterations,
                "seed": 1,
                "metaheuristic": "state-watch",
                "islands": 1,
                "engine": "state",
                "blocks_scheduled": blocks_scheduled,
                "state_search": metadata,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
