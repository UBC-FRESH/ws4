"""Run one scenario profile on the resident GPU population and write web-run artefacts.

This worker is intentionally a subprocess: a long GPU search must not occupy the web
service's event loop. It reuses the P95 vector/cache path and writes the same telemetry,
control, schedule, and summary files the web UI already consumes.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any, cast

from ..report import ending_inventory, write_report
from .archive import write_schedule
from .candidate_cache import CompactCandidates, load_or_build_candidates
from .engine import OptimizeConfig, Optimizer, load_schedule_csv
from .factorized_effects import FactorizedAccountSet, FactorizedEffectArrays
from .gpu_effects import EffectTable
from .gpu_ga import GenomePopulation
from .incremental import IncrementalObjective
from .objective import load_targets, period_value
from .scenario_profiles import get_profile, load_profiles


def _option_count(candidates: Any, block: int) -> int:  # noqa: ANN401
    """Return one block's option count for compact or mapping candidates."""
    method = getattr(candidates, "option_count", None)
    if callable(method):
        return int(method(block))
    return len(candidates.get(block, ()))


def _chain_at(candidates: Any, block: int, index: int) -> tuple[tuple[str, int], ...]:  # noqa: ANN401
    """Return one candidate chain for compact or mapping candidates."""
    method = getattr(candidates, "chain_at", None)
    if callable(method):
        return cast(tuple[tuple[str, int], ...], method(block, index))
    return cast(tuple[tuple[str, int], ...], candidates[block][index])


def _chain_index(
    candidates: Any,  # noqa: ANN401
    block: int,
    chain: tuple[tuple[str, int], ...],
) -> int | None:
    """Return one chain's option index for compact or mapping candidates."""
    method = getattr(candidates, "index_of", None)
    if callable(method):
        return cast(int | None, method(block, chain))
    try:
        return list(candidates.get(block, ())).index(chain)
    except ValueError:
        return None


def _seed(
    blocks: Any,  # noqa: ANN401
    candidates: Any,  # noqa: ANN401
    path: Path | None,
) -> dict[int, tuple[tuple[str, int], ...]]:
    """Return a candidate-only seed schedule."""
    requested = load_schedule_csv(path) if path is not None and path.is_file() else {}
    seed: dict[int, tuple[tuple[str, int], ...]] = {}
    for block in blocks:
        index = int(block)
        count = _option_count(candidates, index)
        if count <= 0:
            continue
        chain = requested.get(index, _chain_at(candidates, index, 0))
        if _chain_index(candidates, index, chain) is None:
            chain = _chain_at(candidates, index, 0)
        seed[index] = chain
    return seed


def _schedule_changes(
    previous: dict[int, tuple[tuple[str, int], ...]] | None,
    current: dict[int, tuple[tuple[str, int], ...]],
) -> tuple[bool, list[list[object]]]:
    """Return the reset flag and changed-block payload for one schedule event."""
    if previous is None:
        return True, [[int(block), chain] for block, chain in current.items()]
    return False, [
        [int(block), chain] for block, chain in current.items() if previous.get(block) != chain
    ]


