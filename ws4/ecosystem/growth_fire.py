"""Bridge the raster FBP growth engine into the cohort process executor.

The growth engine produces a burned-cell field; this module turns its per-fragment arrival
areas into ``fire`` events and applies the corresponding mortality to cohorts. It does not
replace the growth engine or the graph fire process; it is the adapter that lets a raster
growth run participate in the same annual executor.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

import numpy as np

from ..fire.growth import (
    FragmentIgnition,
    FragmentSupport,
    GrowthConfig,
    SiteGrid,
    fragment_ignition_times,
    grow_fire,
)
from ..fire.survival import (
    RelativeSuppressionConfig,
    SurvivalConfig,
    draw_relative_suppression,
    draw_survival,
)
from .events import Event
from .fire import FireConfig, FireProcess
from .process import ProcessContext
from .state import CohortState
from .tape import RandomTape

GROWTH_FIRE_SOURCE: Final[str] = "ws4.fire.growth"


def _number(value: object, field: str, *, positive: bool) -> float:
    """Return a finite number, optionally requiring a positive value."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0.0) or number < 0.0:
        raise ValueError(f"{field} must be {'positive' if positive else 'non-negative'}")
    return number


@dataclass(frozen=True)
class GrowthFireSource:
    """Emit and apply fire events from a raster growth result.

    Parameters
    ----------
    ignitions : mapping of int to sequence of FragmentIgnition
        Year to the fragments reached by that year's growth run.
    scenario_id : str, optional
        Scenario id stamped on events.
    snag_fraction : float, optional
        Fraction of killed biomass left as snags (default 0.1).
    minutes_per_year : float, optional
        Minutes per simulation year (default 525600).
    process_id : str, optional
        Process id used by the executor.
    phases : tuple of str, optional
        Executor phases; growth fire events are emitted in ``propagation``.
    state_reads, state_writes : frozenset of str, optional
        Cohort-state variables read and written by the adapter.
    """

    ignitions: Mapping[int, Sequence[FragmentIgnition]]
    scenario_id: str = "growth-fire"
    snag_fraction: float = 0.1
    minutes_per_year: float = 525_600.0

    process_id: str = "fire-growth"
    phases: tuple[str, ...] = ("propagation",)
    state_reads: frozenset[str] = frozenset(
        {"area_ha", "fragment_areas", "biomass_t_ha", "fuel_t_ha", "snag_t_ha"}
    )
    state_writes: frozenset[str] = frozenset({"biomass_t_ha", "fuel_t_ha", "snag_t_ha"})

    def __post_init__(self) -> None:
        """Validate the source fields."""
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if not isinstance(self.ignitions, Mapping):
            raise ValueError("ignitions must be a mapping")
        for year, entries in self.ignitions.items():
            if isinstance(year, bool) or not isinstance(year, int) or year < 0:
                raise ValueError("ignition years must be non-negative integers")
            if not isinstance(entries, Sequence):
                raise ValueError("ignition entries must be sequences")
            for entry in entries:
                if not isinstance(entry, FragmentIgnition):
                    raise ValueError("ignition entries must be FragmentIgnition values")
        snag = _number(self.snag_fraction, "snag_fraction", positive=False)
        if snag > 1.0:
            raise ValueError("snag_fraction must be between 0 and 1")
        object.__setattr__(self, "scenario_id", self.scenario_id.strip())
        object.__setattr__(self, "snag_fraction", snag)
        object.__setattr__(
            self,
            "minutes_per_year",
            _number(self.minutes_per_year, "minutes_per_year", positive=True),
        )

    def events(self, state: CohortState, context: ProcessContext) -> tuple[Event, ...]:
        """Return the growth fire events for the current year.

        Parameters
        ----------
        state : CohortState
            The current cohort state.
        context : ProcessContext
            The annual context.

        Returns
        -------
        tuple of Event
            Fire events for reached fragments, or an empty tuple for other phases/years.
        """
        if context.phase != "propagation":
            return ()
        existing = {event.event_id for event in context.year_events}
        events: list[Event] = []
        for entry in self.ignitions.get(context.year, ()):
            area = float(state.fragment_areas.get(entry.fragment_id, 0.0))
            if area <= 0.0:
                continue
            fraction = min(1.0, max(0.0, entry.area_ha / area))
            if fraction <= 0.0:
                continue
            event_id = f"fire-growth-{context.year}-{entry.fragment_id}"
            if event_id in existing:
                continue
            time = context.year + min(
                0.999,
                max(0.0, entry.ignition_time_min / self.minutes_per_year),
            )
            events.append(
                Event(
                    event_id=event_id,
                    process_id=self.process_id,
                    event_type="fire",
                    time=time,
                    year=context.year,
                    phase="propagation",
                    source=GROWTH_FIRE_SOURCE,
                    scenario_id=context.scenario_id,
                    fragment_ids=(entry.fragment_id,),
                    severity_value=fraction,
                    magnitude=fraction,
                    area_ha=min(entry.area_ha, area),
                    confidence=1.0,
                    attributes=(
                        ("growth_model", GROWTH_FIRE_SOURCE),
                        ("ignition_event_id", f"growth-{context.year}"),
                        ("ignition_time_min", entry.ignition_time_min),
                        ("burned_cells", float(entry.burned_cells)),
                    ),
                )
            )
        return tuple(sorted(events, key=lambda event: event.sort_key))

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Apply one growth fire event.

        Parameters
        ----------
        state : CohortState
            The current state.
        event : Event
            A growth fire event.

        Returns
        -------
        CohortState
            The updated state.
        """
        return self.apply_many(state, (event,))

    def apply_many(self, state: CohortState, events: Sequence[Event]) -> CohortState:
        """Apply growth fire mortality in one vectorized pass.

        Parameters
        ----------
        state : CohortState
            The current state.
        events : sequence of Event
            Growth fire events.

        Returns
        -------
        CohortState
            The updated state.
        """
        process = FireProcess(
            FireConfig(snag_fraction=self.snag_fraction, batch_fire=True),
            (),
            RandomTape(0),
            scenario_id=self.scenario_id,
        )
        return process.apply_many(state, events)


@dataclass(frozen=True)
class SurvivalIgnition:
    """One ignition with the weather and duration inputs for survival.

    Parameters
    ----------
    cell : tuple of int
        Ignition cell as ``(row, col)``.
    active_days : float
        Active-spread duration in days.
    fwi : float
        Fire Weather Index at ignition.
    bui : float
        Buildup Index at ignition.
    wind_kmh : float
        Ten-metre wind speed at ignition.
    fuel_hazard : float, optional
        Additional fuel/landscape hazard contribution (default zero).
    active_hours_per_day : float, optional
        Hours of active spread per day (default 24).
    """

    cell: tuple[int, int]
    active_days: float
    fwi: float
    bui: float
    wind_kmh: float
    fuel_hazard: float = 0.0
    active_hours_per_day: float = 24.0

    def __post_init__(self) -> None:
        """Validate the ignition inputs."""
        if len(self.cell) != 2 or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in self.cell
        ):
            raise ValueError("survival ignition cells must be non-negative (row, col) pairs")
        for value, field in (
            (self.active_days, "active_days"),
            (self.fwi, "fwi"),
            (self.bui, "bui"),
            (self.wind_kmh, "wind_kmh"),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field} must be a number")
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise ValueError(f"{field} must be finite and non-negative")
        if not math.isfinite(self.fuel_hazard):
            raise ValueError("fuel_hazard must be finite")
        hours = self.active_hours_per_day
        if isinstance(hours, bool) or not isinstance(hours, (int, float)):
            raise ValueError("active_hours_per_day must be a number")
        if not math.isfinite(float(hours)) or not 0.0 < float(hours) <= 24.0:
            raise ValueError("active_hours_per_day must be in (0, 24]")


def _containment_ring(
    shape: tuple[int, int],
    cell: tuple[int, int],
    area_ha: float,
    cell_size_m: float,
) -> np.ndarray:
    """Build a closed containment ring around one ignition for a target area."""
    rows, cols = shape
    cell_area = cell_size_m * cell_size_m / 10_000.0
    radius = math.sqrt(max(area_ha, cell_area) / (math.pi * cell_area))
    rr = np.sqrt(
        (np.arange(rows)[:, None] - cell[0]) ** 2 + (np.arange(cols)[None, :] - cell[1]) ** 2
    )
    ring = (rr >= max(1.0, radius - 0.75)) & (rr < radius + 0.75)
    closure = np.full(shape, np.inf)
    closure[ring] = 0.0
    return closure


def build_survival_fire_source(
    grid: SiteGrid,
    config: GrowthConfig,
    fragment_grid: np.ndarray | FragmentSupport,
    ignitions_by_year: Mapping[int, Sequence[SurvivalIgnition]],
    survival: SurvivalConfig,
    *,
    seed: int = 0,
    scenario_id: str = "survival-fire",
    snag_fraction: float = 0.1,
    minutes_per_year: float = 525_600.0,
) -> GrowthFireSource:
    """Draw survival outcomes, grow each fire, and return the cohort adapter.

    Parameters
    ----------
    grid : SiteGrid
        Raster site grid.
    config : GrowthConfig
        Base growth configuration; time, containment, and area cap are replaced per fire.
    fragment_grid : numpy.ndarray or FragmentSupport
        Fragment raster or area-weighted support grid.
    ignitions_by_year : mapping of int to sequence of SurvivalIgnition
        Survival ignition inputs by simulation year.
    survival : SurvivalConfig
        Survival and escape parameters.
    seed : int, optional
        Deterministic survival seed (default zero).
    scenario_id : str, optional
        Scenario id stamped on events.
    snag_fraction : float, optional
        Fraction of killed biomass left as snags.
    minutes_per_year : float, optional
        Minutes per simulation year.

    Returns
    -------
    GrowthFireSource
        Adapter ready for the process executor.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if isinstance(fragment_grid, FragmentSupport):
        if (fragment_grid.rows, fragment_grid.cols) != (grid.rows, grid.cols):
            raise ValueError("fragment_grid shape must match the site grid")
        support: np.ndarray | FragmentSupport = fragment_grid
    else:
        arrays = np.asarray(fragment_grid)
        if arrays.ndim != 2 or not np.issubdtype(arrays.dtype, np.integer):
            raise ValueError("fragment_grid must be a two-dimensional integer array")
        if arrays.shape != (grid.rows, grid.cols):
            raise ValueError("fragment_grid shape must match the site grid")
        support = arrays
    drawn: dict[int, list[FragmentIgnition]] = {}
    for year, entries in sorted(ignitions_by_year.items()):
        if isinstance(year, bool) or not isinstance(year, int) or year < 0:
            raise ValueError("ignition years must be non-negative integers")
        drawn[year] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, SurvivalIgnition):
                raise ValueError("ignition entries must be SurvivalIgnition values")
            outcome = draw_survival(
                survival,
                random.Random(seed + year * 1_000_003 + index),
                active_days=entry.active_days,
                fwi=entry.fwi,
                bui=entry.bui,
                wind_kmh=entry.wind_kmh,
                fuel_hazard=entry.fuel_hazard,
            )
            closure = (
                None
                if outcome.escaped
                else _containment_ring(
                    (grid.rows, grid.cols),
                    entry.cell,
                    outcome.target_area_ha,
                    grid.cell_size_m,
                )
            )
            fire_config = replace(
                config,
                ignition_cells=(entry.cell,),
                max_time_min=max(1.0, entry.active_days * entry.active_hours_per_day * 60.0),
                max_burned_area_ha=outcome.max_burned_area_ha,
                containment_start_min=closure,
            )
            result = grow_fire(grid, fire_config)
            drawn[year].extend(fragment_ignition_times(result, support))
    return GrowthFireSource(
        ignitions={year: tuple(entries) for year, entries in drawn.items()},
        scenario_id=scenario_id,
        snag_fraction=snag_fraction,
        minutes_per_year=minutes_per_year,
    )


