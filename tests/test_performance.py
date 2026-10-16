"""Performance guardrails: the fast path stays fast, and it stays correct."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target, objective
from ws4.sim.engine import Simulator

import benchmark as bm

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _dataset(tmp_path: Path, fragments: int = 0) -> Path:
    """Build the fixture dataset, optionally with a larger synthetic inventory."""
    if fragments <= 0:
        return build_canonical_dataset(
            _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
        )
    inventory = tmp_path / "fragments.csv"
    bm.synthetic_fragments(fragments, max(1, fragments // 10), seed=1).to_csv(
        inventory, index=False
    )
    return build_canonical_dataset(_FIXTURE / "recipe.xml", inventory, tmp_path / "compiled")


def test_the_simulator_is_deterministic(tmp_path: Path) -> None:
    """The same schedule simulated twice produces identical account values."""
    dataset = _dataset(tmp_path)
    schedule = pd.DataFrame({"block_id": [1, 2], "treatment": ["CC", "CC"], "period": [0, 0]})
    first = Simulator.from_dataset(dataset).simulate(schedule, years=5)
    second = Simulator.from_dataset(dataset).simulate(schedule, years=5)
    pd.testing.assert_frame_equal(
        first.reset_index(drop=True), second.reset_index(drop=True), check_like=True
    )


def test_incremental_evaluation_is_faster_than_a_full_simulation(tmp_path: Path) -> None:
    """The incremental objective is strictly faster than a full re-simulation."""
    dataset = _dataset(tmp_path, fragments=3000)
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=10, iterations=1, seed=1))
    targets = [Target("feature.Volume", 0, minimum=0.0)]
    options = optimizer.candidates()
    schedule = {block: choices[0] for block, choices in options.items() if choices}
    assert schedule

    for _ in range(3):  # warm the caches
        optimizer._evaluate(schedule, targets)

    started = time.perf_counter()
    for _ in range(10):
        optimizer._evaluate(schedule, targets)
    incremental = (time.perf_counter() - started) / 10

    started = time.perf_counter()
    for _ in range(10):
        objective(optimizer._full_values(schedule, None, (), ()), targets)
    full = (time.perf_counter() - started) / 10

    assert incremental < full


def test_incremental_matches_the_full_simulation_on_random_schedules(tmp_path: Path) -> None:
    """Parity holds across several random schedules."""
    import random

    dataset = _dataset(tmp_path, fragments=500)
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=5, iterations=1, seed=1))
    targets = [Target("feature.Volume", 0, minimum=0.0)]
    options = [
        (block, choice) for block, choices in optimizer.candidates().items() for choice in choices
    ]
    rng = random.Random(7)
    for _ in range(5):
        schedule = dict(rng.sample(options, k=min(20, len(options))))
        incremental = optimizer._incremental_values(schedule, ())
        full = optimizer._full_values(schedule, None, (), ())
        joined = (
            incremental.set_index(["year", "account"])["value"]
            .to_frame("incremental")
            .join(full.set_index(["year", "account"])["value"].to_frame("full"), how="outer")
            .fillna(0.0)
        )
        assert (joined["incremental"] - joined["full"]).abs().max() == pytest.approx(0.0, abs=1e-6)
        assert optimizer._evaluate(schedule, targets) == pytest.approx(
            objective(optimizer._full_values(schedule, None, (), ()), targets)
        )
