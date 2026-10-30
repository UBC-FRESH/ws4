"""Tests for the GPU-native candidate-index population search.

The population must reproduce the incremental objective exactly and keep every genome a
valid candidate index.  These tests use the CPU torch path when no device is present; the
same tensor code runs on CUDA.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.gpu_effects import EffectTable
from ws4.opt.gpu_ga import GenomePopulation
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target

torch = pytest.importorskip("torch")

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _dataset(tmp_path: Path, blocks: int = 24) -> Path:
    """Compile a synthetic dataset with enough blocks for a population."""
    fragments = tmp_path / "fragments.csv"
    rows = ["BLOCK,AREA_HA,F_AGE,AU,IFM"]
    rows.extend(
        f"{block},{2.0 + block % 3},{(block * 7) % 80 + 40},1,unmanaged"
        for block in range(1, blocks + 1)
    )
    fragments.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return build_canonical_dataset(_FIXTURE / "recipe.xml", fragments, tmp_path / "compiled")


def _optimizer(
    tmp_path: Path, *, years: int = 4, blocks: int = 24
) -> tuple[Optimizer, IncrementalObjective]:
    """Return the fixture optimizer and a one-tier level-target evaluator."""
    optimizer = Optimizer.from_dataset(
        _dataset(tmp_path, blocks), OptimizeConfig(years=years, iterations=1, seed=1)
    )
    targets = [
        Target("product.Volume", period=1, period_width=1, minimum=1000.0),
        Target("feature.Volume", period=3, period_width=1, minimum=1000.0),
    ]
    return optimizer, IncrementalObjective(optimizer, targets)


def _seed(optimizer: Optimizer) -> dict[int, tuple[tuple[str, int], ...]]:
    """Return the first candidate chain of every block as the seed schedule."""
    return {block: chains[0] for block, chains in optimizer.candidates().items()}


def _exact(
    evaluator: IncrementalObjective, schedule: dict[int, tuple[tuple[str, int], ...]]
) -> float:
    """Return a fresh exact objective for a schedule."""
    verifier = IncrementalObjective(evaluator.optimizer, evaluator.targets)
    verifier.reset(schedule)
    return verifier.objective


def _assert_close(actual: float, expected: float) -> None:
    """Compare scores, treating two infinities as equal."""
    if math.isinf(expected):
        assert math.isinf(actual)
        assert (actual > 0) == (expected > 0)
        return
    assert actual == pytest.approx(expected, rel=1e-9, abs=1e-6)


def test_every_genome_matches_the_exact_objective(tmp_path: Path) -> None:
    """Seeded, mutated, and random genomes all price exactly against the evaluator."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    population = GenomePopulation(
        optimizer,
        evaluator,
        table,
        population=16,
        seed=4,
        seed_schedule=_seed(optimizer),
        random_fraction=0.5,
    )
    scores = population.evaluate()
    assert scores.shape == (16,)
    for index in range(population.population):
        _assert_close(
            float(scores[index]), _exact(evaluator, population.schedule(population.genomes[index]))
        )


def test_even_flow_genomes_match_the_exact_objective(tmp_path: Path) -> None:
    """An even-flow target is priced from period balances, not from single cells."""
    optimizer, _evaluator = _optimizer(tmp_path, years=8)
    targets = [
        Target(
            "product.Volume",
            period=1,
            period_width=2,
            flow="even",
            minimum=-5.0,
            maximum=5.0,
            min_weight=10.0,
            max_weight=10.0,
        ),
        Target("feature.Volume", period=3, period_width=2, minimum=1000.0),
    ]
    evaluator = IncrementalObjective(optimizer, targets)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    population = GenomePopulation(
        optimizer,
        evaluator,
        table,
        population=16,
        seed=5,
        seed_schedule=_seed(optimizer),
        random_fraction=1.0,
    )
    scores = population.evaluate()
    assert any(math.isinf(float(score)) for score in scores)
    for index in range(population.population):
        _assert_close(
            float(scores[index]), _exact(evaluator, population.schedule(population.genomes[index]))
        )


def test_run_is_exact_and_keeps_the_incumbent_under_elitism(tmp_path: Path) -> None:
    """Elitism keeps the initial best and the incumbent never regresses."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    population = GenomePopulation(
        optimizer,
        evaluator,
        table,
        population=8,
        seed=6,
        seed_schedule=_seed(optimizer),
        random_fraction=0.25,
        elite_fraction=0.5,
    )
    initial_scores = population.evaluate()
    best_before = float(initial_scores.min())
    result = population.run(5, check=8)
    assert result.objective <= result.initial_objective
    assert result.evaluations == 6 * 8
    assert result.generations == 5
    assert list(result.history) == sorted(result.history, reverse=True)
    assert float(population.evaluate().min()) <= best_before + 1e-9
    _assert_close(result.objective, _exact(evaluator, result.schedule))


def test_zero_generations_returns_the_seeded_genome(tmp_path: Path) -> None:
    """A zero-generation run is a pure exact evaluation of the initial population."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    seed = _seed(optimizer)
    population = GenomePopulation(
        optimizer, evaluator, table, population=4, seed=7, seed_schedule=seed
    )
    result = population.run(0)
    assert result.schedule == seed
    assert result.evaluations == 4
    assert result.objective == result.initial_objective
    assert result.history == (result.objective,)


