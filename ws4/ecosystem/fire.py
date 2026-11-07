"""The first stochastic landscape process: fire ignition, spread, effects, and salvage.

The process consumes the P144.2 event and tape contracts and the P144.3 cohort state. It is
deliberately a LANDIS-class skeleton, not a calibrated fire-behaviour model: a Poisson
ignition process, graph percolation over a landscape graph, severity and cohort mortality,
and a deterministic salvage source. The analytic oracles and the synthetic grid make the
behaviour checkable before calibration.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

import pandas as pd

from .events import Event
from .log import EventLog, EventLogBuilder, EventLogMetadata
from .state import BridgeSpec, CohortState, StateSchema, StateVariable
from .tape import DrawKey, RandomTape

FIRE_PROCESS_ID: Final[str] = "fire"
SALVAGE_PROCESS_ID: Final[str] = "salvage"
FIRE_SOURCE: Final[str] = "ws4.ecosystem.fire"
SALVAGE_SOURCE: Final[str] = "ws4.ecosystem.salvage"
SALVAGE_TIME: Final[float] = 0.999


class FireError(RuntimeError):
    """Raised when a fire configuration or run is invalid."""


def _finite(value: object, field: str) -> float:
    """Return a finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FireError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise FireError(f"{field} must be finite")
    return 0.0 if number == 0.0 else number


def _probability(value: object, field: str) -> float:
    """Return a probability in [0, 1]."""
    number = _finite(value, field)
    if number < 0.0 or number > 1.0:
        raise FireError(f"{field} must be between 0 and 1")
    return number


def _positive(value: object, field: str) -> float:
    """Return a finite, strictly positive float."""
    number = _finite(value, field)
    if number <= 0.0:
        raise FireError(f"{field} must be positive")
    return number


def _draw_index(kind: str, *parts: object) -> int:
    """Return a stable 64-bit draw index for a named draw."""
    payload = "\x1f".join([kind, *(str(part) for part in parts)]).encode()
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "little")


def _severity_class(severity: float) -> str:
    """Return the categorical severity class of a continuous severity."""
    if severity < 0.25:
        return "low"
    if severity < 0.5:
        return "moderate"
    if severity < 0.75:
        return "high"
    return "very_high"


@dataclass(frozen=True)
class FireEdge:
    """One undirected edge of the landscape graph.

    Parameters
    ----------
    source : int
        The first fragment id.
    target : int
        The second fragment id.
    distance_m : float, optional
        The edge distance in metres (default 0.0).
    bearing_deg : float or None, optional
        The compass bearing of the edge, in degrees clockwise from north. None means the
        edge carries no direction and wind does not favour either side.
    """

    source: int
    target: int
    distance_m: float = 0.0
    bearing_deg: float | None = None

    def __post_init__(self) -> None:
        """Validate the edge and normalize its bearing."""
        if isinstance(self.source, bool) or not isinstance(self.source, int) or self.source <= 0:
            raise FireError("source must be a positive integer")
        if isinstance(self.target, bool) or not isinstance(self.target, int) or self.target <= 0:
            raise FireError("target must be a positive integer")
        if self.source == self.target:
            raise FireError("source and target must differ")
        distance = _finite(self.distance_m, "distance_m")
        if distance < 0.0:
            raise FireError("distance_m must be non-negative")
        bearing = None if self.bearing_deg is None else _finite(self.bearing_deg, "bearing_deg")
        object.__setattr__(self, "distance_m", distance)
        object.__setattr__(self, "bearing_deg", None if bearing is None else bearing % 360.0)


