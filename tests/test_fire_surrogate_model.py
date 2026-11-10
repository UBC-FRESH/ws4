"""Tests for the compact NumPy fire surrogate."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from ws4.fire.fuel import FireFuelError
from ws4.fire.surrogate import SurrogateCorpus, generate_corpus
from ws4.fire.surrogate_model import FEATURE_NAMES, SurrogateModel, sample_features


def _corpus() -> SurrogateCorpus:
    """Return a small deterministic corpus."""
    return generate_corpus(count=5, seed=11, rows=12, cols=12, duration_min=20.0)


def test_feature_matrix_shape_and_finite() -> None:
    """The per-cell feature matrix matches the declared feature names."""
    corpus = _corpus()
    sample = corpus.samples[1]
    features = sample_features(sample)

    assert features.shape == (12 * 12, len(FEATURE_NAMES))
    assert np.isfinite(features).all()


def test_model_fit_predict_and_round_trip(tmp_path: Path) -> None:
    """The model trains, predicts a probability grid, and reloads identically."""
    corpus = _corpus()
    model = SurrogateModel.fit(corpus, hidden_units=8, epochs=20, seed=3)
    sample = corpus.samples[1]
    probability = model.predict_proba(sample)
    mask = model.predict_mask(sample)

    assert probability.shape == sample.shape
    assert np.all((probability >= 0.0) & (probability <= 1.0))
    assert mask.dtype == bool
    model.save(tmp_path)
    loaded = SurrogateModel.load(tmp_path)
    np.testing.assert_allclose(probability, loaded.predict_proba(sample))
    parameters = loaded.to_dict()["parameters"]
    assert isinstance(parameters, int)
    assert parameters > 0


def test_training_is_deterministic() -> None:
    """The same corpus and seed reproduce the weights and losses."""
    corpus = _corpus()
    first = SurrogateModel.fit(corpus, hidden_units=8, epochs=10, seed=5)
    second = SurrogateModel.fit(corpus, hidden_units=8, epochs=10, seed=5)

    np.testing.assert_allclose(first.w1, second.w1)
    np.testing.assert_allclose(first.w2, second.w2)
    assert first.train_loss == pytest.approx(second.train_loss)
    assert first.validation_loss == pytest.approx(second.validation_loss)


def test_model_rejects_bad_configuration() -> None:
    """Invalid architecture sizes and thresholds are rejected."""
    corpus = _corpus()
    with pytest.raises(FireFuelError, match="positive"):
        SurrogateModel.fit(corpus, hidden_units=0)
    model = SurrogateModel.fit(corpus, hidden_units=4, epochs=2, seed=1)
    with pytest.raises(FireFuelError, match="threshold"):
        model.predict_mask(corpus.samples[1], threshold=1.5)
