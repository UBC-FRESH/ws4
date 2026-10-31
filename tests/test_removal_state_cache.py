"""Tests for the fresh-cbm state-cache adapter."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np
import pandas as pd
import pytest
from ws4.opt.engine import Optimizer
from ws4.opt.objective import Target
from ws4.opt.removal import build_removal_effects_from_state_cache


class _FakeCache:
    """The small subset of fresh_cbm.StateCache the adapter reads."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest = {"years": 2, "offsets": [0]}
        self.accounts = ["carbon.system.total"]
        self.index = pd.DataFrame(
            {
                "state_id": [0, 1],
                "track_id": [10, 10],
                "age": [5, 10],
            }
        )

    @classmethod
    def load(cls, root: str | Path) -> _FakeCache:
        return cls(Path(root))


class _FakeOptimizer:
    """The simulator side of the adapter."""

    def __init__(self, dataset_dir: Path) -> None:
        self.dataset_dir = dataset_dir

    def _simulator_base_values(self) -> dict[tuple[int, str], float]:
        return {(0, "product.Yield.managed.Total"): 100.0}

    def _simulator_block_delta(
        self, block: int, chain: tuple[object, ...]
    ) -> dict[tuple[int, str], float]:
        return {
            (0, "product.Yield.managed.Total"): 50.0 if block == 1 else 25.0,
        }


def test_state_cache_adapter_uses_exact_carbon_and_simulator_yield(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carbon cells come from the cache; non-carbon cells from the simulator."""
    root = tmp_path / "cache"
    (root / "values").mkdir(parents=True)
    empty = np.array([[[10.0]], [[20.0]]])
    current = np.array([[[5.0]], [[10.0]]])
    np.save(root / "values" / "empty.npy", empty)
    np.save(root / "values" / "offset_00.npy", current)

    dataset = tmp_path / "dataset"
    dataset.mkdir()
    pd.DataFrame(
        {
            "block_id": [1, 2],
            "track_id": [10, 10],
            "age": [5, 10],
            "area_ha": [2.0, 1.0],
        }
    ).to_parquet(dataset / "fragments.parquet", index=False)

    module = SimpleNamespace(StateCache=_FakeCache)
    monkeypatch.setitem(sys.modules, "fresh_cbm", module)
    targets = (
        Target(account="product.Yield.managed.Total", period=1, minimum=0.0),
        Target(account="carbon.system.total", period=1, maximum=0.0),
    )
    schedule = {1: (("CC", 0),), 2: (("CC", 0),)}
    effects = build_removal_effects_from_state_cache(
        cast(Optimizer, _FakeOptimizer(dataset)), schedule, targets, root
    )

    carbon = effects.cells.index((0, "carbon.system.total"))
    yield_cell = effects.cells.index((0, "product.Yield.managed.Total"))
    assert effects.base[carbon] == 40.0
    assert effects.base[yield_cell] == 100.0
    assert effects.effects[:, carbon].tolist() == [-10.0, -10.0]
    assert effects.effects[:, yield_cell].tolist() == [50.0, 25.0]
