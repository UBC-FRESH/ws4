"""Process-conditioned evaluation of a block-level harvest schedule.

The estate optimizer still searches with account overlays. This module is the first bridge
from a schedule decision to the process engine: it maps blocks to fragments, runs the annual
fire/succession/regeneration/management processes, and returns a replayable final state plus
an account summary. It does not replace the optimizer loop.

The evaluation is deterministic for a given schedule and seed. The final account table is a
reporting view; the compiled management dataset remains authoritative for optimization.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from .bridge import SpeciesVolumeBridge, VolumeBridgeConfig
from .ensemble import ProcessEnsembleConfig, ProcessScenarioResult, run_process_scenario
from .fire import FireConfig, FireEdge
from .log import EventLog
from .management import ScheduleSource
from .process import Process
from .regeneration import RegenerationConfig
from .state import CohortState
from .succession import SuccessionConfig

PROCESS_EVALUATION_VERSION: Final[str] = "ws4.process-evaluation.v1"


class ProcessEvaluationError(ValueError):
    """Raised when a process schedule evaluation is invalid."""


def _float_value(value: object, field: str) -> float:
    """Return a finite float from a tabular value.

    Parameters
    ----------
    value : object
        Candidate value.
    field : str
        Field name for the error.

    Returns
    -------
    float
        The finite value.

    Raises
    ------
    ProcessEvaluationError
        If the value is not a finite number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProcessEvaluationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ProcessEvaluationError(f"{field} must be finite")
    return number


