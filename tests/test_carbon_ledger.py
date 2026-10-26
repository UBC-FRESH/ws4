"""Tests for the block-level carbon ledger and carbon target guard."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.objective import Target


def test_carbon_targets_require_a_package() -> None:
    """A carbon target without a package is rejected before the search."""
    optimizer = Optimizer(Path("."), OptimizeConfig())
    with pytest.raises(ValueError, match="carbon targets"):
        optimizer._require_carbon_target_support(
            [Target(account="carbon.ecosystem.total", minimum=1.0)]
        )
    optimizer_with_package = Optimizer(Path("."), OptimizeConfig(carbon_package_path="pkg"))
    optimizer_with_package._require_carbon_target_support(
        [Target(account="carbon.ecosystem.total", minimum=1.0)]
    )


def test_ledger_matches_a_full_run(tmp_path: Path) -> None:
    """The block ledger reproduces the full-schedule carbon accounts."""
    pytest.importorskip("libcbm")
    from ws4.carbon.ledger import CarbonLedger
    from ws4.carbon.libcbm import carbon_accounts, cbm_defaults_reference, run_libcbm
    from ws4.carbon.sit import build_sit_tables

    from test_carbon_sit import _schedule, _write_dataset, _write_package

    package = _write_package(tmp_path / "package")
    package.manifest.cbm_defaults.sha256 = cbm_defaults_reference().sha256
    dataset = _write_dataset(tmp_path / "dataset")
    schedule_frame = _schedule()
    schedule = {
        1: (("CC", 0),),
        2: (("fire", 5),),
    }
    ledger = CarbonLedger(dataset, package, years=10)
    ledger_values = ledger.schedule_values(schedule)

    tables = build_sit_tables(package, dataset, schedule_frame)
    run = run_libcbm(package, tables, n_steps=10)
    full = carbon_accounts(run)
    full_values = {
        (int(str(row.offset)), str(row.account)): float(str(row.value))
        for row in full.itertuples(index=False)
    }
    common = set(ledger_values) & set(full_values)
    assert common
    max_difference = max(abs(ledger_values[cell] - full_values[cell]) for cell in common)
    assert max_difference == pytest.approx(0.0, abs=1e-6)


def test_ledger_empty_matches_the_empty_schedule(tmp_path: Path) -> None:
    """The ledger's base values match a full empty-schedule run."""
    pytest.importorskip("libcbm")
    from ws4.carbon.ledger import CarbonLedger
    from ws4.carbon.libcbm import carbon_accounts, cbm_defaults_reference, run_libcbm
    from ws4.carbon.sit import build_sit_tables

    from test_carbon_sit import _write_dataset, _write_package

    package = _write_package(tmp_path / "package")
    package.manifest.cbm_defaults.sha256 = cbm_defaults_reference().sha256
    dataset = _write_dataset(tmp_path / "dataset")
    empty = pd.DataFrame({"block_id": [], "treatment": [], "offset": []})
    ledger = CarbonLedger(dataset, package, years=5)
    ledger_values = ledger.base_values()
    tables = build_sit_tables(package, dataset, empty)
    run = run_libcbm(package, tables, n_steps=5)
    full = carbon_accounts(run)
    full_values = {
        (int(str(row.offset)), str(row.account)): float(str(row.value))
        for row in full.itertuples(index=False)
    }
    common = set(ledger_values) & set(full_values)
    assert common
    max_difference = max(abs(ledger_values[cell] - full_values[cell]) for cell in common)
    assert max_difference == pytest.approx(0.0, abs=1e-6)
