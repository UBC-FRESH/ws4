"""Tests for the bounded process neighbourhood search."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.opt.objective import Target
from ws4.opt.process_neighbourhood import (
    PROCESS_NEIGHBOURHOOD_VERSION,
    NeighbourFunction,
    ProcessNeighbourhoodError,
    search_process_neighbourhood,
)
from ws4.opt.process_search import ProcessSearchCandidate


def _fire() -> FireConfig:
    """Return a fire-free configuration for deterministic tests."""
    return FireConfig(ignition_rate_per_fragment_year=0.0)


def _target() -> Target:
    """Return a minimum-harvest target."""
    return Target(account="harvest.area_ha_total", period=1, minimum=20.0)


def _candidates() -> dict[str, ProcessSearchCandidate]:
    """Return the no, one-fragment, and full-harvest candidates."""
    return {
        "none": ProcessSearchCandidate("none", {}),
        "one": ProcessSearchCandidate("one", {2: (("CC", 0),)}),
        "full": ProcessSearchCandidate("full", {1: (("CC", 0),)}),
    }


def _run(
    initial: ProcessSearchCandidate,
    neighbours: NeighbourFunction,
    *,
    max_iterations: int = 5,
    targets: tuple[Target, ...] = (_target(),),
) -> object:
    """Run a neighbourhood search on the small grid."""
    _schema, state, edges = synthetic_grid(3, 3)
    return search_process_neighbourhood(
        state,
        edges,
        initial,
        neighbours,
        {1: (1, 2), 2: (3,)},
        horizon_years=1,
        fire=_fire(),
        targets=targets,
        max_iterations=max_iterations,
        seed=3,
    )


def test_two_step_improving_search_reaches_the_best_candidate() -> None:
    candidates = _candidates()

    def neighbours(candidate: ProcessSearchCandidate) -> Sequence[ProcessSearchCandidate]:
        if candidate.candidate_id == "none":
            return (candidates["one"],)
        if candidate.candidate_id == "one":
            return (candidates["full"],)
        return ()

    result = _run(candidates["none"], neighbours)

    from ws4.opt.process_neighbourhood import ProcessNeighbourhoodResult

    assert isinstance(result, ProcessNeighbourhoodResult)
    assert result.best.candidate.candidate_id == "full"
    assert result.best.objective == 0.0
    assert result.iterations == 2
    assert [step.candidate_id for step in result.history] == ["one", "full"]
    assert [step.objective for step in result.history] == [10.0, 0.0]
    assert [step.improved for step in result.history] == [True, True]
    assert [item.candidate.candidate_id for item in result.evaluations] == [
        "none",
        "one",
        "full",
    ]


def test_iteration_bound_stops_after_the_first_improvement() -> None:
    candidates = _candidates()

    def neighbours(candidate: ProcessSearchCandidate) -> Sequence[ProcessSearchCandidate]:
        return (candidates["one"],) if candidate.candidate_id == "none" else ()

    result = _run(candidates["none"], neighbours, max_iterations=1)

    from ws4.opt.process_neighbourhood import ProcessNeighbourhoodResult

    assert isinstance(result, ProcessNeighbourhoodResult)
    assert result.iterations == 1
    assert result.best.candidate.candidate_id == "one"
    assert result.best.objective == 10.0


def test_non_improving_neighbour_stops_the_search() -> None:
    candidates = _candidates()

    def neighbours(candidate: ProcessSearchCandidate) -> Sequence[ProcessSearchCandidate]:
        return (candidates["one"],) if candidate.candidate_id == "full" else ()

    result = _run(candidates["full"], neighbours)

    from ws4.opt.process_neighbourhood import ProcessNeighbourhoodResult

    assert isinstance(result, ProcessNeighbourhoodResult)
    assert result.iterations == 1
    assert result.best.candidate.candidate_id == "full"
    assert result.history[0].improved is False


def test_seen_and_empty_neighbourhoods_stop_without_rounds() -> None:
    candidates = _candidates()

    def seen(candidate: ProcessSearchCandidate) -> Sequence[ProcessSearchCandidate]:
        return (candidate,)

    seen_result = _run(candidates["none"], seen)
    empty_result = _run(candidates["none"], lambda _candidate: ())

    from ws4.opt.process_neighbourhood import ProcessNeighbourhoodResult

    assert isinstance(seen_result, ProcessNeighbourhoodResult)
    assert isinstance(empty_result, ProcessNeighbourhoodResult)
    assert seen_result.iterations == 0
    assert empty_result.iterations == 0
    assert seen_result.best.candidate.candidate_id == "none"
    assert empty_result.best.candidate.candidate_id == "none"


def test_neighbourhood_artifact(tmp_path: Path) -> None:
    candidates = _candidates()

    def neighbours(candidate: ProcessSearchCandidate) -> Sequence[ProcessSearchCandidate]:
        return (candidates["full"],) if candidate.candidate_id == "none" else ()

    result = _run(candidates["none"], neighbours)
    from ws4.opt.process_neighbourhood import ProcessNeighbourhoodResult

    assert isinstance(result, ProcessNeighbourhoodResult)
    result.write(tmp_path / "neighbourhood")

    summary = json.loads(
        (tmp_path / "neighbourhood" / "process_neighbourhood_search.json").read_text()
    )
    assert summary["schema_version"] == PROCESS_NEIGHBOURHOOD_VERSION
    assert summary["best_candidate"] == "full"
    assert summary["best_objective"] == 0.0
    assert summary["iterations"] == 1
    assert (tmp_path / "neighbourhood" / "process_neighbourhood_history.csv").is_file()


def test_invalid_inputs_fail_loudly() -> None:
    candidate = ProcessSearchCandidate("none", {})

    with pytest.raises(ProcessNeighbourhoodError, match="max_iterations"):
        _run(candidate, lambda _candidate: (), max_iterations=0)
    with pytest.raises(ProcessNeighbourhoodError, match="at least one target"):
        _run(candidate, lambda _candidate: (), targets=())
    with pytest.raises(ProcessNeighbourhoodError, match="duplicate neighbour"):
        _run(
            candidate,
            lambda _candidate: (
                ProcessSearchCandidate("same", {}),
                ProcessSearchCandidate("same", {}),
            ),
        )
