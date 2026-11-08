"""The counter-based random tape that makes stochastic landscape runs reproducible.

Every primitive draw is a pure function of ``(scenario seed, process, spatial unit, year,
draw index)``. There is no global generator and no call-order dependence, so two candidate
schedules can share the same underlying draws (common random numbers), and a run can be
replayed from its seed and event log. The tape is the stochastic substrate the rest of the
ecosystem engine builds on.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Final

import numpy as np

#: The tape algorithm identifier recorded in an event-log manifest.
TAPE_ALGORITHM: Final[str] = "philox-2x64-v1"

#: A size argument for a vector draw.
DrawSize = int | tuple[int, ...]

_MAX_DRAW_INDEX: Final[int] = (1 << 64) - 1


class TapeError(RuntimeError):
    """Raised when a tape key or a draw argument is invalid."""


def _text(value: object, field: str) -> str:
    """Return a non-empty, stripped string.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    str
        The stripped string.

    Raises
    ------
    TapeError
        If the value is not a non-empty string.
    """
    if not isinstance(value, str) or not value.strip():
        raise TapeError(f"{field} must be a non-empty string")
    return value.strip()


def _integer(value: object, field: str) -> int:
    """Return an integer, rejecting booleans and non-integers.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    int
        The integer.

    Raises
    ------
    TapeError
        If the value is not an integer.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TapeError(f"{field} must be an integer")
    return value


