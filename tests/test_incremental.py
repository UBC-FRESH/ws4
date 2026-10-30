"""Tests for the move-based objective deltas."""

from __future__ import annotations

import math
import random
from pathlib import Path

import pandas as pd
import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target, objective
from ws4.opt.operators import CoalesceOperator, Schedule
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
        Target("product.Volume", period=1, minimum=300.0, maximum=400.0),
        Target("product.Volume", period=2, minimum=100.0),
    ]


def _spatial_optimizer(
    tmp_path: Path,
    *,
    max_opening_ha: float | None = 3.0,
    min_green_up_years: int | None = 5,
    min_core_area_ha: float | None = None,
    core_buffer_m: float | None = None,
    years: int = 10,
) -> Optimizer:
    """Build a fixture optimizer with a two-block topology and spatial rules."""
    dataset = _dataset(tmp_path)
    topology = tmp_path / "topology.csv"
    topology.write_text(
        "BLOCK1,BLOCK2,DISTANCE,LENGTH\n1,2,0.0,100.0\n",
        encoding="utf-8",
    )
    return Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=years,
            iterations=1,
            topology_path=str(topology),
            max_opening_ha=max_opening_ha,
            min_green_up_years=min_green_up_years,
            min_core_area_ha=min_core_area_ha,
            core_buffer_m=core_buffer_m,
        ),
    )


def test_coalesce_aligns_a_connected_cluster_to_one_year(tmp_path: Path) -> None:
    """The coalesce move puts adjacent blocks onto the same treatment year."""
    optimizer = _spatial_optimizer(tmp_path, max_opening_ha=None, min_green_up_years=None)
    candidates = optimizer.candidates()
    operator = CoalesceOperator(
        optimizer,
        weight=1.0,
        size=2,
        min_area_ha=5.0,
        max_area_ha=40.0,
        neighbours=optimizer._neighbours(),
    )
    schedule: Schedule = {1: (("CC", 0),), 2: (("CC", 5),)}
    rng = random.Random(1)
    undo = None
    for _ in range(20):
        undo = operator.propose_inplace(schedule, rng, candidates)
        if undo is not None:
            break
    assert undo is not None
    years = {chain[0][1] for chain in schedule.values() if chain}
    assert len(years) == 1


def test_spatial_penalty_is_in_the_incremental_objective(tmp_path: Path) -> None:
    """The incremental objective includes the opening and green-up penalty."""
    optimizer = _spatial_optimizer(tmp_path)
    evaluator = IncrementalObjective(optimizer, [])
    schedule: Schedule = {1: (("CC", 0),), 2: (("CC", 0),)}
    evaluator.reset(schedule)
    # Both blocks in one 5 ha opening exceeds 3 ha by 2; the same-year pair is 5 short.
    assert evaluator.objective == pytest.approx(7.0)
    assert evaluator.objective == pytest.approx(optimizer._evaluate(schedule, []))


def test_block_chain_narrows_feature_offsets_without_changing_products(tmp_path: Path) -> None:
    """Jumping to feature checkpoints preserves the product cells and the selected year."""
    optimizer = _optimizer(tmp_path)
    simulator = optimizer.simulator()
    chain = (("CC", 0),)
    full = simulator.block_chain(1, chain, 4)
    narrow = simulator.block_chain(1, chain, 4, frozenset({3}))
    expected = {
        cell: value
        for cell, value in full.items()
        if cell[0] == 3 or str(cell[1]).startswith("product.")
    }
    assert narrow == expected


def test_flow_delta_tracks_a_random_walk_exactly(tmp_path: Path) -> None:
    """The cached period balances reproduce the full flow objective for every move."""
    optimizer = _optimizer(tmp_path, years=4)
    targets = [
        Target(
            "feature.Volume",
            0,
            period_width=1,
            flow="even",
            flow_reference_period=1,
            minimum=-5.0,
            maximum=5.0,
            min_weight=10_000.0,
            max_weight=10_000.0,
            shape="non_linear",
        )
    ]
    candidates = optimizer.candidates()
    schedule: Schedule = {block: options[0] for block, options in candidates.items() if options}
    evaluator = IncrementalObjective(optimizer, targets)
    evaluator.reset(schedule)
    rng = random.Random(11)
    for _ in range(40):
        move = optimizer.registry.pick(rng).apply(schedule, rng, candidates)
        if move is None:
            continue
        changed = _changed_blocks(schedule, move)
        expected = optimizer._evaluate(move, targets)
        if not (math.isfinite(expected) and math.isfinite(evaluator.objective)):
            evaluator.apply(changed, move)
            schedule = move
            continue
        assert evaluator.objective + evaluator.delta(changed, move) == pytest.approx(
            expected, abs=1e-7
        )
        evaluator.apply(changed, move)
        assert evaluator.objective == pytest.approx(expected, abs=1e-7)
        schedule = move


