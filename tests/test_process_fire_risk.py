"""Process fire-regime risk account tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.ecosystem.ensemble import ProcessEnsembleConfig, run_process_ensemble
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.ecosystem.scenarios import Scenario, ScenarioSet, risk_account_values
from ws4.opt.fire_risk import ProcessFireRiskError, fire_regime_account_values
from ws4.opt.objective import Target


def _ensemble() -> object:
    """Return a two-scenario process ensemble."""
    _schema, state, edges = synthetic_grid(4, 4)
    scenarios = ScenarioSet((Scenario("one", 5, weight=1.0), Scenario("two", 6, weight=1.0)))
    return run_process_ensemble(
        state,
        edges,
        ProcessEnsembleConfig(
            horizon_years=2,
            fire=FireConfig(ignition_rate_per_fragment_year=1.0),
        ),
        scenarios,
    )


def test_fire_regime_accounts_are_complete() -> None:
    result = _ensemble()
    from ws4.ecosystem.ensemble import ProcessEnsembleResult

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=160.0, cell_size_ha=10.0)
    values = fire_regime_account_values(summaries, years=2)

    assert list(values.columns) == ["offset", "account", "value", "scenario"]
    assert set(values["scenario"]) == {"one", "two"}
    assert set(values["offset"]) == {1}
    accounts = set(values["account"])
    assert {
        "fire.regime.total_burned_ha",
        "fire.regime.burn_probability",
        "fire.regime.annual_burn_rate",
        "fire.regime.escaped_fires_per_year",
        "fire.regime.mean_fire_size_ha",
        "fire.regime.max_fire_size_ha",
        "fire.regime.fire_count",
    } <= accounts
    for scenario, summary in summaries.items():
        selected = values.loc[
            (values["scenario"] == scenario) & (values["account"] == "fire.regime.total_burned_ha"),
            "value",
        ]
        assert float(selected.iloc[0]) == pytest.approx(summary.total_burned_ha)


def test_fire_regime_accounts_feed_risk_aggregation() -> None:
    result = _ensemble()
    from ws4.ecosystem.ensemble import ProcessEnsembleResult

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=160.0, cell_size_ha=10.0)
    values = fire_regime_account_values(summaries, years=2)
    target = Target(
        account="fire.regime.annual_burn_rate",
        period=1,
        period_width=2,
        aggregation="mean",
        minimum=0.0,
    )

    aggregated, effective = risk_account_values(
        values, (target,), scenario_ids=("one", "two"), weights={"one": 0.5, "two": 0.5}
    )

    assert not aggregated.empty
    assert aggregated["account"].iloc[0].startswith("risk.mean.")
    assert effective[0].account.startswith("risk.mean.")


def test_zero_fire_accounts_omit_fri() -> None:
    _schema, state, edges = synthetic_grid(3, 3)
    scenarios = ScenarioSet((Scenario("quiet", 1, weight=1.0),))
    result = run_process_ensemble(
        state,
        edges,
        ProcessEnsembleConfig(
            horizon_years=2,
            fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        ),
        scenarios,
    )
    from ws4.ecosystem.ensemble import ProcessEnsembleResult

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=90.0, cell_size_ha=10.0)
    values = fire_regime_account_values(summaries, years=2)

    assert "fire.regime.fire_return_interval_years" not in set(values["account"])
    assert float(values.loc[values["account"] == "fire.regime.fire_count", "value"].iloc[0]) == 0.0


def test_invalid_fire_risk_accounts_fail() -> None:
    with pytest.raises(ProcessFireRiskError, match="years"):
        fire_regime_account_values({}, years=0)
    with pytest.raises(ProcessFireRiskError, match="non-empty"):
        fire_regime_account_values({}, years=1)
    with pytest.raises(ProcessFireRiskError, match="summaries"):
        fire_regime_account_values({"x": object()}, years=1)  # type: ignore[dict-item]


def test_process_fire_risk_report_has_exact_penalty() -> None:
    result = _ensemble()
    from ws4.ecosystem.ensemble import ProcessEnsembleResult
    from ws4.opt.fire_risk import evaluate_process_fire_risk

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=160.0, cell_size_ha=10.0)
    base_target = Target(
        account="fire.regime.annual_burn_rate",
        period=1,
        period_width=2,
        aggregation="mean",
        minimum=0.0,
    )
    base = evaluate_process_fire_risk(
        summaries,
        years=2,
        targets=(base_target,),
        scenario_ids=("one", "two"),
        weights={"one": 0.5, "two": 0.5},
    )
    assert base.objective == 0.0
    assert base.summary()["schema_version"] == "ws4.process-fire-risk-accounts.v1"
    value = float(base.aggregated["value"].iloc[0])

    penalized = evaluate_process_fire_risk(
        summaries,
        years=2,
        targets=(
            Target(
                account="fire.regime.annual_burn_rate",
                period=1,
                period_width=2,
                aggregation="mean",
                minimum=value + 2.0,
            ),
        ),
        scenario_ids=("one", "two"),
        weights={"one": 0.5, "two": 0.5},
    )

    assert penalized.objective == pytest.approx(2.0)


def test_process_fire_risk_report_requires_targets() -> None:
    from ws4.opt.fire_risk import evaluate_process_fire_risk

    with pytest.raises(ProcessFireRiskError, match="target"):
        evaluate_process_fire_risk({}, years=1, targets=())


def test_process_fire_risk_report_artifact(tmp_path: Path) -> None:
    result = _ensemble()
    from ws4.ecosystem.ensemble import ProcessEnsembleResult
    from ws4.opt.fire_risk import evaluate_process_fire_risk

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=160.0, cell_size_ha=10.0)
    report = evaluate_process_fire_risk(
        summaries,
        years=2,
        targets=(
            Target(
                account="fire.regime.annual_burn_rate",
                period=1,
                period_width=2,
                aggregation="mean",
                minimum=0.0,
            ),
        ),
        scenario_ids=("one", "two"),
        weights={"one": 0.5, "two": 0.5},
    )
    report.write(tmp_path / "risk")

    payload = json.loads((tmp_path / "risk" / "process_fire_risk.json").read_text())
    assert payload["schema_version"] == "ws4.process-fire-risk-accounts.v1"
    assert payload["scenarios"] == ["one", "two"]
    assert payload["targets"] == ["risk.mean.0.fire.regime.annual_burn_rate"]
    assert payload["objective"] == 0.0
    assert (tmp_path / "risk" / "process_fire_risk_values.csv").is_file()
    assert (tmp_path / "risk" / "process_fire_risk_aggregated.csv").is_file()


def test_empty_process_fire_risk_report_is_rejected(tmp_path: Path) -> None:
    from ws4.opt.fire_risk import ProcessFireRiskReport

    report = ProcessFireRiskReport(
        values=pd.DataFrame(columns=["offset", "account", "value", "scenario"]),
        aggregated=pd.DataFrame(),
        targets=(),
        objective=0.0,
    )
    with pytest.raises(ProcessFireRiskError, match="empty"):
        report.write(tmp_path / "empty")


def test_process_fire_risk_validation_split_and_gap() -> None:
    _schema, state, edges = synthetic_grid(4, 4)
    scenarios = ScenarioSet(
        tuple(
            Scenario(name, seed, weight=1.0)
            for name, seed in (("a", 1), ("b", 2), ("c", 3), ("d", 4))
        )
    )
    result = run_process_ensemble(
        state,
        edges,
        ProcessEnsembleConfig(
            horizon_years=2,
            fire=FireConfig(ignition_rate_per_fragment_year=1.0),
        ),
        scenarios,
    )
    from ws4.ecosystem.ensemble import ProcessEnsembleResult
    from ws4.opt.fire_risk import evaluate_process_fire_risk_validation

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=160.0, cell_size_ha=10.0)
    target = Target(
        account="fire.regime.annual_burn_rate",
        period=1,
        period_width=2,
        aggregation="mean",
        minimum=0.0,
    )
    validation = evaluate_process_fire_risk_validation(
        summaries,
        years=2,
        targets=(target,),
        train_fraction=0.5,
    )

    assert validation.summary()["train_scenarios"] == ["a", "b"]
    assert validation.summary()["validation_scenarios"] == ["c", "d"]
    assert validation.gap == pytest.approx(
        validation.validation.objective - validation.train.objective
    )


def test_process_fire_risk_validation_artifact(tmp_path: Path) -> None:
    _schema, state, edges = synthetic_grid(3, 3)
    scenarios = ScenarioSet((Scenario("a", 1), Scenario("b", 2)))
    result = run_process_ensemble(
        state,
        edges,
        ProcessEnsembleConfig(
            horizon_years=2,
            fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        ),
        scenarios,
    )
    from ws4.ecosystem.ensemble import ProcessEnsembleResult
    from ws4.opt.fire_risk import evaluate_process_fire_risk_validation

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=90.0, cell_size_ha=10.0)
    validation = evaluate_process_fire_risk_validation(
        summaries,
        years=2,
        targets=(
            Target(
                account="fire.regime.annual_burn_rate",
                period=1,
                period_width=2,
                aggregation="mean",
                minimum=0.0,
            ),
        ),
        train_fraction=0.5,
    )
    validation.write(tmp_path / "validation")

    payload = json.loads(
        (tmp_path / "validation" / "process_fire_risk_validation.json").read_text()
    )
    assert payload["train_scenarios"] == ["a"]
    assert payload["validation_scenarios"] == ["b"]
    assert (tmp_path / "validation" / "process_fire_risk_train_values.csv").is_file()
    assert (tmp_path / "validation" / "process_fire_risk_validation_values.csv").is_file()


def test_process_fire_risk_validation_rejects_bad_splits() -> None:
    from ws4.opt.fire_risk import evaluate_process_fire_risk_validation

    with pytest.raises(ProcessFireRiskError, match="fraction"):
        evaluate_process_fire_risk_validation({}, years=1, targets=(), train_fraction=0.0)
    with pytest.raises(ProcessFireRiskError, match="at least two"):
        evaluate_process_fire_risk_validation({}, years=1, targets=(), train_fraction=0.5)


def test_risk_verification_bundle(tmp_path: Path) -> None:
    _schema, state, edges = synthetic_grid(3, 3)
    scenarios = ScenarioSet((Scenario("a", 1), Scenario("b", 2)))
    result = run_process_ensemble(
        state,
        edges,
        ProcessEnsembleConfig(
            horizon_years=2,
            fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        ),
        scenarios,
    )
    from ws4.ecosystem.ensemble import ProcessEnsembleResult
    from ws4.opt.fire_risk import (
        evaluate_process_fire_risk_validation,
        write_risk_verification_bundle,
    )

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=90.0, cell_size_ha=10.0)
    validation = evaluate_process_fire_risk_validation(
        summaries,
        years=2,
        targets=(
            Target(
                account="fire.regime.annual_burn_rate",
                period=1,
                period_width=2,
                aggregation="mean",
                minimum=0.0,
            ),
        ),
        train_fraction=0.5,
    )
    payload = write_risk_verification_bundle(
        tmp_path / "bundle",
        optimizer_summary={"full_objective": 3.0, "gap": 0.5},
        process=validation,
    )

    written = json.loads((tmp_path / "bundle" / "risk_verification_bundle.json").read_text())
    assert written == payload
    assert written["schema_version"] == "ws4.risk-verification-bundle.v1"
    assert written["optimizer"] == {"full_objective": 3.0, "gap": 0.5}
    assert written["process"]["generalization_gap"] == validation.gap


def test_risk_verification_bundle_rejects_empty_optimizer(tmp_path: Path) -> None:
    from ws4.opt.fire_risk import write_risk_verification_bundle

    with pytest.raises(ProcessFireRiskError, match="optimizer_summary"):
        write_risk_verification_bundle(
            tmp_path / "bundle",
            optimizer_summary={},
            process=object(),  # type: ignore[arg-type]
        )


def test_bundle_existing_optimizer_risk_verification(tmp_path: Path) -> None:
    _schema, state, edges = synthetic_grid(3, 3)
    scenarios = ScenarioSet((Scenario("a", 1), Scenario("b", 2)))
    result = run_process_ensemble(
        state,
        edges,
        ProcessEnsembleConfig(
            horizon_years=2,
            fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        ),
        scenarios,
    )
    from ws4.ecosystem.ensemble import ProcessEnsembleResult
    from ws4.opt.fire_risk import (
        bundle_existing_risk_verification,
        evaluate_process_fire_risk_validation,
    )

    assert isinstance(result, ProcessEnsembleResult)
    summaries = result.fire_regime_summaries(years=2, burnable_area_ha=90.0, cell_size_ha=10.0)
    validation = evaluate_process_fire_risk_validation(
        summaries,
        years=2,
        targets=(
            Target(
                account="fire.regime.annual_burn_rate",
                period=1,
                period_width=2,
                aggregation="mean",
                minimum=0.0,
            ),
        ),
        train_fraction=0.5,
    )
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    (out_dir / "risk_verification.json").write_text(
        json.dumps({"search_objective": 4.0, "full_objective": 5.0, "gap": 1.0})
    )

    payload = bundle_existing_risk_verification(out_dir, process=validation)

    written = json.loads((out_dir / "risk_verification_bundle.json").read_text())
    assert written == payload
    assert written["optimizer"]["search_objective"] == 4.0
    assert written["optimizer"]["gap"] == 1.0
    assert written["process"]["generalization_gap"] == validation.gap


def test_bundle_existing_optimizer_rejects_missing_file(tmp_path: Path) -> None:
    from ws4.opt.fire_risk import bundle_existing_risk_verification

    with pytest.raises(ProcessFireRiskError, match="missing"):
        bundle_existing_risk_verification(tmp_path, process=object())  # type: ignore[arg-type]
