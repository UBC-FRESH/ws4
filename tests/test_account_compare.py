"""Tests for the process/estate account comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.opt.account_compare import (
    ACCOUNT_COMPARISON_VERSION,
    AccountComparisonError,
    compare_accounts,
)


def _process() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "offset": [0, 1, 1],
            "account": ["bridge.volume_m3", "bridge.volume_m3", "state.biomass_t"],
            "value": [90.0, 100.0, 10.0],
        }
    )


def _estate() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "offset": [0, 1],
            "account": ["feature.Volume", "feature.Volume"],
            "value": [90.0, 120.0],
        }
    )


def test_compare_accounts_is_exact() -> None:
    result = compare_accounts(_process(), _estate(), {"bridge.volume_m3": "feature.Volume"})

    assert result.process_offset == 1
    assert result.estate_offset == 1
    row = result.rows.iloc[0]
    assert row["process_value"] == 100.0
    assert row["estate_value"] == 120.0
    assert row["absolute_difference"] == -20.0
    assert row["relative_difference"] == pytest.approx(-20.0 / 120.0)


def test_compare_accounts_artifact(tmp_path: Path) -> None:
    result = compare_accounts(_process(), _estate(), {"bridge.volume_m3": "feature.Volume"})
    result.write(tmp_path / "compare")

    payload = json.loads((tmp_path / "compare" / "account_comparison.json").read_text())
    assert payload["schema_version"] == ACCOUNT_COMPARISON_VERSION
    assert payload["accounts"][0]["absolute_difference"] == -20.0
    assert (tmp_path / "compare" / "account_comparison.csv").is_file()


def test_compare_accounts_selects_scenario() -> None:
    estate = pd.concat(
        [
            _estate().assign(scenario="a"),
            _estate().assign(scenario="b").assign(value=[80.0, 80.0]),
        ],
        ignore_index=True,
    )
    result = compare_accounts(
        _process(), estate, {"bridge.volume_m3": "feature.Volume"}, estate_scenario="b"
    )

    assert result.rows.iloc[0]["estate_value"] == 80.0
    with pytest.raises(AccountComparisonError, match="multiple scenarios"):
        compare_accounts(_process(), estate, {"bridge.volume_m3": "feature.Volume"})


def test_compare_accounts_rejects_missing_accounts() -> None:
    with pytest.raises(AccountComparisonError, match="mapping"):
        compare_accounts(_process(), _estate(), {})
    with pytest.raises(AccountComparisonError, match="missing process"):
        compare_accounts(_process(), _estate(), {"not.an.account": "feature.Volume"})
    with pytest.raises(AccountComparisonError, match="missing estate"):
        compare_accounts(_process(), _estate(), {"bridge.volume_m3": "not.an.account"})


def test_zero_estate_has_no_relative_difference() -> None:
    estate = pd.DataFrame({"offset": [0], "account": ["feature.Volume"], "value": [0.0]})
    result = compare_accounts(
        pd.DataFrame({"offset": [0], "account": ["bridge.volume_m3"], "value": [1.0]}),
        estate,
        {"bridge.volume_m3": "feature.Volume"},
    )

    assert pd.isna(result.rows.iloc[0]["relative_difference"])
    accounts = result.summary()["accounts"]
    assert isinstance(accounts, list)
    assert accounts[0]["relative_difference"] is None
