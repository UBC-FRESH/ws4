"""Tests for the sparse float64 GPU effect table.

The table is a cache over the exact CPU block-delta path, so every test compares it with
the same ``_block_deltas`` values the incremental objective uses.  The CUDA tests are
skipped when no device is available; the CPU tests exercise the identical gather and
segmented-sum code on the host.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.gpu_effects import EffectTable, target_cells
from ws4.opt.incremental import IncrementalObjective
from ws4.opt.objective import Target

torch = pytest.importorskip("torch")

if TYPE_CHECKING:
    import torch as torch_type

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
_CELLS: tuple[tuple[int, str], ...] = (
    (0, "product.Volume"),
    (1, "product.Biomass"),
    (2, "feature.Volume"),
)


def _recipe() -> str:
    """Return the synthetic recipe with a second product account."""
    text = (_FIXTURE / "recipe.xml").read_text(encoding="utf-8")
    marker = (
        '      <attribute label="product.Volume">\n'
        '        <curve idref="natural_volume"/>\n'
        "      </attribute>"
    )
    assert marker in text
    replacement = (
        marker
        + "\n"
        + '      <attribute label="product.Biomass">\n'
        + '        <curve idref="managed_volume"/>\n'
        + "      </attribute>"
    )
    return text.replace(marker, replacement)


def _dataset(tmp_path: Path, blocks: int = 64) -> Path:
    """Compile a synthetic dataset with enough blocks for a 64-row LNS batch."""
    recipe = tmp_path / "recipe.xml"
    recipe.write_text(_recipe(), encoding="utf-8")
    fragments = tmp_path / "fragments.csv"
    rows = ["BLOCK,AREA_HA,F_AGE,AU,IFM"]
    rows.extend(
        f"{block},{2.0 + block % 3},{(block * 7) % 80 + 40},1,unmanaged"
        for block in range(1, blocks + 1)
    )
    fragments.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return build_canonical_dataset(recipe, fragments, tmp_path / "compiled")


def _targets() -> list[Target]:
    """Read the feature stock cell and both product accounts."""
    return [
        Target("product.Volume", period=1, period_width=1, minimum=1.0),
        Target("product.Biomass", period=2, period_width=1, minimum=1.0),
        Target("feature.Volume", period=3, period_width=1, minimum=1.0),
    ]


def _optimizer(tmp_path: Path, blocks: int = 64) -> tuple[Optimizer, IncrementalObjective]:
    """Build the fixture optimizer and evaluator."""
    optimizer = Optimizer.from_dataset(
        _dataset(tmp_path, blocks), OptimizeConfig(years=4, iterations=1, seed=1)
    )
    return optimizer, IncrementalObjective(optimizer, _targets())


def _expected(
    deltas: dict[tuple[int, tuple[tuple[str, int], ...]], dict[tuple[int, str], float]],
    new_pairs: list[tuple[int, tuple[tuple[str, int], ...]]],
    old_pairs: list[tuple[int, tuple[tuple[str, int], ...]]],
    cell_index: dict[tuple[int, str], int],
) -> torch_type.Tensor:
    """Return the CPU float64 dense delta of new rows minus old rows."""
    row: torch_type.Tensor = torch.zeros(len(cell_index), dtype=torch.float64)
    for pair in new_pairs:
        for cell, value in deltas[pair].items():
            column = cell_index.get(cell)
            if column is not None:
                row[column] += value
    for pair in old_pairs:
        for cell, value in deltas[pair].items():
            column = cell_index.get(cell)
            if column is not None:
                row[column] -= value
    return row


def _touched(optimizer: Optimizer, evaluator: IncrementalObjective) -> dict[tuple[int, str], int]:
    """Return how often each target cell is nonzero across all candidate rows."""
    candidates = optimizer.candidates()
    pairs = [(block, chain) for block, chains in candidates.items() for chain in chains]
    deltas = optimizer._block_deltas(pairs, evaluator.accounts, evaluator._wanted_feature_offsets)
    touched = dict.fromkeys(target_cells(evaluator), 0)
    for delta in deltas.values():
        for cell, value in delta.items():
            if cell in touched and value != 0.0:
                touched[cell] += 1
    return touched


def test_table_covers_both_products_and_the_feature_stock_cell(tmp_path: Path) -> None:
    """The table has the exact target columns and every one is exercised."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator)
    assert table.cells == _CELLS
    assert table.rows == sum(len(chains) for chains in optimizer.candidates().values()) + 1
    assert table.values.dtype == torch.float64
    touched = _touched(optimizer, evaluator)
    assert all(touched[cell] > 0 for cell in _CELLS)


