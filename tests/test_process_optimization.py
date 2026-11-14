"""Tests for end-to-end process optimization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.opt.objective import Target
from ws4.opt.process_optimization import (
    PROCESS_OPTIMIZATION_VERSION,
    ProcessOptimizationError,
    optimize_process_schedule,
)
from ws4.opt.process_search import ProcessSearchCandidate
from ws4.opt.schedule_grammar import ScheduleGrammarError, ScheduleMoveGrammar, schedule_id


def _grammar() -> ScheduleMoveGrammar:
    """Return the two-block one-year grammar."""
    return ScheduleMoveGrammar(
        blocks=(1, 2), treatments=("CC",), horizon_years=1, max_events_per_block=1
    )


def _target() -> Target:
    """Return a minimum-harvest target."""
    return Target(account="harvest.area_ha_total", period=1, minimum=20.0)


def _optimize(
    *,
    grammar: ScheduleMoveGrammar | None = None,
    initial: ProcessSearchCandidate | None = None,
    targets: tuple[Target, ...] = (_target(),),
    max_iterations: int = 3,
) -> object:
    """Run the optimization on the small grid."""
    selected_grammar = grammar or _grammar()
    selected_initial = initial or ProcessSearchCandidate(schedule_id({}), {})
    _schema, state, edges = synthetic_grid(3, 3)
    return optimize_process_schedule(
        state,
        edges,
        selected_grammar,
        selected_initial,
        {1: (1, 2), 2: (3,)},
        horizon_years=1,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        targets=targets,
        max_iterations=max_iterations,
        seed=5,
    )


def test_optimization_reaches_the_full_harvest() -> None:
    result = _optimize()
    from ws4.opt.process_optimization import ProcessOptimizationResult

    assert isinstance(result, ProcessOptimizationResult)
    assert result.best.candidate.schedule == {1: (("CC", 0),)}
    assert result.best.objective == 0.0
    assert result.search.iterations == 2
    assert result.search.history[1].improved is False
    assert result.summary()["best_candidate"] == schedule_id({1: (("CC", 0),)})


def test_optimization_is_deterministic() -> None:
    first = _optimize()
    second = _optimize()
    from ws4.opt.process_optimization import ProcessOptimizationResult

    assert isinstance(first, ProcessOptimizationResult)
    assert isinstance(second, ProcessOptimizationResult)
    assert first.summary() == second.summary()


def test_optimization_artifact(tmp_path: Path) -> None:
    result = _optimize()
    from ws4.opt.process_optimization import ProcessOptimizationResult

    assert isinstance(result, ProcessOptimizationResult)
    result.write(tmp_path / "optimization")

    summary = json.loads((tmp_path / "optimization" / "process_optimization.json").read_text())
    assert summary["schema_version"] == PROCESS_OPTIMIZATION_VERSION
    assert summary["best_objective"] == 0.0
    assert summary["best_schedule"] == [[1, [["CC", 0]]]]
    assert summary["best_accounts"]["harvest.area_ha_total"] == 20.0
    assert (tmp_path / "optimization" / "best_evaluation" / "process_evaluation.json").is_file()
    assert (tmp_path / "optimization" / "process_neighbourhood_search.json").is_file()


def test_optimization_rejects_horizon_and_schedule_mismatches() -> None:
    _schema, state, edges = synthetic_grid(2, 2)
    with pytest.raises(ProcessOptimizationError, match="horizon"):
        optimize_process_schedule(
            state,
            edges,
            ScheduleMoveGrammar(
                blocks=(1,), treatments=("CC",), horizon_years=2, max_events_per_block=1
            ),
            ProcessSearchCandidate(schedule_id({}), {}),
            {1: (1,)},
            horizon_years=1,
            fire=FireConfig(ignition_rate_per_fragment_year=0.0),
            targets=(_target(),),
            max_iterations=1,
        )
    with pytest.raises(ScheduleGrammarError, match="outside the grammar"):
        optimize_process_schedule(
            state,
            edges,
            ScheduleMoveGrammar(
                blocks=(1,), treatments=("CC",), horizon_years=1, max_events_per_block=1
            ),
            ProcessSearchCandidate(schedule_id({2: (("CC", 0),)}), {2: (("CC", 0),)}),
            {1: (1,)},
            horizon_years=1,
            fire=FireConfig(ignition_rate_per_fragment_year=0.0),
            targets=(_target(),),
            max_iterations=1,
        )


def test_estate_handoff_round_trips_through_the_loaders(tmp_path: Path) -> None:
    from ws4.ecosystem.management import load_block_fragments, load_schedule
    from ws4.opt.process_optimization import ProcessOptimizationResult

    result = _optimize()
    assert isinstance(result, ProcessOptimizationResult)
    result.write_estate_inputs(tmp_path / "handoff")

    schedule_path = tmp_path / "handoff" / "schedule.csv"
    mapping_path = tmp_path / "handoff" / "block_fragments.csv"
    assert schedule_path.read_text() == "block_id,treatment,offset\n1,CC,0\n"
    assert mapping_path.read_text() == "block_id,fragment_id\n1,1\n1,2\n2,3\n"
    assert load_schedule(schedule_path) == result.best.candidate.schedule
    assert load_block_fragments(mapping_path) == {1: (1, 2), 2: (3,)}
    assert (tmp_path / "handoff" / "best_evaluation" / "process_evaluation.json").is_file()


def test_estate_handoff_rejects_invalid_mappings() -> None:
    from ws4.opt.process_optimization import ProcessOptimizationResult

    result = _optimize()
    from ws4.opt.process_optimization import ProcessOptimizationResult as Result

    assert isinstance(result, Result)
    with pytest.raises(ProcessOptimizationError, match="positive"):
        ProcessOptimizationResult(search=result.search, block_fragments={0: (1,)})
    with pytest.raises(ProcessOptimizationError, match="positive"):
        ProcessOptimizationResult(search=result.search, block_fragments={1: (0,)})
