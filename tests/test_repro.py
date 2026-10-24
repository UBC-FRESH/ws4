"""Tests for the run manifest and data-quality report."""

from __future__ import annotations

import json
from pathlib import Path

from ws4.build.compiler import build_canonical_dataset
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.repro import dataset_quality, write_reproducibility

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _dataset(tmp_path: Path) -> Path:
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml", _FIXTURE / "fragments.csv", tmp_path / "compiled"
    )
    return dataset


def _targets(tmp_path: Path, account: str = "feature.Volume") -> Path:
    path = tmp_path / "targets.yaml"
    path.write_text(
        f"targets:\n  - account: {account}\n    period: 1\n    maximum: 500\n",
        encoding="utf-8",
    )
    return path


def test_manifest_records_code_dataset_config_and_reproducer(tmp_path: Path) -> None:
    """The manifest names the code, dataset reference, configuration, and reproducer."""
    dataset = _dataset(tmp_path)
    targets = _targets(tmp_path)
    run = tmp_path / "run"
    report = write_reproducibility(
        run,
        dataset,
        OptimizeConfig(targets_path=str(targets), years=1, iterations=3, seed=7),
    )
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((run / "data_quality.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["dataset"]["path"] == str(dataset)
    assert manifest["dataset"]["reference"]["manifest_sha256"]
    assert manifest["configuration"]["seed"] == 7
    assert manifest["seeds"] == [7]
    assert manifest["targets"]["active_accounts"] == ["feature.Volume"]
    assert "ws4 optimize" in manifest["reproduce"]["command"]
    assert manifest["quality"]["summary"]["metadata_supplied"] is False
    assert quality["checks"]
    assert report["manifest_path"] == str(run / "run_manifest.json")


def test_quality_reports_missing_metadata_and_absent_targets(tmp_path: Path) -> None:
    """An empty metadata block is unknown; a missing target account is a warning."""
    dataset = _dataset(tmp_path)
    targets = _targets(tmp_path, "feature.DoesNotExist")
    report = dataset_quality(dataset, targets)
    assert report["summary"]["metadata_supplied"] is False
    assert report["summary"]["status"] in {"warn", "unknown"}
    assert report["target_accounts"]["missing"] == ["feature.DoesNotExist"]
    assert any(
        check["name"] == "target_coverage" and check["status"] == "warn"
        for check in report["checks"]
    )
    assert any("No inventory vintage" in line for line in report["limitations"])


def test_quality_marks_present_metadata_and_targets(tmp_path: Path) -> None:
    """Supplied metadata and a matrix account are reported as checked/good."""
    dataset = _dataset(tmp_path)
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    manifest["metadata"] = {"inventory_vintage": "2025", "imputation_share": 0.0}
    (dataset / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = dataset_quality(dataset, _targets(tmp_path))
    assert report["metadata"] == {"inventory_vintage": "2025", "imputation_share": 0.0}
    assert report["summary"]["metadata_supplied"] is True
    assert report["target_accounts"]["missing"] == []


def test_optimizer_writes_the_reproducibility_artefacts(tmp_path: Path) -> None:
    """Every optimizer run writes the manifest and quality report beside the summary."""
    dataset = _dataset(tmp_path)
    targets = _targets(tmp_path)
    cfg = OptimizeConfig(targets_path=str(targets), years=1, iterations=2, seed=1, threads=1)
    run = tmp_path / "run"
    summary = Optimizer.from_dataset(dataset, cfg).run(run)
    assert summary["run_manifest"] == "run_manifest.json"
    assert summary["data_quality_report"] == "data_quality.json"
    assert isinstance(summary["data_quality"], dict)
    assert (run / "run_manifest.json").is_file()
    assert (run / "data_quality.json").is_file()
