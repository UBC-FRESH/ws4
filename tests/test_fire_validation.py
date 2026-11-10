"""Tests for the published fire-model validation registry."""

from __future__ import annotations

import pytest
from ws4.fire.fuel import FireFuelError
from ws4.fire.validation import (
    BENCHMARKS,
    MetricDirection,
    PublishedBenchmark,
    ValidationTier,
    benchmarks_for,
    classify_against_published,
    single_fire_context,
)


def test_registry_entries_are_complete_and_sourced() -> None:
    """Every benchmark has a tier, source, and stated basis."""
    assert BENCHMARKS
    for benchmark in BENCHMARKS:
        assert benchmark.source
        assert benchmark.basis
        assert isinstance(benchmark.tier, ValidationTier)
        assert isinstance(benchmark.direction, MetricDirection)
        assert benchmark.high >= benchmark.low


def test_benchmark_position_handles_boundaries() -> None:
    """Intervals are inclusive and classify below/within/above."""
    benchmark = benchmarks_for(ValidationTier.EVENT, "jaccard")[0]

    assert benchmark.position(benchmark.low - 0.01) == "below"
    assert benchmark.position(benchmark.low) == "within"
    assert benchmark.position(benchmark.high) == "within"
    assert benchmark.position(benchmark.high + 0.01) == "above"


def test_published_classification_uses_the_tier() -> None:
    """Event and risk metrics use their own published envelopes."""
    assert classify_against_published(ValidationTier.EVENT, "jaccard", 0.18) == "within"
    assert classify_against_published(ValidationTier.EVENT, "jaccard", 0.05) == "below"
    assert classify_against_published(ValidationTier.EVENT, "jaccard", 0.40) == "above"
    assert classify_against_published(ValidationTier.RISK, "top_bp_capture", 0.65) == "within"
    assert (
        classify_against_published(ValidationTier.TREE, "stand_mortality_abs_error", 0.15)
        == "within"
    )


def test_missing_benchmark_and_bad_interval_fail() -> None:
    """Unknown metrics and inverted intervals are rejected."""
    with pytest.raises(FireFuelError, match="no benchmark"):
        classify_against_published(ValidationTier.DECISION, "nope", 1.0)
    with pytest.raises(FireFuelError, match="at least low"):
        PublishedBenchmark(
            name="bad",
            metric="x",
            tier=ValidationTier.EVENT,
            low=1.0,
            high=0.5,
            direction=MetricDirection.HIGHER,
            unit="x",
            source="test",
            basis="test",
        )


def test_single_fire_policy_is_explicit() -> None:
    """The registry states that one fire is context, not a universal gate."""
    assert "single observed fire" in single_fire_context()
    assert "not a universal" in single_fire_context()
