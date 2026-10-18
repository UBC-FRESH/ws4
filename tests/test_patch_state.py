"""Parity tests for the incremental patch state.

The incremental state must agree, cell for cell, with the from-scratch computation after any
sequence of block-value changes (including component merges and splits).
"""

from __future__ import annotations

import math
import random

import pytest
from ws4.opt.patch_state import PatchGroupTopology, PatchGroupYear
from ws4.patch.accounts import PatchAccount, patch_account_values_indexed


def _grid(
    rows: int, cols: int, rng: random.Random
) -> tuple[dict[int, tuple[tuple[int, float], ...]], dict[int, float]]:
    """Build a grid topology and random block areas."""
    neighbours: dict[int, list[tuple[int, float]]] = {}
    block_area: dict[int, float] = {}

    def link(a: int, b: int) -> None:
        length = round(rng.uniform(1.0, 30.0), 3)
        neighbours.setdefault(a, []).append((b, length))
        neighbours.setdefault(b, []).append((a, length))

    for row in range(rows):
        for col in range(cols):
            block = row * cols + col
            block_area[block] = round(rng.uniform(0.5, 20.0), 3)
            neighbours.setdefault(block, [])
            if col + 1 < cols:
                link(block, block + 1)
            if row + 1 < rows:
                link(block, block + cols)
    return {b: tuple(v) for b, v in neighbours.items()}, block_area


def test_incremental_state_matches_from_scratch_over_random_mutations() -> None:
    """After every mutation the incremental cells equal the from-scratch computation."""
    rng = random.Random(0)
    neighbours, block_area = _grid(6, 6, rng)
    account = PatchAccount(
        name="patch.p", criteria="c", threshold=0.5, size_classes=(2.0, 10.0, 40.0, math.inf)
    )
    state = PatchGroupYear([account], 0.5, neighbours, block_area)
    values: dict[int, float] = {}
    for step in range(300):
        block = rng.randrange(36)
        value = rng.choice([None, 0.2, 0.45, 0.55, 0.8, 1.0, 1.5])
        state.set_value(block, value)
        if value is None or value <= 0.5:
            values.pop(block, None)
        else:
            values[block] = value
        expected = {
            f"{account.name}.{key}": val
            for key, val in patch_account_values_indexed(
                account, values, neighbours, block_area
            ).items()
        }
        got = state.cells()
        keys = set(expected) | set(got)
        for key in keys:
            assert got.get(key, 0.0) == pytest.approx(expected.get(key, 0.0), abs=1e-9), (
                f"step {step} key {key}"
            )


def test_incremental_state_handles_two_accounts_in_a_group() -> None:
    """Two accounts with different size classes share the member set and agree with the scan."""
    rng = random.Random(1)
    neighbours, block_area = _grid(4, 4, rng)
    accounts = [
        PatchAccount(name="a", criteria="c", threshold=0.5, size_classes=(2.0, 20.0, math.inf)),
        PatchAccount(name="b", criteria="c", threshold=0.5, size_classes=(5.0, math.inf)),
    ]
    state = PatchGroupYear(accounts, 0.5, neighbours, block_area)
    values: dict[int, float] = {}
    for _ in range(150):
        block = rng.randrange(16)
        value = rng.choice([None, 0.3, 0.7, 1.1])
        state.set_value(block, value)
        if value is None or value <= 0.5:
            values.pop(block, None)
        else:
            values[block] = value
        got = state.cells()
        for account in accounts:
            expected = {
                f"{account.name}.{key}": val
                for key, val in patch_account_values_indexed(
                    account, values, neighbours, block_area
                ).items()
            }
            for key, val in expected.items():
                assert got[key] == pytest.approx(val, abs=1e-9)


def test_a_state_over_a_shared_topology_matches_one_built_from_scratch() -> None:
    """A state built over a shared topology is indistinguishable from a self-contained one."""
    rng = random.Random(7)
    neighbours, block_area = _grid(5, 5, rng)
    account = PatchAccount(
        name="patch.p", criteria="c", threshold=0.5, size_classes=(2.0, 10.0, 40.0, math.inf)
    )
    topology = PatchGroupTopology(neighbours, block_area)
    shared = PatchGroupYear.from_topology([account], 0.5, topology)
    own = PatchGroupYear([account], 0.5, neighbours, block_area)
    assert shared._ptr is topology.ptr
    assert shared._v_area is topology.v_area
    for _ in range(120):
        block = rng.randrange(25)
        value = rng.choice([None, 0.2, 0.55, 1.0, 1.6])
        shared.set_value(block, value)
        own.set_value(block, value)
        for key, expected in own.cells().items():
            assert shared.cells()[key] == pytest.approx(expected, abs=1e-9), (
                f"block {block} key {key}"
            )
