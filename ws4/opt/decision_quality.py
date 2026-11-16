"""Decision-quality metrics for alternatives evaluated across uncertainty scenarios.

The contract is deliberately generic: rows identify a decision, a scenario, and a
lower-is-better outcome. It reports expected outcome, worst case, regret against the
per-scenario best, rank stability, and optional constraint satisfaction.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


class DecisionQualityError(ValueError):
    """Raised when a decision matrix is invalid."""


@dataclass(frozen=True)
class DecisionQualityReport:
    """Decision-quality summary for one alternative-by-scenario matrix.

    Parameters
    ----------
    matrix : pandas.DataFrame
        Outcomes with decisions as the index and scenarios as columns.
    metrics : pandas.DataFrame
        Per-decision expected outcome, worst case, regret, rank stability, and
        constraint satisfaction.
    weights : dict of str to float
        Normalized scenario weights.
    deterministic_choice : str
        Decision with the lowest expected outcome.
    robust_choice : str
        Decision with the lowest worst-case outcome.
    minimax_regret_choice : str
        Decision with the lowest maximum regret.
    """

    matrix: pd.DataFrame
    metrics: pd.DataFrame
    weights: dict[str, float]
    deterministic_choice: str
    robust_choice: str
    minimax_regret_choice: str

    def summary(self) -> dict[str, object]:
        """Return a JSON-serializable summary.

        Returns
        -------
        dict
            Choices, weights, and per-decision metrics.
        """
        return {
            "schema_version": "ws4.decision-quality.v1",
            "weights": self.weights,
            "deterministic_choice": self.deterministic_choice,
            "robust_choice": self.robust_choice,
            "minimax_regret_choice": self.minimax_regret_choice,
            "metrics": self.metrics.reset_index().to_dict(orient="records"),
        }

    def write(self, out_dir: Path) -> None:
        """Write matrix, metrics, and summary.

        Parameters
        ----------
        out_dir : pathlib.Path
            Output directory, created when missing.
        """
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        self.matrix.to_csv(target / "decision_quality_matrix.csv")
        self.metrics.to_csv(target / "decision_quality_metrics.csv")
        (target / "decision_quality.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _weights_for(scenarios: list[str], weights: Mapping[str, float] | None) -> dict[str, float]:
    """Return normalized scenario weights."""
    if weights is None:
        raw = dict.fromkeys(scenarios, 1.0)
    else:
        missing = sorted(set(scenarios) - set(weights))
        if missing:
            raise DecisionQualityError(f"missing weights for: {', '.join(missing)}")
        raw = {scenario: float(weights[scenario]) for scenario in scenarios}
    if any(not math.isfinite(value) or value <= 0.0 for value in raw.values()):
        raise DecisionQualityError("scenario weights must be finite and positive")
    total = sum(raw.values())
    return {scenario: value / total for scenario, value in raw.items()}


def evaluate_decisions(
    frame: pd.DataFrame,
    *,
    decision: str,
    scenario: str,
    outcome: str,
    feasible: str | None = None,
    weights: Mapping[str, float] | None = None,
) -> DecisionQualityReport:
    """Evaluate decisions under scenario uncertainty.

    Parameters
    ----------
    frame : pandas.DataFrame
        Long decision matrix.
    decision : str
        Decision column.
    scenario : str
        Scenario column.
    outcome : str
        Lower-is-better outcome column.
    feasible : str or None, optional
        Optional binary constraint column.
    weights : mapping of str to float or None, optional
        Scenario weights. None uses equal weights.

    Returns
    -------
    DecisionQualityReport
        Matrix, metrics, and selected decisions.

    Raises
    ------
    DecisionQualityError
        If columns, values, weights, or uniqueness are invalid.
    """
    required = {decision, scenario, outcome}
    if feasible is not None:
        required.add(feasible)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DecisionQualityError(f"missing columns: {', '.join(missing)}")
    if frame.empty:
        raise DecisionQualityError("decision matrix must not be empty")
    if frame[[decision, scenario]].duplicated().any():
        raise DecisionQualityError("decision/scenario pairs must be unique")
    outcomes = pd.to_numeric(frame[outcome], errors="coerce")
    if outcomes.isna().any() or not np.isfinite(outcomes.to_numpy(dtype=float)).all():
        raise DecisionQualityError("outcomes must be finite numbers")
    decisions = list(dict.fromkeys(str(value) for value in frame[decision]))
    scenarios = list(dict.fromkeys(str(value) for value in frame[scenario]))
    if len(decisions) < 2 or len(scenarios) < 2:
        raise DecisionQualityError("at least two decisions and two scenarios are required")
    working = frame.copy()
    working[decision] = working[decision].astype(str)
    working[scenario] = working[scenario].astype(str)
    working[outcome] = outcomes.astype(float)
    matrix = working.pivot(index=decision, columns=scenario, values=outcome).reindex(
        index=decisions, columns=scenarios
    )
    if matrix.isna().any().any():
        raise DecisionQualityError("matrix is incomplete")
    normalized = _weights_for(scenarios, weights)
    weight_vector = np.array([normalized[scenario] for scenario in matrix.columns])
    expected = pd.Series(matrix.to_numpy() @ weight_vector, index=matrix.index)
    worst = matrix.max(axis=1)
    best = matrix.min(axis=1)
    oracle = matrix.min(axis=0)
    regret = matrix.sub(oracle, axis=1)
    expected_regret = pd.Series(regret.to_numpy() @ weight_vector, index=matrix.index)
    max_regret = regret.max(axis=1)
    ranks = matrix.rank(axis=0, method="min", ascending=True)
    rank_min = ranks.min(axis=1)
    rank_max = ranks.max(axis=1)
    span = max(1, len(decisions) - 1)
    rank_stability = 1.0 - (rank_max - rank_min) / span
    if feasible is None:
        satisfaction = pd.Series(1.0, index=matrix.index)
    else:
        values = frame[feasible]
        if not values.isin([True, False, 0, 1]).all():
            raise DecisionQualityError("feasible values must be boolean or 0/1")
        working["_feasible"] = values.astype(float)
        satisfaction = (
            working.pivot(index=decision, columns=scenario, values="_feasible")
            .reindex(index=decisions, columns=scenarios)
            .to_numpy()
            @ weight_vector
        )
        satisfaction = pd.Series(satisfaction, index=matrix.index)
    metrics = pd.DataFrame(
        {
            "expected_outcome": expected,
            "worst_case": worst,
            "best_case": best,
            "expected_regret": expected_regret,
            "max_regret": max_regret,
            "rank_min": rank_min,
            "rank_max": rank_max,
            "rank_stability": rank_stability,
            "constraint_satisfaction": satisfaction,
        }
    )
    return DecisionQualityReport(
        matrix=matrix,
        metrics=metrics,
        weights=normalized,
        deterministic_choice=str(expected.idxmin()),
        robust_choice=str(worst.idxmin()),
        minimax_regret_choice=str(max_regret.idxmin()),
    )
