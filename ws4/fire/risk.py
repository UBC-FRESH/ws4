"""Fire-regime risk summaries over process event records.

The P187 benchmark validates the scfm regime formulas against published toy values. This
module turns those formulas into a reusable summary of simulated fire events: annual burned
area, burn probability, fire return interval, escaped-fire frequency, and size quantiles.

The summary consumes event-log-like records structurally. It does not import the ecosystem
package, which keeps the fire package independent of the process ensemble and avoids an
import cycle. An :class:`ws4.ecosystem.events.Event` and :class:`ws4.ecosystem.log.EventLog`
both satisfy the protocols.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from .regime import FireRegimeDiagnostics, FireRegimeParameters, fire_regime_diagnostics

FIRE_RISK_VERSION: Final[str] = "ws4.fire-regime-risk.v1"


class FireRiskError(ValueError):
    """Raised when a fire-risk summary input is invalid."""


class FireEventLike(Protocol):
    """The event fields used by the fire-risk summary."""

    @property
    def year(self) -> int:
        """Return the event year.

        Returns
        -------
        int
            The simulation year.
        """
        ...

    @property
    def event_type(self) -> str:
        """Return the event type.

        Returns
        -------
        str
            The event type.
        """
        ...

    @property
    def area_ha(self) -> float | None:
        """Return the event area in hectares, when present.

        Returns
        -------
        float or None
            The event area, or None when the event has no area.
        """
        ...


class EventLogLike(Protocol):
    """The event-log fields used by the fire-risk summary."""

    @property
    def events(self) -> Sequence[FireEventLike]:
        """Return the ordered events.

        Returns
        -------
        sequence of FireEventLike
            The log's events.
        """
        ...

    @property
    def metadata(self) -> object:
        """Return the log metadata.

        Returns
        -------
        object
            An object that carries a ``scenario_id`` attribute.
        """
        ...


@dataclass(frozen=True)
class FireEventRecord:
    """One fire event reduced to the fields a regime summary needs.

    Attributes
    ----------
    year : int
        Simulation year.
    area_ha : float
        Burned area in hectares.
    """

    year: int
    area_ha: float

    def __post_init__(self) -> None:
        """Validate the year and area."""
        if isinstance(self.year, bool) or not isinstance(self.year, int) or self.year < 0:
            raise FireRiskError("year must be a non-negative integer")
        if isinstance(self.area_ha, bool) or not isinstance(self.area_ha, (int, float)):
            raise FireRiskError("area_ha must be a number")
        if not math.isfinite(float(self.area_ha)) or self.area_ha < 0.0:
            raise FireRiskError("area_ha must be finite and non-negative")


@dataclass(frozen=True)
class AnnualFireRecord:
    """One year's fire activity.

    Attributes
    ----------
    year : int
        Simulation year.
    burned_area_ha : float
        Total area burned in the year.
    fire_count : int
        Number of fire events.
    escaped_fire_count : int
        Number of fire events larger than one cell.
    sizes_ha : tuple of float
        Individual fire sizes.
    """

    year: int
    burned_area_ha: float
    fire_count: int
    escaped_fire_count: int
    sizes_ha: tuple[float, ...]


@dataclass(frozen=True)
class FireRegimeRiskSummary:
    """A risk summary of simulated fire events.

    Attributes
    ----------
    years : int
        Number of simulated years.
    burnable_area_ha : float
        Burnable area.
    cell_size_ha : float
        Area of one raster cell.
    annual : tuple of AnnualFireRecord
        One record per year, in ascending year order.
    total_burned_ha : float
        Total burned area across all years.
    mean_annual_burned_ha : float
        Mean annual burned area.
    median_annual_burned_ha : float
        Median annual burned area.
    p90_annual_burned_ha : float
        Nineteeth-percentile annual burned area.
    max_annual_burned_ha : float
        Maximum annual burned area.
    burn_probability : float
        Fraction of years with at least one fire.
    annual_burn_rate : float
        Burned area per hectare per year.
    fire_return_interval_years : float or None
        Years per complete burn of the burnable area, or None when nothing burned.
    fire_count : int
        Number of fire events.
    escaped_fire_count : int
        Number of events larger than one cell.
    escaped_fires_per_year : float
        Escaped events per year.
    mean_fire_size_ha : float
        Mean fire size.
    median_fire_size_ha : float
        Median fire size.
    p90_fire_size_ha : float
        Nineteeth-percentile fire size.
    max_fire_size_ha : float
        Maximum fire size.
    diagnostics : FireRegimeDiagnostics or None
        Target-versus-achieved scfm diagnostics when a target and historical sample exist.
    """

    years: int
    burnable_area_ha: float
    cell_size_ha: float
    annual: tuple[AnnualFireRecord, ...]
    total_burned_ha: float
    mean_annual_burned_ha: float
    median_annual_burned_ha: float
    p90_annual_burned_ha: float
    max_annual_burned_ha: float
    burn_probability: float
    annual_burn_rate: float
    fire_return_interval_years: float | None
    fire_count: int
    escaped_fire_count: int
    escaped_fires_per_year: float
    mean_fire_size_ha: float
    median_fire_size_ha: float
    p90_fire_size_ha: float
    max_fire_size_ha: float
    diagnostics: FireRegimeDiagnostics | None

    def to_dict(self) -> dict[str, object]:
        """Return the summary as a JSON-serializable mapping.

        Returns
        -------
        dict
            Version, inputs, aggregate metrics, annual records, and optional diagnostics.
        """
        return {
            "schema_version": FIRE_RISK_VERSION,
            "years": self.years,
            "burnable_area_ha": self.burnable_area_ha,
            "cell_size_ha": self.cell_size_ha,
            "annual": [
                {
                    "year": record.year,
                    "burned_area_ha": record.burned_area_ha,
                    "fire_count": record.fire_count,
                    "escaped_fire_count": record.escaped_fire_count,
                    "sizes_ha": list(record.sizes_ha),
                }
                for record in self.annual
            ],
            "total_burned_ha": self.total_burned_ha,
            "mean_annual_burned_ha": self.mean_annual_burned_ha,
            "median_annual_burned_ha": self.median_annual_burned_ha,
            "p90_annual_burned_ha": self.p90_annual_burned_ha,
            "max_annual_burned_ha": self.max_annual_burned_ha,
            "burn_probability": self.burn_probability,
            "annual_burn_rate": self.annual_burn_rate,
            "fire_return_interval_years": self.fire_return_interval_years,
            "fire_count": self.fire_count,
            "escaped_fire_count": self.escaped_fire_count,
            "escaped_fires_per_year": self.escaped_fires_per_year,
            "mean_fire_size_ha": self.mean_fire_size_ha,
            "median_fire_size_ha": self.median_fire_size_ha,
            "p90_fire_size_ha": self.p90_fire_size_ha,
            "max_fire_size_ha": self.max_fire_size_ha,
            "diagnostics": self.diagnostics.to_dict() if self.diagnostics else None,
        }


def _quantile(values: Sequence[float], probability: float) -> float:
    """Return a linearly interpolated quantile.

    Parameters
    ----------
    values : sequence of float
        Non-empty sample.
    probability : float
        Quantile in the closed interval [0, 1].

    Returns
    -------
    float
        The interpolated quantile.
    """
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _positive(value: object, field: str) -> float:
    """Return a finite positive float.

    Parameters
    ----------
    value : object
        Candidate value.
    field : str
        Field name for the error message.

    Returns
    -------
    float
        The validated value.

    Raises
    ------
    FireRiskError
        If the value is not a finite positive number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FireRiskError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise FireRiskError(f"{field} must be positive")
    return number