def _finite(value: object, field: str) -> float:
    """Return a finite float, normalizing negative zero.

    Parameters
    ----------
    value : object
        The candidate value.
    field : str
        The field name, used in the error.

    Returns
    -------
    float
        The finite number.

    Raises
    ------
    TapeError
        If the value is not a finite number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TapeError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise TapeError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


@dataclass(frozen=True)
class DrawKey:
    """The coordinates of one reproducible random draw.

    Parameters
    ----------
    process_id : str
        The process or decision source asking for the draw.
    spatial_unit_id : int
        The spatial unit the draw belongs to, or 0 for a landscape-wide draw.
    year : int
        The annual accounting year.
    draw_index : int, optional
        The index of the draw within the unit-year (default 0). Callers must increment it to
        obtain a distinct scalar draw; a vector draw uses ``size`` instead.
    """

    process_id: str
    spatial_unit_id: int
    year: int
    draw_index: int = 0

    def __post_init__(self) -> None:
        """Validate the key coordinates."""
        process_id = _text(self.process_id, "process_id")
        spatial_unit_id = _integer(self.spatial_unit_id, "spatial_unit_id")
        year = _integer(self.year, "year")
        draw_index = _integer(self.draw_index, "draw_index")
        if spatial_unit_id < 0:
            raise TapeError("spatial_unit_id must be non-negative")
        if year < 0:
            raise TapeError("year must be non-negative")
        if draw_index < 0 or draw_index > _MAX_DRAW_INDEX:
            raise TapeError("draw_index must be between 0 and 2**64 - 1")
        object.__setattr__(self, "process_id", process_id)
        object.__setattr__(self, "spatial_unit_id", spatial_unit_id)
        object.__setattr__(self, "year", year)
        object.__setattr__(self, "draw_index", draw_index)


class RandomTape:
    """A counter-based random tape keyed by scenario, process, location, year, and draw.

    Parameters
    ----------
    scenario_seed : int
        The non-negative scenario seed. The same seed and key always produce the same draws.
    algorithm : str, optional
        The tape algorithm identifier (default :data:`TAPE_ALGORITHM`). No other algorithm is
        implemented yet; the field exists so a stored manifest can name its generator.
    """

    def __init__(self, scenario_seed: int, algorithm: str = TAPE_ALGORITHM) -> None:
        """Validate the scenario seed and algorithm, and retain them."""
        seed = _integer(scenario_seed, "scenario_seed")
        if seed < 0:
            raise TapeError("scenario_seed must be non-negative")
        name = _text(algorithm, "algorithm")
        if name != TAPE_ALGORITHM:
            raise TapeError(f"algorithm must be {TAPE_ALGORITHM!r}; got {name!r}")
        self.scenario_seed = seed
        self.algorithm = name

    @property
    def fingerprint(self) -> str:
        """Return a stable SHA-256 digest of the algorithm and scenario seed.

        Returns
        -------
        str
            The hex digest recorded in an event-log manifest.
        """
        payload = f"{self.algorithm}\x1f{self.scenario_seed}".encode()
        return hashlib.sha256(payload).hexdigest()

    def _payload(self, key: DrawKey) -> bytes:
        """Return the canonical byte payload for a draw key.

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.

        Returns
        -------
        bytes
            The UTF-8 payload hashed into the generator key.
        """
        return (
            f"{self.algorithm}\x1f{self.scenario_seed}\x1f{key.process_id}\x1f"
            f"{key.spatial_unit_id}\x1f{key.year}\x1f{key.draw_index}"
        ).encode()

    def _generator(self, key: DrawKey) -> np.random.Generator:
        """Return the counter-based generator for one draw key.

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.

        Returns
        -------
        numpy.random.Generator
            A generator positioned at the key's counter block.
        """
        digest = hashlib.blake2b(self._payload(key), digest_size=16).digest()
        stream_key = np.frombuffer(digest, dtype="<u8").astype(np.uint64, copy=True)
        counter = np.array([key.draw_index, 0, 0, 0], dtype=np.uint64)
        return np.random.Generator(np.random.Philox(key=stream_key, counter=counter))

    def random(self, key: DrawKey, size: DrawSize | None = None) -> float | np.ndarray:
        """Draw a uniform value in [0, 1).

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.
        size : int or tuple of int or None, optional
            The shape of a vector draw; None returns one float.

        Returns
        -------
        float or numpy.ndarray
            The draw, or an array of draws.
        """
        generator = self._generator(key)
        if size is None:
            return float(generator.random())
        return np.asarray(generator.random(size), dtype=float)

    def uniform(
        self,
        key: DrawKey,
        low: float = 0.0,
        high: float = 1.0,
        size: DrawSize | None = None,
    ) -> float | np.ndarray:
        """Draw a value uniformly from ``[low, high)``.

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.
        low : float, optional
            The lower bound (default 0.0).
        high : float, optional
            The upper bound (default 1.0).
        size : int or tuple of int or None, optional
            The shape of a vector draw; None returns one float.

        Returns
        -------
        float or numpy.ndarray
            The draw, or an array of draws.

        Raises
        ------
        TapeError
            If the bounds are not finite or ``high`` is not greater than ``low``.
        """
        lower = _finite(low, "low")
        upper = _finite(high, "high")
        if upper <= lower:
            raise TapeError("high must be greater than low")
        generator = self._generator(key)
        if size is None:
            return float(generator.uniform(lower, upper))
        return np.asarray(generator.uniform(lower, upper, size), dtype=float)

    def integers(
        self,
        key: DrawKey,
        low: int,
        high: int,
        size: DrawSize | None = None,
    ) -> int | np.ndarray:
        """Draw an integer from ``[low, high)``.

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.
        low : int
            The inclusive lower bound.
        high : int
            The exclusive upper bound.
        size : int or tuple of int or None, optional
            The shape of a vector draw; None returns one integer.

        Returns
        -------
        int or numpy.ndarray
            The draw, or an array of draws.

        Raises
        ------
        TapeError
            If the bounds are not integers or ``high`` is not greater than ``low``.
        """
        lower = _integer(low, "low")
        upper = _integer(high, "high")
        if upper <= lower:
            raise TapeError("high must be greater than low")
        generator = self._generator(key)
        if size is None:
            return int(generator.integers(lower, upper))
        return np.asarray(generator.integers(lower, upper, size), dtype=np.int64)

    def normal(
        self,
        key: DrawKey,
        loc: float = 0.0,
        scale: float = 1.0,
        size: DrawSize | None = None,
    ) -> float | np.ndarray:
        """Draw from a normal distribution.

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.
        loc : float, optional
            The mean (default 0.0).
        scale : float, optional
            The standard deviation (default 1.0).
        size : int or tuple of int or None, optional
            The shape of a vector draw; None returns one float.

        Returns
        -------
        float or numpy.ndarray
            The draw, or an array of draws.

        Raises
        ------
        TapeError
            If ``loc`` is not finite or ``scale`` is not finite and non-negative.
        """
        mean = _finite(loc, "loc")
        deviation = _finite(scale, "scale")
        if deviation < 0.0:
            raise TapeError("scale must be non-negative")
        generator = self._generator(key)
        if size is None:
            return float(generator.normal(mean, deviation))
        return np.asarray(generator.normal(mean, deviation, size), dtype=float)

    def exponential(
        self,
        key: DrawKey,
        scale: float = 1.0,
        size: DrawSize | None = None,
    ) -> float | np.ndarray:
        """Draw from an exponential distribution.

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.
        scale : float, optional
            The mean of the distribution (default 1.0).
        size : int or tuple of int or None, optional
            The shape of a vector draw; None returns one float.

        Returns
        -------
        float or numpy.ndarray
            The draw, or an array of draws.

        Raises
        ------
        TapeError
            If ``scale`` is not finite and strictly positive.
        """
        mean = _finite(scale, "scale")
        if mean <= 0.0:
            raise TapeError("scale must be positive")
        generator = self._generator(key)
        if size is None:
            return float(generator.exponential(mean))
        return np.asarray(generator.exponential(mean, size), dtype=float)

    def poisson(
        self,
        key: DrawKey,
        lam: float,
        size: DrawSize | None = None,
    ) -> int | np.ndarray:
        """Draw from a Poisson distribution.

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.
        lam : float
            The rate parameter.
        size : int or tuple of int or None, optional
            The shape of a vector draw; None returns one integer.

        Returns
        -------
        int or numpy.ndarray
            The draw, or an array of draws.

        Raises
        ------
        TapeError
            If ``lam`` is not finite and non-negative.
        """
        rate = _finite(lam, "lam")
        if rate < 0.0:
            raise TapeError("lam must be non-negative")
        generator = self._generator(key)
        if size is None:
            return int(generator.poisson(rate))
        return np.asarray(generator.poisson(rate, size), dtype=np.int64)

    def bernoulli(
        self,
        key: DrawKey,
        p: float,
        size: DrawSize | None = None,
    ) -> bool | np.ndarray:
        """Draw a Bernoulli outcome with probability ``p``.

        Parameters
        ----------
        key : DrawKey
            The draw coordinates.
        p : float
            The success probability in [0, 1].
        size : int or tuple of int or None, optional
            The shape of a vector draw; None returns one boolean.

        Returns
        -------
        bool or numpy.ndarray
            The draw, or an array of draws.

        Raises
        ------
        TapeError
            If ``p`` is not between 0 and 1.
        """
        probability = _finite(p, "p")
        if probability < 0.0 or probability > 1.0:
            raise TapeError("p must be between 0 and 1")
        generator = self._generator(key)
        if size is None:
            return float(generator.random()) < probability
        return np.asarray(generator.random(size), dtype=float) < probability
