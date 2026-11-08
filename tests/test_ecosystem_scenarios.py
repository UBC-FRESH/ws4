"""Tests for scenario ensembles, risk aggregation, and sample-average approximation."""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import pandas as pd
import pytest
from ws4.ecosystem import (
    FireConfig,
    OutOfSampleReport,
    SampleAverageApproximation,
    Scenario,
    ScenarioError,
    ScenarioEvaluation,
    ScenarioSet,
    fire_evaluator,
    load_scenarios,
    risk_account_values,
    synthetic_grid,
)
from ws4.opt.objective import Target, load_targets, objective


def values_frame() -> pd.DataFrame:
    """Build four scenarios with a volume of 10, 20, 30, and 40."""
    return pd.DataFrame(
        [
            {"offset": 4, "account": "volume", "value": value, "scenario": scenario}
            for scenario, value in zip(
                ("s1", "s2", "s3", "s4"),
                (10.0, 20.0, 30.0, 40.0),
                strict=True,
            )
        ]
    )


def test_scenario_round_trips() -> None:
    scenario = Scenario("s1", 11, 2.0, {"ignition_rate": 0.02}, "test")

    assert Scenario.from_dict(scenario.to_dict()) == scenario
    assert scenario.overrides == {"ignition_rate": 0.02}


def test_scenario_validation_rejects_bad_values() -> None:
    with pytest.raises(ScenarioError, match="scenario_id"):
        Scenario(" ", 1)
    with pytest.raises(ScenarioError, match="seed"):
        Scenario("s", -1)
    with pytest.raises(ScenarioError, match="seed"):
        Scenario("s", True)
    with pytest.raises(ScenarioError, match="weight"):
        Scenario("s", 1, 0.0)
    with pytest.raises(ScenarioError, match="overrides"):
        # deliberately invalid: overrides must be a mapping
        Scenario("s", 1, overrides=5)  # type: ignore[arg-type]


def test_scenario_set_from_seeds_and_split() -> None:
    scenarios = ScenarioSet.from_seeds([1, 2, 3, 4, 5], name="base")

    train, validation = scenarios.split(0.6)

    assert scenarios.scenario_ids == ("s1", "s2", "s3", "s4", "s5")
    assert train.scenario_ids == ("s1", "s2", "s3")
    assert validation.scenario_ids == ("s4", "s5")
    assert train.name == "base.train"
    assert validation.name == "base.validation"
    assert scenarios.weights() == {"s1": 1.0, "s2": 1.0, "s3": 1.0, "s4": 1.0, "s5": 1.0}


def test_scenario_set_rejects_bad_ensembles() -> None:
    with pytest.raises(ScenarioError, match="at least one"):
        ScenarioSet(())
    with pytest.raises(ScenarioError, match="duplicate"):
        ScenarioSet((Scenario("s", 1), Scenario("s", 2)))
    with pytest.raises(ScenarioError, match="at least two"):
        ScenarioSet.from_seeds([1]).split()
    with pytest.raises(ScenarioError, match="train_fraction"):
        ScenarioSet.from_seeds([1, 2]).split(1.0)
    with pytest.raises(ScenarioError, match="same length"):
        ScenarioSet.from_seeds([1, 2], weights=[1.0])


def test_scenario_set_round_trips_yaml_and_json(tmp_path: Path) -> None:
    scenarios = ScenarioSet.from_seeds([1, 2, 3], name="base")
    yaml_path = tmp_path / "scenarios.yaml"
    json_path = tmp_path / "scenarios.json"

    scenarios.write(yaml_path)
    scenarios.write(json_path)

    assert load_scenarios(yaml_path) == scenarios
    assert load_scenarios(json_path) == scenarios
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == "ws4.scenario.v1"


def test_scenario_set_accepts_id_alias(tmp_path: Path) -> None:
    path = tmp_path / "scenarios.yaml"
    path.write_text(
        "schema_version: ws4.scenario.v1\nname: alias\nscenarios:\n"
        "  - id: a\n    seed: 7\n    weight: 2.0\n",
        encoding="utf-8",
    )

    scenarios = load_scenarios(path)

    assert scenarios.scenario_ids == ("a",)
    assert scenarios.scenarios[0].weight == 2.0


def test_load_scenarios_rejects_bad_files(tmp_path: Path) -> None:
    with pytest.raises(ScenarioError, match="JSON or YAML"):
        load_scenarios(tmp_path / "scenarios.txt")
    path = tmp_path / "bad.yaml"
    path.write_text("name: base\n", encoding="utf-8")
    with pytest.raises(ScenarioError, match="scenarios list"):
        load_scenarios(path)


@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [
        ("mean", 25.0),
        ("min", 10.0),
        ("max", 40.0),
        ("cvar", 15.0),
        ("cvar_lower", 15.0),
        ("cvar_upper", 35.0),
        ("quantile", 20.0),
    ],
)
def test_risk_statistics(aggregation: str, expected: float) -> None:
    target = Target(
        "volume",
        period=5,
        minimum=0.0,
        aggregation=aggregation,
        risk_alpha=0.5,
    )

    aggregated, effective = risk_account_values(values_frame(), [target])

    assert float(aggregated.iloc[0]["value"]) == pytest.approx(expected)
    assert effective[0].account.startswith(f"risk.{aggregation}.0.volume")
    assert effective[0].aggregation == "single"


