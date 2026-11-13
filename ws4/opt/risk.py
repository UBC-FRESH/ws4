"""Scenario and risk evaluation for the estate optimizer.

P181 adds a fast account-overlay risk path. It is deliberately not a stochastic ecological
simulation: one deterministic account frame is evaluated under several scenario multipliers,
the per-scenario frames are risk-aggregated, and the existing weighted-goal objective is
applied to the aggregated targets. Process-driven scenario simulation remains later work.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class RiskValidationReport:
    """A train-versus-validation risk comparison for one deterministic frame.

    Attributes
    ----------
    train : RiskEvaluation
        The training-scenario evaluation.
    validation : RiskEvaluation
        The held-out evaluation.
    train_fraction : float
        The fraction of scenarios assigned to training.
    """

    train: RiskEvaluation
    validation: RiskEvaluation
    train_fraction: float

    @property
    def gap(self) -> float:
        """Return the validation objective minus the training objective.

        Returns
        -------
        float
            The generalization gap; positive means validation is worse.
        """
        return self.validation.objective - self.train.objective

    def summary(self) -> dict[str, object]:
        """Return a stable summary of the report.

        Returns
        -------
        dict
            Training/validation scenario counts and objectives, the gap, and the fraction.
        """
        return {
            "train_fraction": self.train_fraction,
            "train_scenarios": len(self.train.values["scenario"].unique()),
            "validation_scenarios": len(self.validation.values["scenario"].unique()),
            "train_objective": self.train.objective,
            "validation_objective": self.validation.objective,
            "generalization_gap": self.gap,
        }

    def write(self, out_dir: Path) -> None:
        """Write train/validation values, aggregations, and a summary.

        Parameters
        ----------
        out_dir : Path
            The output directory, created when missing.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.train.values.to_csv(out_dir / "risk_train_values.csv", index=False)
        self.validation.values.to_csv(out_dir / "risk_validation_values.csv", index=False)
        self.train.aggregated.to_csv(out_dir / "risk_train_aggregated.csv", index=False)
        self.validation.aggregated.to_csv(out_dir / "risk_validation_aggregated.csv", index=False)
        (out_dir / "risk_validation.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def split_scenarios(
    scenarios: ScenarioSet,
    train_fraction: float = 0.7,
) -> tuple[ScenarioSet, ScenarioSet]:
    """Split a scenario set into ordered training and validation subsets.

    Parameters
    ----------
    scenarios : ScenarioSet
        The full ensemble.
    train_fraction : float, optional
        The fraction assigned to training, in (0, 1) (default 0.7).

    Returns
    -------
    tuple of ScenarioSet
        The training and validation sets.

    Raises
    ------
    RiskEvaluationError
        If the fraction is invalid or fewer than two scenarios are available.
    """
    if (
        isinstance(train_fraction, bool)
        or not isinstance(train_fraction, (int, float))
        or not math.isfinite(float(train_fraction))
        or not 0.0 < float(train_fraction) < 1.0
    ):
        raise RiskEvaluationError("train_fraction must be between 0 and 1")
    if len(scenarios.scenarios) < 2:
        raise RiskEvaluationError("a train/validation split needs at least two scenarios")
    return scenarios.split(float(train_fraction))


def evaluate_risk_validation(
    values: pd.DataFrame,
    targets: Sequence[Target],
    scenarios: ScenarioSet,
    train_fraction: float = 0.7,
) -> RiskValidationReport:
    """Evaluate one deterministic frame on a train/validation scenario split.

    Parameters
    ----------
    values : pandas.DataFrame
        The deterministic account values.
    targets : sequence of Target
        Risk-aggregated targets.
    scenarios : ScenarioSet
        The full scenario ensemble.
    train_fraction : float, optional
        The training fraction (default 0.7).

    Returns
    -------
    RiskValidationReport
        The train/validation evaluations and gap.

    Raises
    ------
    RiskEvaluationError
        If the split or an evaluation is invalid.
    """
    train, validation = split_scenarios(scenarios, train_fraction)
    return RiskValidationReport(
        train=RiskAccountEvaluator(train, targets).evaluate(values),
        validation=RiskAccountEvaluator(validation, targets).evaluate(values),
        train_fraction=train_fraction,
    )
