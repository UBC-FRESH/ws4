"""Tests for generated default stock-guarded scenarios."""

from __future__ import annotations

from pathlib import Path

import yaml
from ws4.opt.default_scenario import (
    build_default_stock90_targets,
    find_initial_stock,
    initial_managed_stock,
)


def _run(path: Path, value: float, account: str = "feature.Yield.managed.Total") -> Path:
    """Write one run with an initial managed stock row."""
    path.mkdir(parents=True)
    (path / "account_values.csv").write_text(
        f"offset,account,value\n-1,{account},{value}\n0,{account},{value - 1}\n",
        encoding="utf-8",
    )
    return path


def test_initial_managed_stock_finds_the_aggregate(tmp_path: Path) -> None:
    run = _run(tmp_path / "run", 1000.0, "feature.Yield.managed")
    assert initial_managed_stock(run) is None
    _run(tmp_path / "run2", 1000.0)
    assert initial_managed_stock(tmp_path / "run2") == (
        "feature.Yield.managed.Total",
        1000.0,
    )


def test_find_initial_stock_uses_the_newest_run(tmp_path: Path) -> None:
    import os

    older = _run(tmp_path / "runs" / "older", 100.0)
    newer = _run(tmp_path / "runs" / "newer", 200.0)
    os.utime(older / "account_values.csv", (1_000_000, 1_000_000))
    os.utime(newer / "account_values.csv", (2_000_000, 2_000_000))
    account, value = find_initial_stock(tmp_path / "runs") or ("", 0.0)
    assert account == "feature.Yield.managed.Total"
    assert value == 200.0


def test_default_target_raises_volume_and_adds_the_stock_floor(tmp_path: Path) -> None:
    source = tmp_path / "targets.yaml"
    source.write_text(
        "targets:\n"
        "  - account: product.Yield.managed.Total\n"
        "    period: 1\n"
        "    period_width: 10\n"
        "    flow: even\n"
        "    minimum: -5\n"
        "    maximum: 5\n"
        "  - account: product.Yield.managed.Total\n"
        "    period: 1\n"
        "    period_width: 10\n"
        "    minimum: 1000\n"
        "    min_weight: 1\n"
        "  - account: product.Yield.managed.Total\n"
        "    period: 2\n"
        "    period_width: 10\n"
        "    minimum: 1000\n"
        "    min_weight: 1\n",
        encoding="utf-8",
    )
    output = build_default_stock90_targets(
        source,
        tmp_path / "default.yaml",
        initial_stock=1000.0,
        stock_account="feature.Yield.managed.Total",
    )
    entries = yaml.safe_load(output.read_text(encoding="utf-8"))["targets"]
    flow = next(entry for entry in entries if entry.get("flow"))
    assert flow["minimum"] == -5
    assert flow["maximum"] == 5
    levels = [
        entry
        for entry in entries
        if entry["account"].startswith("product.")
        and not entry.get("flow")
        and entry.get("period") in (1, 2)
    ]
    assert [entry["minimum"] for entry in levels] == [2000.0, 2000.0]
    stock = next(entry for entry in entries if entry["account"] == "feature.Yield.managed.Total")
    assert stock["period"] == 2
    assert stock["minimum"] == 900.0
    assert stock["normalization"] == "auto"


def test_default_target_can_force_volume_above_an_existing_guard(tmp_path: Path) -> None:
    """A caller can raise half-AAC bands while preserving the existing stock floor."""
    source = tmp_path / "targets.yaml"
    source.write_text(
        "targets:\n"
        "  - account: product.Yield.managed.Total\n"
        "    period: 1\n"
        "    minimum: 1000\n"
        "    maximum: 1100\n"
        "  - account: feature.Yield.managed.Total\n"
        "    period: 1\n"
        "    minimum: 950\n",
        encoding="utf-8",
    )
    output = build_default_stock90_targets(
        source,
        tmp_path / "default.yaml",
        initial_stock=1000.0,
        stock_account="feature.Yield.managed.Total",
        force_volume_multiplier=True,
    )
    entries = yaml.safe_load(output.read_text(encoding="utf-8"))["targets"]
    volume = next(entry for entry in entries if entry["account"] == "product.Yield.managed.Total")
    stock = next(entry for entry in entries if entry["account"] == "feature.Yield.managed.Total")
    assert volume["minimum"] == 2000.0
    assert volume["maximum"] == 2200.0
    assert stock["minimum"] == 950


def test_default_target_updates_a_weak_existing_stock_guard(tmp_path: Path) -> None:
    """A final stock row below 90% is replaced rather than duplicated."""
    source = tmp_path / "targets.yaml"
    source.write_text(
        "targets:\n"
        "  - account: product.Yield.managed.Total\n"
        "    period: 1\n"
        "    minimum: 1000\n"
        "  - account: feature.Yield.managed.Total\n"
        "    period: 1\n"
        "    minimum: 500\n",
        encoding="utf-8",
    )
    output = build_default_stock90_targets(
        source,
        tmp_path / "default.yaml",
        initial_stock=1000.0,
        stock_account="feature.Yield.managed.Total",
    )
    entries = yaml.safe_load(output.read_text(encoding="utf-8"))["targets"]
    stock = [entry for entry in entries if entry["account"] == "feature.Yield.managed.Total"]
    assert len(stock) == 1
    assert stock[0]["minimum"] == 900.0
    volume = next(entry for entry in entries if entry["account"] == "product.Yield.managed.Total")
    assert volume["minimum"] == 2000.0


def test_default_target_does_not_double_an_existing_stock_guard(tmp_path: Path) -> None:
    source = tmp_path / "targets.yaml"
    source.write_text(
        "targets:\n"
        "  - account: product.Yield.managed.Total\n"
        "    period: 1\n"
        "    minimum: 1000\n"
        "  - account: feature.Yield.managed.Total\n"
        "    period: 1\n"
        "    minimum: 950\n",
        encoding="utf-8",
    )
    output = build_default_stock90_targets(
        source,
        tmp_path / "default.yaml",
        initial_stock=1000.0,
        stock_account="feature.Yield.managed.Total",
    )
    entries = yaml.safe_load(output.read_text(encoding="utf-8"))["targets"]
    volume = next(entry for entry in entries if entry["account"] == "product.Yield.managed.Total")
    stock = next(entry for entry in entries if entry["account"] == "feature.Yield.managed.Total")
    assert volume["minimum"] == 1000
    assert stock["minimum"] == 950
