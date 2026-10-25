"""Tests for dataset provenance sidecars and the quality command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner
from ws4.build.compiler import build_canonical_dataset
from ws4.cli import app
from ws4.opt.repro import dataset_quality, load_provenance

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _dataset(tmp_path: Path) -> Path:
    return build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )


def _sidecar(dataset: Path) -> Path:
    path = dataset / "data_quality.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "inventory": {"vintage": "2025", "imputation_share": None},
                "curves": {"source": "VDYP7 transform", "accepted": False},
                "thlb": {"source": "predecessor-derived", "reviewed": False},
                "limitations": ["Not an accepted TIPSY curve."],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def test_sidecar_loader_rejects_a_non_mapping(tmp_path: Path) -> None:
    """A sidecar must be a mapping with the supported schema."""
    dataset = _dataset(tmp_path)
    (dataset / "data_quality.yaml").write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_provenance(dataset)


def test_sidecar_makes_the_quality_report_ok(tmp_path: Path) -> None:
    """A valid sidecar is reported as supplied and makes the dataset status ok."""
    dataset = _dataset(tmp_path)
    _sidecar(dataset)
    report = dataset_quality(dataset)
    assert report["provenance"] is not None
    assert report["summary"]["provenance_supplied"] is True
    assert report["summary"]["status"] == "ok"
    assert any(
        check["name"] == "provenance" and check["status"] == "ok" for check in report["checks"]
    )
    assert "Not an accepted TIPSY curve." in report["limitations"]


def test_missing_sidecar_is_unknown(tmp_path: Path) -> None:
    """Without a sidecar the report remains unknown, not a pass."""
    dataset = _dataset(tmp_path)
    report = dataset_quality(dataset)
    assert report["summary"]["provenance_supplied"] is False
    assert report["summary"]["status"] == "unknown"
    assert any("not supplied" in warning for warning in report["summary"]["warnings"])


def test_quality_command_checks_and_writes(tmp_path: Path) -> None:
    """--check fails without a sidecar and passes with one."""
    dataset = _dataset(tmp_path)
    runner = CliRunner()
    missing = runner.invoke(app, ["quality", "--dataset", str(dataset), "--check"])
    assert missing.exit_code == 1
    _sidecar(dataset)
    out = tmp_path / "report"
    passed = runner.invoke(
        app,
        ["quality", "--dataset", str(dataset), "--out", str(out), "--check"],
    )
    assert passed.exit_code == 0, passed.output
    payload = json.loads((out / "quality.json").read_text(encoding="utf-8"))
    assert payload["summary"]["provenance_supplied"] is True
    assert (out / "quality.md").is_file()


def test_quality_command_installs_a_sidecar(tmp_path: Path) -> None:
    """--sidecar copies the tracked record beside the matrix before checking."""
    dataset = _dataset(tmp_path)
    sidecar = tmp_path / "tracked_quality.yaml"
    sidecar.write_text("schema_version: 1\ninventory:\n  vintage: '2025'\n", encoding="utf-8")
    out = tmp_path / "installed"
    result = CliRunner().invoke(
        app,
        [
            "quality",
            "--dataset",
            str(dataset),
            "--sidecar",
            str(sidecar),
            "--out",
            str(out),
            "--check",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (dataset / "data_quality.yaml").is_file()
    assert (out / "quality.json").is_file()