def test_probability_and_regret_statistics() -> None:
    probability = Target(
        "volume",
        period=5,
        minimum=25.0,
        aggregation="probability",
        risk_minimum=0.5,
    )
    regret = Target(
        "volume",
        period=5,
        aggregation="regret",
        risk_maximum=20.0,
    )

    aggregated, effective = risk_account_values(values_frame(), [probability, regret])

    assert float(aggregated.iloc[0]["value"]) == pytest.approx(0.5)
    assert float(aggregated.iloc[1]["value"]) == pytest.approx(30.0)
    assert effective[0].minimum == 0.5
    assert effective[1].maximum == 20.0


def test_weighted_mean_uses_scenario_weights() -> None:
    target = Target("volume", period=5, minimum=0.0, aggregation="mean")
    weights = {"s1": 1.0, "s2": 2.0, "s3": 3.0, "s4": 4.0}

    aggregated, _ = risk_account_values(values_frame(), [target], weights=weights)

    assert float(aggregated.iloc[0]["value"]) == pytest.approx(30.0)


def test_risk_account_values_without_scenarios_is_a_noop() -> None:
    frame = pd.DataFrame([{"offset": 4, "account": "volume", "value": 10.0}])
    target = Target("volume", period=5, minimum=0.0, aggregation="mean")

    values, targets = risk_account_values(frame, [target])

    assert values.equals(frame)
    assert targets == [target]


def test_risk_account_values_rejects_single_aggregation_with_scenarios() -> None:
    target = Target("volume", period=5, minimum=0.0)

    with pytest.raises(ScenarioError, match="aggregation 'single'"):
        risk_account_values(values_frame(), [target])


def test_target_aggregation_validation_and_defaults() -> None:
    with pytest.raises(ValueError, match="unknown risk aggregation"):
        Target("a", 0, aggregation="bogus")
    with pytest.raises(ValueError, match="risk_alpha"):
        Target("a", 0, risk_alpha=1.0)
    with pytest.raises(ValueError, match="flow targets"):
        Target("a", 0, flow="even", aggregation="mean")

    probability = Target("a", 0, aggregation="probability")
    regret = Target("a", 0, aggregation="regret")

    assert probability.risk_minimum == 0.9
    assert regret.risk_maximum == 0.0


def test_load_targets_parses_risk_fields(tmp_path: Path) -> None:
    path = tmp_path / "targets.yaml"
    path.write_text(
        "targets:\n"
        "  - account: volume\n"
        "    period: 5\n"
        "    minimum: 10\n"
        "    aggregation: cvar\n"
        "    risk_alpha: 0.75\n"
        "    risk_minimum: 5\n"
        "    risk_maximum: 50\n"
        "  - account: flow\n"
        "    period: 5\n"
        "    flow: even\n",
        encoding="utf-8",
    )

    targets = load_targets(path)

    assert targets[0].aggregation == "cvar"
    assert targets[0].risk_alpha == pytest.approx(0.75)
    assert targets[0].risk_minimum == pytest.approx(5.0)
    assert targets[0].risk_maximum == pytest.approx(50.0)
    assert targets[1].aggregation == "single"


def test_sample_average_approximation_best_and_crn() -> None:
    scenarios = ScenarioSet.from_seeds([1, 2, 3])
    calls: list[tuple[object, int]] = []

    def evaluator(decision: object, scenario: Scenario) -> pd.DataFrame:
        calls.append((decision, scenario.seed))
        value = 10.0 + float(str(decision)) + scenario.seed
        return pd.DataFrame([{"offset": 4, "account": "volume", "value": value}])

    target = Target("volume", period=5, minimum=100.0, aggregation="mean")
    saa = SampleAverageApproximation(scenarios, evaluator, [target])

    best = saa.best([0.0, 50.0, 100.0])

    assert best.decision == 100.0
    assert best.objective == pytest.approx(0.0)
    assert isinstance(best, ScenarioEvaluation)
    assert best.aggregated.shape[0] == 1
    assert [seed for _, seed in calls[:3]] == [1, 2, 3]
    assert [seed for _, seed in calls[3:6]] == [1, 2, 3]
    assert [seed for _, seed in calls[6:9]] == [1, 2, 3]


def test_out_of_sample_report() -> None:
    scenarios = ScenarioSet.from_seeds([1, 2, 3], name="base")
    validation = ScenarioSet.from_seeds([4, 5], name="holdout")

    def evaluator(decision: object, scenario: Scenario) -> pd.DataFrame:
        value = 10.0 + float(str(decision)) + scenario.seed
        return pd.DataFrame([{"offset": 4, "account": "volume", "value": value}])

    target = Target("volume", period=5, minimum=120.0, aggregation="mean")
    saa = SampleAverageApproximation(scenarios, evaluator, [target])

    report = saa.report(100.0, validation)

    assert isinstance(report, OutOfSampleReport)
    assert report.generalization_gap == pytest.approx(
        report.validation.objective - report.train.objective
    )
    assert report.train.objective == pytest.approx(8.0)
    assert report.validation.objective == pytest.approx(5.5)