def events_from_log(log: EventLogLike) -> tuple[FireEventRecord, ...]:
    """Extract fire events from an event-log-like object.

    Parameters
    ----------
    log : EventLogLike
        An object with ``events`` and ``metadata.scenario_id``.

    Returns
    -------
    tuple of FireEventRecord
        Fire records in log order.

    Raises
    ------
    FireRiskError
        If a fire event lacks an area or carries an invalid year/area.
    """
    records: list[FireEventRecord] = []
    for event in log.events:
        if event.event_type != "fire":
            continue
        if event.area_ha is None:
            raise FireRiskError("a fire event must have an area_ha")
        records.append(FireEventRecord(year=event.year, area_ha=float(event.area_ha)))
    return tuple(records)


def summarize_fire_events(
    records: Sequence[FireEventRecord],
    *,
    years: int,
    burnable_area_ha: float,
    cell_size_ha: float,
    target: FireRegimeParameters | None = None,
    historical_sizes_ha: Sequence[float] | None = None,
) -> FireRegimeRiskSummary:
    """Summarize fire events over a fixed horizon.

    Parameters
    ----------
    records : sequence of FireEventRecord
        Fire events. Event order does not affect the summary.
    years : int
        Number of simulated years.
    burnable_area_ha : float
        Burnable area.
    cell_size_ha : float
        Area of one raster cell.
    target : FireRegimeParameters or None, optional
        Target regime. Requires ``historical_sizes_ha``.
    historical_sizes_ha : sequence of float or None, optional
        Historical fire sizes used by the target diagnostics. Requires ``target``.

    Returns
    -------
    FireRegimeRiskSummary
        Annual and aggregate risk metrics.

    Raises
    ------
    FireRiskError
        If the horizon, area, cell size, or event years are invalid, or if only one of
        ``target`` and ``historical_sizes_ha`` is supplied.
    """
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise FireRiskError("years must be a positive integer")
    area = _positive(burnable_area_ha, "burnable_area_ha")
    cell = _positive(cell_size_ha, "cell_size_ha")
    if (target is None) != (historical_sizes_ha is None):
        raise FireRiskError("target and historical_sizes_ha must be supplied together")
    if not years >= 0:
        raise FireRiskError("years must be non-negative")
    by_year: list[list[FireEventRecord]] = [[] for _ in range(years)]
    for record in records:
        if not isinstance(record, FireEventRecord):
            raise FireRiskError("records must contain FireEventRecord values")
        if record.year >= years:
            raise FireRiskError(f"event year {record.year} is outside the {years}-year horizon")
        by_year[record.year].append(record)
    annual: list[AnnualFireRecord] = []
    all_sizes: list[float] = []
    for year, year_records in enumerate(by_year):
        sizes = tuple(record.area_ha for record in year_records)
        all_sizes.extend(sizes)
        annual.append(
            AnnualFireRecord(
                year=year,
                burned_area_ha=sum(sizes),
                fire_count=len(sizes),
                escaped_fire_count=sum(1 for size in sizes if size > cell),
                sizes_ha=sizes,
            )
        )
    annual_areas = [record.burned_area_ha for record in annual]
    total_burned = sum(all_sizes)
    burn_rate = total_burned / (years * area)
    diagnostics: FireRegimeDiagnostics | None = None
    if target is not None and historical_sizes_ha is not None and all_sizes:
        diagnostics = fire_regime_diagnostics(
            burnable_area_ha=area,
            years=float(years),
            ignition_rate=target.ignition_rate,
            p_escape=target.p_escape,
            historical_sizes_ha=list(historical_sizes_ha),
            simulated_sizes_ha=all_sizes,
            cell_size_ha=cell,
            empirical_burn_rate=target.empirical_burn_rate,
        )
    return FireRegimeRiskSummary(
        years=years,
        burnable_area_ha=area,
        cell_size_ha=cell,
        annual=tuple(annual),
        total_burned_ha=total_burned,
        mean_annual_burned_ha=statistics.fmean(annual_areas),
        median_annual_burned_ha=statistics.median(annual_areas),
        p90_annual_burned_ha=_quantile(annual_areas, 0.9),
        max_annual_burned_ha=max(annual_areas),
        burn_probability=sum(1 for value in annual_areas if value > 0.0) / years,
        annual_burn_rate=burn_rate,
        fire_return_interval_years=(None if burn_rate <= 0.0 else 1.0 / burn_rate),
        fire_count=len(all_sizes),
        escaped_fire_count=sum(1 for size in all_sizes if size > cell),
        escaped_fires_per_year=sum(1 for size in all_sizes if size > cell) / years,
        mean_fire_size_ha=(total_burned / len(all_sizes) if all_sizes else 0.0),
        median_fire_size_ha=statistics.median(all_sizes) if all_sizes else 0.0,
        p90_fire_size_ha=_quantile(all_sizes, 0.9),
        max_fire_size_ha=max(all_sizes) if all_sizes else 0.0,
        diagnostics=diagnostics,
    )