def _target_event_payload(
    targets: Any,  # noqa: ANN401
    index: dict[tuple[int, str], float],
    iteration: int,
) -> dict[str, object]:
    """Return the profile target event for one generation."""
    return {
        "type": "targets",
        "profile": True,
        "iteration": iteration,
        "values": [
            {
                "index": target_index,
                "account": target.account,
                "period": target.period,
                "year": target.year,
                "flow": target.flow,
                "value": period_value(index, target),
            }
            for target_index, target in enumerate(targets)
            if target.active
        ],
        "series": [
            {"year": offset + 1, "account": account, "value": value}
            for (offset, account), value in index.items()
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """Run one profile and write the web-run output set.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments; None uses ``sys.argv``.

    Returns
    -------
    int
        Process exit status.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--profile-file", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument("--population", type=int, default=64)
    parser.add_argument("--generations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--schedule-every", type=int, default=100)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args(argv)
    if args.generations < 0:
        parser.error("--generations must not be negative")

    profiles = load_profiles(args.profile_file)
    profile = get_profile(profiles, args.profile)
    required = {
        "table": profile.table,
        "cache_dir": profile.cache_dir,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error(f"profile {args.profile!r} is missing: {', '.join(missing)}")
    if profile.factorized is None and profile.factorized_cache is not None:
        parser.error(f"profile {args.profile!r} sets factorized_cache without factorized")
    assert profile.table is not None
    assert profile.cache_dir is not None

    target_list = load_targets(profile.targets)
    cfg = OptimizeConfig(
        years=args.years,
        targets_path=str(profile.targets),
        iterations=1,
        threads=1,
    )
    optimizer = Optimizer.from_dataset(args.dataset, cfg)
    table = EffectTable.load(profile.table, device=args.device)
    cache_dir = profile.cache_dir
    candidates_path = cache_dir / "candidates-compact.npz"
    candidates: object
    if candidates_path.is_file():
        candidates = CompactCandidates.load(candidates_path)
    else:
        candidates = load_or_build_candidates(optimizer, cache_dir / "candidates.pkl")
    blocks = [int(value) for value in table.blocks]
    accounts = None
    if profile.factorized is not None:
        arrays = FactorizedEffectArrays.load(profile.factorized)
        accounts = FactorizedAccountSet.from_artifact(
            profile.factorized,
            optimizer.simulator(),
            years=args.years,
            device=args.device,
            cache=profile.factorized_cache,
            arrays=arrays,
        )
        if [int(value) for value in accounts.blocks] != blocks:
            raise SystemExit("factorized blocks do not match the effect table")
    seed = _seed(blocks, candidates, profile.seed_schedule)
    base_cache = profile.table.with_name(profile.table.name + ".base.pt")
    base_totals = None
    if base_cache.is_file():
        import torch

        base_totals = torch.load(base_cache, map_location=args.device, weights_only=True)
    population = GenomePopulation(
        optimizer,
        IncrementalObjective(optimizer, []),
        table,
        population=args.population,
        seed=args.seed,
        seed_schedule=seed,
        candidates=candidates,
        base_totals=base_totals,
        factorized=accounts,
        random_fraction=0.05,
        initial_mutation_rate=0.02,
        mutation_rate=0.002,
    )
    population.update_targets(target_list)
    population.reset(seed, seed=args.seed)

    args.out.mkdir(parents=True, exist_ok=True)
    telemetry = (args.out / "telemetry.jsonl").open("w", encoding="utf-8")
    control = args.out / "control.json"
    control.write_text('{"action": "run"}\n', encoding="utf-8")
    started = time.perf_counter()
    evaluations = 0
    completed = 0
    stopped = False
    previous_schedule: dict[int, tuple[tuple[str, int], ...]] | None = None
    for generation in range(args.generations + 1):
        action = "run"
        if control.is_file():
            try:
                action = str(json.loads(control.read_text(encoding="utf-8")).get("action", "run"))
            except ValueError:
                action = "run"
        while action == "pause":
            time.sleep(0.25)
            try:
                action = str(json.loads(control.read_text(encoding="utf-8")).get("action", "run"))
            except ValueError:
                action = "run"
        if action == "stop":
            stopped = True
            break
        population.advance()
        evaluations += args.population
        completed = generation
        telemetry.write(
            json.dumps(
                {
                    "type": "step",
                    "iteration": generation,
                    "objective": population.best_objective,
                    "evaluations": evaluations,
                    "generation": generation,
                }
            )
            + "\n"
        )
        cadence = max(1, int(args.schedule_every))
        if generation % cadence == 0 or generation == args.generations:
            if population.totals is not None and population.scores is not None:
                import torch

                best_index = int(torch.argmin(population.scores))
                cells = [*population.table.cells, *population._extra_cells]
                row = population.totals[best_index]
                index = {
                    (int(cell[0]), str(cell[1])): float(value)
                    for cell, value in zip(cells, row.tolist(), strict=True)
                }
                telemetry.write(
                    json.dumps(_target_event_payload(target_list, index, generation)) + "\n"
                )
            current = population.schedule(population.best_genome)
            reset, changed = _schedule_changes(previous_schedule, current)
            telemetry.write(
                json.dumps({"type": "schedule", "reset": reset, "changed": changed}) + "\n"
            )
            previous_schedule = current
        telemetry.flush()
    telemetry.close()

    schedule_path = args.out / "schedule.csv"
    write_schedule(schedule_path, population.schedule(population.best_genome))
    verifier = IncrementalObjective(optimizer, target_list)
    verifier.reset(population.schedule(population.best_genome))
    ending: dict[str, object] = {}
    if args.replay:
        simulator = optimizer.simulator()
        simulator.reset()
        values = simulator.run(
            schedule_path,
            years=args.years,
            out_dir=args.out,
        )
        write_report(values, target_list, args.out)
        ending_frame = ending_inventory(values)
        if not ending_frame.empty:
            ending = {
                "offset": int(ending_frame["offset"].iloc[0]),
                "accounts": {
                    str(row.account): float(cast(float, row.value))
                    for row in ending_frame.itertuples(index=False)
                },
            }
    elapsed = time.perf_counter() - started
    summary = {
        "status": "stopped" if stopped else "ok",
        "profile": args.profile,
        "factorized": accounts is not None,
        "targets": str(profile.targets),
        "schedule": str(schedule_path),
        "incumbent_objective": population.best_objective,
        "verified_objective": verifier.objective,
        "exact_match": math.isclose(
            verifier.objective, population.best_objective, rel_tol=1e-9, abs_tol=1e-6
        ),
        "generations": completed,
        "evaluations": evaluations,
        "seconds": elapsed,
        "population": args.population,
        "seed": args.seed,
        "factorized_cells": [
            [int(offset), str(account)] for offset, account in population._extra_cells
        ],
        "ending_inventory": ending,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
