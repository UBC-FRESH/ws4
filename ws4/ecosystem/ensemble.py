"""Process-driven scenario ensembles over the P179 executor.

The P181 optimizer risk path is an account overlay. This module runs the actual process engine:
fire, succession, salvage, and regeneration, one executor per scenario seed. It produces
per-year, account-like metrics and optionally risk-aggregates them with the existing scenario
layer. It does not yet bridge the resulting process state back into an estate schedule.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..opt.objective import Target
from .bridge import SpeciesVolumeBridge, VolumeBridgeConfig
from .executor import Executor
from .fire import (
    FireConfig,
    FireEdge,
    FireProcess,
    FireProcessSource,
    SalvageProcessSource,
    SalvageSource,
)
from .log import EventLog, EventLogMetadata
from .process import DecisionSource, Process
from .regeneration import RegenerationConfig, RegenerationProcess
from .scenarios import ScenarioSet, risk_account_values
from .state import CohortState
from .succession import SuccessionConfig, SuccessionProcess
from .tape import RandomTape

PROCESS_ENSEMBLE_VERSION = "ws4.process-ensemble.v1"


class ProcessEnsembleError(RuntimeError):
    """Raised when a process ensemble configuration is invalid."""


@dataclass(frozen=True)
class ProcessEnsembleConfig:
    """Configuration for one process scenario run.

    Parameters
    ----------
    horizon_years : int
        Simulation horizon.
    fire : FireConfig
        Fire and salvage parameters.
    succession : SuccessionConfig, optional
        Succession parameters.
    regeneration : RegenerationConfig, optional
        Regeneration parameters.
    bridge : VolumeBridgeConfig, optional
        Provisional volume bridge parameters.
    management : DecisionSource or None, optional
        A controlled management source, such as a schedule harvest source.
    succession_process : Process or None, optional
        Override the default logistic succession source, e.g. with a LANDIS process.
    """

    horizon_years: int
    fire: FireConfig
    succession: SuccessionConfig = field(default_factory=SuccessionConfig)
    regeneration: RegenerationConfig = field(default_factory=RegenerationConfig)
    bridge: VolumeBridgeConfig = field(default_factory=VolumeBridgeConfig)
    management: DecisionSource | None = None
    succession_process: Process | None = None

    def __post_init__(self) -> None:
        """Validate the horizon."""
        if (
            isinstance(self.horizon_years, bool)
            or not isinstance(self.horizon_years, int)
            or self.horizon_years < 0
        ):
            raise ProcessEnsembleError("horizon_years must be a non-negative integer")


@dataclass(frozen=True)
class ProcessScenarioResult:
    """One scenario's process run.

    Attributes
    ----------
    scenario_id : str
        Scenario id.
    seed : int
        Tape seed.
    state : CohortState
        Final state.
    log : EventLog
        Replayable event log.
    values : pandas.DataFrame
        Per-year metrics with ``offset``, ``account``, and ``value``.
    """

    scenario_id: str
    seed: int
    state: CohortState
    log: EventLog
    values: pd.DataFrame


@dataclass(frozen=True)
class ProcessEnsembleResult:
    """A process-driven scenario ensemble.

    Attributes
    ----------
    values : pandas.DataFrame
        Per-scenario, per-year metrics.
    aggregated : pandas.DataFrame
        Risk pseudo-account rows when targets were supplied.
    targets : tuple
        Effective risk targets.
    scenarios : tuple of ProcessScenarioResult
        Per-scenario runs.
    """

    values: pd.DataFrame
    aggregated: pd.DataFrame
    targets: tuple[Target, ...]
    scenarios: tuple[ProcessScenarioResult, ...]

    def summary(self) -> dict[str, object]:
        """Return a stable summary.

        Returns
        -------
        dict
            Schema version, scenario ids, and final metric means.
        """
        final = self.values[self.values["offset"] == self.values["offset"].max()]
        means = {
            str(account): float(group["value"].mean())
            for account, group in final.groupby("account", sort=True)
        }
        return {
            "schema_version": PROCESS_ENSEMBLE_VERSION,
            "scenarios": [result.scenario_id for result in self.scenarios],
            "metrics": means,
        }

    def write(self, out_dir: Path) -> None:
        """Write values, aggregated rows, and a summary.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.values.to_csv(out_dir / "process_values.csv", index=False)
        self.aggregated.to_csv(out_dir / "process_aggregated.csv", index=False)
        (out_dir / "process_summary.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def _copy_state(state: CohortState) -> CohortState:
    """Return an independent copy of a cohort state."""
    return CohortState(
        cohorts=state.cohorts.copy(deep=True),
        schema=state.schema,
        fragment_areas=dict(state.fragment_areas),
    )


def _totals(state: CohortState) -> dict[str, float]:
    """Return area-weighted state totals."""
    frame = state.cohorts
    if frame.empty:
        return {"biomass_t": 0.0, "fuel_t": 0.0, "snag_t": 0.0}
    area = frame["fragment_id"].map(state.fragment_areas)
    weight = frame["area_fraction"] * area
    return {
        "biomass_t": float((frame["biomass_t_ha"] * weight).sum()),
        "fuel_t": float((frame["fuel_t_ha"] * weight).sum()),
        "snag_t": float((frame["snag_t_ha"] * weight).sum()),
    }


def run_process_scenario(
    state: CohortState,
    edges: Sequence[FireEdge],
    config: ProcessEnsembleConfig,
    *,
    scenario_id: str,
    seed: int,
) -> ProcessScenarioResult:
    """Run fire, succession, salvage, regeneration, and the bridge for one scenario.

    Parameters
    ----------
    state : CohortState
        Initial state.
    edges : sequence of FireEdge
        Landscape graph.
    config : ProcessEnsembleConfig
        Process parameters.
    scenario_id : str
        Scenario id.
    seed : int
        Random-tape seed.

    Returns
    -------
    ProcessScenarioResult
        Final state, event log, and metric table.
    """
    if not scenario_id.strip():
        raise ProcessEnsembleError("scenario_id must be non-empty")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ProcessEnsembleError("seed must be a non-negative integer")
    tape = RandomTape(seed)
    fire = FireProcess(config.fire, edges, tape, scenario_id=scenario_id)
    salvage = SalvageSource(config.fire, scenario_id=scenario_id)
    regeneration = RegenerationProcess(config.regeneration, tape, scenario_id=scenario_id)
    succession = config.succession_process or SuccessionProcess(config.succession)
    sources: list[Process | DecisionSource] = [FireProcessSource(fire), succession]
    if config.management is not None:
        sources.append(config.management)
    sources.extend((SalvageProcessSource(salvage), regeneration))
    bridge = SpeciesVolumeBridge(config.bridge)
    rows: list[dict[str, object]] = []

    def on_year(year: int, current: CohortState, events: Sequence[object]) -> None:
        fires = [event for event in events if getattr(event, "event_type", "") == "fire"]
        burned = sum(float(getattr(event, "area_ha", 0.0) or 0.0) for event in fires)
        mortality = sum(
            float(getattr(event, "area_ha", 0.0) or 0.0)
            * float(getattr(event, "magnitude", 0.0) or 0.0)
            for event in fires
        )
        totals = _totals(current)
        volume = float(bridge.table(current)["volume_m3"].sum())
        counts = {
            event_type: sum(1 for event in events if getattr(event, "event_type", "") == event_type)
            for event_type in ("fire", "succession", "salvage", "regeneration")
        }
        values = {
            "fire.count": counts["fire"],
            "fire.burned_area_ha": burned,
            "fire.mortality_area_ha": mortality,
            "succession.count": counts["succession"],
            "salvage.count": counts["salvage"],
            "regeneration.count": counts["regeneration"],
            "state.biomass_t": totals["biomass_t"],
            "state.fuel_t": totals["fuel_t"],
            "state.snag_t": totals["snag_t"],
            "bridge.volume_m3": volume,
        }
        for account, value in values.items():
            rows.append({"offset": year, "account": account, "value": float(value)})

    executor = Executor(
        _copy_state(state),
        sources,
        EventLogMetadata(scenario_id=scenario_id, scenario_seed=seed),
        on_year=on_year,
    )
    result = executor.run(config.horizon_years)
    return ProcessScenarioResult(
        scenario_id=scenario_id,
        seed=seed,
        state=result.state,
        log=result.log,
        values=pd.DataFrame(rows, columns=["offset", "account", "value"]),
    )


def run_process_ensemble(
    state: CohortState,
    edges: Sequence[FireEdge],
    config: ProcessEnsembleConfig,
    scenarios: ScenarioSet,
    targets: Sequence[Target] = (),
) -> ProcessEnsembleResult:
    """Run one process scenario per scenario seed and aggregate risk targets.

    Parameters
    ----------
    state : CohortState
        Initial state.
    edges : sequence of FireEdge
        Landscape graph.
    config : ProcessEnsembleConfig
        Process parameters.
    scenarios : ScenarioSet
        Scenario seeds and weights.
    targets : sequence of Target, optional
        Risk-aggregated targets. Empty skips aggregation.

    Returns
    -------
    ProcessEnsembleResult
        Per-scenario runs and risk rows.
    """
    results: list[ProcessScenarioResult] = []
    frames: list[pd.DataFrame] = []
    for scenario in scenarios.scenarios:
        result = run_process_scenario(
            state, edges, config, scenario_id=scenario.scenario_id, seed=scenario.seed
        )
        results.append(result)
        frame = result.values.copy()
        frame["scenario"] = scenario.scenario_id
        frames.append(frame)
    values = pd.concat(frames, ignore_index=True)
    if targets:
        aggregated, effective = risk_account_values(
            values,
            targets,
            scenario_ids=scenarios.scenario_ids,
            weights=scenarios.weights(),
        )
    else:
        aggregated = pd.DataFrame(columns=["offset", "account", "value", "scenario"])
        effective = []
    return ProcessEnsembleResult(
        values=values,
        aggregated=aggregated,
        targets=tuple(effective),
        scenarios=tuple(results),
    )
