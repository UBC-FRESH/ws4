"""Deterministic succession for the stochastic landscape engine.

P180 adds the first living ecological process. Succession advances cohort age, grows biomass
toward a species maximum, accumulates fuel as a fraction of biomass, and decays snags. It is a
bounded, transparent process: the parameters are explicit and no observed calibration is
claimed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from .events import Event
from .process import ProcessContext
from .state import CohortState

SUCCESSION_PROCESS_ID: Final[str] = "succession"
SUCCESSION_SOURCE: Final[str] = "ws4.ecosystem.succession"


class SuccessionError(RuntimeError):
    """Raised when succession parameters or state are invalid."""


def _positive(value: object, field: str) -> float:
    """Return a finite, positive float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SuccessionError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise SuccessionError(f"{field} must be positive")
    return number


def _probability(value: object, field: str) -> float:
    """Return a finite probability in [0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SuccessionError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise SuccessionError(f"{field} must be between 0 and 1")
    return number


@dataclass(frozen=True)
class SpeciesGrowth:
    """Provisional growth parameters for one species.

    Parameters
    ----------
    max_biomass_t_ha : float
        Asymptotic live biomass.
    growth_rate : float
        Annual logistic growth rate.
    fuel_fraction : float
        Fuel biomass as a fraction of live biomass.
    snag_decay_rate : float
        Annual fraction of snag biomass lost.
    """

    max_biomass_t_ha: float = 300.0
    growth_rate: float = 0.06
    fuel_fraction: float = 0.15
    snag_decay_rate: float = 0.05

    def __post_init__(self) -> None:
        """Validate the growth parameters."""
        object.__setattr__(
            self, "max_biomass_t_ha", _positive(self.max_biomass_t_ha, "max_biomass_t_ha")
        )
        object.__setattr__(self, "growth_rate", _positive(self.growth_rate, "growth_rate"))
        object.__setattr__(self, "fuel_fraction", _probability(self.fuel_fraction, "fuel_fraction"))
        object.__setattr__(
            self, "snag_decay_rate", _probability(self.snag_decay_rate, "snag_decay_rate")
        )


@dataclass(frozen=True)
class SuccessionConfig:
    """Configuration for the succession process.

    Parameters
    ----------
    species : mapping of str to SpeciesGrowth
        Species-specific parameters.
    default : SpeciesGrowth
        Parameters for species not listed. The defaults are provisional.
    """

    species: Mapping[str, SpeciesGrowth] = field(default_factory=dict)
    default: SpeciesGrowth = field(default_factory=SpeciesGrowth)

    def __post_init__(self) -> None:
        """Validate the parameter map."""
        if not isinstance(self.species, Mapping):
            raise SuccessionError("species must be a mapping")
        for name, params in self.species.items():
            if not isinstance(name, str) or not name.strip():
                raise SuccessionError("species names must be non-empty strings")
            if not isinstance(params, SpeciesGrowth):
                raise SuccessionError("species values must be SpeciesGrowth")
        if not isinstance(self.default, SpeciesGrowth):
            raise SuccessionError("default must be SpeciesGrowth")

    def parameters(self, species: str) -> SpeciesGrowth:
        """Return the parameters for one species.

        Parameters
        ----------
        species : str
            The species label.

        Returns
        -------
        SpeciesGrowth
            Species-specific parameters or the default.
        """
        return self.species.get(species, self.default)


class SuccessionProcess:
    """Age and grow cohorts deterministically.

    Parameters
    ----------
    config : SuccessionConfig, optional
        The growth parameters.
    """

    process_id: str = SUCCESSION_PROCESS_ID
    phases: tuple[str, ...] = ("growth",)
    state_reads: frozenset[str] = frozenset({"age", "biomass_t_ha", "fuel_t_ha", "snag_t_ha"})
    state_writes: frozenset[str] = frozenset({"age", "biomass_t_ha", "fuel_t_ha", "snag_t_ha"})

    def __init__(self, config: SuccessionConfig | None = None) -> None:
        """Retain the parameters."""
        self.config = config or SuccessionConfig()

    def events(self, state: CohortState, context: ProcessContext) -> Sequence[Event]:
        """Return one succession event per covered fragment.

        Parameters
        ----------
        state : CohortState
            The current cohort state.
        context : ProcessContext
            The annual context.

        Returns
        -------
        sequence of Event
            Succession events not already in the current year.
        """
        existing = {event.event_id for event in context.year_events}
        events: list[Event] = []
        for fragment in sorted({int(value) for value in state.cohorts["fragment_id"]}):
            event_id = f"succession-{context.year}-{fragment}"
            if event_id in existing:
                continue
            events.append(
                Event(
                    event_id=event_id,
                    process_id=self.process_id,
                    event_type="succession",
                    time=float(context.year) + 0.5,
                    year=context.year,
                    phase="growth",
                    source=SUCCESSION_SOURCE,
                    scenario_id=context.scenario_id,
                    fragment_ids=(fragment,),
                    area_ha=state.fragment_areas[fragment],
                )
            )
        return tuple(events)

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Advance one fragment's cohorts by one year.

        Parameters
        ----------
        state : CohortState
            The current state.
        event : Event
            A succession event.

        Returns
        -------
        CohortState
            The updated state; other event types are returned unchanged.
        """
        if event.event_type != "succession" or not event.fragment_ids:
            return state
        fragment = event.fragment_ids[0]
        frame = state.cohorts.copy()
        mask = frame["fragment_id"] == fragment
        if not bool(mask.any()):
            return state
        for index in frame.index[mask]:
            row = frame.loc[index]
            species = str(row["species"])
            params = self.config.parameters(species)
            biomass = max(0.0, float(row["biomass_t_ha"]))
            if 0.0 < biomass < params.max_biomass_t_ha:
                biomass = min(
                    params.max_biomass_t_ha,
                    biomass
                    + params.growth_rate * biomass * (1.0 - biomass / params.max_biomass_t_ha),
                )
            fuel = max(float(row["fuel_t_ha"]), biomass * params.fuel_fraction)
            snag = max(0.0, float(row["snag_t_ha"]) * (1.0 - params.snag_decay_rate))
            frame.at[index, "age"] = int(row["age"]) + 1
            frame.at[index, "biomass_t_ha"] = biomass
            frame.at[index, "fuel_t_ha"] = fuel
            frame.at[index, "snag_t_ha"] = snag
        return CohortState(
            cohorts=frame.reset_index(drop=True),
            schema=state.schema,
            fragment_areas=state.fragment_areas,
        )