def test_single_block_delta_matches_the_cpu_delta(tmp_path: Path) -> None:
    """One new row minus one old row is exactly the cached CPU delta."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator)
    candidates = optimizer.candidates()
    blocks = sorted(candidates)
    rng = random.Random(3)
    specs = []
    for _ in range(40):
        new_block = rng.choice(blocks)
        old_block = rng.choice(blocks)
        specs.append(
            (
                new_block,
                rng.choice(candidates[new_block]),
                old_block,
                rng.choice(candidates[old_block] + [()]),
            )
        )
    pairs = [(old_block, old_chain) for _nb, _nc, old_block, old_chain in specs]
    pairs += [(new_block, new_chain) for new_block, new_chain, _ob, _oc in specs]
    deltas = optimizer._block_deltas(pairs, evaluator.accounts, evaluator._wanted_feature_offsets)
    new_ids = torch.tensor(
        [table.row_id(block, chain) for block, chain, _ob, _oc in specs], dtype=torch.int64
    )
    old_ids = torch.tensor(
        [table.row_id(block, chain) for _nb, _nc, block, chain in specs], dtype=torch.int64
    )
    actual = table.move_deltas(new_ids, old_ids)
    cell_index = {cell: column for column, cell in enumerate(table.cells)}
    for index, (new_block, new_chain, old_block, old_chain) in enumerate(specs):
        expected = _expected(deltas, [(new_block, new_chain)], [(old_block, old_chain)], cell_index)
        torch.testing.assert_close(actual[index], expected, rtol=0.0, atol=1e-9)


def test_lns_64_row_delta_matches_the_cpu_segment_sum(tmp_path: Path) -> None:
    """A 64-block LNS batch equals the float64 sum of 128 CPU effect rows."""
    optimizer, evaluator = _optimizer(tmp_path)
    table = EffectTable.build(optimizer, evaluator)
    candidates = optimizer.candidates()
    blocks = sorted(candidates)
    rng = random.Random(5)
    moves = 8
    specs: list[
        tuple[
            list[tuple[int, tuple[tuple[str, int], ...]]],
            list[tuple[int, tuple[tuple[str, int], ...]]],
        ]
    ] = []
    for _ in range(moves):
        chosen = rng.sample(blocks, 64)
        specs.append(
            (
                [(block, rng.choice(candidates[block])) for block in chosen],
                [
                    (block, () if rng.random() < 0.25 else rng.choice(candidates[block] + [()]))
                    for block in chosen
                ],
            )
        )
    pairs = [pair for new, old in specs for pair in (*new, *old)]
    deltas = optimizer._block_deltas(pairs, evaluator.accounts, evaluator._wanted_feature_offsets)
    new_ids = torch.tensor(
        [[table.row_id(block, chain) for block, chain in new] for new, _old in specs],
        dtype=torch.int64,
    )
    old_ids = torch.tensor(
        [[table.row_id(block, chain) for block, chain in old] for _new, old in specs],
        dtype=torch.int64,
    )
    actual = table.lns_deltas(new_ids, old_ids)
    cell_index = {cell: column for column, cell in enumerate(table.cells)}
    expected = torch.stack([_expected(deltas, new, old, cell_index) for new, old in specs])
    torch.testing.assert_close(actual, expected, rtol=0.0, atol=1e-9)
    feature = cell_index[(2, "feature.Volume")]
    conifer = cell_index[(0, "product.Volume")]
    deciduous = cell_index[(1, "product.Biomass")]
    assert bool((expected[:, feature] != 0.0).any())
    assert bool((expected[:, conifer] != 0.0).any())
    assert bool((expected[:, deciduous] != 0.0).any())


def test_seed_chains_outside_the_candidate_list_can_be_added(tmp_path: Path) -> None:
    """An extra seed chain keeps its exact row even when it is not a candidate."""
    optimizer, evaluator = _optimizer(tmp_path, blocks=4)
    candidates = optimizer.candidates()
    seed_chain = (("CC", 0), ("CC", 2))
    assert seed_chain not in candidates[1]
    table = EffectTable.build(
        optimizer,
        evaluator,
        blocks=[1],
        extra_pairs=[(1, seed_chain)],
        candidates=candidates,
    )
    row = table.row_id(1, seed_chain)
    assert row > 0
    delta = optimizer._block_deltas(
        [(1, seed_chain)], evaluator.accounts, evaluator._wanted_feature_offsets
    )[(1, seed_chain)]
    cell_index = {cell: column for column, cell in enumerate(table.cells)}
    expected = torch.zeros(table.columns, dtype=torch.float64)
    for cell, value in delta.items():
        column = cell_index.get(cell)
        if column is not None:
            expected[column] = value
    assert torch.equal(table.gather(torch.tensor([row], dtype=torch.int64))[0], expected)


def test_segmented_delta_respects_signs_and_duplicate_segments(tmp_path: Path) -> None:
    """The generic segmented sum adds and subtracts rows in the requested segment."""
    optimizer, evaluator = _optimizer(tmp_path, blocks=4)
    table = EffectTable.build(optimizer, evaluator)
    new_id = table.row_id(1, optimizer.candidates()[1][0])
    old_id = table.row_id(2, optimizer.candidates()[2][0])
    actual = table.segmented_delta(
        torch.tensor([new_id, old_id, new_id], dtype=torch.int64),
        torch.tensor([0, 0, 1], dtype=torch.int64),
        torch.tensor([1.0, -1.0, 1.0], dtype=torch.float64),
    )
    rows = table.gather(torch.tensor([new_id, old_id], dtype=torch.int64))
    expected = torch.stack((rows[0] - rows[1], rows[0]))
    assert torch.equal(actual, expected)


def test_empty_chain_maps_to_the_zero_row(tmp_path: Path) -> None:
    """The reserved row zero is all zeros and ``row_id`` maps an empty chain to it."""
    optimizer, evaluator = _optimizer(tmp_path, blocks=4)
    table = EffectTable.build(optimizer, evaluator)
    assert table.row_id(1, ()) == 0
    assert torch.count_nonzero(table.gather(torch.tensor([0], dtype=torch.int64))) == 0


def test_invalid_row_and_segment_inputs_raise(tmp_path: Path) -> None:
    """Bad ids and mismatched shapes fail loudly instead of reading the wrong row."""
    optimizer, evaluator = _optimizer(tmp_path, blocks=4)
    table = EffectTable.build(optimizer, evaluator)
    with pytest.raises(IndexError):
        table.gather(torch.tensor([table.rows], dtype=torch.int64))
    with pytest.raises(ValueError, match="same shape"):
        table.move_deltas(
            torch.tensor([1, 2], dtype=torch.int64), torch.tensor([1], dtype=torch.int64)
        )
    with pytest.raises(ValueError, match="must not be negative"):
        table.segmented_delta(
            torch.tensor([1, 2], dtype=torch.int64), torch.tensor([-1, 0], dtype=torch.int64)
        )
    with pytest.raises(ValueError, match="two-dimensional"):
        table.lns_deltas(torch.tensor([1], dtype=torch.int64), torch.tensor([1], dtype=torch.int64))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is not available")
def test_cuda_table_matches_the_cpu_table(tmp_path: Path) -> None:
    """Uploading the sparse table does not change a single float64 delta."""
    optimizer, evaluator = _optimizer(tmp_path)
    cpu = EffectTable.build(optimizer, evaluator)
    cuda = cpu.to("cuda")
    candidates = optimizer.candidates()
    blocks = sorted(candidates)
    rng = random.Random(9)
    specs = [
        [(block, rng.choice(candidates[block])) for block in rng.sample(blocks, 64)]
        for _ in range(4)
    ]
    ids = torch.tensor(
        [[cpu.row_id(block, chain) for block, chain in spec] for spec in specs], dtype=torch.int64
    )
    expected = cpu.lns_deltas(ids, torch.zeros_like(ids))
    actual = cuda.lns_deltas(ids.to("cuda"), torch.zeros_like(ids).to("cuda")).cpu()
    assert torch.equal(actual, expected)
