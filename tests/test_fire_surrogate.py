"""Tests for the deterministic fire-surrogate corpus."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from ws4.fire.fuel import FireFuelError
from ws4.fire.surrogate import (
    CORPUS_SCHEMA_VERSION,
    SurrogateCorpus,
    generate_corpus,
    load_corpus,
    save_corpus,
)


def _corpus() -> SurrogateCorpus:
    """Return a small deterministic corpus."""
    return generate_corpus(count=4, seed=7, rows=16, cols=16, duration_min=20.0)


def test_generate_corpus_is_deterministic() -> None:
    """The same seed reproduces inputs and targets."""
    first = _corpus()
    second = _corpus()

    assert first.manifest() == second.manifest()
    for left, right in zip(first.samples, second.samples, strict=True):
        np.testing.assert_array_equal(left.fuel_index, right.fuel_index)
        np.testing.assert_array_equal(left.arrival_time_min, right.arrival_time_min)
        np.testing.assert_array_equal(left.burned_mask, right.burned_mask)


def test_corpus_manifest_and_split() -> None:
    """The manifest records provenance and a disjoint split."""
    corpus = _corpus()
    manifest = corpus.manifest()

    assert manifest["schema_version"] == CORPUS_SCHEMA_VERSION
    assert manifest["kernel_version"]
    assert manifest["sample_count"] == 4
    assert manifest["train_count"] == 3
    assert manifest["validation_count"] == 1
    assert isinstance(manifest["fuel_order"], list)
    assert {sample.split for sample in corpus.samples} == {"train", "validation"}
    assert all(sample.burned_count >= 1 for sample in corpus.samples)
    assert all(sample.burnable_count >= 1 for sample in corpus.samples)


def test_corpus_round_trips(tmp_path: Path) -> None:
    """The saved arrays and manifest load back into the same corpus."""
    corpus = _corpus()
    manifest_path = save_corpus(corpus, tmp_path)

    loaded = load_corpus(tmp_path)

    assert manifest_path.is_file()
    assert loaded.manifest() == corpus.manifest()
    for original, restored in zip(corpus.samples, loaded.samples, strict=True):
        np.testing.assert_array_equal(original.fuel_index, restored.fuel_index)
        np.testing.assert_array_equal(original.arrival_time_min, restored.arrival_time_min)
        np.testing.assert_array_equal(original.burned_mask, restored.burned_mask)


def test_corpus_rejects_too_few_samples() -> None:
    """A corpus needs a train/validation split, so one sample is invalid."""
    with pytest.raises(FireFuelError, match="at least 2"):
        generate_corpus(count=1, seed=1, rows=8, cols=8)


def test_sample_metadata_and_invalid_cases() -> None:
    """Sample metadata is complete and invalid samples are rejected."""
    from dataclasses import replace

    sample = _corpus().samples[0]
    metadata = sample.to_metadata()

    assert metadata["sample_id"] == "sample_0000"
    assert metadata["split"] == "validation"
    assert metadata["burned_cells"] == sample.burned_count
    assert metadata["burnable_cells"] == sample.burnable_count
    with pytest.raises(FireFuelError, match="split"):
        replace(sample, split="holdout")
    with pytest.raises(FireFuelError, match="burnable"):
        replace(sample, fuel_index=np.zeros(sample.shape, dtype=np.uint8))
    with pytest.raises(FireFuelError, match="shape"):
        replace(sample, burned_mask=np.zeros((1, 1), dtype=bool))


def test_corpus_rejects_duplicate_ids_and_bad_geometry() -> None:
    """Corpus construction rejects duplicate ids and mismatched grids."""
    corpus = _corpus()
    with pytest.raises(FireFuelError, match="unique"):
        SurrogateCorpus(
            seed=corpus.seed,
            rows=corpus.rows,
            cols=corpus.cols,
            cell_size_m=corpus.cell_size_m,
            duration_min=corpus.duration_min,
            samples=(corpus.samples[0], corpus.samples[0]),
        )
    with pytest.raises(FireFuelError, match="2 x 2"):
        SurrogateCorpus(
            seed=1,
            rows=1,
            cols=1,
            cell_size_m=100.0,
            duration_min=10.0,
            samples=(corpus.samples[0],),
        )


def test_load_corpus_reports_missing_files(tmp_path: Path) -> None:
    """The loader names a missing manifest or array file."""
    with pytest.raises(FireFuelError, match="manifest"):
        load_corpus(tmp_path)
    (tmp_path / "manifest.json").write_text('{"samples": []}', encoding="utf-8")
    with pytest.raises(FireFuelError, match="arrays"):
        load_corpus(tmp_path)