def test_feature_target_uses_the_same_objective_with_narrow_offsets(tmp_path: Path) -> None:
    """A feature target is still exact when only its period-end cell is evaluated."""
    optimizer = _optimizer(tmp_path)
    targets = [Target("feature.Volume", period=2, minimum=100.0)]
    evaluator = IncrementalObjective(optimizer, targets)
    schedule: Schedule = {1: (("CC", 0),), 2: (("CC", 1),)}
    evaluator.reset(schedule)
    assert evaluator.objective == pytest.approx(optimizer._evaluate(schedule, targets))


def test_spatial_delta_tracks_a_random_walk(tmp_path: Path) -> None:
    """delta() prices spatial moves exactly and apply() keeps the state consistent."""
    optimizer = _spatial_optimizer(tmp_path, max_opening_ha=10.0)
    targets = _targets()
    candidates = optimizer.candidates()
    evaluator = IncrementalObjective(optimizer, targets)
    schedule = {block: options[0] for block, options in candidates.items() if options}
    evaluator.reset(schedule)
    rng = random.Random(7)
    for _ in range(30):
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


def test_spatial_delta_is_exact_for_a_single_block_move(tmp_path: Path) -> None:
    """A move that clears the same-year opening lowers the penalty by the exact amount."""
    optimizer = _spatial_optimizer(tmp_path)
    evaluator = IncrementalObjective(optimizer, [])
    schedule: Schedule = {1: (("CC", 0),), 2: (("CC", 0),)}
    evaluator.reset(schedule)
    moved: Schedule = {1: (("CC", 0),), 2: (("CC", 2),)}
    expected = optimizer._evaluate(moved, [])
    assert expected == pytest.approx(3.0)  # 5-year green-up, 2-year gap
    assert evaluator.objective + evaluator.delta([2], moved) == pytest.approx(expected)
    evaluator.apply([2], moved)
    assert evaluator.objective == pytest.approx(expected)


def test_core_area_penalty_is_in_the_incremental_objective(tmp_path: Path) -> None:
    """The core-area rule is priced on the same delta path as opening and green-up."""
    optimizer = _spatial_optimizer(
        tmp_path,
        max_opening_ha=None,
        min_green_up_years=None,
        min_core_area_ha=100.0,
        core_buffer_m=10.0,
    )
    evaluator = IncrementalObjective(optimizer, [])
    schedule: Schedule = {1: (("CC", 0),)}
    evaluator.reset(schedule)
    assert evaluator.objective == pytest.approx(optimizer._evaluate(schedule, []))


def test_the_delta_path_is_used_when_spatial_rules_are_active(tmp_path: Path) -> None:
    """Spatial rules no longer force the whole-schedule fallback."""
    optimizer = _spatial_optimizer(tmp_path)
    assert optimizer.delta_evaluator([]) is not None


def test_spatial_delta_solver_matches_a_fresh_evaluation(tmp_path: Path) -> None:
    """The spatial delta SA returns an objective a whole-schedule evaluation confirms."""
    optimizer = _spatial_optimizer(tmp_path, max_opening_ha=10.0)
    evaluator = IncrementalObjective(optimizer, [])
    candidates = optimizer.candidates()
    initial = {block: options[0] for block, options in candidates.items() if options}
    best, best_obj = solve_sa_delta(
        evaluator,
        random.Random(3),
        iterations=20,
        temperature=1000.0,
        cooling=0.99,
        candidates=candidates,
        registry=optimizer.registry,
        initial=initial,
    )
    assert best_obj == pytest.approx(optimizer._evaluate(best, []))


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


