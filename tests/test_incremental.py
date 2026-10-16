"""Tests for the move-based objective deltas."""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target, objective
from ws4.opt.solvers import _changed_blocks, solve_sa_delta

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _dataset(tmp_path: Path) -> Path:
    """Compile the synthetic fixture."""
    return build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "c"
    )


def _optimizer(tmp_path: Path, years: int = 4, iterations: int = 1) -> Optimizer:
    """Build a fixture optimizer."""
    return Optimizer.from_dataset(
        _dataset(tmp_path), OptimizeConfig(years=years, iterations=iterations, seed=1)
    )


def _targets() -> list[Target]:
    """A couple of goals on a raw product account."""
    return [
        Target("product.Volume", 0, minimum=300.0, maximum=400.0),
        Target("product.Volume", 1, minimum=100.0),
    ]


def test_reset_matches_the_whole_schedule_evaluation(tmp_path: Path) -> None:
    """The tracked totals reproduce the objective the whole-schedule path computes."""
    optimizer = _optimizer(tmp_path)
    targets = _targets()
    candidates = optimizer.candidates()
    schedule = {block: options[0] for block, options in candidates.items() if options}
    evaluator = IncrementalObjective(optimizer, targets)
    evaluator.reset(schedule)
    assert evaluator.objective == pytest.approx(optimizer._evaluate(schedule, targets))


def test_delta_tracks_a_random_walk_of_moves(tmp_path: Path) -> None:
    """delta() prices each move exactly, and apply() keeps the state consistent."""
    optimizer = _optimizer(tmp_path, years=6)
    targets = _targets()
    candidates = optimizer.candidates()
    evaluator = IncrementalObjective(optimizer, targets)
    schedule = {block: options[0] for block, options in candidates.items() if options}
    evaluator.reset(schedule)
    rng = random.Random(11)
    for _ in range(40):
        move = optimizer.registry.pick(rng).apply(schedule, rng, candidates)
        if move is None:
            continue
        changed = _changed_blocks(schedule, move)
        expected = optimizer._evaluate(move, targets)
        assert evaluator.objective + evaluator.delta(changed, move) == pytest.approx(
            expected, abs=1e-9
        )
        evaluator.apply(changed, move)
        assert evaluator.objective == pytest.approx(expected, abs=1e-9)
        schedule = move


def test_removing_a_block_is_priced_exactly(tmp_path: Path) -> None:
    """Clearing a block's assignment is a move the delta handles."""
    optimizer = _optimizer(tmp_path)
    targets = _targets()
    candidates = optimizer.candidates()
    schedule = {block: options[0] for block, options in candidates.items() if options}
    evaluator = IncrementalObjective(optimizer, targets)
    evaluator.reset(schedule)
    block = next(iter(schedule))
    empty = dict(schedule)
    del empty[block]
    expected = optimizer._evaluate(empty, targets)
    changed = _changed_blocks(schedule, empty)
    assert evaluator.objective + evaluator.delta(changed, empty) == pytest.approx(
        expected, abs=1e-9
    )
    evaluator.apply(changed, empty)
    assert evaluator.objective == pytest.approx(expected, abs=1e-9)


def test_delta_solver_agrees_with_a_fresh_evaluation(tmp_path: Path) -> None:
    """The delta-priced SA returns a schedule whose objective a fresh evaluation confirms."""
    optimizer = _optimizer(tmp_path, years=3, iterations=30)
    targets = _targets()
    evaluator = IncrementalObjective(optimizer, targets)
    candidates = optimizer.candidates()
    initial = {block: options[0] for block, options in candidates.items() if options}
    best, objective = solve_sa_delta(
        evaluator,
        random.Random(5),
        iterations=30,
        temperature=1000.0,
        cooling=0.99,
        candidates=candidates,
        registry=optimizer.registry,
        initial=initial,
    )
    assert objective == pytest.approx(optimizer._evaluate(best, targets))


