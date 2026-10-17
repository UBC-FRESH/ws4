"""Tests for patch size-distribution accounts in the optimizer."""

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
from ws4.opt.operators import Schedule
from ws4.opt.patch import PatchModel
from ws4.opt.patch_state import PatchGroupYear
from ws4.patch.accounts import (
    PatchAccount,
    PatchLedger,
    load_patch_accounts,
    patch_account_values,
    patch_account_values_indexed,
)
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _topology(path: Path) -> Path:
    """Write a one-edge topology joining the fixture's two blocks.

    The blocks share a vertex (distance 0), so the default ``search_distance`` of 0 keeps the
    edge.
    """
    path.write_text("BLOCK1,BLOCK2,DISTANCE,LENGTH\n1,2,0,100\n", encoding="utf-8")
    return path


def _patches(path: Path) -> Path:
    """Write a patch-account definition on the fixture's feature.Volume."""
    path.write_text(
        "accounts:\n"
        "  - name: patch.harvest\n"
        "    criteria: feature.Volume\n"
        "    threshold: 0.0\n"
        "    size_classes: [5.0, 50.0, .inf]\n",
        encoding="utf-8",
    )
    return path


def test_indexed_patch_values_match_the_edge_scan() -> None:
    """The block-indexed computation equals the whole-edge-scan computation."""
    account = PatchAccount(
        name="p", criteria="c", threshold=0.5, size_classes=(5.0, 50.0, math.inf)
    )
    edges = [(1, 2, 10.0), (2, 3, 5.0), (3, 4, 7.0), (5, 6, 3.0)]
    values = {1: 0.8, 2: 0.6, 3: 0.4, 4: 0.9, 5: 1.0, 6: 0.2}
    block_area = dict.fromkeys(range(1, 7), 10.0)
    neighbours: dict[int, list[tuple[int, float]]] = {}
    for source, target, length in edges:
        neighbours.setdefault(source, []).append((target, length))
        neighbours.setdefault(target, []).append((source, length))
    members = {block: value for block, value in values.items() if value > account.threshold}
    expected = patch_account_values(account, values, edges, block_area)
    indexed = patch_account_values_indexed(account, members, neighbours, block_area)
    assert indexed == pytest.approx(expected)


def test_load_patch_accounts_round_trips(tmp_path: Path) -> None:
    """The YAML loader reads the definitions, including the size classes."""
    accounts = load_patch_accounts(_patches(tmp_path / "patches.yaml"))
    assert len(accounts) == 1
    assert accounts[0].name == "patch.harvest"
    assert accounts[0].criteria == "feature.Volume"
    assert accounts[0].size_classes == (5.0, 50.0, math.inf)


