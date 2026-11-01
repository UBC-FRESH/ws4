#!/usr/bin/env python3
"""Build a persisted lean effect table for a full compiled model."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ws4.opt.candidate_cache import load_or_build_candidates, load_or_build_simulator  # noqa: E402
from ws4.opt.engine import OptimizeConfig, Optimizer  # noqa: E402
from ws4.opt.gpu_effects import EffectTable, watchable_cells  # noqa: E402
from ws4.opt.incremental import IncrementalObjective  # noqa: E402
from ws4.opt.objective import load_targets  # noqa: E402


def main() -> int:
    """Build and persist a lean effect table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--candidates-cache", type=Path, required=True)
    parser.add_argument("--simulator-cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--years", type=int, default=200)
    parser.add_argument(
        "--cell-accounts",
        default="",
        help="Comma-separated accounts for a target-independent cell basis",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Worker processes; defaults to one. Parallel builds need --allow-parallel.",
    )
    parser.add_argument(
        "--allow-parallel",
        action="store_true",
        help="Explicitly allow more than one worker process",
    )
    parser.add_argument(
        "--max-estimated-gb",
        type=float,
        default=4.0,
        help="Refuse a dense feature-cell basis above this estimated sparse size",
    )
    parser.add_argument(
        "--allow-dense-feature",
        action="store_true",
        help="Explicitly allow a dense feature-cell basis above the estimate limit",
    )
    args = parser.parse_args()
    started = time.perf_counter()
    optimizer = Optimizer.from_dataset(
        args.dataset,
        OptimizeConfig(years=args.years, targets_path=str(args.targets), iterations=1, threads=1),
    )
    targets = load_targets(args.targets)
    load_or_build_simulator(optimizer, args.simulator_cache)
    candidates = load_or_build_candidates(optimizer, args.candidates_cache)
    target_accounts = {target.account for target in targets}
    cell_accounts = tuple(
        sorted(
            target_accounts
            | {value.strip() for value in args.cell_accounts.split(",") if value.strip()}
        )
    )
    evaluator = IncrementalObjective(optimizer, targets, extra_accounts=cell_accounts)
    cells = watchable_cells(cell_accounts, args.years)
    rows = 1 + sum(len(chains) for chains in candidates.values())
    feature_cells = sum(1 for _offset, account in cells if not str(account).startswith("product."))
    dense_nnz = rows * feature_cells
    estimated_gb = (dense_nnz * 16 + rows * 8) / 1_000_000_000
    print(
        f"preflight: rows={rows} cells={len(cells)} feature_cells={feature_cells} "
        f"estimated_gb={estimated_gb:.1f}",
        flush=True,
    )
    if estimated_gb > args.max_estimated_gb and not args.allow_dense_feature:
        print(
            "refusing dense feature-cell build: estimate "
            f"{estimated_gb:.1f} GB exceeds {args.max_estimated_gb:.1f} GB; "
            "use a separate display path or explicitly override",
            file=sys.stderr,
        )
        return 2
    workers = max(1, args.workers)
    if workers > 1 and not args.allow_parallel:
        print("refusing parallel build without --allow-parallel", file=sys.stderr)
        return 2
    print(
        f"building table... basis_accounts={len(cell_accounts)} cells={len(cells)}",
        flush=True,
    )
    table = EffectTable.build(
        optimizer,
        evaluator,
        candidates=candidates,
        cells=cells,
        include_row_index=False,
        workers=workers,
    )
    table.save(args.out, include_row_index=False, candidates=candidates)
    print(
        f"rows={table.rows} nnz={table.nnz} bytes={table.nbytes()} "
        f"seconds={time.perf_counter() - started:.1f} out={args.out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