def test_out_of_sample_report_writes_files(tmp_path: Path) -> None:
    scenarios = ScenarioSet.from_seeds([1, 2])
    validation = ScenarioSet.from_seeds([3, 4])

    def evaluator(decision: object, scenario: Scenario) -> pd.DataFrame:
        return pd.DataFrame([{"offset": 4, "account": "volume", "value": 10.0 + scenario.seed}])

    target = Target("volume", period=5, minimum=100.0, aggregation="mean")
    report = SampleAverageApproximation(scenarios, evaluator, [target]).report(0.0, validation)

    report.write(tmp_path)

    assert (tmp_path / "summary.json").is_file()
    assert (tmp_path / "train_values.csv").is_file()
    assert (tmp_path / "validation_aggregated.csv").is_file()
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["train"]["scenario_count"] == 2
    assert summary["validation"]["scenario_count"] == 2


def test_single_scenario_matches_the_deterministic_objective() -> None:
    scenarios = ScenarioSet.from_seeds([1])
    frame = pd.DataFrame([{"offset": 4, "account": "volume", "value": 11.0}])
    target = Target("volume", period=5, minimum=100.0, aggregation="mean")

    def evaluator(decision: object, scenario: Scenario) -> pd.DataFrame:
        return frame

    evaluation = SampleAverageApproximation(scenarios, evaluator, [target]).evaluate(0.0)

    assert evaluation.objective == pytest.approx(objective(frame, [target]))


def test_sample_average_approximation_rejects_bad_frames() -> None:
    scenarios = ScenarioSet.from_seeds([1])
    target = Target("volume", period=5, minimum=0.0, aggregation="mean")

    def bad_evaluator(decision: object, scenario: Scenario) -> pd.DataFrame:
        return pd.DataFrame([{"offset": 4, "value": 1.0}])

    saa = SampleAverageApproximation(scenarios, bad_evaluator, [target])

    with pytest.raises(ScenarioError, match="account"):
        saa.evaluate(0.0)
    with pytest.raises(ScenarioError, match="at least one decision"):
        saa.best([])


def test_common_random_numbers_reduce_paired_variance() -> None:
    crn_scenarios = ScenarioSet.from_seeds(list(range(1, 21)))
    independent_scenarios = ScenarioSet.from_seeds(list(range(21, 41)))

    def evaluator(decision: object, scenario: Scenario) -> pd.DataFrame:
        noise = float((scenario.seed * 37) % 11)
        value = 100.0 + float(str(decision)) + noise
        return pd.DataFrame([{"offset": 4, "account": "volume", "value": value}])

    target = Target("volume", period=5, minimum=0.0, aggregation="mean")
    crn = SampleAverageApproximation(crn_scenarios, evaluator, [target])
    independent = SampleAverageApproximation(independent_scenarios, evaluator, [target])

    crn_differences = [
        float(crn.evaluate(1.0, ScenarioSet((scenario,))).values.iloc[0]["value"])
        - float(crn.evaluate(0.0, ScenarioSet((scenario,))).values.iloc[0]["value"])
        for scenario in crn_scenarios.scenarios
    ]
    independent_differences = [
        float(independent.evaluate(1.0, ScenarioSet((high,))).values.iloc[0]["value"])
        - float(crn.evaluate(0.0, ScenarioSet((low,))).values.iloc[0]["value"])
        for low, high in zip(
            crn_scenarios.scenarios,
            independent_scenarios.scenarios,
            strict=True,
        )
    ]

    assert statistics.pvariance(crn_differences) == pytest.approx(0.0)
    assert statistics.pvariance(independent_differences) > 0.0


def test_fire_evaluator_runs_scenarios_without_mutating_the_initial_state() -> None:
    _, state, edges = synthetic_grid(2, 2)
    original = state.cohorts.copy(deep=True)
    scenarios = ScenarioSet.from_seeds([1, 2])
    evaluator = fire_evaluator(state, edges, 5)
    target = Target(
        "fire.burned_area_ha",
        period=5,
        maximum=100.0,
        max_weight=1.0,
        aggregation="mean",
    )
    decisions = [
        FireConfig(ignition_rate_per_fragment_year=0.05, base_spread_probability=0.5),
        FireConfig(ignition_rate_per_fragment_year=0.05, base_spread_probability=0.2),
    ]

    saa = SampleAverageApproximation(scenarios, evaluator, [target])
    best = saa.best(decisions)

    assert best.decision in decisions
    assert best.aggregated.shape[0] == 1
    assert math.isfinite(best.objective)
    assert state.cohorts.equals(original)