@dataclass(frozen=True)
class ProcessScheduleEvaluation:
    """One schedule evaluated through the process engine.

    Attributes
    ----------
    scenario_id : str
        Scenario id stamped on events.
    seed : int
        Random-tape seed.
    horizon_years : int
        Evaluation horizon.
    state : CohortState
        Final cohort state.
    log : EventLog
        Replayable event log.
    values : pandas.DataFrame
        Per-year process metrics with ``offset``, ``account``, and ``value``.
    accounts : pandas.DataFrame
        Final evaluation accounts with ``offset``, ``account``, and ``value``.
    """

    scenario_id: str
    seed: int
    horizon_years: int
    state: CohortState
    log: EventLog
    values: pd.DataFrame
    accounts: pd.DataFrame

    def summary(self) -> dict[str, object]:
        """Return a stable summary of the evaluation.

        Returns
        -------
        dict
            Schema version, scenario identity, final accounts, and event counts.
        """
        accounts = {
            str(row.account): _float_value(row.value, "account value")
            for row in self.accounts.itertuples(index=False)
        }
        counts = Counter(event.event_type for event in self.log.events)
        return {
            "schema_version": PROCESS_EVALUATION_VERSION,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "horizon_years": self.horizon_years,
            "final_offset": int(self.accounts["offset"].max()) if len(self.accounts) else 0,
            "accounts": dict(sorted(accounts.items())),
            "event_counts": dict(sorted(counts.items())),
        }

    def write(self, out_dir: Path) -> None:
        """Write values, accounts, and the summary.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.
        """
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        self.values.to_csv(target / "process_evaluation_values.csv", index=False)
        self.accounts.to_csv(target / "process_evaluation_accounts.csv", index=False)
        (target / "process_evaluation.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def _state_totals(state: CohortState) -> dict[str, float]:
    """Return area-weighted state totals.

    Parameters
    ----------
    state : CohortState
        The cohort state.

    Returns
    -------
    dict
        Biomass, fuel, and snag totals.
    """
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


def _value_total(values: pd.DataFrame, account: str) -> float:
    """Return the sum of one account over all years.

    Parameters
    ----------
    values : pandas.DataFrame
        Per-year metrics.
    account : str
        Account name.

    Returns
    -------
    float
        The sum, or zero when the account is absent.
    """
    if values.empty or account not in set(values["account"]):
        return 0.0
    return float(values.loc[values["account"] == account, "value"].sum())


def _accounts(
    result: ProcessScenarioResult,
    *,
    bridge_config: VolumeBridgeConfig,
    horizon_years: int,
) -> pd.DataFrame:
    """Build the final evaluation account table.

    Parameters
    ----------
    result : ProcessScenarioResult
        Process run.
    bridge_config : VolumeBridgeConfig
        Provisional volume bridge parameters.
    horizon_years : int
        Evaluation horizon.

    Returns
    -------
    pandas.DataFrame
        Rows with ``offset``, ``account``, and ``value``.
    """
    final_offset = max(0, horizon_years - 1)
    totals = _state_totals(result.state)
    volume = float(SpeciesVolumeBridge(bridge_config).table(result.state)["volume_m3"].sum())
    events = result.log.events
    harvest = [event for event in events if event.event_type == "harvest"]
    harvest_fragments = {fragment for event in harvest for fragment in event.fragment_ids}
    harvest_area = sum(
        result.state.fragment_areas.get(fragment, 0.0) for fragment in harvest_fragments
    )
    values = {
        "state.biomass_t": totals["biomass_t"],
        "state.fuel_t": totals["fuel_t"],
        "state.snag_t": totals["snag_t"],
        "bridge.volume_m3": volume,
        "fire.burned_area_ha_total": _value_total(result.values, "fire.burned_area_ha"),
        "fire.count_total": _value_total(result.values, "fire.count"),
        "harvest.count_total": float(len(harvest)),
        "harvest.area_ha_total": float(harvest_area),
        "salvage.count_total": _value_total(result.values, "salvage.count"),
        "regeneration.count_total": _value_total(result.values, "regeneration.count"),
    }
    return pd.DataFrame(
        [
            {"offset": final_offset, "account": account, "value": value}
            for account, value in sorted(values.items())
        ],
        columns=["offset", "account", "value"],
    )


def _positive_int(value: object, field: str) -> int:
    """Return a non-negative integer.

    Parameters
    ----------
    value : object
        Candidate value.
    field : str
        Field name for the error.

    Returns
    -------
    int
        The validated value.

    Raises
    ------
    ProcessEvaluationError
        If the value is not a non-negative integer.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProcessEvaluationError(f"{field} must be a non-negative integer")
    return value


def evaluate_process_schedule(
    state: CohortState,
    edges: Sequence[FireEdge],
    schedule: Mapping[int, Sequence[tuple[str, int]]],
    block_fragments: Mapping[int, Sequence[int]],
    *,
    horizon_years: int,
    fire: FireConfig,
    succession: SuccessionConfig | None = None,
    regeneration: RegenerationConfig | None = None,
    bridge: VolumeBridgeConfig | None = None,
    succession_process: Process | None = None,
    harvest_fraction: float = 1.0,
    scenario_id: str = "process-schedule",
    seed: int = 0,
) -> ProcessScheduleEvaluation:
    """Evaluate one block schedule through the process engine.

    Parameters
    ----------
    state : CohortState
        Initial cohort state.
    edges : sequence of FireEdge
        Landscape graph.
    schedule : mapping of int to sequence of (str, int)
        Block to ordered treatment/offset entries.
    block_fragments : mapping of int to sequence of int
        Block to fragment ids.
    horizon_years : int
        Evaluation horizon.
    fire : FireConfig
        Fire and salvage parameters.
    succession : SuccessionConfig or None, optional
        Default logistic succession parameters.
    regeneration : RegenerationConfig or None, optional
        Regeneration parameters.
    bridge : VolumeBridgeConfig or None, optional
        Provisional volume bridge parameters.
    succession_process : Process or None, optional
        Override the default succession source, e.g. a LANDIS process.
    harvest_fraction : float, optional
        Fraction of each live cohort removed by a harvest (default 1.0).
    scenario_id : str, optional
        Scenario id stamped on events (default ``process-schedule``).
    seed : int, optional
        Random-tape seed (default zero).

    Returns
    -------
    ProcessScheduleEvaluation
        Final state, log, per-year values, and final accounts.

    Raises
    ------
    ProcessEvaluationError
        If the horizon, seed, or scenario id is invalid.
    ManagementError
        If the schedule or block mapping is invalid.
    """
    horizon = _positive_int(horizon_years, "horizon_years")
    seed_value = _positive_int(seed, "seed")
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ProcessEvaluationError("scenario_id must be a non-empty string")
    source = ScheduleSource(
        schedule,
        block_fragments,
        harvest_fraction=harvest_fraction,
        scenario_id=scenario_id,
    )
    bridge_config = bridge or VolumeBridgeConfig()
    config = ProcessEnsembleConfig(
        horizon_years=horizon,
        fire=fire,
        succession=succession or SuccessionConfig(),
        regeneration=regeneration or RegenerationConfig(),
        bridge=bridge_config,
        management=source,
        succession_process=succession_process,
    )
    result = run_process_scenario(state, edges, config, scenario_id=scenario_id, seed=seed_value)
    return ProcessScheduleEvaluation(
        scenario_id=scenario_id,
        seed=seed_value,
        horizon_years=horizon,
        state=result.state,
        log=result.log,
        values=result.values,
        accounts=_accounts(result, bridge_config=bridge_config, horizon_years=horizon),
    )
