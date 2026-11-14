"""Tests for the deterministic schedule mutation grammar."""

from __future__ import annotations

import pytest
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.opt.objective import Target
from ws4.opt.process_neighbourhood import search_process_neighbourhood
from ws4.opt.process_search import ProcessSearchCandidate
from ws4.opt.schedule_grammar import (
    ScheduleGrammarError,
    ScheduleMoveGrammar,
    schedule_id,
)


def _grammar(*, max_events: int = 1) -> ScheduleMoveGrammar:
    """Return the two-block, one-treatment grammar."""
    return ScheduleMoveGrammar(
        blocks=(1, 2),
        treatments=("CC",),
        horizon_years=2,
        max_events_per_block=max_events,
    )


def test_empty_schedule_has_only_add_neighbours() -> None:
    grammar = _grammar()
    neighbours = grammar.neighbours(ProcessSearchCandidate(schedule_id({}), {}))

    assert len(neighbours) == 4
    assert len({candidate.candidate_id for candidate in neighbours}) == 4
    assert [candidate.schedule for candidate in neighbours] == [
        {1: (("CC", 0),)},
        {1: (("CC", 1),)},
        {2: (("CC", 0),)},
        {2: (("CC", 1),)},
    ]


def test_single_event_has_add_and_remove_neighbours() -> None:
    grammar = _grammar(max_events=2)
    schedule = {1: (("CC", 0),)}
    neighbours = grammar.neighbours(ProcessSearchCandidate(schedule_id(schedule), schedule))

    assert len(neighbours) == 4
    assert {candidate.candidate_id for candidate in neighbours} == {
        schedule_id({1: (("CC", 0), ("CC", 1))}),
        schedule_id({1: (("CC", 0),), 2: (("CC", 0),)}),
        schedule_id({1: (("CC", 0),), 2: (("CC", 1),)}),
        schedule_id({}),
    }


def test_schedule_ids_are_canonical_and_stable() -> None:
    unordered = {1: (("CC", 1), ("CC", 0))}
    ordered = {1: (("CC", 0), ("CC", 1))}

    assert schedule_id(unordered) == schedule_id(ordered)
    assert schedule_id({}) == schedule_id({})
    assert schedule_id({1: (("CC", 0),)}) != schedule_id({})


def test_grammar_validates_the_candidate_universe() -> None:
    grammar = _grammar()
    cases = (
        {3: (("CC", 0),)},
        {1: (("CT", 0),)},
        {1: (("CC", 2),)},
        {1: (("CC", 0), ("CC", 1))},
        {1: (("CC", 0), ("CC", 0))},
    )
    for schedule in cases:
        with pytest.raises(ScheduleGrammarError):
            grammar.neighbours(ProcessSearchCandidate(schedule_id(schedule), schedule))


def test_invalid_grammar_configuration_fails_loudly() -> None:
    with pytest.raises(ScheduleGrammarError, match="blocks"):
        ScheduleMoveGrammar(blocks=(), treatments=("CC",), horizon_years=1)
    with pytest.raises(ScheduleGrammarError, match="unique"):
        ScheduleMoveGrammar(blocks=(1, 1), treatments=("CC",), horizon_years=1)
    with pytest.raises(ScheduleGrammarError, match="treatments"):
        ScheduleMoveGrammar(blocks=(1,), treatments=("  ",), horizon_years=1)
    with pytest.raises(ScheduleGrammarError, match="horizon_years"):
        ScheduleMoveGrammar(blocks=(1,), treatments=("CC",), horizon_years=0)
    with pytest.raises(ScheduleGrammarError, match="max_events_per_block"):
        ScheduleMoveGrammar(
            blocks=(1,), treatments=("CC",), horizon_years=1, max_events_per_block=0
        )


