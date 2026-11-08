"""Tests for the factorized option-effect basis."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.opt.factorized_effects import (
    FactorizedAccountSet,
    FactorizedEffectArrays,
    FactorizedEffectBasis,
    PaddedFactorizedEvents,
    PaddedFactorizedTensors,
    build_feature_value_table,
    build_product_value_table,
)

from test_gpu_ga import _optimizer

torch = pytest.importorskip("torch")


def test_factorized_option_matches_block_chain(tmp_path: Path) -> None:
    """Feature and product period values match one block's exact cells."""
    optimizer, _evaluator = _optimizer(tmp_path)
    simulator = optimizer.simulator()
    candidates = optimizer.candidates()
    block = next(iter(candidates))
    chain = candidates[block][0]
    basis = FactorizedEffectBasis.build(optimizer, {block: [chain]}, years=4)
    cells = simulator.block_chain(block, chain, 4)
    feature = basis.feature_period_values("feature.Volume", {block: chain}, period_width=1)
    product = basis.product_period_values("product.Volume", {block: chain}, period_width=1)
    for period, offset in enumerate(range(4), start=1):
        assert feature[period] == pytest.approx(cells.get((offset, "feature.Volume"), 0.0))
        assert product[period] == pytest.approx(cells.get((offset, "product.Volume"), 0.0))


def test_factorized_full_schedule_matches_target_cells(tmp_path: Path) -> None:
    """Full-schedule factorized values match the target cells, not every offset."""
    optimizer, evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    schedule = {block: chains[0] for block, chains in candidates.items()}
    basis = FactorizedEffectBasis.build(optimizer, candidates, years=4)
    evaluator.reset(schedule)
    for target in evaluator.targets:
        end = target.end_offset()
        period = end // max(1, target.period_width) + 1
        if target.account.startswith("product."):
            value = basis.product_period_values(
                target.account, schedule, period_width=target.period_width
            )[period]
        else:
            value = basis.feature_period_values(
                target.account, schedule, period_width=target.period_width
            )[period]
        assert value == pytest.approx(evaluator.totals.get((end, target.account), 0.0))


def test_factorized_arrays_match_option_count(tmp_path: Path) -> None:
    """The flat descriptor arrays cover every candidate option."""
    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    assert arrays.option_count == sum(len(chains) for chains in candidates.values())
    assert arrays.segment_offsets[-1] == len(arrays.segment_start)
    assert arrays.event_offsets[-1] == len(arrays.event_offset)
    assert arrays.nbytes() > 0


def test_parallel_factorized_arrays_match_sequential(tmp_path: Path) -> None:
    """Forked descriptor chunks merge to the same flat arrays."""
    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    sequential = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    parallel = FactorizedEffectArrays.build_parallel(
        optimizer,
        candidates,
        years=4,
        workers=2,
        chunk_blocks=8,
    )
    assert parallel.option_count == sequential.option_count
    assert parallel.labels == sequential.labels
    for name in (
        "chain_offsets",
        "segment_offsets",
        "segment_start",
        "segment_track",
        "segment_age",
        "segment_area",
        "event_offsets",
        "event_offset",
        "event_track",
        "event_age",
        "event_label",
        "event_area",
    ):
        assert (getattr(parallel, name) == getattr(sequential, name)).all()


def test_factorized_array_evaluator_matches_target_cells(tmp_path: Path) -> None:
    """Flat array evaluation matches exact target cells on a full schedule."""
    optimizer, evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    schedule = {block: chains[0] for block, chains in candidates.items()}
    options = dict.fromkeys(candidates, 0)
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    evaluator.reset(schedule)
    simulator = optimizer.simulator()
    for target in evaluator.targets:
        end = target.end_offset()
        period = end // max(1, target.period_width) + 1
        if target.account.startswith("product."):
            value = arrays.product_period_values(
                target.account,
                options,
                period_width=target.period_width,
                years=4,
                simulator=simulator,
            )[period]
        else:
            value = arrays.feature_period_values(
                target.account,
                options,
                period_width=target.period_width,
                years=4,
                simulator=simulator,
            )[period]
        assert value == pytest.approx(evaluator.totals.get((end, target.account), 0.0))


