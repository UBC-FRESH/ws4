"""Scenario and risk evaluation for the estate optimizer.

P181 adds a fast account-overlay risk path. It is deliberately not a stochastic ecological
simulation: one deterministic account frame is evaluated under several scenario multipliers,
the per-scenario frames are risk-aggregated, and the existing weighted-goal objective is
applied to the aggregated targets. Process-driven scenario simulation remains later work.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from ..ecosystem.scenarios import ScenarioSet, risk_account_values
from .objective import Target, objective


class RiskEvaluationError(ValueError):
    """Raised when a scenario overlay or risk objective is invalid."""


def apply_account_multipliers(
    values: pd.DataFrame,
    overrides: Mapping[str, object],
    scenario_id: str,
) -> pd.DataFrame:
    """Return one scenario's account values after account multipliers.

    Parameters
    ----------
    values : pandas.DataFrame
        Deterministic account values with ``offset``, ``account``, and ``value``.
    overrides : mapping of str to object
        Scenario overrides. The recognised key is ``account_multipliers``, a mapping of
        account name to a non-negative multiplier.
    scenario_id : str
        Scenario id added as the ``scenario`` column.

    Returns
    -------
    pandas.DataFrame
        A copy with scaled values and the scenario column.

    Raises
    ------
    RiskEvaluationError
        If the frame is missing a required column or a multiplier is invalid.
    """
    for column in ("offset", "account", "value"):
        if column not in values.columns:
            raise RiskEvaluationError(f"values need a {column!r} column")
    multipliers = overrides.get("account_multipliers", {})
    if multipliers is None:
        multipliers = {}
    if not isinstance(multipliers, Mapping):
        raise RiskEvaluationError("account_multipliers must be a mapping")
    cleaned: dict[str, float] = {}
    for account, raw in multipliers.items():
        if not isinstance(account, str) or not account.strip():
            raise RiskEvaluationError("account multiplier names must be non-empty strings")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise RiskEvaluationError(f"multiplier for {account!r} must be a number")
        value = float(raw)
        if not math.isfinite(value) or value < 0.0:
            raise RiskEvaluationError(f"multiplier for {account!r} must be finite and non-negative")
        cleaned[account] = value
    frame = values.copy()
    if cleaned:
        known = {str(account) for account in frame["account"].unique()}
        unknown = sorted(set(cleaned) - known)
        if unknown:
            raise RiskEvaluationError(f"unknown account multiplier(s): {', '.join(unknown)}")
        mask = frame["account"].astype(str).isin(cleaned)
        frame.loc[mask, "value"] = [
            float(value) * cleaned[str(account)]
            for value, account in zip(
                frame.loc[mask, "value"], frame.loc[mask, "account"], strict=True
            )
        ]
    frame["scenario"] = scenario_id
    return frame


@dataclass(frozen=True)
class RiskEvaluation:
    """The per-scenario, aggregated, and objective view of one decision.

    Attributes
    ----------
    values : pandas.DataFrame
        Per-scenario account values.
    aggregated : pandas.DataFrame
        Risk pseudo-account rows.
    targets : tuple of Target
        Effective targets after risk aggregation.
    objective : float
        Weighted-goal objective on the aggregated targets.
    """

    values: pd.DataFrame
    aggregated: pd.DataFrame
    targets: tuple[Target, ...]
    objective: float


class RiskAccountEvaluator:
    """Evaluate a deterministic account frame under a scenario ensemble.

    Parameters
    ----------
    scenarios : ScenarioSet
        The scenarios and their account multipliers.
    targets : sequence of Target
        Targets whose aggregation fields select the risk statistic.
    """

    def __init__(self, scenarios: ScenarioSet, targets: Sequence[Target]) -> None:
        """Retain the scenario set and targets."""
        if not scenarios.scenarios:
            raise RiskEvaluationError("a scenario set needs at least one scenario")
        self.scenarios = scenarios
        self.targets = tuple(targets)

    def evaluate(self, values: pd.DataFrame) -> RiskEvaluation:
        """Evaluate one deterministic frame under every scenario.

        Parameters
        ----------
        values : pandas.DataFrame
            The deterministic account values.

        Returns
        -------
        RiskEvaluation
            Per-scenario values, risk aggregation, effective targets, and objective.

        Raises
        ------
        RiskEvaluationError
            If a scenario multiplier or risk target is invalid.
        """
        frames = [
            apply_account_multipliers(values, scenario.overrides, scenario.scenario_id)
            for scenario in self.scenarios.scenarios
        ]
        combined = pd.concat(frames, ignore_index=True)
        try:
            aggregated, effective = risk_account_values(
                combined,
                self.targets,
                scenario_ids=self.scenarios.scenario_ids,
                weights=self.scenarios.weights(),
            )
        except Exception as error:
            raise RiskEvaluationError(str(error)) from error
        return RiskEvaluation(
            values=combined,
            aggregated=aggregated,
            targets=tuple(effective),
            objective=objective(aggregated, effective),
        )