@dataclass(frozen=True)
class FireConfig:
    """The parameters of the fire process and its salvage source.

    Parameters
    ----------
    ignition_rate_per_fragment_year : float, optional
        The Poisson ignition rate per eligible fragment-year (default 0.01).
    base_spread_probability : float, optional
        The base edge-crossing probability (default 0.45).
    fuel_reference_t_ha : float, optional
        The target fuel at which the fuel factor reaches one (default 20.0).
    distance_scale_m : float, optional
        The exponential distance decay scale in metres (default 250.0).
    wind_direction_deg : float or None, optional
        The wind direction in degrees clockwise from north. None disables wind.
    wind_strength : float, optional
        The wind strength in [0, 1] (default 0.0).
    severity_min : float, optional
        The minimum severity draw (default 0.2).
    severity_max : float, optional
        The maximum severity draw (default 1.0).
    mortality_factor : float, optional
        The fraction of the severity that kills a cohort (default 0.8).
    snag_fraction : float, optional
        The fraction of killed biomass left as snags (default 0.1).
    salvage_delay_years : int, optional
        The delay before a burned fragment is salvaged (default 1).
    salvage_volume_m3_per_t : float, optional
        The merchantable volume per tonne of snag (default 1.0).
    max_spread_steps : int, optional
        The maximum burned fragments per fire, a guard against a runaway run (default 10000).
    """

    ignition_rate_per_fragment_year: float = 0.01
    base_spread_probability: float = 0.45
    fuel_reference_t_ha: float = 20.0
    distance_scale_m: float = 250.0
    wind_direction_deg: float | None = None
    wind_strength: float = 0.0
    severity_min: float = 0.2
    severity_max: float = 1.0
    mortality_factor: float = 0.8
    snag_fraction: float = 0.1
    salvage_delay_years: int = 1
    salvage_volume_m3_per_t: float = 1.0
    max_spread_steps: int = 10_000

    def __post_init__(self) -> None:
        """Validate the configuration."""
        if self.ignition_rate_per_fragment_year < 0.0:
            raise FireError("ignition_rate_per_fragment_year must be non-negative")
        _finite(self.ignition_rate_per_fragment_year, "ignition_rate_per_fragment_year")
        _probability(self.base_spread_probability, "base_spread_probability")
        _positive(self.fuel_reference_t_ha, "fuel_reference_t_ha")
        _positive(self.distance_scale_m, "distance_scale_m")
        if self.wind_direction_deg is not None:
            _finite(self.wind_direction_deg, "wind_direction_deg")
        _probability(self.wind_strength, "wind_strength")
        _probability(self.severity_min, "severity_min")
        _probability(self.severity_max, "severity_max")
        if self.severity_min > self.severity_max:
            raise FireError("severity_min must not exceed severity_max")
        _probability(self.mortality_factor, "mortality_factor")
        _probability(self.snag_fraction, "snag_fraction")
        if isinstance(self.salvage_delay_years, bool) or not isinstance(
            self.salvage_delay_years, int
        ):
            raise FireError("salvage_delay_years must be an integer")
        if self.salvage_delay_years < 0:
            raise FireError("salvage_delay_years must be non-negative")
        if self.salvage_volume_m3_per_t < 0.0:
            raise FireError("salvage_volume_m3_per_t must be non-negative")
        _finite(self.salvage_volume_m3_per_t, "salvage_volume_m3_per_t")
        if isinstance(self.max_spread_steps, bool) or not isinstance(self.max_spread_steps, int):
            raise FireError("max_spread_steps must be an integer")
        if self.max_spread_steps <= 0:
            raise FireError("max_spread_steps must be positive")