def test_factorized_arrays_pack_to_device_tensors(tmp_path: Path) -> None:
    """The flat descriptors expose the expected device tensor pack."""
    optimizer, _evaluator = _optimizer(tmp_path)
    arrays = FactorizedEffectArrays.build(optimizer, optimizer.candidates(), years=4)
    tensors = arrays.to_tensors()
    assert tensors["blocks"].shape == arrays.blocks.shape
    assert tensors["segment_offsets"].shape == arrays.segment_offsets.shape
    assert (
        tensors["event_labels" if "event_labels" in tensors else "event_label"].shape
        == arrays.event_label.shape
    )


def test_padded_feature_batch_matches_array_evaluator(tmp_path: Path) -> None:
    """The padded device layout reproduces the flat feature evaluator."""
    import numpy as np
    import torch

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    padded = PaddedFactorizedTensors.from_arrays(arrays)
    simulator = optimizer.simulator()
    tracks = [int(track) for track in simulator._track_features]
    max_age = max(int(arrays.segment_age.max()) + 4, 4)
    feature_values = np.zeros((max(tracks) + 1, max_age), dtype=np.float64)
    for track in tracks:
        for curve, label in simulator._track_features[track]:
            if label == "feature.Volume":
                feature_values[track] = [
                    simulator._curve_value(curve, age) for age in range(max_age)
                ]
    genomes = torch.zeros((1, len(candidates)), dtype=torch.int64)
    device_values = padded.feature_batch(
        genomes,
        torch.as_tensor(feature_values),
        years=4,
        period_width=1,
    )
    options = dict.fromkeys(candidates, 0)
    expected = arrays.feature_period_values(
        "feature.Volume", options, period_width=1, years=4, simulator=simulator
    )
    for period in range(1, 5):
        assert float(device_values[0, period - 1]) == pytest.approx(expected[period])


def test_padded_feature_batch_matches_random_genomes(tmp_path: Path) -> None:
    """Batched random genomes match the exact array evaluator per block."""
    import numpy as np
    import torch

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    padded = PaddedFactorizedTensors.from_arrays(arrays)
    simulator = optimizer.simulator()
    tracks = [int(track) for track in simulator._track_features]
    max_age = max(int(arrays.segment_age.max()) + 4, 4)
    feature_values = np.zeros((max(tracks) + 1, max_age), dtype=np.float64)
    for track in tracks:
        for curve, label in simulator._track_features[track]:
            if label == "feature.Volume":
                feature_values[track] = [
                    simulator._curve_value(curve, age) for age in range(max_age)
                ]
    rng = np.random.default_rng(5)
    genomes = torch.as_tensor(rng.integers(0, 4, size=(5, len(candidates))), dtype=torch.int64)
    device_values = padded.feature_batch(
        genomes,
        torch.as_tensor(feature_values),
        years=4,
        period_width=1,
    )
    for genome_row in range(genomes.shape[0]):
        options = {block: int(genomes[genome_row, index]) for index, block in enumerate(candidates)}
        expected = arrays.feature_period_values(
            "feature.Volume", options, period_width=1, years=4, simulator=simulator
        )
        for period in range(1, 5):
            assert float(device_values[genome_row, period - 1]) == pytest.approx(expected[period])


def test_padded_product_batch_matches_arrays(tmp_path: Path) -> None:
    """Padded event tensors reproduce the flat product evaluator."""
    import numpy as np
    import torch

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    events = PaddedFactorizedEvents.from_arrays(arrays)
    simulator = optimizer.simulator()
    labels = sorted(
        {str(label) for curves in simulator._products_by_key.values() for _, label in curves}
    )
    account = labels[0]
    table = build_product_value_table(arrays, simulator, account)
    rng = np.random.default_rng(11)
    genomes = torch.as_tensor(rng.integers(0, 2, size=(4, len(candidates))), dtype=torch.int64)
    device_values = events.product_batch(
        genomes,
        torch.as_tensor(table),
        years=4,
        period_width=1,
    )
    for genome_row in range(genomes.shape[0]):
        options = {block: int(genomes[genome_row, index]) for index, block in enumerate(candidates)}
        expected = arrays.product_period_values(
            account, options, period_width=1, years=4, simulator=simulator
        )
        for period in range(1, 5):
            assert float(device_values[genome_row, period - 1]) == pytest.approx(expected[period])


