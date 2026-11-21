"""Pre-registered regime calibration for P164.8.

This module implements the fixed parameter bounds, size metrics, decision gates, and
training-only search defined by ``notes/design/ws4-regime-calibration-protocol.md``.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np

from .survival import RelativeSuppressionConfig, draw_relative_suppression

CONTAINED_FRACTION_BOUNDS: Final[tuple[float, float]] = (1e-5, 1e-2)
CONTAINED_SIGMA_BOUNDS: Final[tuple[float, float]] = (0.3, 1.5)
ESCAPED_FRACTION_BOUNDS: Final[tuple[float, float]] = (0.01, 1.0)
ESCAPED_SIGMA_BOUNDS: Final[tuple[float, float]] = (0.05, 0.6)
ESCAPE_CAP_BOUNDS: Final[tuple[float, float]] = (5_000.0, 30_000.0)
INTERCEPT_BOUNDS: Final[tuple[float, float]] = (-7.0, -3.0)

MEDIAN_BAND: Final[tuple[float, float]] = (20.0, 30.0)
P90_BAND: Final[tuple[float, float]] = (350.0, 700.0)
OVER_100_BAND: Final[tuple[float, float]] = (0.20, 0.30)
OVER_500_BAND: Final[tuple[float, float]] = (0.06, 0.12)
OVER_1000_BAND: Final[tuple[float, float]] = (0.04, 0.09)
OVER_5000_BAND: Final[tuple[float, float]] = (0.01, 0.04)
MINIMUM_MAXIMUM_HA: Final[float] = 10_000.0


class RegimeCalibrationError(ValueError):
    """Raised when a regime calibration input or parameter is invalid."""


@dataclass(frozen=True)
class RegimeParameters:
    """Parameters allowed by the P164.8 protocol.

    Parameters
    ----------
    contained_fraction_median : float
        Median retained fraction after containment.
    contained_fraction_sigma : float
        Log-sigma of the contained fraction.
    escaped_fraction_median : float
        Median retained fraction after escape.
    escaped_fraction_sigma : float
        Log-sigma of the escaped fraction.
    escape_cap_ha : float
        Absolute escaped-area cap.
    intercept : float
        Escape hazard logit intercept.
    """

    contained_fraction_median: float
    contained_fraction_sigma: float
    escaped_fraction_median: float
    escaped_fraction_sigma: float
    escape_cap_ha: float
    intercept: float

    def __post_init__(self) -> None:
        """Validate every parameter against its pre-registered bounds."""
        for value, field, bounds in (
            (
                self.contained_fraction_median,
                "contained_fraction_median",
                CONTAINED_FRACTION_BOUNDS,
            ),
            (self.contained_fraction_sigma, "contained_fraction_sigma", CONTAINED_SIGMA_BOUNDS),
            (self.escaped_fraction_median, "escaped_fraction_median", ESCAPED_FRACTION_BOUNDS),
            (self.escaped_fraction_sigma, "escaped_fraction_sigma", ESCAPED_SIGMA_BOUNDS),
            (self.escape_cap_ha, "escape_cap_ha", ESCAPE_CAP_BOUNDS),
            (self.intercept, "intercept", INTERCEPT_BOUNDS),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RegimeCalibrationError(f"{field} must be a number")
            number = float(value)
            if not math.isfinite(number) or number < bounds[0] or number > bounds[1]:
                raise RegimeCalibrationError(f"{field} is outside its pre-registered bounds")

    def to_dict(self) -> dict[str, float]:
        """Return the parameters as a JSON-serializable mapping.

        Returns
        -------
        dict
            Parameter names and values.
        """
        return {
            "contained_fraction_median": self.contained_fraction_median,
            "contained_fraction_sigma": self.contained_fraction_sigma,
            "escaped_fraction_median": self.escaped_fraction_median,
            "escaped_fraction_sigma": self.escaped_fraction_sigma,
            "escape_cap_ha": self.escape_cap_ha,
            "intercept": self.intercept,
        }

    def suppression(self) -> RelativeSuppressionConfig:
        """Return the relative-suppression config for this parameter point.

        Returns
        -------
        RelativeSuppressionConfig
            The fixed-weight suppression configuration.
        """
        return RelativeSuppressionConfig(
            contained_fraction_median=self.contained_fraction_median,
            contained_fraction_sigma=self.contained_fraction_sigma,
            escaped_fraction_median=self.escaped_fraction_median,
            escaped_fraction_sigma=self.escaped_fraction_sigma,
            escape_cap_ha=self.escape_cap_ha,
            min_area_ha=6.25,
            intercept=self.intercept,
            duration_weight=0.5,
            fwi_weight=0.2,
            bui_weight=0.1,
            wind_weight=0.1,
        )


@dataclass(frozen=True)
class PotentialFire:
    """One potential-fire observation used by the calibration harness.

    Parameters
    ----------
    potential_ha : float
        Unsuppressed potential area.
    active_days : float
        Active-spread duration in days.
    fwi : float
        Fire Weather Index.
    bui : float
        Buildup Index.
    wind_kmh : float
        Ten-metre wind speed.
    """

    potential_ha: float
    active_days: float
    fwi: float
    bui: float
    wind_kmh: float

    def __post_init__(self) -> None:
        """Validate the potential-fire inputs."""
        for value, field in (
            (self.potential_ha, "potential_ha"),
            (self.active_days, "active_days"),
            (self.fwi, "fwi"),
            (self.bui, "bui"),
            (self.wind_kmh, "wind_kmh"),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RegimeCalibrationError(f"{field} must be a number")
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise RegimeCalibrationError(f"{field} must be finite and non-negative")
        if self.active_days <= 0.0:
            raise RegimeCalibrationError("active_days must be positive")
        if self.potential_ha <= 0.0:
            raise RegimeCalibrationError("potential_ha must be positive")


@dataclass(frozen=True)
class RegimeMetrics:
    """Event-size metrics used by the pre-registered gates.

    Attributes
    ----------
    count : int
        Number of fires.
    mean : float
        Mean area.
    median : float
        Median area.
    p90 : float
        90th percentile area.
    p95 : float
        95th percentile area.
    over_100 : float
        Fraction over 100 ha.
    over_500 : float
        Fraction over 500 ha.
    over_1000 : float
        Fraction over 1,000 ha.
    over_5000 : float
        Fraction over 5,000 ha.
    maximum : float
        Maximum area.
    """

    count: int
    mean: float
    median: float
    p90: float
    p95: float
    over_100: float
    over_500: float
    over_1000: float
    over_5000: float
    maximum: float

    def to_dict(self) -> dict[str, float | int]:
        """Return the metrics as a JSON-serializable mapping.

        Returns
        -------
        dict
            Metric names and values.
        """
        return {
            "count": self.count,
            "mean": self.mean,
            "median": self.median,
            "p90": self.p90,
            "p95": self.p95,
            "over_100": self.over_100,
            "over_500": self.over_500,
            "over_1000": self.over_1000,
            "over_5000": self.over_5000,
            "maximum": self.maximum,
        }


def size_metrics(values: Sequence[float]) -> RegimeMetrics:
    """Compute the pre-registered size metrics.

    Parameters
    ----------
    values : sequence of float
        Burned areas in hectares.

    Returns
    -------
    RegimeMetrics
        Count, quantiles, threshold fractions, and maximum.

    Raises
    ------
    RegimeCalibrationError
        If no values are supplied or a value is invalid.
    """
    if not values:
        raise RegimeCalibrationError("at least one area is required")
    array = np.asarray(values, dtype=float)
    if not np.isfinite(array).all() or (array < 0.0).any():
        raise RegimeCalibrationError("areas must be finite and non-negative")
    return RegimeMetrics(
        count=int(array.size),
        mean=float(array.mean()),
        median=float(np.median(array)),
        p90=float(np.quantile(array, 0.9)),
        p95=float(np.quantile(array, 0.95)),
        over_100=float((array > 100.0).mean()),
        over_500=float((array > 500.0).mean()),
        over_1000=float((array > 1_000.0).mean()),
        over_5000=float((array > 5_000.0).mean()),
        maximum=float(array.max()),
    )


def gate_results(metrics: RegimeMetrics) -> dict[str, bool]:
    """Return each pre-registered gate result.

    Parameters
    ----------
    metrics : RegimeMetrics
        Candidate metrics.

    Returns
    -------
    dict of str to bool
        Gate name to pass/fail.
    """
    return {
        "median": MEDIAN_BAND[0] <= metrics.median <= MEDIAN_BAND[1],
        "p90": P90_BAND[0] <= metrics.p90 <= P90_BAND[1],
        "over_100": OVER_100_BAND[0] <= metrics.over_100 <= OVER_100_BAND[1],
        "over_500": OVER_500_BAND[0] <= metrics.over_500 <= OVER_500_BAND[1],
        "over_1000": OVER_1000_BAND[0] <= metrics.over_1000 <= OVER_1000_BAND[1],
        "over_5000": OVER_5000_BAND[0] <= metrics.over_5000 <= OVER_5000_BAND[1],
        "maximum": metrics.maximum >= MINIMUM_MAXIMUM_HA,
    }


def passes_gates(metrics: RegimeMetrics) -> bool:
    """Return whether every pre-registered gate passes.

    Parameters
    ----------
    metrics : RegimeMetrics
        Candidate metrics.

    Returns
    -------
    bool
        True when every gate passes.
    """
    return all(gate_results(metrics).values())


def training_score(metrics: RegimeMetrics) -> float:
    """Return a deterministic training-only ranking score.

    The score is a normalized distance from the gate midpoints. It is only used to rank
    candidates inside the training split; the validation split is never used for selection.

    Parameters
    ----------
    metrics : RegimeMetrics
        Candidate metrics.

    Returns
    -------
    float
        Lower-is-better training score.
    """
    median_mid = sum(MEDIAN_BAND) / 2.0
    p90_mid = sum(P90_BAND) / 2.0
    over_100_mid = sum(OVER_100_BAND) / 2.0
    over_500_mid = sum(OVER_500_BAND) / 2.0
    over_1000_mid = sum(OVER_1000_BAND) / 2.0
    over_5000_mid = sum(OVER_5000_BAND) / 2.0
    return (
        abs(math.log((metrics.median + 1.0) / (median_mid + 1.0)))
        + abs(math.log((metrics.p90 + 1.0) / (p90_mid + 1.0)))
        + 3.0 * abs(metrics.over_100 - over_100_mid)
        + 3.0 * abs(metrics.over_500 - over_500_mid)
        + 3.0 * abs(metrics.over_1000 - over_1000_mid)
        + 2.0 * abs(metrics.over_5000 - over_5000_mid)
        + 0.2 * abs(math.log((metrics.maximum + 1.0) / (MINIMUM_MAXIMUM_HA + 1.0)))
    )


def parameter_candidates(seed: int, count: int = 1_500) -> tuple[RegimeParameters, ...]:
    """Return deterministic log-uniform candidates inside the protocol bounds.

    Parameters
    ----------
    seed : int
        Fixed search seed.
    count : int, optional
        Number of candidates (default 1,500).

    Returns
    -------
    tuple of RegimeParameters
        Candidate parameter points in deterministic order.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise RegimeCalibrationError("seed must be a non-negative integer")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise RegimeCalibrationError("count must be a positive integer")
    rng = random.Random(seed)

    def log_uniform(bounds: tuple[float, float]) -> float:
        return math.pow(10.0, rng.uniform(math.log10(bounds[0]), math.log10(bounds[1])))

    def uniform(bounds: tuple[float, float]) -> float:
        return rng.uniform(bounds[0], bounds[1])

    return tuple(
        RegimeParameters(
            contained_fraction_median=log_uniform(CONTAINED_FRACTION_BOUNDS),
            contained_fraction_sigma=uniform(CONTAINED_SIGMA_BOUNDS),
            escaped_fraction_median=log_uniform(ESCAPED_FRACTION_BOUNDS),
            escaped_fraction_sigma=uniform(ESCAPED_SIGMA_BOUNDS),
            escape_cap_ha=uniform(ESCAPE_CAP_BOUNDS),
            intercept=uniform(INTERCEPT_BOUNDS),
        )
        for _ in range(count)
    )


