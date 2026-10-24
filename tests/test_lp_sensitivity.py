"""Tests for the advisory LP dual and reduced-cost report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from ws4.build.compiler import build_canonical_dataset

from lp_sensitivity import lp_report, main

pytest.importorskip("scipy")

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    """Compile the synthetic fixture and write an impossible volume floor."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n"
        "  - account: feature.Volume\n"
        "    period: 1\n"
        "    minimum: 1000\n"
        "    min_weight: 1\n",
        encoding="utf-8",
    )
    return dataset, targets


def test_lp_report_prices_a_binding_floor(tmp_path: Path) -> None:
    """An impossible floor is binding, has a positive dual, and names reduced costs."""
    dataset, targets = _setup(tmp_path)
    report = lp_report(dataset=dataset, targets=targets, years=1, limit_blocks=2)
    assert report["status"] == "optimal"
    assert report["variables"] == 2
    duals = report["duals"]
    assert isinstance(duals, list)
    assert duals[0]["bound"] == "minimum"
    assert duals[0]["binding"] is True
    assert duals[0]["dual"] > 0.0
    assert report["reduced_costs"]
    assert report["reduced_cost_total"] == 2
    assert "Dual is the objective reduction" in str(report["markdown"])


def test_lp_report_rejects_an_empty_top(tmp_path: Path) -> None:
    """A non-positive top is a configuration error, not an empty table."""
    dataset, targets = _setup(tmp_path)
    with pytest.raises(ValueError, match="top"):
        lp_report(dataset=dataset, targets=targets, top=0)


def test_main_writes_json_and_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI writes both reports and exits zero on an optimal LP."""
    dataset, targets = _setup(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lp_sensitivity.py",
            "--dataset",
            str(dataset),
            "--targets",
            str(targets),
            "--years",
            "1",
            "--limit-blocks",
            "2",
            "--out",
            str(out),
        ],
    )
    assert main() == 0
    payload = json.loads((out / "lp_sensitivity.json").read_text(encoding="utf-8"))
    assert payload["status"] == "optimal"
    assert (out / "lp_sensitivity.md").is_file()
