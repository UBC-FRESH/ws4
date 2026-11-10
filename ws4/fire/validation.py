"""Published fire-model validation envelopes and tier-specific decision gates.

The registry is deliberately explicit about comparison basis. A single-fire perimeter is
context, not a universal acceptance threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

from .fuel import FireFuelError, _non_negative


class ValidationTier(StrEnum):
    """The validation tiers used by the P164 ladder.

    Attributes
    ----------
    STANDARD
        Standard physical/behaviour cases.
    EVENT
        Observed-fire perimeter reconstruction.
    RISK
        Burn-probability calibration and skill.
    TREATMENT
        Stand/landscape treatment response.
    TREE
        Tree-level fire effects.
    DECISION
        Planning/decision quality.
    """

    STANDARD = "standard"
    EVENT = "event"
    RISK = "risk"
    TREATMENT = "treatment"
    TREE = "tree"
    DECISION = "decision"


class MetricDirection(StrEnum):
    """Whether higher or lower values are better, or the value is context only."""

    HIGHER = "higher"
    LOWER = "lower"
    CONTEXT = "context"


Position = Literal["below", "within", "above"]


@dataclass(frozen=True)
class PublishedBenchmark:
    """One published benchmark interval.

    Parameters
    ----------
    name : str
        Human-readable benchmark name.
    metric : str
        Metric identifier.
    tier : ValidationTier
        Validation tier.
    low, high : float
        Published or declared interval.
    direction : MetricDirection
        Whether higher or lower values are better, or context only.
    unit : str
        Display unit.
    source : str
        Citation or URL.
    basis : str
        What the interval represents, including its caveats.
    """

    name: str
    metric: str
    tier: ValidationTier
    low: float
    high: float
    direction: MetricDirection
    unit: str
    source: str
    basis: str

    def __post_init__(self) -> None:
        """Validate the benchmark interval."""
        if not self.name or not self.metric or not self.unit or not self.source or not self.basis:
            raise FireFuelError("benchmark fields must be non-empty")
        if not isinstance(self.tier, ValidationTier):
            raise FireFuelError("tier must be a ValidationTier")
        if not isinstance(self.direction, MetricDirection):
            raise FireFuelError("direction must be a MetricDirection")
        low = _non_negative(self.low, "low")
        high = _non_negative(self.high, "high")
        if high < low:
            raise FireFuelError("benchmark high must be at least low")

    def position(self, value: float) -> Position:
        """Return whether a value is below, within, or above the interval.

        Parameters
        ----------
        value : float
            Metric value.

        Returns
        -------
        str
            ``below``, ``within``, or ``above``.
        """
        number = _non_negative(value, "value")
        if number < self.low:
            return "below"
        if number > self.high:
            return "above"
        return "within"

    def to_dict(self) -> dict[str, object]:
        """Return the benchmark as a JSON-serializable mapping.

        Returns
        -------
        dict
            All fields.
        """
        return {
            "name": self.name,
            "metric": self.metric,
            "tier": self.tier.value,
            "low": self.low,
            "high": self.high,
            "direction": self.direction.value,
            "unit": self.unit,
            "source": self.source,
            "basis": self.basis,
        }


# Published examples, not universal acceptance thresholds.
BENCHMARKS: Final[tuple[PublishedBenchmark, ...]] = (
    PublishedBenchmark(
        name="WildfireAV ELMFIRE event Jaccard",
        metric="jaccard",
        tier=ValidationTier.EVENT,
        low=0.15,
        high=0.30,
        direction=MetricDirection.HIGHER,
        unit="Jaccard",
        source="WildfireAV / ELMFIRE validation summary",
        basis=(
            "Multi-fire mean 0.178; interval is an envelope around published means, "
            "not a pass mark."
        ),
    ),
    PublishedBenchmark(
        name="WildfireAV FARSITE event Jaccard",
        metric="jaccard",
        tier=ValidationTier.EVENT,
        low=0.15,
        high=0.30,
        direction=MetricDirection.HIGHER,
        unit="Jaccard",
        source="WildfireAV / FARSITE validation summary",
        basis="Multi-fire mean 0.176; interval is an envelope, not a pass mark.",
    ),
    PublishedBenchmark(
        name="Prometheus Dogrib case 4 FoM",
        metric="jaccard",
        tier=ValidationTier.EVENT,
        low=0.10,
        high=0.30,
        direction=MetricDirection.HIGHER,
        unit="Figure of Merit",
        source="ABWiSE / Prometheus Dogrib validation",
        basis="Published 0.21 at 200 m on a difficult case; context only.",
    ),
    PublishedBenchmark(
        name="Prometheus Dogrib case 3 FoM",
        metric="jaccard",
        tier=ValidationTier.EVENT,
        low=0.40,
        high=0.65,
        direction=MetricDirection.HIGHER,
        unit="Figure of Merit",
        source="ABWiSE / Prometheus Dogrib validation",
        basis="Published 0.568 on a better-conditioned case; context only.",
    ),
    PublishedBenchmark(
        name="FSim top-20% BP capture",
        metric="top_bp_capture",
        tier=ValidationTier.RISK,
        low=0.57,
        high=0.80,
        direction=MetricDirection.HIGHER,
        unit="fraction",
        source="Moran et al. 2025, FSim California",
        basis="Published 56.7-79.8% of burned area in the top 20% of mapped BP.",
    ),
    PublishedBenchmark(
        name="FSim logarithmic skill score",
        metric="log_skill",
        tier=ValidationTier.RISK,
        low=0.10,
        high=0.40,
        direction=MetricDirection.HIGHER,
        unit="LSS",
        source="Moran et al. 2025, FSim California",
        basis="Published means 0.114-0.339 against reference models.",
    ),
    PublishedBenchmark(
        name="FOFEM stand mortality error",
        metric="stand_mortality_abs_error",
        tier=ValidationTier.TREE,
        low=0.0,
        high=0.20,
        direction=MetricDirection.LOWER,
        unit="fraction",
        source="Hood et al. 2007, International Journal of Wildland Fire",
        basis="Stand-level prediction within ±20% for most western conifer species.",
    ),
)


def benchmarks_for(
    tier: ValidationTier, metric: str | None = None
) -> tuple[PublishedBenchmark, ...]:
    """Return benchmarks for a tier and optional metric.

    Parameters
    ----------
    tier : ValidationTier
        Tier to filter.
    metric : str or None, optional
        Metric to filter.

    Returns
    -------
    tuple of PublishedBenchmark
        Matching benchmarks.
    """
    return tuple(
        item
        for item in BENCHMARKS
        if item.tier == tier and (metric is None or item.metric == metric)
    )


def classify_against_published(
    tier: ValidationTier,
    metric: str,
    value: float,
) -> str:
    """Classify a value against the first matching published interval.

    Parameters
    ----------
    tier : ValidationTier
        Metric tier.
    metric : str
        Metric identifier.
    value : float
        Observed value.

    Returns
    -------
    str
        ``below``, ``within``, or ``above``.

    Raises
    ------
    FireFuelError
        If no benchmark exists for the tier and metric.
    """
    matches = benchmarks_for(tier, metric)
    if not matches:
        raise FireFuelError(f"no benchmark for tier={tier.value!r}, metric={metric!r}")
    return matches[0].position(value)


def single_fire_context() -> str:
    """Return the project position on single-fire validation.

    Returns
    -------
    str
        A short policy statement.
    """
    return (
        "A single observed fire is context evidence. It is not a universal acceptance "
        "threshold and cannot establish regional calibration."
    )