def load_potential_records(path: Path) -> tuple[PotentialFire, ...]:
    """Load potential-fire records from a JSON list.

    Parameters
    ----------
    path : Path
        JSON file containing a list of mappings with potential_ha, active_days, fwi, bui,
        and wind_kmh.

    Returns
    -------
    tuple of PotentialFire
        Validated records.

    Raises
    ------
    RegimeCalibrationError
        If the file is not a JSON list or a record is invalid.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RegimeCalibrationError(f"cannot read potential records: {error}") from error
    if not isinstance(payload, list):
        raise RegimeCalibrationError("potential records must be a JSON list")
    records: list[PotentialFire] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise RegimeCalibrationError("each potential record must be a mapping")
        try:
            records.append(
                PotentialFire(
                    potential_ha=entry["potential_ha"],
                    active_days=entry["active_days"],
                    fwi=entry["fwi"],
                    bui=entry["bui"],
                    wind_kmh=entry["wind_kmh"],
                )
            )
        except KeyError as error:
            raise RegimeCalibrationError(f"potential record is missing {error.args[0]}") from error
    return tuple(records)


def simulate(
    parameters: RegimeParameters,
    records: Sequence[PotentialFire],
    seed: int,
) -> list[float]:
    """Apply relative suppression to potential records with one deterministic draw each.

    Parameters
    ----------
    parameters : RegimeParameters
        Candidate parameters.
    records : sequence of PotentialFire
        Potential-fire records.
    seed : int
        Deterministic draw seed.

    Returns
    -------
    list of float
        Simulated final areas in hectares.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise RegimeCalibrationError("seed must be a non-negative integer")
    rng = random.Random(seed)
    config = parameters.suppression()
    return [
        draw_relative_suppression(
            config,
            rng,
            potential_area_ha=record.potential_ha,
            active_days=record.active_days,
            fwi=record.fwi,
            bui=record.bui,
            wind_kmh=record.wind_kmh,
        ).target_area_ha
        for record in records
    ]


