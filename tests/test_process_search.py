"""Tests for the deterministic process candidate search."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ws4.ecosystem.evaluation import evaluate_process_schedule
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.opt.objective import Target
from ws4.opt.process_search import (
    PROCESS_SEARCH_VERSION,
    ProcessSearchCandidate,
    ProcessSearchError,
    ProcessSearchEvaluation,
    search_process_candidates,
)


def _fire() -> FireConfig:
    """Return a fire-free configuration for deterministic tests."""
    return FireConfig(ignition_rate_per_fragment_year=0.0)


def _target() -> Target:
    """Return a minimum-harvest target."""
    return Target(account="harvest.area_ha_total", period=1, minimum=20.0)


def _search(
    candidates: tuple[ProcessSearchCandidate, ...],
    *,
    targets: tuple[Target, ...] = (_target(),),
    seed: int = 3,
) -> object:
    """Run a candidate search on the small grid."""
    _schema, state, edges = synthetic_grid(3, 3)
    return search_process_candidates(
        state,
        edges,
        candidates,
        {1: (1, 2), 2: (3,)},
        horizon_years=1,
        fire=_fire(),
        targets=targets,
        seed=seed,
    )


def test_candidate_search_ranks_exact_objectives() -> None:
    result = _search(
        (
            ProcessSearchCandidate("none", {}),
            ProcessSearchCandidate("one", {2: (("CC", 0),)}),
            ProcessSearchCandidate("full", {1: (("CC", 0),)}),
        )
    )

    from ws4.opt.process_search import ProcessSearchResult

    assert isinstance(result, ProcessSearchResult)
    assert [item.candidate.candidate_id for item in result.ranking] == ["full", "one", "none"]
    assert [item.objective for item in result.ranking] == [0.0, 10.0, 20.0]
    assert [item.evaluation.terms for item in result.ranking] == [(0.0,), (10.0,), (20.0,)]
    assert result.best.candidate.candidate_id == "full"
    assert [item.candidate.candidate_id for item in result.results] == ["none", "one", "full"]


def test_equal_objectives_break_ties_by_candidate_id() -> None:
    result = _search(
        (
            ProcessSearchCandidate("b", {}),
            ProcessSearchCandidate("a", {}),
        )
    )

    from ws4.opt.process_search import ProcessSearchResult

    assert isinstance(result, ProcessSearchResult)
    assert [item.candidate.candidate_id for item in result.ranking] == ["a", "b"]


def test_candidate_search_is_deterministic() -> None:
    candidates = (
        ProcessSearchCandidate("none", {}),
        ProcessSearchCandidate("full", {1: (("CC", 0),)}),
    )
    first = _search(candidates)
    second = _search(candidates)

    from ws4.opt.process_search import ProcessSearchResult

    assert isinstance(first, ProcessSearchResult)
    assert isinstance(second, ProcessSearchResult)
    assert first.summary() == second.summary()


def test_candidate_search_artifact(tmp_path: Path) -> None:
    result = _search(
        (
            ProcessSearchCandidate("none", {}),
            ProcessSearchCandidate("full", {1: (("CC", 0),)}),
        )
    )
    from ws4.opt.process_search import ProcessSearchResult

    assert isinstance(result, ProcessSearchResult)
    result.write(tmp_path / "search")

    summary = json.loads((tmp_path / "search" / "process_candidate_search.json").read_text())
    assert summary["schema_version"] == PROCESS_SEARCH_VERSION
    assert summary["best_candidate"] == "full"
    assert summary["best_objective"] == 0.0
    assert summary["target_accounts"] == ["harvest.area_ha_total"]
    assert (tmp_path / "search" / "process_candidate_ranking.csv").is_file()


def test_candidate_search_rejects_invalid_inputs() -> None:
    with pytest.raises(ProcessSearchError, match="at least one candidate"):
        _search(())
    with pytest.raises(ProcessSearchError, match="at least one target"):
        _search((ProcessSearchCandidate("a", {}),), targets=())
    with pytest.raises(ProcessSearchError, match="duplicate"):
        _search(
            (
                ProcessSearchCandidate("same", {}),
                ProcessSearchCandidate("same", {}),
            )
        )
    with pytest.raises(ProcessSearchError, match="seed"):
        _search((ProcessSearchCandidate("a", {}),), seed=-1)
    with pytest.raises(ProcessSearchError, match="candidate_id"):
        ProcessSearchCandidate("", {})


def test_evaluation_without_objective_cannot_be_ranked() -> None:
    _schema, state, edges = synthetic_grid(2, 2)
    evaluation = evaluate_process_schedule(
        state,
        edges,
        {},
        {},
        horizon_years=1,
        fire=_fire(),
    )
    item = ProcessSearchEvaluation(
        candidate=ProcessSearchCandidate("none", {}),
        evaluation=evaluation,
    )

    with pytest.raises(ProcessSearchError, match="no objective"):
        _ = item.objective