def build_two_stage_fire_source(
    grid: SiteGrid,
    config: GrowthConfig,
    fragment_grid: np.ndarray | FragmentSupport,
    ignitions_by_year: Mapping[int, Sequence[SurvivalIgnition]],
    survival: SurvivalConfig,
    *,
    seed: int = 0,
    scenario_id: str = "two-stage-fire",
    snag_fraction: float = 0.1,
    minutes_per_year: float = 525_600.0,
) -> GrowthFireSource:
    """Grow potential fires, then apply the survival containment/escape cap.

    Parameters
    ----------
    grid : SiteGrid
        Raster site grid.
    config : GrowthConfig
        Base growth configuration; time and area cap are replaced per fire.
    fragment_grid : numpy.ndarray or FragmentSupport
        Fragment raster or area-weighted support grid.
    ignitions_by_year : mapping of int to sequence of SurvivalIgnition
        Ignition and weather inputs by simulation year.
    survival : SurvivalConfig
        Contained and escaped size distributions.
    seed : int, optional
        Deterministic survival seed.
    scenario_id : str, optional
        Scenario id stamped on events.
    snag_fraction : float, optional
        Fraction of killed biomass left as snags.
    minutes_per_year : float, optional
        Minutes per simulation year.

    Returns
    -------
    GrowthFireSource
        Adapter ready for the process executor.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if isinstance(fragment_grid, FragmentSupport):
        if (fragment_grid.rows, fragment_grid.cols) != (grid.rows, grid.cols):
            raise ValueError("fragment_grid shape must match the site grid")
        support: np.ndarray | FragmentSupport = fragment_grid
    else:
        arrays = np.asarray(fragment_grid)
        if arrays.ndim != 2 or not np.issubdtype(arrays.dtype, np.integer):
            raise ValueError("fragment_grid must be a two-dimensional integer array")
        if arrays.shape != (grid.rows, grid.cols):
            raise ValueError("fragment_grid shape must match the site grid")
        support = arrays
    drawn: dict[int, list[FragmentIgnition]] = {}
    for year, entries in sorted(ignitions_by_year.items()):
        if isinstance(year, bool) or not isinstance(year, int) or year < 0:
            raise ValueError("ignition years must be non-negative integers")
        drawn[year] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, SurvivalIgnition):
                raise ValueError("ignition entries must be SurvivalIgnition values")
            outcome = draw_survival(
                survival,
                random.Random(seed + year * 1_000_003 + index),
                active_days=entry.active_days,
                fwi=entry.fwi,
                bui=entry.bui,
                wind_kmh=entry.wind_kmh,
                fuel_hazard=entry.fuel_hazard,
            )
            base = replace(
                config,
                ignition_cells=(entry.cell,),
                max_time_min=max(1.0, entry.active_days * entry.active_hours_per_day * 60.0),
                max_burned_area_ha=None,
                containment_start_min=None,
            )
            potential = grow_fire(grid, base)
            if potential.burned_area_ha > outcome.max_burned_area_ha:
                result = grow_fire(
                    grid,
                    replace(base, max_burned_area_ha=outcome.max_burned_area_ha),
                )
            else:
                result = potential
            drawn[year].extend(fragment_ignition_times(result, support))
    return GrowthFireSource(
        ignitions={year: tuple(entries) for year, entries in drawn.items()},
        scenario_id=scenario_id,
        snag_fraction=snag_fraction,
        minutes_per_year=minutes_per_year,
    )


def build_relative_fire_source(
    grid: SiteGrid,
    config: GrowthConfig,
    fragment_grid: np.ndarray | FragmentSupport,
    ignitions_by_year: Mapping[int, Sequence[SurvivalIgnition]],
    suppression: RelativeSuppressionConfig | Mapping[int, RelativeSuppressionConfig],
    *,
    region_grid: np.ndarray | None = None,
    seed: int = 0,
    scenario_id: str = "relative-fire",
    snag_fraction: float = 0.1,
    minutes_per_year: float = 525_600.0,
) -> GrowthFireSource:
    """Grow potential fires, then retain a relative suppression fraction.

    Parameters
    ----------
    grid : SiteGrid
        Raster site grid.
    config : GrowthConfig
        Base growth configuration; time and area cap are replaced per fire.
    fragment_grid : numpy.ndarray or FragmentSupport
        Fragment raster or area-weighted support grid.
    ignitions_by_year : mapping of int to sequence of SurvivalIgnition
        Ignition and weather inputs by year.
    suppression : RelativeSuppressionConfig or mapping of int to RelativeSuppressionConfig
        Relative contained/escaped fraction parameters, globally or by region id.
    region_grid : numpy.ndarray or None, optional
        Two-dimensional non-negative region ids used when ``suppression`` is a mapping.
    seed : int, optional
        Deterministic suppression seed.
    scenario_id : str, optional
        Scenario id stamped on events.
    snag_fraction : float, optional
        Fraction of killed biomass left as snags.
    minutes_per_year : float, optional
        Minutes per simulation year.

    Returns
    -------
    GrowthFireSource
        Adapter ready for the process executor.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    regioned = isinstance(suppression, Mapping)
    if regioned:
        if region_grid is None:
            raise ValueError("region_grid is required for region-level suppression")
        regions = np.asarray(region_grid)
        if (
            regions.ndim != 2
            or not np.issubdtype(regions.dtype, np.integer)
            or regions.shape != (grid.rows, grid.cols)
        ):
            raise ValueError("region_grid must be a two-dimensional integer grid")
        if bool((regions < 0).any()):
            raise ValueError("region_grid ids must be non-negative")
    if isinstance(fragment_grid, FragmentSupport):
        if (fragment_grid.rows, fragment_grid.cols) != (grid.rows, grid.cols):
            raise ValueError("fragment_grid shape must match the site grid")
        support: np.ndarray | FragmentSupport = fragment_grid
    else:
        arrays = np.asarray(fragment_grid)
        if arrays.ndim != 2 or not np.issubdtype(arrays.dtype, np.integer):
            raise ValueError("fragment_grid must be a two-dimensional integer array")
        if arrays.shape != (grid.rows, grid.cols):
            raise ValueError("fragment_grid shape must match the site grid")
        support = arrays
    drawn: dict[int, list[FragmentIgnition]] = {}
    for year, entries in sorted(ignitions_by_year.items()):
        if isinstance(year, bool) or not isinstance(year, int) or year < 0:
            raise ValueError("ignition years must be non-negative integers")
        drawn[year] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, SurvivalIgnition):
                raise ValueError("ignition entries must be SurvivalIgnition values")
            base = replace(
                config,
                ignition_cells=(entry.cell,),
                max_time_min=max(1.0, entry.active_days * entry.active_hours_per_day * 60.0),
                max_burned_area_ha=None,
                containment_start_min=None,
            )
            chosen = suppression
            if regioned:
                chosen = suppression[int(regions[entry.cell])]  # type: ignore[index]
            if not isinstance(chosen, RelativeSuppressionConfig):
                raise ValueError(
                    "suppression mapping must contain RelativeSuppressionConfig values"
                )
            potential = grow_fire(grid, base)
            outcome = draw_relative_suppression(
                chosen,
                random.Random(seed + year * 1_000_003 + index),
                potential_area_ha=potential.burned_area_ha,
                active_days=entry.active_days,
                fwi=entry.fwi,
                bui=entry.bui,
                wind_kmh=entry.wind_kmh,
                fuel_hazard=entry.fuel_hazard,
            )
            if potential.burned_area_ha > outcome.max_burned_area_ha:
                result = grow_fire(
                    grid,
                    replace(base, max_burned_area_ha=outcome.max_burned_area_ha),
                )
            else:
                result = potential
            drawn[year].extend(fragment_ignition_times(result, support))
    return GrowthFireSource(
        ignitions={year: tuple(entries) for year, entries in drawn.items()},
        scenario_id=scenario_id,
        snag_fraction=snag_fraction,
        minutes_per_year=minutes_per_year,
    )