def test_periodic_target_sums_the_account_over_its_period() -> None:
    """A period-width target scores the account summed over the years of the period."""
    values = pd.DataFrame(
        {"year": [0, 1, 2, 3], "account": ["a"] * 4, "value": [1.0, 2.0, 3.0, 4.0]}
    )
    periodic = [
        Target("a", 0, minimum=3.0, maximum=3.0, period_width=2),
        Target("a", 2, minimum=3.0, maximum=3.0, period_width=2),
    ]
    assert objective(values, periodic) == pytest.approx(4.0)  # |3-3| + |7-3|


def test_incremental_matches_periodic_targets(tmp_path: Path) -> None:
    """The move-based evaluator scores a periodic target the same as the whole-schedule path."""
    optimizer = _optimizer(tmp_path, years=6)
    targets = [Target("product.Volume", 0, minimum=300.0, maximum=300.0, period_width=2)]
    candidates = optimizer.candidates()
    schedule = {block: chains[0] for block, chains in candidates.items() if chains}
    evaluator = IncrementalObjective(optimizer, targets)
    evaluator.reset(schedule)
    full = optimizer._incremental_values(schedule, (), ())
    assert evaluator.objective == pytest.approx(objective(full, targets))


def test_delta_evaluator_is_available_without_routes(tmp_path: Path) -> None:
    """A plain configuration yields a move-based evaluator."""
    optimizer = _optimizer(tmp_path)
    assert optimizer.delta_evaluator(_targets()) is not None


def test_operator_weights_come_from_the_config(tmp_path: Path) -> None:
    """The optimizer builds its operator registry from the config weights."""
    optimizer = Optimizer.from_dataset(
        _dataset(tmp_path),
        OptimizeConfig(years=2, iterations=1, seed=1, toggle_weight=2.0, lns_weight=0.0),
    )
    weights = optimizer.registry.weights()
    assert weights["toggle"] == 2.0
    assert weights["lns"] == 0.0


def test_candidates_are_treatment_chains(tmp_path: Path) -> None:
    """A block's candidates are chains of (treatment, year) events."""
    optimizer = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    chains = [chain for chains in candidates.values() for chain in chains]
    assert chains
    for chain in chains:
        assert isinstance(chain, tuple)
        assert chain
        for event in chain:
            assert isinstance(event, tuple)
            assert len(event) == 2
            assert isinstance(event[0], str)
            assert isinstance(event[1], int)


def test_a_chain_schedule_evaluates_incrementally_and_fully(tmp_path: Path) -> None:
    """A schedule of chains agrees between the incremental and the full simulation."""
    optimizer = _optimizer(tmp_path, years=6)
    candidates = optimizer.candidates()
    schedule = {block: chains[0] for block, chains in candidates.items() if chains}
    incremental = optimizer._incremental_values(schedule, (), ())
    full = optimizer._full_values(schedule, None, (), ())
    joined = (
        incremental.set_index(["year", "account"])["value"]
        .to_frame("incremental")
        .join(full.set_index(["year", "account"])["value"].to_frame("full"), how="outer")
        .fillna(0.0)
    )
    assert (joined["incremental"] - joined["full"]).abs().max() == pytest.approx(0.0, abs=1e-6)


def test_optimizer_uses_the_delta_path(tmp_path: Path) -> None:
    """A plain SA run searches with the move-based evaluator, and the result re-evaluates."""
    optimizer = _optimizer(tmp_path, years=3, iterations=25)
    targets_path = tmp_path / "targets.yaml"
    targets_path.write_text(
        "targets:\n  - account: product.Volume\n    year: 0\n    minimum: 300\n    maximum: 400\n",
        encoding="utf-8",
    )
    optimizer.cfg.targets_path = str(targets_path)
    targets = [Target("product.Volume", 0, minimum=300.0, maximum=400.0)]
    best, objective = optimizer._solve(3)
    assert objective == pytest.approx(optimizer._evaluate(best, targets))
