"""Optimizer account rows from process fire-regime summaries.

The process ensemble reports fire-regime distributions per scenario. This module maps those
summaries to the account-value frame the existing optimizer risk aggregation consumes. It does
not change the optimizer search or calibrate the fire model.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import pandas as pd

from ..fire.risk import FireRegimeRiskSummary
from .objective import Target, objective

PROCESS_FIRE_RISK_VERSION: Final[str] = "ws4.process-fire-risk-accounts.v1"


class ProcessFireRiskError(ValueError):
    """Raised when process fire-risk accounts are invalid."""


def _account(
    rows: list[dict[str, object]], *, offset: int, scenario: str, name: str, value: float
) -> None:
    """Append one finite account row.

    Parameters
    ----------
    rows : list of dict
        Destination rows.
    offset : int
        Account offset.
    scenario : str
        Scenario id.
    name : str
        Account name.
    value : float
        Account value.
    """
    if not math.isfinite(value):
        raise ProcessFireRiskError(f"account {name!r} must be finite")
    rows.append({"offset": offset, "account": name, "value": value, "scenario": scenario})


def fire_regime_account_values(
    summaries: Mapping[str, FireRegimeRiskSummary], *, years: int
) -> pd.DataFrame:
    """Convert per-scenario fire-regime summaries to optimizer account rows.

    Parameters
    ----------
    summaries : mapping of str to FireRegimeRiskSummary
        Fire-regime summaries by scenario id.
    years : int
        Number of simulated years.

    Returns
    -------
    pandas.DataFrame
        Rows with ``offset``, ``account``, ``value``, and ``scenario``.

    Raises
    ------
    ProcessFireRiskError
        If the horizon is invalid, the mapping is empty, or a summary value is not finite.
    """
    if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
        raise ProcessFireRiskError("years must be a positive integer")
    if not isinstance(summaries, Mapping) or not summaries:
        raise ProcessFireRiskError("summaries must be a non-empty mapping")
    rows: list[dict[str, object]] = []
    offset = years - 1
    for raw_scenario, summary in sorted(summaries.items()):
        if not isinstance(raw_scenario, str) or not raw_scenario.strip():
            raise ProcessFireRiskError("scenario ids must be non-empty strings")
        if not isinstance(summary, FireRegimeRiskSummary):
            raise ProcessFireRiskError("summaries must contain FireRegimeRiskSummary values")
        scenario = raw_scenario.strip()
        _account(
            rows,
            offset=offset,
            scenario=scenario,
            name="fire.regime.total_burned_ha",
            value=summary.total_burned_ha,
        )
        _account(
            rows,
            offset=offset,
            scenario=scenario,
            name="fire.regime.burn_probability",
            value=summary.burn_probability,
        )
        _account(
            rows,
            offset=offset,
            scenario=scenario,
            name="fire.regime.annual_burn_rate",
            value=summary.annual_burn_rate,
        )
        _account(
            rows,
            offset=offset,
            scenario=scenario,
            name="fire.regime.escaped_fires_per_year",
            value=summary.escaped_fires_per_year,
        )
        _account(
            rows,
            offset=offset,
            scenario=scenario,
            name="fire.regime.mean_fire_size_ha",
            value=summary.mean_fire_size_ha,
        )
        _account(
            rows,
            offset=offset,
            scenario=scenario,
            name="fire.regime.max_fire_size_ha",
            value=summary.max_fire_size_ha,
        )
        _account(
            rows,
            offset=offset,
            scenario=scenario,
            name="fire.regime.fire_count",
            value=float(summary.fire_count),
        )
        if summary.fire_return_interval_years is not None:
            _account(
                rows,
                offset=offset,
                scenario=scenario,
                name="fire.regime.fire_return_interval_years",
                value=summary.fire_return_interval_years,
            )
    return pd.DataFrame(rows, columns=["offset", "account", "value", "scenario"]).sort_values(
        ["scenario", "account"], ignore_index=True
    )


@dataclass(frozen=True)
class ProcessFireRiskReport:
    """Risk evaluation over process fire-regime summaries.

    Attributes
    ----------
    values : pandas.DataFrame
        Per-scenario fire-regime account rows.
    aggregated : pandas.DataFrame
        Risk pseudo-account rows.
    targets : tuple of Target
        Effective targets.
    objective : float
        Weighted objective on the aggregated targets.
    """

    values: pd.DataFrame
    aggregated: pd.DataFrame
    targets: tuple[Target, ...]
    objective: float

    def summary(self) -> dict[str, object]:
        """Return a stable summary.

        Returns
        -------
        dict
            Schema version, scenario count, aggregated account count, and objective.
        """
        return {
            "schema_version": PROCESS_FIRE_RISK_VERSION,
            "scenarios": sorted(self.values["scenario"].unique().tolist()),
            "aggregated_accounts": len(self.aggregated),
            "objective": self.objective,
        }


def evaluate_process_fire_risk(
    summaries: Mapping[str, FireRegimeRiskSummary],
    *,
    years: int,
    targets: Sequence[Target],
    scenario_ids: Sequence[str] | None = None,
    weights: Mapping[str, float] | None = None,
) -> ProcessFireRiskReport:
    """Risk-aggregate process fire-regime summaries with the existing objective.

    Parameters
    ----------
    summaries : mapping of str to FireRegimeRiskSummary
        Per-scenario fire-regime summaries.
    years : int
        Number of simulated years.
    targets : sequence of Target
        Risk-aggregated targets.
    scenario_ids : sequence of str or None, optional
        Full scenario list. None infers it from the account frame.
    weights : mapping of str to float or None, optional
        Scenario weights.

    Returns
    -------
    ProcessFireRiskReport
        Account values, aggregated rows, effective targets, and objective.

    Raises
    ------
    ProcessFireRiskError
        If no targets are supplied.
    """
    if not targets:
        raise ProcessFireRiskError("at least one target is required")
    from ..ecosystem.scenarios import risk_account_values

    values = fire_regime_account_values(summaries, years=years)
    aggregated, effective = risk_account_values(
        values,
        targets,
        scenario_ids=scenario_ids,
        weights=weights,
    )
    return ProcessFireRiskReport(
        values=values,
        aggregated=aggregated,
        targets=tuple(effective),
        objective=objective(aggregated, effective),
    )
