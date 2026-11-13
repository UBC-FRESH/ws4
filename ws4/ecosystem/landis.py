"""LANDIS-II Biomass Succession kernel equations.

This is an original Python implementation of the published LANDIS-II Biomass Succession
equations. The Predictive Ecology ``Biomass_core`` tests are used as a reference oracle; no
third-party code is copied. The functions operate on a cohort table with the same columns used
by the published tests and by the WS4 cohort state.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

import numpy as np
import pandas as pd

from .events import Event
from .process import ProcessContext
from .state import CohortState

LANDIS_KERNEL_VERSION: Final[str] = "landis-biomass-succession-v3.2.1"
STAGES: Final[tuple[str, ...]] = ("spinup", "nonSpinup")


class LandisError(ValueError):
    """Raised when a LANDIS kernel input is invalid."""


def _stage(stage: str) -> str:
    """Return one of the two accepted stages."""
    if stage not in STAGES:
        raise LandisError(f"stage must be one of: {', '.join(STAGES)}")
    return stage


def _required(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    """Require columns and numeric values."""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise LandisError(f"cohort table is missing: {', '.join(missing)}")


def calculate_sum_b(
    cohort_data: pd.DataFrame,
    *,
    last_reg: int,
    current_time: int,
    succession_timestep: int,
) -> pd.DataFrame:
    """Return cohort data with LANDIS ``sumB`` per pixel group.

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``pixelGroup``, ``age``, and ``B``.
    last_reg : int
        Last regeneration time.
    current_time : int
        Current simulation time.
    succession_timestep : int
        Succession time step.

    Returns
    -------
    pandas.DataFrame
        A copy with the ``sumB`` column.
    """
    _required(cohort_data, ("pixelGroup", "age", "B"))
    if succession_timestep <= 0:
        raise LandisError("succession_timestep must be positive")
    frame = cohort_data.copy()
    if current_time == last_reg + succession_timestep - 2:
        include = frame["age"] > succession_timestep
    else:
        include = frame["age"] >= succession_timestep
    sums = frame.loc[include].groupby("pixelGroup", sort=False)["B"].sum()
    frame["sumB"] = frame["pixelGroup"].map(sums).fillna(0.0)
    return frame


def calculate_competition(cohort_data: pd.DataFrame, *, stage: str = "nonSpinup") -> pd.DataFrame:
    """Return cohort data with LANDIS ``bAP`` and ``bPM`` competition indices.

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``pixelGroup``, ``age``, ``B``, ``maxB``, and ``sumB``.
    stage : str, optional
        ``spinup`` or ``nonSpinup`` (default).

    Returns
    -------
    pandas.DataFrame
        A copy with ``bAP`` and ``bPM``.
    """
    stage = _stage(stage)
    _required(cohort_data, ("pixelGroup", "age", "B", "maxB", "sumB"))
    frame = cohort_data.copy()
    frame["bAP"] = np.nan
    frame["bPM"] = np.nan
    eligible = frame["age"] > 0 if stage == "spinup" else pd.Series(True, index=frame.index)
    if not bool(eligible.any()):
        return frame
    subset = frame.loc[eligible]
    potential = np.maximum(1.0, subset["maxB"] - subset["sumB"] + subset["B"])
    b_ap: pd.Series = subset["B"] / potential
    multiplier = np.maximum(np.power(np.maximum(subset["B"], 0.0), 0.95), 1.0)
    totals = (
        pd.Series(multiplier, index=subset.index).groupby(subset["pixelGroup"]).transform("sum")
    )
    frame.loc[eligible, "bAP"] = b_ap
    frame.loc[eligible, "bPM"] = multiplier / totals
    return frame


def calculate_anpp(cohort_data: pd.DataFrame, *, stage: str = "nonSpinup") -> pd.DataFrame:
    """Return cohort data with LANDIS actual ANPP (``aNPPAct``).

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``age``, ``bAP``, ``bPM``, ``growthcurve``, and ``maxANPP``.
    stage : str, optional
        ``spinup`` or ``nonSpinup`` (default).

    Returns
    -------
    pandas.DataFrame
        A copy with ``aNPPAct``.
    """
    stage = _stage(stage)
    _required(cohort_data, ("age", "bAP", "bPM", "growthcurve", "maxANPP"))
    frame = cohort_data.copy()
    frame["aNPPAct"] = np.nan
    eligible = frame["age"] > 0 if stage == "spinup" else pd.Series(True, index=frame.index)
    if not bool(eligible.any()):
        return frame
    subset = frame.loc[eligible]
    exponent = np.power(subset["bAP"], subset["growthcurve"])
    raw = subset["maxANPP"] * math.e * exponent * np.exp(-exponent) * subset["bPM"]
    frame.loc[eligible, "aNPPAct"] = np.minimum(subset["maxANPP"] * subset["bPM"], raw)
    return frame


def calculate_growth_mortality(
    cohort_data: pd.DataFrame, *, stage: str = "nonSpinup"
) -> pd.DataFrame:
    """Return cohort data with LANDIS developmental mortality (``mBio``).

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``age``, ``B``, ``bAP``, ``bPM``, and ``maxANPP``.
    stage : str, optional
        ``spinup`` or ``nonSpinup`` (default).

    Returns
    -------
    pandas.DataFrame
        A copy with ``mBio``.
    """
    stage = _stage(stage)
    _required(cohort_data, ("age", "B", "bAP", "bPM", "maxANPP"))
    frame = cohort_data.copy()
    frame["mBio"] = np.nan
    eligible = frame["age"] > 0 if stage == "spinup" else pd.Series(True, index=frame.index)
    if not bool(eligible.any()):
        return frame
    subset = frame.loc[eligible]
    base = np.where(
        subset["bAP"] > 1.0,
        subset["maxANPP"] * subset["bPM"],
        subset["maxANPP"] * (2.0 * subset["bAP"]) / (1.0 + subset["bAP"]) * subset["bPM"],
    )
    capped = np.minimum(np.minimum(subset["B"], base), subset["maxANPP"] * subset["bPM"])
    frame.loc[eligible, "mBio"] = capped
    return frame


def calculate_age_mortality(
    cohort_data: pd.DataFrame,
    *,
    stage: str = "nonSpinup",
    spinup_mortality_fraction: float = 0.0,
) -> pd.DataFrame:
    """Return cohort data with LANDIS age-related mortality (``mAge``).

    Parameters
    ----------
    cohort_data : pandas.DataFrame
        Cohort table with ``age``, ``B``, ``longevity``, and ``mortalityshape``.
    stage : str, optional
        ``spinup`` or ``nonSpinup`` (default).
    spinup_mortality_fraction : float, optional
        Additional annual mortality during spin-up (default zero).

    Returns
    -------
    pandas.DataFrame
        A copy with ``mAge``.
    """
    stage = _stage(stage)
    _required(cohort_data, ("age", "B", "longevity", "mortalityshape"))
    if spinup_mortality_fraction < 0.0 or not math.isfinite(spinup_mortality_fraction):
        raise LandisError("spinup_mortality_fraction must be finite and non-negative")
    frame = cohort_data.copy()
    frame["mAge"] = np.nan
    eligible = frame["age"] > 0 if stage == "spinup" else pd.Series(True, index=frame.index)
    if not bool(eligible.any()):
        return frame
    subset = frame.loc[eligible]
    age_mortality = subset["B"] * (
        np.exp((subset["age"] / subset["longevity"]) * subset["mortalityshape"])
        / np.exp(subset["mortalityshape"])
    )
    if stage == "spinup":
        age_mortality = age_mortality + subset["B"] * spinup_mortality_fraction
    frame.loc[eligible, "mAge"] = np.minimum(subset["B"], age_mortality)
    return frame


@dataclass(frozen=True)
class LandisSpeciesTraits:
    """Provisional LANDIS traits for one species.

    Parameters
    ----------
    max_b : float
        Maximum cohort biomass.
    max_anpp : float
        Maximum aboveground net primary productivity.
    growthcurve : float
        LANDIS growth-curve exponent.
    mortalityshape : float
        LANDIS age-mortality shape.
    longevity : float
        Species longevity.
    fuel_fraction : float
        Fuel as a fraction of live biomass.
    snag_decay_rate : float
        Annual snag decay fraction.
    """

    max_b: float = 300.0
    max_anpp: float = 500.0
    growthcurve: float = 0.25
    mortalityshape: float = 2.0
    longevity: float = 150.0
    fuel_fraction: float = 0.15
    snag_decay_rate: float = 0.05

    def __post_init__(self) -> None:
        """Validate the trait values."""
        for name in ("max_b", "max_anpp", "longevity"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise LandisError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        for name in ("growthcurve", "mortalityshape", "fuel_fraction", "snag_decay_rate"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise LandisError(f"{name} must be non-negative")
            if name in {"fuel_fraction", "snag_decay_rate"} and value > 1.0:
                raise LandisError(f"{name} must be between 0 and 1")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class LandisSuccessionConfig:
    """Configuration for the LANDIS succession process.

    Parameters
    ----------
    species : mapping of str to LandisSpeciesTraits
        Species-specific traits.
    default : LandisSpeciesTraits
        Traits for species not listed.
    succession_timestep : int, optional
        Succession step passed to the sumB kernel (default 1).
    stage : str, optional
        ``nonSpinup`` (default) or ``spinup``.
    """

    species: Mapping[str, LandisSpeciesTraits] = field(default_factory=dict)
    default: LandisSpeciesTraits = field(default_factory=LandisSpeciesTraits)
    succession_timestep: int = 1
    stage: str = "nonSpinup"

    def __post_init__(self) -> None:
        """Validate the configuration."""
        if not isinstance(self.species, Mapping):
            raise LandisError("species must be a mapping")
        for name, traits in self.species.items():
            if not isinstance(name, str) or not name.strip():
                raise LandisError("species names must be non-empty")
            if not isinstance(traits, LandisSpeciesTraits):
                raise LandisError("species values must be LandisSpeciesTraits")
        if not isinstance(self.default, LandisSpeciesTraits):
            raise LandisError("default must be LandisSpeciesTraits")
        if self.succession_timestep < 1:
            raise LandisError("succession_timestep must be positive")
        _stage(self.stage)

    def traits(self, species: str) -> LandisSpeciesTraits:
        """Return traits for one species.

        Parameters
        ----------
        species : str
            Species label.

        Returns
        -------
        LandisSpeciesTraits
            Species-specific traits or the default.
        """
        return self.species.get(species, self.default)


class LandisSuccessionProcess:
    """Run one annual LANDIS succession transition per fragment.

    Parameters
    ----------
    config : LandisSuccessionConfig, optional
        Species traits and kernel settings.
    """

    process_id: str = "landis-succession"
    phases: tuple[str, ...] = ("growth",)
    state_reads: frozenset[str] = frozenset({"age", "biomass_t_ha", "fuel_t_ha", "snag_t_ha"})
    state_writes: frozenset[str] = frozenset({"age", "biomass_t_ha", "fuel_t_ha", "snag_t_ha"})

    def __init__(self, config: LandisSuccessionConfig | None = None) -> None:
        """Retain the configuration."""
        self.config = config or LandisSuccessionConfig()

    def events(self, state: CohortState, context: ProcessContext) -> tuple[Event, ...]:
        """Return one succession event per covered fragment.

        Parameters
        ----------
        state : CohortState
            The current state.
        context : ProcessContext
            The annual context.

        Returns
        -------
        tuple of Event
            Succession events not already in the year.
        """
        existing = {event.event_id for event in context.year_events}
        events: list[Event] = []
        for fragment in sorted({int(value) for value in state.cohorts["fragment_id"]}):
            event_id = f"landis-succession-{context.year}-{fragment}"
            if event_id in existing:
                continue
            events.append(
                Event(
                    event_id=event_id,
                    process_id=self.process_id,
                    event_type="landis_succession",
                    time=float(context.year) + 0.5,
                    year=context.year,
                    phase="growth",
                    source="ws4.ecosystem.landis",
                    scenario_id=context.scenario_id,
                    fragment_ids=(fragment,),
                    area_ha=state.fragment_areas[fragment],
                )
            )
        return tuple(events)

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Apply one LANDIS succession transition.

        Parameters
        ----------
        state : CohortState
            The current state.
        event : Event
            A LANDIS succession event.

        Returns
        -------
        CohortState
            The updated state; other event types are returned unchanged.
        """
        if event.event_type != "landis_succession" or not event.fragment_ids:
            return state
        fragment = event.fragment_ids[0]
        frame = state.cohorts.copy()
        mask = frame["fragment_id"] == fragment
        if not bool(mask.any()):
            return state
        group = frame.loc[mask].copy()
        group["pixelGroup"] = fragment
        group["B"] = group["biomass_t_ha"].astype(float)
        group["maxB"] = [self.config.traits(str(species)).max_b for species in group["species"]]
        group["maxANPP"] = [
            self.config.traits(str(species)).max_anpp for species in group["species"]
        ]
        group["growthcurve"] = [
            self.config.traits(str(species)).growthcurve for species in group["species"]
        ]
        group["mortalityshape"] = [
            self.config.traits(str(species)).mortalityshape for species in group["species"]
        ]
        group["longevity"] = [
            self.config.traits(str(species)).longevity for species in group["species"]
        ]
        group = calculate_sum_b(
            group,
            last_reg=event.year - 1,
            current_time=event.year,
            succession_timestep=self.config.succession_timestep,
        )
        group = calculate_competition(group, stage=self.config.stage)
        group = calculate_anpp(group, stage=self.config.stage)
        group = calculate_growth_mortality(group, stage=self.config.stage)
        group = calculate_age_mortality(group, stage=self.config.stage)
        for index, row in group.iterrows():
            traits = self.config.traits(str(row["species"]))
            biomass = (
                float(row["B"]) + float(row["aNPPAct"]) - float(row["mBio"]) - float(row["mAge"])
            )
            biomass = max(0.0, min(traits.max_b, biomass))
            frame.at[index, "age"] = int(row["age"]) + 1
            frame.at[index, "biomass_t_ha"] = biomass
            frame.at[index, "fuel_t_ha"] = max(
                float(row["fuel_t_ha"]), biomass * traits.fuel_fraction
            )
            frame.at[index, "snag_t_ha"] = max(
                0.0, float(row["snag_t_ha"]) * (1.0 - traits.snag_decay_rate)
            )
        return CohortState(
            cohorts=frame.reset_index(drop=True),
            schema=state.schema,
            fragment_areas=state.fragment_areas,
        )
