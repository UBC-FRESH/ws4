"""Stochastic juvenile establishment for the stochastic landscape engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from .events import Event
from .process import ProcessContext
from .state import CohortState
from .tape import DrawKey, RandomTape

REGENERATION_PROCESS_ID: Final[str] = "regeneration"
REGENERATION_SOURCE: Final[str] = "ws4.ecosystem.regeneration"


class RegenerationError(RuntimeError):
    """Raised when regeneration parameters are invalid."""


def _probability(value: object, field: str) -> float:
    """Return a finite probability in [0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegenerationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise RegenerationError(f"{field} must be between 0 and 1")
    return number


def _non_negative(value: object, field: str) -> float:
    """Return a finite, non-negative float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegenerationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise RegenerationError(f"{field} must be non-negative")
    return number


@dataclass(frozen=True)
class RegenerationConfig:
    """Provisional juvenile-establishment parameters.

    Parameters
    ----------
    establishment_probability : float
        Annual establishment probability for a juvenile fragment.
    max_regeneration_age : int
        Oldest juvenile age eligible for establishment.
    initial_biomass_t_ha : float
        Biomass assigned on establishment.
    initial_fuel_t_ha : float
        Fuel assigned on establishment.
    max_biomass_t_ha : float
        Juvenile biomass ceiling for eligibility.
    """

    establishment_probability: float = 0.25
    max_regeneration_age: int = 5
    initial_biomass_t_ha: float = 20.0
    initial_fuel_t_ha: float = 3.0
    max_biomass_t_ha: float = 25.0

    def __post_init__(self) -> None:
        """Validate the parameters."""
        object.__setattr__(
            self,
            "establishment_probability",
            _probability(self.establishment_probability, "establishment_probability"),
        )
        if (
            isinstance(self.max_regeneration_age, bool)
            or not isinstance(self.max_regeneration_age, int)
            or self.max_regeneration_age < 0
        ):
            raise RegenerationError("max_regeneration_age must be a non-negative integer")
        object.__setattr__(
            self,
            "initial_biomass_t_ha",
            _non_negative(self.initial_biomass_t_ha, "initial_biomass_t_ha"),
        )
        object.__setattr__(
            self, "initial_fuel_t_ha", _non_negative(self.initial_fuel_t_ha, "initial_fuel_t_ha")
        )
        object.__setattr__(
            self, "max_biomass_t_ha", _non_negative(self.max_biomass_t_ha, "max_biomass_t_ha")
        )


class RegenerationProcess:
    """Establish biomass in juvenile cohorts after disturbance.

    Parameters
    ----------
    config : RegenerationConfig, optional
        The establishment parameters.
    tape : RandomTape
        The scenario random tape.
    scenario_id : str, optional
        The scenario id stamped on events.
    """

    process_id: str = REGENERATION_PROCESS_ID
    phases: tuple[str, ...] = ("regeneration",)
    state_reads: frozenset[str] = frozenset({"age", "biomass_t_ha", "fuel_t_ha"})
    state_writes: frozenset[str] = frozenset({"biomass_t_ha", "fuel_t_ha"})

    def __init__(
        self,
        config: RegenerationConfig,
        tape: RandomTape,
        scenario_id: str = REGENERATION_PROCESS_ID,
    ) -> None:
        """Retain the configuration, tape, and scenario."""
        self.config = config
        self.tape = tape
        self.scenario_id = scenario_id
        self._year = -1
        self._done: set[str] = set()

    def _sync_year(self, year: int) -> None:
        """Reset per-year event bookkeeping."""
        if year != self._year:
            self._year = year
            self._done.clear()

    def events(self, state: CohortState, context: ProcessContext) -> tuple[Event, ...]:
        """Return establishment events for eligible fragments.

        Parameters
        ----------
        state : CohortState
            The current cohort state.
        context : ProcessContext
            The annual context.

        Returns
        -------
        tuple of Event
            Establishment events not yet emitted this year.
        """
        self._sync_year(context.year)
        events: list[Event] = []
        for fragment, group in state.cohorts.groupby("fragment_id", sort=True):
            key = f"regeneration-{context.year}-{int(str(fragment))}"
            if key in self._done:
                continue
            juvenile = group[
                (group["age"] <= self.config.max_regeneration_age)
                & (group["biomass_t_ha"] <= self.config.max_biomass_t_ha)
                & (group["area_fraction"] > 0.0)
            ]
            if juvenile.empty:
                continue
            draw = self.tape.bernoulli(
                DrawKey(REGENERATION_PROCESS_ID, int(str(fragment)), context.year, 0),
                self.config.establishment_probability,
            )
            if not draw:
                self._done.add(key)
                continue
            self._done.add(key)
            events.append(
                Event(
                    event_id=key,
                    process_id=self.process_id,
                    event_type="regeneration",
                    time=float(context.year) + 0.75,
                    year=context.year,
                    phase="regeneration",
                    source=REGENERATION_SOURCE,
                    scenario_id=context.scenario_id,
                    fragment_ids=(int(str(fragment)),),
                    area_ha=state.fragment_areas[int(str(fragment))],
                    attributes=(
                        ("establishment_probability", self.config.establishment_probability),
                        ("juvenile_cohorts", len(juvenile)),
                    ),
                )
            )
        return tuple(events)

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Establish biomass and fuel in eligible juvenile cohorts.

        Parameters
        ----------
        state : CohortState
            The current state.
        event : Event
            A regeneration event.

        Returns
        -------
        CohortState
            The updated state; other event types are returned unchanged.
        """
        if event.event_type != "regeneration" or not event.fragment_ids:
            return state
        fragment = event.fragment_ids[0]
        frame = state.cohorts.copy()
        mask = (
            (frame["fragment_id"] == fragment)
            & (frame["age"] <= self.config.max_regeneration_age)
            & (frame["biomass_t_ha"] <= self.config.max_biomass_t_ha)
        )
        if not bool(mask.any()):
            return state
        frame.loc[mask, "biomass_t_ha"] = frame.loc[mask, "biomass_t_ha"].clip(
            lower=self.config.initial_biomass_t_ha
        )
        frame.loc[mask, "fuel_t_ha"] = frame.loc[mask, "fuel_t_ha"].clip(
            lower=self.config.initial_fuel_t_ha
        )
        return CohortState(
            cohorts=frame.reset_index(drop=True),
            schema=state.schema,
            fragment_areas=state.fragment_areas,
        )