def summarize_event_log(
    log: EventLogLike,
    *,
    years: int,
    burnable_area_ha: float,
    cell_size_ha: float,
    target: FireRegimeParameters | None = None,
    historical_sizes_ha: Sequence[float] | None = None,
) -> FireRegimeRiskSummary:
    """Summarize one event log.

    Parameters
    ----------
    log : EventLogLike
        Event log or log-like object.
    years : int
        Number of simulated years.
    burnable_area_ha : float
        Burnable area.
    cell_size_ha : float
        Area of one raster cell.
    target : FireRegimeParameters or None, optional
        Target regime.
    historical_sizes_ha : sequence of float or None, optional
        Historical fire sizes for the target diagnostics.

    Returns
    -------
    FireRegimeRiskSummary
        Summary of the log's fire events.
    """
    return summarize_fire_events(
        events_from_log(log),
        years=years,
        burnable_area_ha=burnable_area_ha,
        cell_size_ha=cell_size_ha,
        target=target,
        historical_sizes_ha=historical_sizes_ha,
    )


def summarize_event_logs(
    logs: Sequence[EventLogLike],
    *,
    years: int,
    burnable_area_ha: float,
    cell_size_ha: float,
    target: FireRegimeParameters | None = None,
    historical_sizes_ha: Sequence[float] | None = None,
) -> dict[str, FireRegimeRiskSummary]:
    """Summarize several event logs by scenario id.

    Parameters
    ----------
    logs : sequence of EventLogLike
        Event logs, one per scenario.
    years : int
        Number of simulated years.
    burnable_area_ha : float
        Burnable area.
    cell_size_ha : float
        Area of one raster cell.
    target : FireRegimeParameters or None, optional
        Target regime.
    historical_sizes_ha : sequence of float or None, optional
        Historical fire sizes for the target diagnostics.

    Returns
    -------
    dict
        Scenario id to summary.

    Raises
    ------
    FireRiskError
        If a scenario id is missing, duplicated, or empty.
    """
    summaries: dict[str, FireRegimeRiskSummary] = {}
    for log in logs:
        scenario = getattr(log.metadata, "scenario_id", None)
        if not isinstance(scenario, str) or not scenario.strip():
            raise FireRiskError("every event log needs a non-empty metadata.scenario_id")
        scenario = scenario.strip()
        if scenario in summaries:
            raise FireRiskError(f"duplicate scenario id {scenario!r}")
        summaries[scenario] = summarize_event_log(
            log,
            years=years,
            burnable_area_ha=burnable_area_ha,
            cell_size_ha=cell_size_ha,
            target=target,
            historical_sizes_ha=historical_sizes_ha,
        )
    return summaries