def test_tournament_selects_the_best_of_each_contender_set(tmp_path: Path) -> None:
    """With every genome in the tournament, the winner is the global best."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    population = GenomePopulation(
        optimizer,
        evaluator,
        table,
        population=4,
        seed=8,
        seed_schedule=_seed(optimizer),
        tournament_size=4,
    )
    scores = torch.tensor([10.0, 1.0, 5.0, 3.0], dtype=torch.float64)
    winners = population._tournament(scores, 32)
    assert int(winners.min()) == 1
    assert int(winners.max()) == 1


def test_island_migration_runs_and_keeps_genomes_valid(tmp_path: Path) -> None:
    """Migration between two islands preserves candidate indices and the incumbent."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    population = GenomePopulation(
        optimizer,
        evaluator,
        table,
        population=8,
        seed=9,
        seed_schedule=_seed(optimizer),
        random_fraction=0.25,
        islands=2,
        migration_interval=1,
        migrants=1,
    )
    result = population.run(4, check=8)
    assert population.genomes.shape == (8, len(population.blocks))
    assert bool((population.genomes >= 0).all())
    assert bool((population.genomes < population.lengths.unsqueeze(0)).all())
    assert 0 <= result.best_island < 2
    _assert_close(result.objective, _exact(evaluator, result.schedule))


def test_invalid_population_shape_raises(tmp_path: Path) -> None:
    """A population that is not divisible by the island count is rejected."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    with pytest.raises(ValueError, match="divisible"):
        GenomePopulation(
            optimizer, evaluator, table, population=6, islands=4, seed_schedule=_seed(optimizer)
        )


def test_invalid_genome_index_is_rejected(tmp_path: Path) -> None:
    """An option index outside a block's candidate list fails loudly."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    population = GenomePopulation(
        optimizer, evaluator, table, population=4, seed=10, seed_schedule=_seed(optimizer)
    )
    invalid = population.genomes.clone()
    invalid[0, 0] = population.lengths[0]
    with pytest.raises(ValueError, match="candidate list"):
        population.evaluate(invalid)


def test_ndy_flow_is_rejected(tmp_path: Path) -> None:
    """The prototype refuses a target shape it cannot price exactly."""
    optimizer, _evaluator = _optimizer(tmp_path, years=8)
    evaluator = IncrementalObjective(
        optimizer,
        [Target("product.Volume", period=1, period_width=2, flow="ndy", minimum=-5.0)],
    )
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    with pytest.raises(NotImplementedError, match="ndy"):
        GenomePopulation(optimizer, evaluator, table, seed_schedule=_seed(optimizer))


def test_agrp_exchange_reseeds_every_worker_with_the_master_elite(tmp_path: Path) -> None:
    """The AGrp exchange returns elites and re-seeds every worker with the master best."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    population = GenomePopulation(
        optimizer,
        evaluator,
        table,
        population=8,
        seed=12,
        seed_schedule=_seed(optimizer),
        random_fraction=0.5,
        islands=2,
        exchange="agrp",
        migration_interval=1,
        migrants=1,
    )
    scores = population.evaluate()
    best_score = float(scores.min())
    population._migrate()
    assert population.scores is not None
    migrated_scores = population.scores.clone()
    for island in range(2):
        start = island * 4
        assert float(migrated_scores[start : start + 4].min()) == pytest.approx(
            best_score, abs=1e-9
        )
    assert torch.equal(population.evaluate(), migrated_scores)


def test_invalid_exchange_raises(tmp_path: Path) -> None:
    """An unknown elite-exchange topology is rejected."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    with pytest.raises(ValueError, match="exchange"):
        GenomePopulation(
            optimizer,
            evaluator,
            table,
            population=8,
            seed_schedule=_seed(optimizer),
            islands=2,
            exchange="tournament",
        )


def test_saved_table_and_population_state_round_trip(tmp_path: Path) -> None:
    """A persisted table and population state reproduce the same scores."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    seed = _seed(optimizer)
    population = GenomePopulation(
        optimizer, evaluator, table, population=8, seed=11, seed_schedule=seed
    )
    population.run(2)
    expected = population.evaluate().clone()
    state = population.save_state(tmp_path / "population.pt")
    table_path = table.save(tmp_path / "effects.pt")

    loaded_table = EffectTable.load(table_path, device="cpu")
    loaded = GenomePopulation(
        optimizer, evaluator, loaded_table, population=8, seed=11, seed_schedule=seed
    )
    loaded.load_state(state)
    actual = loaded.evaluate()
    assert torch.equal(actual, expected)
    assert loaded.schedule(loaded.best_genome) == population.schedule(population.best_genome)


def test_effect_table_missing_a_seed_chain_raises(tmp_path: Path) -> None:
    """A seed chain that was not given an extra row is reported, not silently dropped."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator, device="cpu")
    candidates = optimizer.candidates()
    block = sorted(candidates)[0]
    seed = {block: (("CC", 999),)}
    with pytest.raises(ValueError, match="extra_pairs"):
        GenomePopulation(optimizer, evaluator, table, population=4, seed_schedule=seed)
