"""Tests for scenario-overlay risk evaluation in the optimizer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.ecosystem.scenarios import Scenario, ScenarioSet
from ws4.opt.objective import Target
from ws4.opt.risk import (
    RiskAccountEvaluator,
    RiskEvaluationError,
    apply_account_multipliers,
)


def _values() -> pd.DataFrame:
    """Return one deterministic account frame."""
    return pd.DataFrame(
        [
            {"offset": 0, "account": "feature.Volume", "value": 100.0},
            {"offset": 0, "account": "feature.Old", "value": 50.0},
        ]
    )


def _scenarios() -> ScenarioSet:
    """Return low and high account-multiplier scenarios."""
    return ScenarioSet(
        (
            Scenario("low", 1, overrides={"account_multipliers": {"feature.Volume": 0.8}}),
            Scenario("high", 2, overrides={"account_multipliers": {"feature.Volume": 1.2}}),
        ),
        name="risk-test",
    )


def test_account_multipliers_scale_only_named_accounts() -> None:
    frame = apply_account_multipliers(
        _values(), {"account_multipliers": {"feature.Volume": 0.5}}, "low"
    )

    assert frame.loc[frame["account"] == "feature.Volume", "value"].iloc[0] == 50.0
    assert frame.loc[frame["account"] == "feature.Old", "value"].iloc[0] == 50.0
    assert set(frame["scenario"]) == {"low"}


def test_unknown_multiplier_fails() -> None:
    with pytest.raises(RiskEvaluationError, match="unknown account"):
        apply_account_multipliers(_values(), {"account_multipliers": {"missing": 0.5}}, "low")


def test_risk_evaluator_uses_mean_and_reports_objective() -> None:
    evaluator = RiskAccountEvaluator(
        _scenarios(),
        (Target(account="feature.Volume", period=1, minimum=90.0, aggregation="mean"),),
    )

    result = evaluator.evaluate(_values())

    assert set(result.values["scenario"]) == {"low", "high"}
    assert result.objective == pytest.approx(0.0)
    assert result.targets[0].account == "risk.mean.0.feature.Volume"
    assert result.targets[0].minimum == pytest.approx(90.0)


def test_risk_evaluator_prices_a_shortfall() -> None:
    evaluator = RiskAccountEvaluator(
        _scenarios(),
        (Target(account="feature.Volume", period=1, minimum=110.0, aggregation="mean"),),
    )

    result = evaluator.evaluate(_values())

    assert result.objective == pytest.approx(10.0)


def test_single_aggregation_with_scenarios_fails() -> None:
    evaluator = RiskAccountEvaluator(
        _scenarios(), (Target(account="feature.Volume", period=1, minimum=90.0),)
    )

    with pytest.raises(RiskEvaluationError, match="scenario"):
        evaluator.evaluate(_values())


def test_optimizer_uses_the_risk_overlay(tmp_path: Path) -> None:
    from ws4.build.compiler import build_canonical_dataset
    from ws4.opt.engine import OptimizeConfig, Optimizer
    from ws4.opt.objective import load_targets

    fixture = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
    dataset = build_canonical_dataset(
        fixture / "recipe.xml", fixture / "fragments.csv", tmp_path / "compiled"
    )
    scenario_file = tmp_path / "scenarios.yaml"
    scenario_file.write_text(
        "schema_version: ws4.scenario.v1\n"
        "scenarios:\n"
        "  - scenario_id: low\n"
        "    seed: 1\n"
        "    overrides:\n"
        "      account_multipliers:\n"
        "        feature.Volume: 0.8\n"
        "  - scenario_id: high\n"
        "    seed: 2\n"
        "    overrides:\n"
        "      account_multipliers:\n"
        "        feature.Volume: 1.2\n",
        encoding="utf-8",
    )
    targets_file = tmp_path / "targets.yaml"
    targets_file.write_text(
        "targets:\n"
        "  - account: feature.Volume\n"
        "    period: 1\n"
        "    minimum: 90\n"
        "    aggregation: mean\n",
        encoding="utf-8",
    )
    optimizer = Optimizer.from_dataset(
        dataset, OptimizeConfig(years=1, scenario_path=str(scenario_file))
    )
    targets = load_targets(targets_file)

    value = optimizer._evaluate({}, targets)

    assert value == pytest.approx(0.0)
    risk = optimizer.last_risk_evaluation()
    assert risk is not None
    assert set(risk.values["scenario"]) == {"low", "high"}
    assert optimizer.delta_evaluator(targets) is None


def test_optimizer_writes_risk_artifacts(tmp_path: Path) -> None:
    from ws4.build.compiler import build_canonical_dataset
    from ws4.opt.engine import OptimizeConfig, Optimizer

    fixture = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
    dataset = build_canonical_dataset(
        fixture / "recipe.xml", fixture / "fragments.csv", tmp_path / "compiled"
    )
    scenario_file = tmp_path / "scenarios.yaml"
    scenario_file.write_text(
        "schema_version: ws4.scenario.v1\n"
        "scenarios:\n"
        "  - scenario_id: low\n"
        "    seed: 1\n"
        "    overrides:\n"
        "      account_multipliers:\n"
        "        feature.Volume: 0.8\n"
        "  - scenario_id: high\n"
        "    seed: 2\n"
        "    overrides:\n"
        "      account_multipliers:\n"
        "        feature.Volume: 1.2\n",
        encoding="utf-8",
    )
    targets_file = tmp_path / "targets.yaml"
    targets_file.write_text(
        "targets:\n"
        "  - account: feature.Volume\n"
        "    period: 1\n"
        "    minimum: 90\n"
        "    aggregation: mean\n",
        encoding="utf-8",
    )
    optimizer = Optimizer.from_dataset(
        dataset,
        OptimizeConfig(
            years=1,
            iterations=1,
            scenario_path=str(scenario_file),
            risk_validation_fraction=0.5,
        ),
    )
    summary = optimizer.run(tmp_path / "run")

    assert summary["risk"]["scenarios"] == ["low", "high"]
    assert (tmp_path / "run" / "risk_values.csv").is_file()
    assert (tmp_path / "run" / "risk_aggregated.csv").is_file()
    assert (tmp_path / "run" / "risk_summary.json").is_file()
    assert (tmp_path / "run" / "risk_verification.json").is_file()
    assert (tmp_path / "run" / "risk_validation.json").is_file()
    assert (tmp_path / "run" / "risk_train_values.csv").is_file()
    assert (tmp_path / "run" / "risk_validation_values.csv").is_file()
    assert summary["risk"]["verification"]["gap"] == pytest.approx(0.0)
    assert summary["risk"]["validation"]["train_scenarios"] == 1


def test_risk_validation_split_and_write(tmp_path: Path) -> None:
    from ws4.opt.risk import evaluate_risk_validation

    scenarios = ScenarioSet(
        (
            Scenario("s1", 1, overrides={"account_multipliers": {"feature.Volume": 0.8}}),
            Scenario("s2", 2, overrides={"account_multipliers": {"feature.Volume": 0.9}}),
            Scenario("s3", 3, overrides={"account_multipliers": {"feature.Volume": 1.1}}),
            Scenario("s4", 4, overrides={"account_multipliers": {"feature.Volume": 1.2}}),
        )
    )
    targets = (Target(account="feature.Volume", period=1, minimum=90.0, aggregation="mean"),)

    report = evaluate_risk_validation(_values(), targets, scenarios, 0.5)
    report.write(tmp_path / "validation")

    assert report.gap == pytest.approx(report.validation.objective - report.train.objective)
    assert (tmp_path / "validation" / "risk_validation.json").is_file()
    assert (tmp_path / "validation" / "risk_train_values.csv").is_file()
    assert (tmp_path / "validation" / "risk_validation_aggregated.csv").is_file()


def test_risk_validation_needs_two_scenarios() -> None:
    from ws4.opt.risk import evaluate_risk_validation

    scenarios = ScenarioSet((Scenario("only", 1),))
    targets = (Target(account="feature.Volume", period=1, minimum=90.0, aggregation="mean"),)

    with pytest.raises(RiskEvaluationError, match="at least two"):
        evaluate_risk_validation(_values(), targets, scenarios)