def test_warm_precomputes_the_candidate_contributions(tmp_path: Path) -> None:
    """warm() fills the contribution cache for every candidate chain."""
    optimizer = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    evaluator = IncrementalObjective(optimizer, _targets())
    evaluator.reset({})
    evaluator.warm(candidates)
    assert len(evaluator._contributions) == sum(len(chains) for chains in candidates.values())


def test_a_product_target_sums_the_account_over_its_period() -> None:
    """A product accumulates over its period's offsets."""
    values = pd.DataFrame(
        {"offset": [0, 1, 2, 3], "account": ["product.a"] * 4, "value": [1.0, 2.0, 3.0, 4.0]}
    )
    periodic = [
        # period 1 with width 2 covers offsets 0-1 -> 1 + 2 = 3
        Target("product.a", period=1, minimum=3.0, maximum=3.0, period_width=2),
        # period 2 with width 2 covers offsets 2-3 -> 3 + 4 = 7
        Target("product.a", period=2, minimum=7.0, maximum=7.0, period_width=2),
    ]
    assert objective(values, periodic) == pytest.approx(0.0)
    off = [Target("product.a", period=2, minimum=9.0, maximum=9.0, period_width=2)]
    assert objective(values, off) == pytest.approx(2.0)  # the period's total, not one offset


def test_a_level_target_is_read_at_its_periods_end() -> None:
    """A feature is a state of the map, so a period's value is the account at its end offset."""
    values = pd.DataFrame(
        {"offset": [0, 1, 2, 3], "account": ["feature.a"] * 4, "value": [1.0, 2.0, 3.0, 4.0]}
    )
    # period 1 with width 4 covers offsets 0-3, read at its end offset 3 -> 4
    targets = [Target("feature.a", period=1, minimum=4.0, maximum=4.0, period_width=4)]
    assert objective(values, targets) == pytest.approx(0.0)
    off = [Target("feature.a", period=1, minimum=5.0, maximum=5.0, period_width=4)]
    assert objective(values, off) == pytest.approx(1.0)  # the end offset, not the sum of the window


def test_incremental_matches_periodic_targets(tmp_path: Path) -> None:
    """The move-based evaluator scores a periodic target the same as the whole-schedule path."""
    optimizer = _optimizer(tmp_path, years=6)
    targets = [Target("product.Volume", period=1, minimum=300.0, maximum=300.0, period_width=2)]
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
        incremental.set_index(["offset", "account"])["value"]
        .to_frame("incremental")
        .join(full.set_index(["offset", "account"])["value"].to_frame("full"), how="outer")
        .fillna(0.0)
    )
    assert (joined["incremental"] - joined["full"]).abs().max() == pytest.approx(0.0, abs=1e-6)


def test_optimizer_uses_the_delta_path(tmp_path: Path) -> None:
    """A plain SA run searches with the move-based evaluator, and the result re-evaluates."""
    optimizer = _optimizer(tmp_path, years=3, iterations=25)
    targets_path = tmp_path / "targets.yaml"
    targets_path.write_text(
        "targets:\n  - account: product.Volume\n    period: 1\n"
        "    minimum: 300\n    maximum: 400\n",
        encoding="utf-8",
    )
    optimizer.cfg.targets_path = str(targets_path)
    targets = [Target("product.Volume", period=1, minimum=300.0, maximum=400.0)]
    best, objective = optimizer._solve(3)
    assert objective == pytest.approx(optimizer._evaluate(best, targets))


def test_incremental_matches_priority_and_normalized_targets(tmp_path: Path) -> None:
    """The delta path and the whole-schedule objective agree with tiers and auto scaling."""
    optimizer = _optimizer(tmp_path)
    targets = [
        Target("product.Volume", period=1, minimum=300.0, normalization="auto", priority=1),
        Target("product.Volume", period=2, minimum=100.0, normalization="auto", priority=2),
    ]
    evaluator = optimizer.delta_evaluator(targets)
    assert evaluator is not None
    block = min(optimizer.candidates())
    evaluator.reset({})
    before = evaluator.objective
    delta = evaluator.delta([block], {block: optimizer.candidates()[block][0]})
    evaluator.apply([block], {block: optimizer.candidates()[block][0]})
    assert evaluator.objective == pytest.approx(before + delta)
    assert evaluator.objective == pytest.approx(objective(evaluator.values_frame(), targets))
