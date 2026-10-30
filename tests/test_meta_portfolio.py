"""Tests for the fixed round-robin master/worker metaheuristic portfolio."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.meta_portfolio import (
    MetaPortfolio,
    PortfolioArchive,
    PortfolioElite,
    WorkerSpec,
    default_worker_specs,
)
from ws4.opt.objective import Target

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _dataset(tmp_path: Path, blocks: int = 16) -> Path:
    """Compile a small synthetic dataset with several candidate chains per block."""
    fragments = tmp_path / "fragments.csv"
    rows = ["BLOCK,AREA_HA,F_AGE,AU,IFM"]
    rows.extend(
        f"{block},{2.0 + block % 3},{(block * 7) % 80 + 40},1,unmanaged"
        for block in range(1, blocks + 1)
    )
    fragments.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return build_canonical_dataset(_FIXTURE / "recipe.xml", fragments, tmp_path / "compiled")


def _optimizer(
    tmp_path: Path, *, years: int = 4, blocks: int = 16
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


def _elite(
    objective: float, source: str, schedule: dict[int, tuple[tuple[str, int], ...]] | None = None
) -> PortfolioElite:
    """Build a small archive record."""
    return PortfolioElite(
        objective=objective,
        schedule={1: (("CC", 0),)} if schedule is None else schedule,
        source=source,
        method="test",
        worker="test",
        round_index=0,
    )


def test_archive_keeps_distinct_best_elites_and_a_capacity_bound() -> None:
    """The archive deduplicates schedules, replaces same-schedule copies, and caps size."""
    archive = PortfolioArchive(capacity=2)
    assert archive.add(_elite(3.0, "c"))
    assert archive.add(_elite(2.0, "b", {1: (("CC", 100),)}))
    assert not archive.add(_elite(4.0, "worst", {1: (("CC", 200),)}))
    assert [elite.source for elite in archive.elites] == ["b", "c"]
    assert archive.add(_elite(1.0, "better-copy", {1: (("CC", 0),)}))
    assert [elite.source for elite in archive.elites] == ["better-copy", "b"]
    assert not archive.add(_elite(5.0, "same", {1: (("CC", 0),)}))
    assert archive.add(_elite(0.5, "d", {1: (("CC", 300),)}))
    assert [elite.source for elite in archive.elites] == ["d", "better-copy"]
    assert len(archive.elites) == 2


def test_archive_rejects_an_empty_capacity() -> None:
    """A capacity below one is a configuration error."""
    with pytest.raises(ValueError, match="capacity"):
        PortfolioArchive(capacity=0)


def test_worker_spec_rejects_invalid_values() -> None:
    """Worker slots validate their name, method, and budget."""
    with pytest.raises(ValueError, match="name"):
        WorkerSpec("", "sa", 1, 1)
    with pytest.raises(ValueError, match="method"):
        WorkerSpec("bad", "nope", 1, 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="budget"):
        WorkerSpec("bad", "sa", -1, 1)


def test_default_worker_specs_cover_the_five_methods() -> None:
    """The seven-slot default is a fixed heterogeneous AGrp-style allocation."""
    specs = default_worker_specs(seed=3, iterations=50, generations=4)
    assert len(specs) == 7
    assert {spec.method for spec in specs} == {"sa", "tabu", "ils", "ga", "lns"}
    assert [spec.seed for spec in specs] == [3, 4, 5, 6, 7, 8, 9]
    assert specs[-1].diverse
    with pytest.raises(ValueError, match="positive"):
        default_worker_specs(iterations=0)


def test_portfolio_validates_the_allocation_and_parameters(tmp_path: Path) -> None:
    """Invalid combinations fail before any search starts."""
    optimizer, evaluator = _optimizer(tmp_path)
    with pytest.raises(ValueError, match="at least one worker"):
        MetaPortfolio(optimizer, evaluator.targets, workers=())
    with pytest.raises(ValueError, match="unique"):
        MetaPortfolio(
            optimizer,
            evaluator.targets,
            workers=(WorkerSpec("a", "sa", 1, 1), WorkerSpec("a", "sa", 1, 2)),
        )
    with pytest.raises(ValueError, match="effect table"):
        MetaPortfolio(optimizer, evaluator.targets, workers=(WorkerSpec("ga", "ga", 1, 1),))
    with pytest.raises(ValueError, match="effect table"):
        MetaPortfolio(
            optimizer,
            evaluator.targets,
            workers=(WorkerSpec("lns", "lns", 1, 1),),
            lns_backend="gpu",
        )
    with pytest.raises(ValueError, match="rounds"):
        MetaPortfolio(
            optimizer,
            evaluator.targets,
            rounds=0,
            workers=(WorkerSpec("a", "sa", 1, 1),),
        )
    with pytest.raises(ValueError, match="cooling"):
        MetaPortfolio(
            optimizer, evaluator.targets, cooling=0.0, workers=(WorkerSpec("a", "sa", 1, 1),)
        )
    with pytest.raises(ValueError, match="capacity"):
        MetaPortfolio(
            optimizer,
            evaluator.targets,
            archive_capacity=0,
            workers=(WorkerSpec("a", "sa", 1, 1),),
        )


def test_round_robin_records_migrations_and_returns_an_exact_incumbent(tmp_path: Path) -> None:
    """Two rounds of SA, tabu, ILS, LNS, and a diverse restart are recorded exactly."""
    optimizer, evaluator = _optimizer(tmp_path)
    initial = _seed(optimizer)
    workers = (
        WorkerSpec("sa", "sa", 6, 1),
        WorkerSpec("tabu", "tabu", 2, 2),
        WorkerSpec("ils", "ils", 2, 3),
        WorkerSpec("lns", "lns", 6, 4),
        WorkerSpec("restart", "sa", 6, 5, diverse=True),
    )
    portfolio = MetaPortfolio(
        optimizer,
        evaluator.targets,
        initial=initial,
        workers=workers,
        rounds=2,
        tenure=3,
        tabu_samples=2,
        perturbation=2,
    )
    result = portfolio.run()
    assert len(result.migrations) == 10
    assert len(result.history) == 11
    assert result.rounds == 2
    assert result.objective == pytest.approx(_exact(evaluator, result.schedule), abs=1e-6)
    assert result.objective <= result.seed_objective
    assert result.time_to_best <= result.seconds
    assert {migration.method for migration in result.migrations} == {
        "sa",
        "tabu",
        "ils",
        "lns",
    }
    assert result.contributions["sa"].slices == 4
    assert result.contributions["tabu"].slices == 2
    assert result.contributions["lns"].evaluations == 12
    assert result.contributions["tabu"].as_dict()["best_objective"] is not None
    assert result.elites
    assert result.elites[0].objective <= result.seed_objective + 1e-9
    json.dumps(result.as_dict())


def test_repeated_runs_from_the_same_seeds_are_reproducible(tmp_path: Path) -> None:
    """Independent workers and the fixed allocation leave no hidden run-to-run state."""
    optimizer, evaluator = _optimizer(tmp_path)
    workers = (
        WorkerSpec("sa", "sa", 4, 1),
        WorkerSpec("ils", "ils", 2, 2),
        WorkerSpec("lns", "lns", 4, 3),
    )
    first = MetaPortfolio(
        optimizer,
        evaluator.targets,
        initial=_seed(optimizer),
        workers=workers,
        rounds=2,
        perturbation=2,
    ).run()
    second = MetaPortfolio(
        optimizer,
        evaluator.targets,
        initial=_seed(optimizer),
        workers=workers,
        rounds=2,
        perturbation=2,
    ).run()
    assert first.objective == second.objective
    assert first.schedule == second.schedule
    assert first.history == second.history
    assert [m.returned_objective for m in first.migrations] == [
        m.returned_objective for m in second.migrations
    ]


def test_ga_worker_returns_an_exact_verified_elite(tmp_path: Path) -> None:
    """The GPU population path is seeded from an elite and verified by the master."""
    pytest.importorskip("torch")
    from ws4.opt.gpu_effects import EffectTable

    optimizer, evaluator = _optimizer(tmp_path)
    initial = _seed(optimizer)
    candidates = optimizer.candidates()
    table = EffectTable.build(
        optimizer,
        evaluator,
        blocks=tuple(sorted(candidates)),
        extra_pairs=list(initial.items()),
        candidates=candidates,
        device="cpu",
    )
    portfolio = MetaPortfolio(
        optimizer,
        evaluator.targets,
        initial=initial,
        table=table,
        workers=(WorkerSpec("ga", "ga", 2, 7),),
        rounds=2,
        ga_population=8,
        ga_random_fraction=0.5,
        ga_mutation_rate=0.1,
    )
    result = portfolio.run()
    assert len(result.migrations) == 2
    assert [migration.method for migration in result.migrations] == ["ga", "ga"]
    assert result.contributions["ga"].slices == 2
    assert result.migrations[1].seeded_objective in {elite.objective for elite in result.elites}
    assert result.objective == pytest.approx(_exact(evaluator, result.schedule), abs=1e-6)


def test_gpu_lns_worker_returns_an_exact_verified_elite(tmp_path: Path) -> None:
    """The batched GPU LNS prototype can serve as one portfolio worker."""
    pytest.importorskip("torch")
    from ws4.opt.gpu_effects import EffectTable

    optimizer, evaluator = _optimizer(tmp_path)
    initial = _seed(optimizer)
    candidates = optimizer.candidates()
    table = EffectTable.build(
        optimizer,
        evaluator,
        blocks=tuple(sorted(candidates)),
        extra_pairs=list(initial.items()),
        candidates=candidates,
        device="cpu",
    )
    portfolio = MetaPortfolio(
        optimizer,
        evaluator.targets,
        initial=initial,
        table=table,
        workers=(WorkerSpec("lns", "lns", 2, 8),),
        lns_backend="gpu",
        lns_proposals=4,
    )
    result = portfolio.run()
    assert len(result.migrations) == 1
    assert result.migrations[0].method == "lns"
    assert result.contributions["lns"].evaluations == 8
    assert result.objective == pytest.approx(_exact(evaluator, result.schedule), abs=1e-6)


def test_time_limit_stops_before_the_first_slice(tmp_path: Path) -> None:
    """A deadline is honoured between slices and the seed remains the incumbent."""
    optimizer, evaluator = _optimizer(tmp_path)
    portfolio = MetaPortfolio(
        optimizer,
        evaluator.targets,
        initial=_seed(optimizer),
        workers=(WorkerSpec("sa", "sa", 1, 1),),
    )
    with pytest.raises(ValueError, match="time_limit"):
        portfolio.run(time_limit=0.0)
    result = portfolio.run(time_limit=1e-12)
    assert result.migrations == ()
    assert result.rounds == 0
    assert result.objective == pytest.approx(result.seed_objective, abs=1e-6)
    assert result.history == (result.seed_objective,)


def test_candidate_slice_and_effect_table_are_checked(tmp_path: Path) -> None:
    """A slice outside the optimizer or outside the table fails before searching."""
    optimizer, evaluator = _optimizer(tmp_path)
    with pytest.raises(ValueError, match="does not know"):
        MetaPortfolio(
            optimizer,
            evaluator.targets,
            candidates={999_999: [(("CC", 0),)]},
            workers=(WorkerSpec("sa", "sa", 1, 1),),
        )
    pytest.importorskip("torch")
    from ws4.opt.gpu_effects import EffectTable

    initial = _seed(optimizer)
    candidates = optimizer.candidates()
    table = EffectTable.build(
        optimizer,
        evaluator,
        blocks=tuple(sorted(candidates)),
        extra_pairs=list(initial.items()),
        candidates=candidates,
        device="cpu",
    )
    first = min(candidates)
    with pytest.raises(ValueError, match="outside the candidate slice"):
        MetaPortfolio(
            optimizer,
            evaluator.targets,
            candidates={first: candidates[first]},
            initial={first: initial[first]},
            table=table,
            workers=(WorkerSpec("sa", "sa", 1, 1),),
        )


def test_a_worker_claim_that_disagrees_with_exact_evaluation_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The master's fresh evaluation is an oracle over a stale or wrong worker objective."""
    optimizer, evaluator = _optimizer(tmp_path)
    portfolio = MetaPortfolio(
        optimizer,
        evaluator.targets,
        initial=_seed(optimizer),
        workers=(WorkerSpec("sa", "sa", 1, 1),),
    )
    from ws4.opt.meta_portfolio import _WorkerOutcome

    def bad_worker(
        spec: WorkerSpec,
        source: PortfolioElite,
        deadline: float | None,
        ga_workers: dict[str, object],
    ) -> _WorkerOutcome:
        return _WorkerOutcome(dict(source.schedule), source.objective + 1.0, 0.0, 1)

    monkeypatch.setattr(portfolio, "_run_worker", bad_worker)
    with pytest.raises(AssertionError, match="claimed objective"):
        portfolio.run()