def test_grammar_drives_the_process_neighbourhood_search() -> None:
    grammar = ScheduleMoveGrammar(
        blocks=(1, 2), treatments=("CC",), horizon_years=1, max_events_per_block=1
    )
    initial = ProcessSearchCandidate(schedule_id({}), {})
    _schema, state, edges = synthetic_grid(3, 3)

    result = search_process_neighbourhood(
        state,
        edges,
        initial,
        grammar.neighbours,
        {1: (1, 2), 2: (3,)},
        horizon_years=1,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        targets=(Target(account="harvest.area_ha_total", period=1, minimum=20.0),),
        max_iterations=3,
        seed=5,
    )

    assert result.best.candidate.schedule == {1: (("CC", 0),)}
    assert result.best.objective == 0.0
    assert result.iterations == 2
    assert [step.candidate_id for step in result.history] == [
        schedule_id({1: (("CC", 0),)}),
        schedule_id({1: (("CC", 0),), 2: (("CC", 0),)}),
    ]
    assert result.history[1].improved is False


def test_offset_moves_are_optional_and_exact() -> None:
    schedule = {1: (("CC", 0), ("CC", 1))}
    base = ScheduleMoveGrammar(
        blocks=(1,), treatments=("CC",), horizon_years=3, max_events_per_block=3
    )
    moving = ScheduleMoveGrammar(
        blocks=(1,),
        treatments=("CC",),
        horizon_years=3,
        max_events_per_block=3,
        allow_offset_moves=True,
    )

    base_ids = {
        candidate.candidate_id
        for candidate in base.neighbours(ProcessSearchCandidate(schedule_id(schedule), schedule))
    }
    move_ids = {
        candidate.candidate_id
        for candidate in moving.neighbours(ProcessSearchCandidate(schedule_id(schedule), schedule))
    }

    assert base_ids == {
        schedule_id({1: (("CC", 0), ("CC", 1), ("CC", 2))}),
        schedule_id({1: (("CC", 1),)}),
        schedule_id({1: (("CC", 0),)}),
    }
    assert move_ids == base_ids | {
        schedule_id({1: (("CC", 1), ("CC", 2))}),
        schedule_id({1: (("CC", 0), ("CC", 2))}),
    }


def test_windows_restrict_adds_and_validate_schedules() -> None:
    grammar = ScheduleMoveGrammar(
        blocks=(1, 2),
        treatments=("CC",),
        horizon_years=4,
        max_events_per_block=1,
        windows={1: (1, 3)},
    )
    neighbours = grammar.neighbours(ProcessSearchCandidate(schedule_id({}), {}))

    assert {candidate.candidate_id for candidate in neighbours} == {
        schedule_id({1: (("CC", 1),)}),
        schedule_id({1: (("CC", 2),)}),
        schedule_id({2: (("CC", 0),)}),
        schedule_id({2: (("CC", 1),)}),
        schedule_id({2: (("CC", 2),)}),
        schedule_id({2: (("CC", 3),)}),
    }
    with pytest.raises(ScheduleGrammarError, match="window"):
        grammar.neighbours(
            ProcessSearchCandidate(schedule_id({1: (("CC", 0),)}), {1: (("CC", 0),)})
        )


def test_invalid_windows_fail_loudly() -> None:
    common = {"blocks": (1,), "treatments": ("CC",), "horizon_years": 2}
    with pytest.raises(ScheduleGrammarError, match="outside the grammar"):
        ScheduleMoveGrammar(**common, windows={2: (0, 1)})  # type: ignore[arg-type]
    with pytest.raises(ScheduleGrammarError, match="bounds"):
        ScheduleMoveGrammar(**common, windows={1: (-1, 1)})  # type: ignore[arg-type]
    with pytest.raises(ScheduleGrammarError, match="bounds"):
        ScheduleMoveGrammar(**common, windows={1: (1, 1)})  # type: ignore[arg-type]
    with pytest.raises(ScheduleGrammarError, match="bounds"):
        ScheduleMoveGrammar(**common, windows={1: (0, 3)})  # type: ignore[arg-type]