@dataclass(frozen=True)
class CalibrationResult:
    """The best training-only parameter point.

    Attributes
    ----------
    parameters : RegimeParameters
        Selected parameters.
    metrics : RegimeMetrics
        Training metrics.
    score : float
        Training score.
    seed : int
        Search seed.
    candidates : int
        Number of evaluated candidates.
    """

    parameters: RegimeParameters
    metrics: RegimeMetrics
    score: float
    seed: int
    candidates: int

    def to_dict(self) -> dict[str, object]:
        """Return the result as a JSON-serializable mapping.

        Returns
        -------
        dict
            Parameters, metrics, score, seed, candidates, and gates.
        """
        return {
            "parameters": self.parameters.to_dict(),
            "metrics": self.metrics.to_dict(),
            "score": self.score,
            "seed": self.seed,
            "candidates": self.candidates,
            "gates": gate_results(self.metrics),
            "passes": passes_gates(self.metrics),
        }


def search_training(
    records: Sequence[PotentialFire],
    *,
    seed: int = 0,
    count: int = 1_500,
) -> CalibrationResult:
    """Search the pre-registered training candidates and return the best score.

    Parameters
    ----------
    records : sequence of PotentialFire
        Training potential records.
    seed : int, optional
        Fixed search seed (default zero).
    count : int, optional
        Number of candidates (default 1,500).

    Returns
    -------
    CalibrationResult
        Best training candidate and its metrics.
    """
    best: CalibrationResult | None = None
    best_passing: CalibrationResult | None = None
    for index, parameters in enumerate(parameter_candidates(seed, count)):
        metrics = size_metrics(simulate(parameters, records, seed + index * 1_000_003))
        score = training_score(metrics)
        result = CalibrationResult(
            parameters=parameters,
            metrics=metrics,
            score=score,
            seed=seed,
            candidates=count,
        )
        if best is None or score < best.score:
            best = result
        if passes_gates(metrics) and (best_passing is None or score < best_passing.score):
            best_passing = result
    if best_passing is not None:
        return best_passing
    if best is None:
        raise RegimeCalibrationError("no candidates were evaluated")
    return best


def validate(
    parameters: RegimeParameters,
    records: Sequence[PotentialFire],
    *,
    seed: int = 0,
) -> RegimeMetrics:
    """Evaluate frozen parameters once on validation records.

    Parameters
    ----------
    parameters : RegimeParameters
        Frozen parameters.
    records : sequence of PotentialFire
        Validation potential records.
    seed : int, optional
        Deterministic draw seed.

    Returns
    -------
    RegimeMetrics
        Validation metrics.
    """
    return size_metrics(simulate(parameters, records, seed))
