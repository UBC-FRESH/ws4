"""Optimizer account rows from process fire-regime summaries.

The process ensemble reports fire-regime distributions per scenario. This module maps those
summaries to the account-value frame the existing optimizer risk aggregation consumes. It does
not change the optimizer search or calibrate the fire model.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from ..fire.risk import FireRegimeRiskSummary
from .objective import Target, objective

PROCESS_FIRE_RISK_VERSION: Final[str] = "ws4.process-fire-risk-accounts.v1"
RISK_VERIFICATION_BUNDLE_VERSION: Final[str] = "ws4.risk-verification-bundle.v1"


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
            "targets": [target.account for target in self.targets],
            "objective": self.objective,
        }

    def write(self, out_dir: Path) -> None:
        """Write values, aggregated rows, and the summary.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.

        Raises
        ------
        ProcessFireRiskError
            If the report has no account values.
        """
        if self.values.empty:
            raise ProcessFireRiskError("cannot write an empty fire-risk report")
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        self.values.to_csv(target / "process_fire_risk_values.csv", index=False)
        self.aggregated.to_csv(target / "process_fire_risk_aggregated.csv", index=False)
        (target / "process_fire_risk.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


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


@dataclass(frozen=True)
class ProcessFireRiskValidation:
    """Train/validation comparison for process fire risk.

    Attributes
    ----------
    train : ProcessFireRiskReport
        Training-scenario report.
    validation : ProcessFireRiskReport
        Held-out report.
    train_fraction : float
        Fraction of scenarios assigned to training.
    """

    train: ProcessFireRiskReport
    validation: ProcessFireRiskReport
    train_fraction: float

    @property
    def gap(self) -> float:
        """Return validation objective minus training objective.

        Returns
        -------
        float
            The generalization gap; positive means validation is worse.
        """
        return self.validation.objective - self.train.objective

    def summary(self) -> dict[str, object]:
        """Return a stable train/validation summary.

        Returns
        -------
        dict
            Train fraction, scenario counts, objectives, and gap.
        """
        return {
            "schema_version": PROCESS_FIRE_RISK_VERSION,
            "train_fraction": self.train_fraction,
            "train_scenarios": sorted(self.train.values["scenario"].unique().tolist()),
            "validation_scenarios": sorted(self.validation.values["scenario"].unique().tolist()),
            "train_objective": self.train.objective,
            "validation_objective": self.validation.objective,
            "generalization_gap": self.gap,
        }

    def write(self, out_dir: Path) -> None:
        """Write train/validation values and summary.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.
        """
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        self.train.values.to_csv(target / "process_fire_risk_train_values.csv", index=False)
        self.validation.values.to_csv(
            target / "process_fire_risk_validation_values.csv", index=False
        )
        (target / "process_fire_risk_validation.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def evaluate_process_fire_risk_validation(
    summaries: Mapping[str, FireRegimeRiskSummary],
    *,
    years: int,
    targets: Sequence[Target],
    train_fraction: float,
    weights: Mapping[str, float] | None = None,
) -> ProcessFireRiskValidation:
    """Split scenarios and compare training and validation risk objectives.

    Parameters
    ----------
    summaries : mapping of str to FireRegimeRiskSummary
        Per-scenario summaries.
    years : int
        Number of simulated years.
    targets : sequence of Target
        Risk-aggregated targets.
    train_fraction : float
        Fraction in (0, 1) assigned to training. The split is deterministic by sorted id.
    weights : mapping of str to float or None, optional
        Scenario weights. Missing weights use the aggregation defaults.

    Returns
    -------
    ProcessFireRiskValidation
        Training and validation reports plus the generalization gap.

    Raises
    ------
    ProcessFireRiskError
        If there are fewer than two scenarios or the fraction is invalid.
    """
    if not isinstance(train_fraction, (int, float)) or isinstance(train_fraction, bool):
        raise ProcessFireRiskError("train_fraction must be a number")
    fraction = float(train_fraction)
    if not 0.0 < fraction < 1.0:
        raise ProcessFireRiskError("train_fraction must be between 0 and 1")
    ids = sorted(summaries)
    if len(ids) < 2:
        raise ProcessFireRiskError("at least two scenarios are required")
    count = max(1, min(len(ids) - 1, int(len(ids) * fraction)))
    train_ids = tuple(ids[:count])
    validation_ids = tuple(ids[count:])

    def weights_for(selected: Sequence[str]) -> Mapping[str, float] | None:
        if weights is None:
            return None
        missing = sorted(set(selected) - set(weights))
        if missing:
            raise ProcessFireRiskError(f"missing weights for: {', '.join(missing)}")
        return {scenario: float(weights[scenario]) for scenario in selected}

    train = evaluate_process_fire_risk(
        {scenario: summaries[scenario] for scenario in train_ids},
        years=years,
        targets=targets,
        scenario_ids=train_ids,
        weights=weights_for(train_ids),
    )
    validation = evaluate_process_fire_risk(
        {scenario: summaries[scenario] for scenario in validation_ids},
        years=years,
        targets=targets,
        scenario_ids=validation_ids,
        weights=weights_for(validation_ids),
    )
    return ProcessFireRiskValidation(train=train, validation=validation, train_fraction=fraction)


def write_risk_verification_bundle(
    out_dir: Path,
    *,
    optimizer_summary: Mapping[str, object],
    process: ProcessFireRiskValidation,
) -> dict[str, object]:
    """Write optimizer and process risk summaries into one JSON bundle.

    Parameters
    ----------
    out_dir : Path
        Output directory, created when missing.
    optimizer_summary : mapping of str to object
        Existing optimizer risk verification summary.
    process : ProcessFireRiskValidation
        Process fire-risk train/validation report.

    Returns
    -------
    dict
        The written payload.

    Raises
    ------
    ProcessFireRiskError
        If the optimizer summary is empty or the process report is invalid.
    """
    if not isinstance(optimizer_summary, Mapping) or not optimizer_summary:
        raise ProcessFireRiskError("optimizer_summary must be a non-empty mapping")
    if not isinstance(process, ProcessFireRiskValidation):
        raise ProcessFireRiskError("process must be a ProcessFireRiskValidation")
    payload: dict[str, object] = {
        "schema_version": RISK_VERIFICATION_BUNDLE_VERSION,
        "optimizer": dict(optimizer_summary),
        "process": process.summary(),
    }
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "risk_verification_bundle.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def bundle_existing_risk_verification(
    out_dir: Path, *, process: ProcessFireRiskValidation
) -> dict[str, object]:
    """Bundle an optimizer's written risk verification with process risk.

    Parameters
    ----------
    out_dir : Path
        Optimizer output directory containing ``risk_verification.json``.
    process : ProcessFireRiskValidation
        Process fire-risk train/validation report.

    Returns
    -------
    dict
        The written bundle payload.

    Raises
    ------
    ProcessFireRiskError
        If the optimizer verification file is missing or malformed.
    """
    target = Path(out_dir)
    path = target / "risk_verification.json"
    if not path.is_file():
        raise ProcessFireRiskError(f"optimizer risk verification is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProcessFireRiskError("optimizer risk verification is not valid JSON") from error
    if not isinstance(payload, Mapping):
        raise ProcessFireRiskError("optimizer risk verification must be an object")
    required = {"search_objective", "full_objective", "gap"}
    missing = sorted(required - set(payload))
    if missing:
        raise ProcessFireRiskError(f"optimizer risk verification is missing: {', '.join(missing)}")
    return write_risk_verification_bundle(target, optimizer_summary=payload, process=process)