class FireProcess:
    """Generate fire ignition and spread events and apply their cohort effects.

    Parameters
    ----------
    config : FireConfig
        The process parameters.
    edges : sequence of FireEdge
        The undirected landscape graph.
    tape : RandomTape
        The scenario's random tape.
    scenario_id : str, optional
        The scenario id stamped on every event (default ``fire``).
    """

    def __init__(
        self,
        config: FireConfig,
        edges: Sequence[FireEdge],
        tape: RandomTape,
        scenario_id: str = FIRE_PROCESS_ID,
    ) -> None:
        """Index the graph and retain the configuration and tape."""
        if not scenario_id.strip():
            raise FireError("scenario_id must be non-empty")
        self.config = config
        self.tape = tape
        self.scenario_id = scenario_id
        self._neighbors: dict[int, tuple[FireEdge, ...]] = {}
        for edge in edges:
            reverse = replace(
                edge,
                source=edge.target,
                target=edge.source,
                bearing_deg=(
                    None if edge.bearing_deg is None else (edge.bearing_deg + 180.0) % 360.0
                ),
            )
            self._neighbors.setdefault(edge.source, ())
            self._neighbors[edge.source] = (*self._neighbors[edge.source], edge)
            self._neighbors.setdefault(edge.target, ())
            self._neighbors[edge.target] = (*self._neighbors[edge.target], reverse)
        self._neighbors = {
            fragment: tuple(sorted(items, key=lambda item: (item.target, item.distance_m)))
            for fragment, items in self._neighbors.items()
        }

    def ignitions(self, state: CohortState, year: int) -> tuple[Event, ...]:
        """Return the ignition events of one year.

        Parameters
        ----------
        state : CohortState
            The current cohort state.
        year : int
            The annual accounting year.

        Returns
        -------
        tuple of Event
            The ignition events, sorted by their execution key.
        """
        if year < 0:
            raise FireError("year must be non-negative")
        fuel = self._fragment_values(state, "fuel_t_ha")
        events: list[Event] = []
        for fragment in sorted(fuel):
            if fuel[fragment] <= 0.0:
                continue
            key = DrawKey(FIRE_PROCESS_ID, fragment, year, 0)
            count = self.tape.poisson(key, self.config.ignition_rate_per_fragment_year)
            for index in range(int(count)):
                time = year + float(
                    self.tape.uniform(
                        DrawKey(
                            FIRE_PROCESS_ID,
                            fragment,
                            year,
                            _draw_index("ignition_time", fragment, index),
                        ),
                        0.0,
                        1.0,
                    )
                )
                events.append(
                    Event(
                        event_id=f"fire-ignition-{year}-{fragment}-{index}",
                        process_id=FIRE_PROCESS_ID,
                        event_type="fire_ignition",
                        time=time,
                        year=year,
                        phase="ignition",
                        source=FIRE_SOURCE,
                        scenario_id=self.scenario_id,
                        fragment_ids=(fragment,),
                        confidence=1.0,
                        attributes=(
                            ("ignition_count", int(count)),
                            ("ignition_index", index),
                        ),
                    )
                )
        return tuple(sorted(events, key=lambda event: event.sort_key))

    def spread(self, state: CohortState, ignition: Event) -> tuple[Event, ...]:
        """Propagate one ignition over the landscape graph.

        Parameters
        ----------
        state : CohortState
            The state at the start of the fire.
        ignition : Event
            The ignition event that starts the fire.

        Returns
        -------
        tuple of Event
            One ``fire`` event per burned fragment, sorted by the execution key.
        """
        if not ignition.fragment_ids:
            return ()
        start = ignition.fragment_ids[0]
        if start not in state.fragment_areas:
            return ()
        fuel = self._fragment_values(state, "fuel_t_ha")
        year = ignition.year
        burned: set[int] = set()
        events: list[Event] = []
        queue: deque[tuple[int, int, str]] = deque([(start, 0, ignition.event_id)])
        while queue and len(events) < self.config.max_spread_steps:
            fragment, depth, parent = queue.popleft()
            if fragment in burned:
                continue
            burned.add(fragment)
            severity = self._severity(fragment, year)
            mortality = min(1.0, severity * self.config.mortality_factor)
            event = Event(
                event_id=f"fire-{ignition.event_id}-{fragment}",
                process_id=FIRE_PROCESS_ID,
                event_type="fire",
                time=ignition.time,
                year=year,
                phase="propagation",
                source=FIRE_SOURCE,
                scenario_id=self.scenario_id,
                priority=depth,
                fragment_ids=(fragment,),
                severity_class=_severity_class(severity),
                severity_value=severity,
                magnitude=mortality,
                area_ha=state.fragment_areas[fragment],
                parent_event_id=parent,
                confidence=1.0,
                attributes=(
                    ("depth", depth),
                    ("ignition_event_id", ignition.event_id),
                    ("mortality_fraction", mortality),
                ),
            )
            events.append(event)
            for edge in self._neighbors.get(fragment, ()):
                if edge.target in burned:
                    continue
                probability = self._spread_probability(fuel.get(edge.target, 0.0), edge)
                key = DrawKey(
                    FIRE_PROCESS_ID,
                    edge.target,
                    year,
                    _draw_index("spread", edge.source, edge.target),
                )
                if self.tape.bernoulli(key, probability):
                    queue.append((edge.target, depth + 1, event.event_id))
        return tuple(sorted(events, key=lambda item: item.sort_key))

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Apply one fire event's mortality to the cohort state.

        Parameters
        ----------
        state : CohortState
            The current state.
        event : Event
            A ``fire`` event.

        Returns
        -------
        CohortState
            The updated state; other event types are returned unchanged.
        """
        if event.event_type != "fire" or not event.fragment_ids:
            return state
        mortality = event.magnitude
        if mortality is None or mortality <= 0.0:
            return state
        mortality = min(1.0, float(mortality))
        fragment = event.fragment_ids[0]
        frame = state.cohorts.copy()
        group = frame[frame["fragment_id"] == fragment]
        if group.empty:
            return state
        next_id = int(group["cohort_id"].max()) + 1
        drop: list[int] = []
        new_rows: list[dict[str, object]] = []
        for index, row in group.iterrows():
            fraction = float(row["area_fraction"])
            killed = fraction * mortality
            survivor = fraction - killed
            if survivor > 1e-12:
                frame.at[index, "area_fraction"] = survivor
            else:
                drop.append(int(str(index)))
            if killed > 1e-12:
                new_rows.append(
                    {
                        "fragment_id": fragment,
                        "cohort_id": next_id,
                        "species": str(row["species"]),
                        "age": 0,
                        "area_fraction": killed,
                        "biomass_t_ha": 0.0,
                        "fuel_t_ha": 0.0,
                        "snag_t_ha": float(row["biomass_t_ha"]) * self.config.snag_fraction,
                        "attributes_json": "{}",
                    }
                )
                next_id += 1
        if drop:
            frame = frame.drop(index=drop)
        if new_rows:
            frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)
        return CohortState(
            cohorts=frame.reset_index(drop=True),
            schema=state.schema,
            fragment_areas=state.fragment_areas,
        )

    def _severity(self, fragment: int, year: int) -> float:
        """Draw the severity of one burned fragment."""
        return float(
            self.tape.uniform(
                DrawKey(
                    FIRE_PROCESS_ID,
                    fragment,
                    year,
                    _draw_index("severity", fragment),
                ),
                self.config.severity_min,
                self.config.severity_max,
            )
        )

    def _spread_probability(self, target_fuel: float, edge: FireEdge) -> float:
        """Return the probability of crossing one edge into a target fragment."""
        fuel = min(1.0, max(0.0, target_fuel / self.config.fuel_reference_t_ha))
        distance = math.exp(-edge.distance_m / self.config.distance_scale_m)
        wind = 1.0
        if (
            self.config.wind_direction_deg is not None
            and self.config.wind_strength > 0.0
            and edge.bearing_deg is not None
        ):
            wind = max(
                0.0,
                1.0
                + self.config.wind_strength
                * math.cos(math.radians(edge.bearing_deg - self.config.wind_direction_deg)),
            )
        probability = self.config.base_spread_probability * fuel * distance * wind
        return min(1.0, max(0.0, probability))

    def _fragment_values(self, state: CohortState, column: str) -> dict[int, float]:
        """Return one area-weighted fragment value from the cohort state."""
        aggregate = state.aggregate_to_fragments()
        if aggregate.empty:
            return {}
        values = aggregate.set_index("fragment_id")[column].to_dict()
        return {int(str(fragment)): float(str(value)) for fragment, value in values.items()}


class SalvageSource:
    """Generate and apply salvage events for burned fragments.

    Parameters
    ----------
    config : FireConfig
        The fire configuration, which carries the salvage delay and volume rate.
    scenario_id : str, optional
        The scenario id stamped on every event (default ``fire``).
    """

    def __init__(self, config: FireConfig, scenario_id: str = FIRE_PROCESS_ID) -> None:
        """Retain the configuration and start with no salvaged fragments."""
        if not scenario_id.strip():
            raise FireError("scenario_id must be non-empty")
        self.config = config
        self.scenario_id = scenario_id
        self._salvaged: set[str] = set()

    def events(self, state: CohortState, year: int, fires: Sequence[Event]) -> tuple[Event, ...]:
        """Return salvage events for eligible fires.

        Parameters
        ----------
        state : CohortState
            The state after the year's fires.
        year : int
            The annual accounting year.
        fires : sequence of Event
            The fire events seen so far.

        Returns
        -------
        tuple of Event
            The new salvage events, sorted by their execution key.
        """
        events: list[Event] = []
        for fire in sorted(fires, key=lambda item: item.sort_key):
            if fire.event_type != "fire" or not fire.fragment_ids:
                continue
            if fire.year + self.config.salvage_delay_years > year:
                continue
            if fire.event_id in self._salvaged:
                continue
            fragment = fire.fragment_ids[0]
            volume = self._volume(state, fragment)
            if volume <= 0.0:
                continue
            event = Event(
                event_id=f"salvage-{fire.event_id}",
                process_id=SALVAGE_PROCESS_ID,
                event_type="salvage",
                time=year + SALVAGE_TIME,
                year=year,
                phase="treatment",
                source=SALVAGE_SOURCE,
                scenario_id=self.scenario_id,
                fragment_ids=(fragment,),
                block_ids=fire.block_ids,
                magnitude=volume,
                area_ha=fire.area_ha,
                parent_event_id=fire.event_id,
                confidence=1.0,
                attributes=(
                    ("fire_event_id", fire.event_id),
                    ("volume_m3", volume),
                ),
            )
            events.append(event)
            self._salvaged.add(fire.event_id)
        return tuple(sorted(events, key=lambda event: event.sort_key))

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Remove the salvaged snags from the cohort state.

        Parameters
        ----------
        state : CohortState
            The current state.
        event : Event
            A ``salvage`` event.

        Returns
        -------
        CohortState
            The updated state; other event types are returned unchanged.
        """
        if event.event_type != "salvage" or not event.fragment_ids:
            return state
        fragment = event.fragment_ids[0]
        frame = state.cohorts.copy()
        mask = frame["fragment_id"] == fragment
        if not bool(mask.any()):
            return state
        frame.loc[mask, "snag_t_ha"] = 0.0
        return CohortState(
            cohorts=frame.reset_index(drop=True),
            schema=state.schema,
            fragment_areas=state.fragment_areas,
        )

    def _volume(self, state: CohortState, fragment: int) -> float:
        """Return the salvage volume of one fragment, in cubic metres."""
        area = state.fragment_areas.get(fragment)
        if area is None:
            return 0.0
        group = state.cohorts[state.cohorts["fragment_id"] == fragment]
        if group.empty:
            return 0.0
        return float(
            (
                group["snag_t_ha"]
                * group["area_fraction"]
                * area
                * self.config.salvage_volume_m3_per_t
            ).sum()
        )


