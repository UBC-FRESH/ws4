"""Tests for the block-level carbon ledger and carbon target guard."""

from __future__ import annotations

import os
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


def test_carbon_fertilization_requires_a_package() -> None:
    """A fertilization configuration without a carbon package is a configuration error."""
    with pytest.raises(ValueError, match="carbon fertilization"):
        OptimizeConfig(carbon_fertilization_path="fertilization.yaml")


def test_fertilization_targets_require_a_fertilization_config() -> None:
    """A fertilization account target needs the fertilization configuration."""
    optimizer = Optimizer(Path("."), OptimizeConfig(carbon_package_path="pkg"))
    with pytest.raises(ValueError, match="fertilization config"):
        optimizer._require_carbon_target_support(
            [Target(account="fertilization.co2e_t", maximum=1.0)]
        )


def test_hwp_targets_require_a_hwp_config() -> None:
    """An HWP or whole-system target needs the lifecycle assumptions."""
    optimizer = Optimizer(Path("."), OptimizeConfig(carbon_package_path="pkg"))
    with pytest.raises(ValueError, match="HWP config"):
        optimizer._require_carbon_target_support(
            [Target(account="carbon.co2e.system.emissions", maximum=1.0)]
        )
    configured = Optimizer(
        Path("."),
        OptimizeConfig(carbon_package_path="pkg", carbon_hwp_path="hwp.yaml"),
    )
    configured._require_carbon_target_support(
        [Target(account="carbon.co2e.system.emissions", maximum=1.0)]
    )


def test_hwp_config_requires_a_carbon_package() -> None:
    """HWP assumptions alone are not a carbon run."""
    with pytest.raises(ValueError, match="carbon HWP accounting"):
        OptimizeConfig(carbon_hwp_path="hwp.yaml")


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


def test_parallel_base_matches_serial(tmp_path: Path) -> None:
    """Fork workers produce the same empty-schedule base as a serial ledger."""
    if os.name != "posix":
        pytest.skip("fork-based carbon workers are POSIX-only")
    pytest.importorskip("libcbm")
    from ws4.carbon.ledger import CarbonLedger
    from ws4.carbon.libcbm import cbm_defaults_reference

    from test_carbon_sit import _write_dataset, _write_package

    package = _write_package(tmp_path / "package")
    package.manifest.cbm_defaults.sha256 = cbm_defaults_reference().sha256
    dataset = _write_dataset(tmp_path / "dataset")
    serial = CarbonLedger(dataset, package, years=5)
    parallel = CarbonLedger(dataset, package, years=5, base_workers=2)
    assert parallel.base_values() == serial.base_values()


def test_ledger_prices_duplicate_stand_states_once(tmp_path: Path) -> None:
    """Two blocks with the same track and age share one per-hectare carbon state."""
    pytest.importorskip("libcbm")
    from ws4.carbon.ledger import CarbonLedger
    from ws4.carbon.libcbm import cbm_defaults_reference

    from test_carbon_sit import _write_dataset, _write_package

    dataset = _write_dataset(tmp_path / "dataset")
    fragments = pd.read_parquet(dataset / "fragments.parquet")
    duplicate = fragments.iloc[[0]].copy()
    duplicate["fragment_id"] = 3
    duplicate["block_id"] = 3
    pd.concat([fragments, duplicate], ignore_index=True).to_parquet(
        dataset / "fragments.parquet", index=False
    )
    package = _write_package(tmp_path / "package")
    package.manifest.cbm_defaults.sha256 = cbm_defaults_reference().sha256
    ledger = CarbonLedger(dataset, package, years=5)
    ledger.prepare({block: [()] for block in ledger.block_ids})
    assert len(ledger._unit_cache) == 2


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
