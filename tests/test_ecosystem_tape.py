"""Tests for the counter-based random tape and common random numbers."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from ws4.ecosystem import DrawKey, RandomTape, TapeError


def key(
    process_id: str = "fire",
    spatial_unit_id: int = 1,
    year: int = 0,
    draw_index: int = 0,
) -> DrawKey:
    """Build one valid draw key."""
    return DrawKey(process_id, spatial_unit_id, year, draw_index)


def test_same_key_is_stable() -> None:
    tape = RandomTape(42)

    assert tape.random(key()) == tape.random(key())


def test_a_pinned_draw_is_stable() -> None:
    assert RandomTape(42).random(key()) == pytest.approx(0.2502356771450378, abs=1e-15)


def test_draw_order_does_not_matter() -> None:
    first = key("fire", 1, 0, 0)
    second = key("fire", 2, 0, 0)
    forward = RandomTape(7)
    backward = RandomTape(7)

    assert forward.random(first) == backward.random(first)
    assert forward.random(second) == backward.random(second)


def test_common_random_numbers_across_tapes() -> None:
    left = RandomTape(99)
    right = RandomTape(99)

    for index in range(20):
        assert left.random(key(draw_index=index)) == right.random(key(draw_index=index))


def test_different_seeds_differ() -> None:
    left = RandomTape(1)
    right = RandomTape(2)

    assert left.random(key()) != right.random(key())


def test_vector_draws_are_deterministic_and_shaped() -> None:
    tape = RandomTape(5)

    flat = tape.random(key(), size=5)
    matrix = tape.random(key(), size=(2, 3))

    assert isinstance(flat, np.ndarray)
    assert isinstance(matrix, np.ndarray)
    assert flat.shape == (5,)
    assert matrix.shape == (2, 3)
    assert np.array_equal(flat, tape.random(key(), size=5))


def test_uniform_respects_its_bounds() -> None:
    draws = RandomTape(3).uniform(key(), 2.0, 5.0, size=2000)

    assert isinstance(draws, np.ndarray)
    assert float(draws.min()) >= 2.0
    assert float(draws.max()) < 5.0
    assert float(draws.mean()) == pytest.approx(3.5, abs=0.1)


def test_integers_respect_their_bounds() -> None:
    draws = RandomTape(3).integers(key(), 1, 4, size=2000)

    assert isinstance(draws, np.ndarray)
    assert {int(value) for value in draws} == {1, 2, 3}


def test_normal_is_reproducible() -> None:
    tape = RandomTape(11)
    first = tape.normal(key(), size=10)
    second = tape.normal(key(), size=10)

    assert isinstance(first, np.ndarray)
    assert isinstance(second, np.ndarray)
    assert np.array_equal(first, second)


def test_exponential_mean_is_the_configured_scale() -> None:
    draws = RandomTape(13).exponential(key(), 2.0, size=10000)

    assert isinstance(draws, np.ndarray)
    assert float(draws.mean()) == pytest.approx(2.0, abs=0.15)


def test_poisson_mean_is_the_configured_rate() -> None:
    draws = RandomTape(17).poisson(key(), 3.0, size=10000)

    assert isinstance(draws, np.ndarray)
    assert float(draws.mean()) == pytest.approx(3.0, abs=0.1)


def test_bernoulli_frequency_is_the_configured_probability() -> None:
    draws = RandomTape(19).bernoulli(key(), 0.3, size=10000)

    assert isinstance(draws, np.ndarray)
    assert float(np.asarray(draws, dtype=float).mean()) == pytest.approx(0.3, abs=0.03)


def test_bernoulli_extremes_are_certain() -> None:
    tape = RandomTape(23)

    assert not bool(tape.bernoulli(key(), 0.0))
    assert bool(tape.bernoulli(key(), 1.0))


def test_fingerprint_changes_with_the_seed() -> None:
    assert RandomTape(1).fingerprint != RandomTape(2).fingerprint
    assert RandomTape(1).fingerprint == RandomTape(1).fingerprint


@pytest.mark.parametrize("seed", [-1, -100])
def test_negative_seed_is_rejected(seed: int) -> None:
    with pytest.raises(TapeError, match="scenario_seed must be non-negative"):
        RandomTape(seed)


def test_unknown_algorithm_is_rejected() -> None:
    with pytest.raises(TapeError, match="algorithm must be"):
        RandomTape(1, "mersenne")


@pytest.mark.parametrize(
    "bad_key",
    [
        ("", 1, 0, 0),
        ("fire", -1, 0, 0),
        ("fire", 0, -1, 0),
        ("fire", 0, 0, -1),
        ("fire", 0, 0, 1 << 64),
    ],
)
def test_invalid_keys_are_rejected(bad_key: tuple[str, int, int, int]) -> None:
    with pytest.raises(TapeError):
        DrawKey(*bad_key)


def test_uniform_rejects_an_empty_interval() -> None:
    with pytest.raises(TapeError, match="high must be greater than low"):
        RandomTape(1).uniform(key(), 5.0, 5.0)


def test_integers_reject_an_empty_interval() -> None:
    with pytest.raises(TapeError, match="high must be greater than low"):
        RandomTape(1).integers(key(), 5, 5)


def test_normal_rejects_a_negative_scale() -> None:
    with pytest.raises(TapeError, match="scale must be non-negative"):
        RandomTape(1).normal(key(), scale=-1.0)


def test_exponential_rejects_a_non_positive_scale() -> None:
    with pytest.raises(TapeError, match="scale must be positive"):
        RandomTape(1).exponential(key(), scale=0.0)


def test_poisson_rejects_a_negative_rate() -> None:
    with pytest.raises(TapeError, match="lam must be non-negative"):
        RandomTape(1).poisson(key(), lam=-1.0)


def test_bernoulli_rejects_a_bad_probability() -> None:
    with pytest.raises(TapeError, match="p must be between"):
        RandomTape(1).bernoulli(key(), p=1.5)


@settings(max_examples=40, deadline=None)
@given(
    coordinates=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=20),
            st.integers(min_value=0, max_value=10),
            st.integers(min_value=0, max_value=10),
        ),
        min_size=1,
        max_size=12,
        unique=True,
    )
)
def test_tape_is_order_independent(coordinates: list[tuple[int, int, int]]) -> None:
    keys = [DrawKey("fire", *coordinate) for coordinate in coordinates]
    forward = RandomTape(31)
    backward = RandomTape(31)

    forward_values = {key: forward.random(key) for key in keys}
    backward_values = {key: backward.random(key) for key in reversed(keys)}

    assert forward_values == backward_values


def test_scalar_draws_have_scalar_types() -> None:
    tape = RandomTape(29)

    assert isinstance(tape.random(key()), float)
    assert isinstance(tape.uniform(key(), 1.0, 2.0), float)
    assert isinstance(tape.integers(key(), 1, 2), int)
    assert isinstance(tape.normal(key()), float)
    assert isinstance(tape.exponential(key()), float)
    assert isinstance(tape.poisson(key(), 2.0), int)
    assert isinstance(tape.bernoulli(key(), 0.5), bool)


def test_boolean_key_components_are_rejected() -> None:
    with pytest.raises(TapeError, match="spatial_unit_id must be an integer"):
        DrawKey("fire", True, 0)


def test_non_finite_arguments_are_rejected() -> None:
    with pytest.raises(TapeError, match="high must be finite"):
        RandomTape(1).uniform(key(), 0.0, float("inf"))
    with pytest.raises(TapeError, match="scale must be finite"):
        RandomTape(1).normal(key(), scale=float("nan"))