def test_patch_model_matches_the_reporting_path(tmp_path: Path) -> None:
    """The incremental patch model agrees with the reporting ledger, cell for cell."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    topology = _topology(tmp_path / "topology.csv")
    patches = _patches(tmp_path / "patches.yaml")
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=2,
            iterations=1,
            seed=1,
            warm_start=True,
            topology_path=str(topology),
            patch_accounts_path=str(patches),
        ),
    )
    candidates = optimizer.candidates()
    schedule = {block: chains[0] for block, chains in candidates.items() if chains}
    evaluator = IncrementalObjective(optimizer, [], (), optimizer.patch_accounts())
    evaluator.reset(schedule)
    model_cells: dict[tuple[int, str], float] = {
        (year, account): value
        for (year, account), value in evaluator.totals.items()
        if account.startswith("patch.")
    }

    # the reporting path: a fresh simulator, the ledger recorded per year
    from ws4.patch.accounts import load_patch_edges_detailed

    accounts = optimizer.patch_accounts()
    edges = load_patch_edges_detailed(topology)
    simulator = Simulator.from_dataset(dataset)
    block_area = simulator.fragments.groupby("block_id")["area_ha"].sum().to_dict()
    ledger = PatchLedger(
        accounts, edges, {int(float(str(k))): float(v) for k, v in block_area.items()}
    )
    frame = pd.DataFrame(
        [
            {"block_id": block, "treatment": treatment, "period": year}
            for block, chain in schedule.items()
            for treatment, year in chain
        ],
        columns=["block_id", "treatment", "period"],
    )
    simulator.fragments["offset"] = simulator.fragments["age"].astype(int)
    for year in range(2):
        simulator.apply_treatments(frame, year)
        ledger.record(year, {"feature.Volume": simulator.block_criteria("feature.Volume")})
        simulator.fragments["offset"] = simulator.fragments["offset"].astype(int) + 1
    records = ledger.frame().to_dict("records")
    ledger_cells: dict[tuple[int, str], float] = {}
    for row in records:
        year = int(float(str(row["year"])))
        for key, value in row.items():
            name = str(key)
            if name.startswith("patch."):
                ledger_cells[(year, name)] = float(str(value))

    keys = set(model_cells) | set(ledger_cells)
    assert keys  # the fixture produces patch cells
    for cell in keys:
        assert model_cells.get(cell, 0.0) == pytest.approx(ledger_cells.get(cell, 0.0), abs=1e-9)


def test_a_gap_is_a_non_member_between_two_components() -> None:
    """is_gap is true only for a non-member whose member-neighbours span two components."""
    account = PatchAccount(name="p", criteria="c", threshold=0.5, size_classes=(2.0, float("inf")))
    neighbours = {1: ((2, 1.0),), 2: ((1, 1.0), (3, 1.0)), 3: ((2, 1.0),)}
    area = {1: 1.0, 2: 1.0, 3: 1.0}
    state = PatchGroupYear([account], 0.5, neighbours, area)
    state.set_value(1, 1.0)
    state.set_value(3, 1.0)
    assert state.is_gap(state.index[2])  # block 2 joins the components of 1 and 3
    state.set_value(2, 1.0)
    assert not state.is_gap(state.index[1])  # a member is never a gap
    state.set_value(3, None)
    assert not state.is_gap(state.index[2])  # only one component left to join


def test_a_cut_block_is_the_one_that_splits_a_patch() -> None:
    """is_cut identifies the interior block of a chain, not its end."""
    account = PatchAccount(name="p", criteria="c", threshold=0.5, size_classes=(2.0, float("inf")))
    neighbours = {1: ((2, 1.0),), 2: ((1, 1.0), (3, 1.0)), 3: ((2, 1.0),)}
    area = {1: 1.0, 2: 1.0, 3: 1.0}
    state = PatchGroupYear([account], 0.5, neighbours, area)
    for block in (1, 2, 3):
        state.set_value(block, 1.0)
    assert state.is_cut(state.index[2])  # removing the middle block splits the chain
    assert not state.is_cut(state.index[1])  # an end block does not
    state.set_value(2, None)
    assert not state.is_cut(state.index[1])  # not a member any more


def test_an_empty_schedule_still_prices_the_inventory_patches(tmp_path: Path) -> None:
    """With no treatments the model prices the inventory patches, not nothing (regression)."""
    from ws4.patch.accounts import load_patch_edges

    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    topology = _topology(tmp_path / "topology.csv")
    patches = _patches(tmp_path / "patches.yaml")
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=1,
            iterations=1,
            seed=1,
            topology_path=str(topology),
            patch_accounts_path=str(patches),
        ),
    )
    account = optimizer.patch_accounts()[0]
    simulator = Simulator.from_dataset(dataset)
    block_area = {
        int(float(str(k))): float(v)
        for k, v in simulator.fragments.groupby("block_id")["area_ha"].sum().to_dict().items()
    }
    expected = {
        f"{account.name}.{key}": value
        for key, value in patch_account_values(
            account,
            simulator.block_criteria("feature.Volume"),
            load_patch_edges(topology),
            block_area,
        ).items()
    }
    assert expected["patch.harvest.TOTAL.frequency"] > 0.0  # an untended member remains

    evaluator = IncrementalObjective(optimizer, [], (), optimizer.patch_accounts())
    evaluator.reset({})
    assert evaluator.patch is not None
    got = {name: value for (year, name), value in evaluator.patch.cell_map().items() if year == 0}
    for key in set(expected) | set(got):
        assert got.get(key, 0.0) == pytest.approx(expected.get(key, 0.0), abs=1e-9)


def test_incremental_patch_model_tracks_moves(tmp_path: Path) -> None:
    """After random moves the incremental patch cells match a freshly built model."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    topology = _topology(tmp_path / "topology.csv")
    patches = _patches(tmp_path / "patches.yaml")
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=3,
            iterations=1,
            seed=1,
            warm_start=True,
            topology_path=str(topology),
            patch_accounts_path=str(patches),
        ),
    )
    candidates = optimizer.candidates()
    schedule: Schedule = {block: chains[0] for block, chains in candidates.items() if chains}
    evaluator = IncrementalObjective(optimizer, [], (), optimizer.patch_accounts())
    evaluator.reset(schedule)
    rng = random.Random(2)
    for _ in range(20):
        operator = optimizer.registry.pick(rng)
        undo = operator.propose_inplace(schedule, rng, candidates)
        if undo is None:
            continue
        changed = list(undo)
        evaluator.delta(changed, schedule)
        evaluator.apply(changed, schedule)
        fresh = PatchModel(optimizer, optimizer.patch_accounts())
        fresh.reset(schedule)
        expected = fresh.cell_map()
        got = {
            (year, account): value
            for (year, account), value in evaluator.totals.items()
            if account.startswith("patch.")
        }
        for cell in set(expected) | set(got):
            assert got.get(cell, 0.0) == pytest.approx(expected.get(cell, 0.0), abs=1e-9)


def test_a_patch_target_is_scored(tmp_path: Path) -> None:
    """A target on a patch account is scored against the model's cells."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    topology = _topology(tmp_path / "topology.csv")
    patches = _patches(tmp_path / "patches.yaml")
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=1,
            iterations=1,
            seed=1,
            warm_start=True,
            topology_path=str(topology),
            patch_accounts_path=str(patches),
        ),
    )
    schedule: Schedule = {1: (("CC", 0),)}
    target = Target("patch.harvest.0_5.frequency", 0, maximum=0.0)
    values = optimizer._full_values(schedule, None, (), ())
    expected = objective(values, [target])
    evaluator = IncrementalObjective(optimizer, [target], (), optimizer.patch_accounts())
    evaluator.reset(schedule)
    assert evaluator.objective == pytest.approx(expected)