@dataclass(frozen=True)
class FireResult:
    """The output of one fire run.

    Attributes
    ----------
    state : CohortState
        The final cohort state.
    log : EventLog
        The replayable event log.
    accounts : pandas.DataFrame
        Account values with ``year``, ``account``, and ``value`` columns.
    fires : tuple of Event
        The fire events, in log order.
    salvage : tuple of Event
        The salvage events, in log order.
    start_year : int, optional
        The calendar year of simulation offset 0 (default 1900).
    """

    state: CohortState
    log: EventLog
    accounts: pd.DataFrame
    fires: tuple[Event, ...]
    salvage: tuple[Event, ...]
    start_year: int = 1900

    def write(self, out_dir: Path) -> None:
        """Write the event log, accounts, disturbance rows, and final cohorts.

        Parameters
        ----------
        out_dir : Path
            The output directory. It is created when missing.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.log.write(out_dir / "events.json")
        self.accounts.to_csv(out_dir / "accounts.csv", index=False)
        rows = [event.to_disturbance_dict(self.start_year) for event in self.fires]
        (out_dir / "disturbances.json").write_text(
            json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.state.cohorts.to_csv(out_dir / "cohorts.csv", index=False)
        summary = {
            "event_count": len(self.log.events),
            "fire_count": len(self.fires),
            "salvage_count": len(self.salvage),
            "replay_token": self.log.replay_token,
        }
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


class FireRun:
    """Run the fire process year by year over one cohort state.

    Parameters
    ----------
    state : CohortState
        The initial cohort state. The run mutates it; create a new run for a new scenario.
    edges : sequence of FireEdge
        The undirected landscape graph.
    config : FireConfig
        The fire and salvage configuration.
    scenario_id : str, optional
        The scenario id stamped on every event (default ``fire``).
    seed : int, optional
        The random-tape seed (default 0).
    package_hashes : sequence of (str, str) pairs, optional
        Package names and digests recorded in the event-log metadata.
    start_year : int, optional
        The calendar year of simulation offset 0 (default 1900).
    """

    def __init__(
        self,
        state: CohortState,
        edges: Sequence[FireEdge],
        config: FireConfig,
        scenario_id: str = FIRE_PROCESS_ID,
        seed: int = 0,
        package_hashes: Sequence[tuple[str, str]] = (),
        start_year: int = 1900,
    ) -> None:
        """Build the tape, process, salvage source, and event-log builder."""
        if isinstance(start_year, bool) or not isinstance(start_year, int) or start_year < 0:
            raise FireError("start_year must be a non-negative integer")
        self.state = state
        self.config = config
        self.scenario_id = scenario_id
        self.seed = seed
        self.start_year = start_year
        self.tape = RandomTape(seed)
        self.fire = FireProcess(config, edges, self.tape, scenario_id)
        self.salvage = SalvageSource(config, scenario_id)
        self.metadata = EventLogMetadata(
            scenario_id=scenario_id,
            scenario_seed=seed,
            package_hashes=tuple(package_hashes),
            attributes=(("calendar_start_year", start_year),),
        )
        self._builder = EventLogBuilder(self.metadata)
        self._fires: list[Event] = []
        self._salvage: list[Event] = []

    def run(self, years: int) -> FireResult:
        """Run the process for a number of years.

        Parameters
        ----------
        years : int
            The horizon in years.

        Returns
        -------
        FireResult
            The final state, event log, accounts, and events.
        """
        if isinstance(years, bool) or not isinstance(years, int) or years < 0:
            raise FireError("years must be a non-negative integer")
        rows: list[dict[str, object]] = []
        for year in range(years):
            year_events: list[Event] = []
            year_fires: list[Event] = []
            year_salvage: list[Event] = []
            burned_this_year: set[int] = set()
            ignitions = self.fire.ignitions(self.state, year)
            for ignition in ignitions:
                year_events.append(ignition)
                fragment = ignition.fragment_ids[0]
                if fragment in burned_this_year:
                    continue
                events = self.fire.spread(self.state, ignition)
                for event in events:
                    self.state = self.fire.apply(self.state, event)
                    burned_this_year.add(event.fragment_ids[0])
                    year_fires.append(event)
                    year_events.append(event)
            salvage_events = self.salvage.events(self.state, year, self._fires + year_fires)
            for event in salvage_events:
                self.state = self.salvage.apply(self.state, event)
                year_salvage.append(event)
                year_events.append(event)
            self._fires.extend(year_fires)
            self._salvage.extend(year_salvage)
            year_events.sort(key=lambda event: event.sort_key)
            self._builder.extend(year_events)
            rows.extend(self._account_rows(year, year_fires, year_salvage))
        return FireResult(
            state=self.state,
            log=self._builder.build(),
            accounts=pd.DataFrame(rows, columns=["year", "account", "value"]),
            fires=tuple(self._fires),
            salvage=tuple(self._salvage),
            start_year=self.start_year,
        )

    def _account_rows(
        self, year: int, fires: Sequence[Event], salvage: Sequence[Event]
    ) -> list[dict[str, object]]:
        """Return the account rows of one year."""
        burned_area = sum(float(event.area_ha) for event in fires if event.area_ha is not None)
        mortality_area = sum(
            float(event.area_ha) * float(event.magnitude)
            for event in fires
            if event.area_ha is not None and event.magnitude is not None
        )
        severity_area = sum(
            float(event.area_ha) * float(event.severity_value)
            for event in fires
            if event.area_ha is not None and event.severity_value is not None
        )
        salvage_area = sum(float(event.area_ha) for event in salvage if event.area_ha is not None)
        salvage_volume = sum(
            float(event.magnitude) for event in salvage if event.magnitude is not None
        )
        totals = self._state_totals()
        return [
            {"year": year, "account": "fire.count", "value": float(len(fires))},
            {"year": year, "account": "fire.burned_area_ha", "value": burned_area},
            {
                "year": year,
                "account": "fire.mortality_area_ha",
                "value": mortality_area,
            },
            {
                "year": year,
                "account": "fire.severity_area_weighted",
                "value": 0.0 if burned_area <= 0.0 else severity_area / burned_area,
            },
            {
                "year": year,
                "account": "salvage.count",
                "value": float(len(salvage)),
            },
            {
                "year": year,
                "account": "salvage.area_ha",
                "value": salvage_area,
            },
            {
                "year": year,
                "account": "salvage.volume_m3",
                "value": salvage_volume,
            },
            {"year": year, "account": "state.biomass_t", "value": totals["biomass_t"]},
            {"year": year, "account": "state.fuel_t", "value": totals["fuel_t"]},
            {"year": year, "account": "state.snag_t", "value": totals["snag_t"]},
        ]

    def _state_totals(self) -> dict[str, float]:
        """Return the cohort state's biomass, fuel, and snag totals."""
        frame = self.state.cohorts
        if frame.empty:
            return {"biomass_t": 0.0, "fuel_t": 0.0, "snag_t": 0.0}
        area = frame["fragment_id"].map(self.state.fragment_areas)
        weight = frame["area_fraction"] * area
        return {
            "biomass_t": float((frame["biomass_t_ha"] * weight).sum()),
            "fuel_t": float((frame["fuel_t_ha"] * weight).sum()),
            "snag_t": float((frame["snag_t_ha"] * weight).sum()),
        }


