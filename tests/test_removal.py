"""Tests for the exact keep/remove carbon effect search."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from ws4.opt.objective import Target, period_value
from ws4.opt.removal import (
    RemovalEffects,
    RemovalResult,
    solve_removal,
    solve_removal_milp,
    write_removal_schedule,
)

CELLS = ((0, "product.Yield.managed.Total"), (0, "carbon.co2e.system.emissions.cumulative"))


def _effects() -> RemovalEffects:
    """Return a four-block table with one clearly bad removal."""
    return RemovalEffects(
        blocks=(1, 2, 3, 4),
        schedule={
            1: (("CC", 0),),
            2: (("CC", 0),),
            3: (("CC", 0),),
            4: (("CC", 0),),
        },
        cells=CELLS,
        base=np.zeros(2, dtype=np.float64),
        effects=np.array(
            [
                [10.0, 100.0],
                [10.0, 1.0],
                [10.0, 1.0],
                [10.0, 1.0],
            ],
            dtype=np.float64,
        ),
        target_cells=((0,), (1,)),
        targets=(
            Target(
                account="product.Yield.managed.Total",
                period=1,
                minimum=30.0,
                min_weight=10.0,
            ),
            Target(
                account="carbon.co2e.system.emissions.cumulative",
                period=1,
                maximum=0.0,
                max_weight=0.001,
            ),
        ),
    )


def test_removal_search_drops_the_high_emission_block() -> None:
    """The search removes the high-emission block while meeting yield."""
    result = solve_removal(_effects(), population=512, generations=1500, seed=1)
    assert 1 not in result.schedule
    assert len(result.schedule) == 3
    assert result.values[CELLS[0]] == 30.0
    assert result.values[CELLS[1]] == 3.0
    assert result.objective == 0.003


def test_removal_result_writes_the_schedule_schema(tmp_path: Path) -> None:
    """The winning schedule is written in block/treatment/offset form."""
    result = RemovalResult(
        schedule={1: (("CC", 0),), 3: (("CC", 2),)},
        keep=np.array([True, False, True], dtype=bool),
        objective=0.0,
        values={},
        generations=1,
        search_seconds=0.0,
    )
    path = tmp_path / "schedule.csv"
    write_removal_schedule(result, path)
    frame = pd.read_csv(path)
    assert list(frame.columns) == ["block_id", "treatment", "offset"]
    assert frame.to_dict("records") == [
        {"block_id": 1, "treatment": "CC", "offset": 0},
        {"block_id": 3, "treatment": "CC", "offset": 2},
    ]


def test_period_value_reads_accumulating_product_cells() -> None:
    """The exact report uses the same period semantics as the optimizer."""
    values = {(0, "product.Yield.managed.Total"): 12.0}
    target = Target(account="product.Yield.managed.Total", period=1)
    assert period_value(values, target) == 12.0


def test_effect_table_round_trip(tmp_path: Path) -> None:
    """The exact effect table is cacheable without rebuilding."""
    effects = _effects()
    path = effects.save(tmp_path / "cache")
    loaded = RemovalEffects.load(path, effects.schedule, effects.targets)
    np.testing.assert_array_equal(loaded.blocks, effects.blocks)
    np.testing.assert_array_equal(loaded.base, effects.base)
    np.testing.assert_array_equal(loaded.effects, effects.effects)
    assert loaded.target_cells == effects.target_cells


def test_milp_finds_the_binary_optimum() -> None:
    """The exact knapsack removes the high-emission block."""
    pytest.importorskip("scipy")
    result = solve_removal_milp(_effects())
    assert 1 not in result.schedule
    assert len(result.schedule) == 3
    assert result.values[CELLS[0]] == 30.0
    assert result.values[CELLS[1]] == 3.0
