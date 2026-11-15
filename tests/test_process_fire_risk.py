"""Process fire-regime risk account tests."""

from __future__ import annotations

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