def synthetic_grid(
    rows: int = 5,
    cols: int = 5,
    *,
    fragment_area_ha: float = 10.0,
    species: str = "PL",
    age: int = 60,
    biomass_t_ha: float = 100.0,
    fuel_t_ha: float = 20.0,
    snag_t_ha: float = 2.0,
    distance_m: float = 100.0,
) -> tuple[StateSchema, CohortState, tuple[FireEdge, ...]]:
    """Build a synthetic square-grid landscape for the fire example and tests.

    Parameters
    ----------
    rows : int, optional
        The number of fragment rows (default 5).
    cols : int, optional
        The number of fragment columns (default 5).
    fragment_area_ha : float, optional
        The area of every fragment, in hectares (default 10.0).
    species : str, optional
        The synthetic species label (default ``PL``).
    age : int, optional
        The initial cohort age (default 60).
    biomass_t_ha : float, optional
        The initial live biomass (default 100.0).
    fuel_t_ha : float, optional
        The initial surface fuel (default 20.0).
    snag_t_ha : float, optional
        The initial snag load (default 2.0).
    distance_m : float, optional
        The edge distance in metres (default 100.0).

    Returns
    -------
    tuple of (StateSchema, CohortState, tuple of FireEdge)
        The schema, the initial state, and the undirected grid edges.
    """
    if isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0:
        raise FireError("rows must be a positive integer")
    if isinstance(cols, bool) or not isinstance(cols, int) or cols <= 0:
        raise FireError("cols must be a positive integer")
    variables = {
        "species": StateVariable("species", "string", "cohort", "", None, ""),
        "age": StateVariable("age", "int", "cohort", "years", None, ""),
        "area_fraction": StateVariable("area_fraction", "float", "cohort", "", None, ""),
        "biomass_t_ha": StateVariable("biomass_t_ha", "float", "cohort", "t/ha", 0.0, ""),
        "fuel_t_ha": StateVariable("fuel_t_ha", "float", "cohort", "t/ha", 0.0, ""),
        "snag_t_ha": StateVariable("snag_t_ha", "float", "cohort", "t/ha", 0.0, ""),
    }
    schema = StateSchema(
        variables=variables,
        bridges=(BridgeSpec("null", "null", {}, (), ()),),
    )
    fragment_areas = {
        row * cols + col + 1: float(fragment_area_ha) for row in range(rows) for col in range(cols)
    }
    cohorts = pd.DataFrame(
        [
            {
                "fragment_id": fragment,
                "cohort_id": 1,
                "species": species,
                "age": int(age),
                "area_fraction": 1.0,
                "biomass_t_ha": float(biomass_t_ha),
                "fuel_t_ha": float(fuel_t_ha),
                "snag_t_ha": float(snag_t_ha),
                "attributes_json": "{}",
            }
            for fragment in fragment_areas
        ],
        columns=[
            "fragment_id",
            "cohort_id",
            "species",
            "age",
            "area_fraction",
            "biomass_t_ha",
            "fuel_t_ha",
            "snag_t_ha",
            "attributes_json",
        ],
    )
    edges: list[FireEdge] = []
    for row in range(rows):
        for col in range(cols):
            fragment = row * cols + col + 1
            if col + 1 < cols:
                edges.append(FireEdge(fragment, fragment + 1, distance_m, 90.0))
            if row + 1 < rows:
                edges.append(FireEdge(fragment, fragment + cols, distance_m, 180.0))
    state = CohortState(
        cohorts=cohorts,
        schema=schema,
        fragment_areas=fragment_areas,
    )
    return schema, state, tuple(edges)


def run_fire_demo(*, rows: int = 5, cols: int = 5, years: int = 30, seed: int = 7) -> FireResult:
    """Run the synthetic fire example.

    Parameters
    ----------
    rows : int, optional
        The number of fragment rows (default 5).
    cols : int, optional
        The number of fragment columns (default 5).
    years : int, optional
        The horizon in years (default 30).
    seed : int, optional
        The random-tape seed (default 7).

    Returns
    -------
    FireResult
        The demo run.
    """
    _, state, edges = synthetic_grid(rows, cols)
    config = FireConfig(
        ignition_rate_per_fragment_year=0.02,
        base_spread_probability=0.5,
        distance_scale_m=150.0,
        wind_direction_deg=225.0,
        wind_strength=0.3,
    )
    return FireRun(state, edges, config, scenario_id="demo", seed=seed).run(years)