def build_growth_fire_source(
    grid: SiteGrid,
    config: GrowthConfig,
    fragment_grid: np.ndarray | FragmentSupport,
    ignitions_by_year: Mapping[int, Sequence[tuple[int, int]]],
    *,
    scenario_id: str = "growth-fire",
    snag_fraction: float = 0.1,
    minutes_per_year: float = 525_600.0,
) -> GrowthFireSource:
    """Run one growth case per year and return the cohort adapter.

    Parameters
    ----------
    grid : SiteGrid
        Raster site grid.
    config : GrowthConfig
        Growth configuration; its ignition cells are replaced per year.
    fragment_grid : numpy.ndarray or FragmentSupport
        Two-dimensional fragment-id raster or an area-weighted support grid.
    ignitions_by_year : mapping of int to sequence of (int, int)
        Ignition cells for each year.
    scenario_id : str, optional
        Scenario id.
    snag_fraction : float, optional
        Fraction of killed biomass left as snags.
    minutes_per_year : float, optional
        Minutes per simulation year.

    Returns
    -------
    GrowthFireSource
        The adapter ready for the process executor.

    Raises
    ------
    ValueError
        If a year, cell, or growth result is invalid.
    """
    if isinstance(fragment_grid, FragmentSupport):
        if (fragment_grid.rows, fragment_grid.cols) != (grid.rows, grid.cols):
            raise ValueError("fragment_grid shape must match the site grid")
        support: np.ndarray | FragmentSupport = fragment_grid
    else:
        arrays = np.asarray(fragment_grid)
        if arrays.ndim != 2 or not np.issubdtype(arrays.dtype, np.integer):
            raise ValueError("fragment_grid must be a two-dimensional integer array")
        if arrays.shape != (grid.rows, grid.cols):
            raise ValueError("fragment_grid shape must match the site grid")
        support = arrays
    ignitions: dict[int, tuple[FragmentIgnition, ...]] = {}
    for year, cells in sorted(ignitions_by_year.items()):
        if isinstance(year, bool) or not isinstance(year, int) or year < 0:
            raise ValueError("ignition years must be non-negative integers")
        if not cells:
            ignitions[year] = ()
            continue
        result = grow_fire(grid, replace(config, ignition_cells=tuple(cells)))
        ignitions[year] = fragment_ignition_times(result, support)
    return GrowthFireSource(
        ignitions=ignitions,
        scenario_id=scenario_id,
        snag_fraction=snag_fraction,
        minutes_per_year=minutes_per_year,
    )