def test_feature_table_helper_matches_flat_feature_values(tmp_path: Path) -> None:
    """The feature lookup helper carries the exact curve values."""
    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    simulator = optimizer.simulator()
    table = build_feature_value_table(arrays, simulator, "feature.Volume", years=4)
    for track in range(table.shape[0]):
        for age in range(table.shape[1]):
            expected = next(
                (
                    simulator._curve_value(curve, age)
                    for curve, label in simulator._track_features.get(track, ())
                    if label == "feature.Volume"
                ),
                0.0,
            )
            assert float(table[track, age]) == pytest.approx(expected)


def test_padded_offsets_match_period_width_one(tmp_path: Path) -> None:
    """Feature and product offset reads match the one-year exact evaluator."""
    import numpy as np
    import torch

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    segments = PaddedFactorizedTensors.from_arrays(arrays)
    events = PaddedFactorizedEvents.from_arrays(arrays)
    simulator = optimizer.simulator()
    feature_table = build_feature_value_table(arrays, simulator, "feature.Volume", years=4)
    product_account = sorted(
        {str(label) for curves in simulator._products_by_key.values() for _, label in curves}
    )[0]
    product_table = build_product_value_table(arrays, simulator, product_account)
    rng = np.random.default_rng(17)
    genomes = torch.as_tensor(rng.integers(0, 2, size=(2, len(candidates))), dtype=torch.int64)
    offsets = [0, 1, 2, 3]
    feature_values = segments.feature_offsets(genomes, torch.as_tensor(feature_table), offsets)
    product_values = events.product_offsets(
        genomes, torch.as_tensor(product_table), offsets, years=4
    )
    for genome_row in range(genomes.shape[0]):
        options = {block: int(genomes[genome_row, index]) for index, block in enumerate(candidates)}
        feature_expected = arrays.feature_period_values(
            "feature.Volume", options, period_width=1, years=4, simulator=simulator
        )
        product_expected = arrays.product_period_values(
            product_account, options, period_width=1, years=4, simulator=simulator
        )
        for column, offset in enumerate(offsets):
            assert float(feature_values[genome_row, column]) == pytest.approx(
                feature_expected[offset + 1]
            )
            assert float(product_values[genome_row, column]) == pytest.approx(
                product_expected[offset + 1]
            )


def test_factorized_account_set_prices_feature_and_product_cells(tmp_path: Path) -> None:
    """The account set fills requested target cells without an account matrix."""
    import numpy as np
    import torch

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    simulator = optimizer.simulator()
    accounts = FactorizedAccountSet.from_arrays(arrays, simulator, years=4)
    product_account = sorted(
        {str(label) for curves in simulator._products_by_key.values() for _, label in curves}
    )[0]
    cells = [(1, "feature.Volume"), (2, product_account), (3, "feature.Volume")]
    rng = np.random.default_rng(19)
    genomes = torch.as_tensor(rng.integers(0, 2, size=(3, len(candidates))), dtype=torch.int64)
    totals = accounts.totals(genomes, cells)
    for genome_row in range(genomes.shape[0]):
        options = {block: int(genomes[genome_row, index]) for index, block in enumerate(candidates)}
        feature_expected = arrays.feature_period_values(
            "feature.Volume", options, period_width=1, years=4, simulator=simulator
        )
        product_expected = arrays.product_period_values(
            product_account, options, period_width=1, years=4, simulator=simulator
        )
        assert float(totals[genome_row, 0]) == pytest.approx(feature_expected[2])
        assert float(totals[genome_row, 1]) == pytest.approx(product_expected[3])
        assert float(totals[genome_row, 2]) == pytest.approx(feature_expected[4])


def test_population_target_switch_uses_factorized_cells(tmp_path: Path) -> None:
    """A new target account is priced without extending the effect table."""
    from ws4.opt.gpu_effects import EffectTable
    from ws4.opt.gpu_ga import GenomePopulation
    from ws4.opt.incremental import IncrementalObjective
    from ws4.opt.objective import Target

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    accounts = FactorizedAccountSet.from_arrays(arrays, optimizer.simulator(), years=4)
    initial_targets = [Target("product.Volume", period=4, period_width=1, minimum=1.0)]
    initial = IncrementalObjective(optimizer, initial_targets)
    table = EffectTable.build(optimizer, initial, candidates=candidates)
    seed = {block: chains[0] for block, chains in candidates.items() if chains}
    population = GenomePopulation(
        optimizer,
        initial,
        table,
        population=8,
        seed_schedule=seed,
        candidates=candidates,
        factorized=accounts,
    )
    targets = [Target("feature.Volume", period=2, period_width=1, minimum=500.0)]
    cell_count = len(population.table.cells)
    population.update_targets(targets)
    assert len(population.table.cells) == cell_count
    assert population._extra_cells == ((1, "feature.Volume"),)
    scores = population.evaluate()
    for index in range(population.population):
        exact = IncrementalObjective(optimizer, targets)
        exact.reset(population.schedule(population.genomes[index]))
        assert float(scores[index]) == pytest.approx(exact.objective)


def test_watcher_display_uses_factorized_cells_without_table_extension(
    tmp_path: Path,
) -> None:
    """A watched feature account is read from factorized cells, not the table."""
    from io import StringIO

    from rich.console import Console
    from ws4.opt.gpu_effects import EffectTable
    from ws4.opt.gpu_ga import GenomePopulation
    from ws4.opt.gpu_watch import run_gpu_watch
    from ws4.opt.incremental import IncrementalObjective
    from ws4.opt.objective import Target

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    accounts = FactorizedAccountSet.from_arrays(arrays, optimizer.simulator(), years=4)
    targets = [Target("product.Volume", period=1, period_width=1, minimum=1.0)]
    evaluator = IncrementalObjective(optimizer, targets)
    table = EffectTable.build(optimizer, evaluator, candidates=candidates)
    seed = {block: chains[0] for block, chains in candidates.items() if chains}
    population = GenomePopulation(
        optimizer,
        evaluator,
        table,
        population=8,
        seed_schedule=seed,
        candidates=candidates,
        factorized=accounts,
    )
    cells = len(population.table.cells)
    stream = StringIO()
    summary = run_gpu_watch(
        population,
        targets,
        ("feature.Volume",),
        generations=1,
        period_width=1,
        plain=True,
        console=Console(file=stream, width=120),
    )
    assert summary["objective"] < float("inf")
    assert len(population.table.cells) == cells
    assert "feature.Volume" in stream.getvalue()


def test_factorized_account_cache_round_trips(tmp_path: Path) -> None:
    """A persisted padded cache reproduces the built account values."""
    import numpy as np
    import torch

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    simulator = optimizer.simulator()
    accounts = FactorizedAccountSet.from_arrays(arrays, simulator, years=4)
    cache = accounts.save_cache(tmp_path / "factorized.padded.pt")
    loaded = FactorizedAccountSet.load_cache(cache, simulator, device="cpu")
    rng = np.random.default_rng(29)
    genomes = torch.as_tensor(rng.integers(0, 2, size=(3, len(candidates))), dtype=torch.int64)
    cells = [(1, "feature.Volume"), (2, "product.Volume")]
    expected = accounts.totals(genomes, cells)
    actual = loaded.totals(genomes, cells)
    assert torch.equal(actual, expected)


def test_factorized_vector_totals_match_padded_totals(tmp_path: Path) -> None:
    """Cached option-value vectors match the padded account evaluator."""
    import numpy as np
    import torch

    optimizer, _evaluator = _optimizer(tmp_path)
    candidates = optimizer.candidates()
    arrays = FactorizedEffectArrays.build(optimizer, candidates, years=4)
    accounts = FactorizedAccountSet.from_arrays(arrays, optimizer.simulator(), years=4)
    product_account = sorted(
        {
            str(label)
            for curves in optimizer.simulator()._products_by_key.values()
            for _, label in curves
        }
    )[0]
    cells = [(1, "feature.Volume"), (2, product_account)]
    rng = np.random.default_rng(31)
    genomes = torch.as_tensor(rng.integers(0, 2, size=(3, len(candidates))), dtype=torch.int64)
    padded = accounts.totals(genomes, cells)
    vectors = accounts.totals(genomes, cells, vectors=True)
    assert torch.allclose(vectors, padded, rtol=1e-10, atol=1e-8)
    assert accounts.option_values("feature.Volume", 1).shape == (arrays.option_count,)
    assert accounts.option_values(product_account, 2).shape == (arrays.option_count,)
