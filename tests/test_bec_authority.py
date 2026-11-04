"""Contract tests for the packaged BEC authority tables and manifest."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ws4" / "sdmd" / "data" / "sdmd"


def _authority() -> Any:  # noqa: ANN401 - test-only dynamic module loader
    """Load the script without making ``scripts`` an import package.

    Returns
    -------
    Any
        The loaded module. Its attributes are dynamic by design.
    """
    spec = importlib.util.spec_from_file_location(
        "check_bec_authority_test", ROOT / "scripts" / "check_bec_authority.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


authority = _authority()


def _copy_data(tmp_path: Path) -> Path:
    """Copy the authority CSVs and manifest to a temporary directory."""
    target = tmp_path / "data"
    target.mkdir()
    for path in DATA.iterdir():
        if path.is_file():
            shutil.copy(path, target / path.name)
    return target


def test_bec_authority_tables_and_manifest_agree() -> None:
    """The packaged tables, counts, and SHA-256 manifest stay in step."""
    assert authority.check_bec_authority(DATA, DATA / "bec_sources.json") == []


def test_bec_authority_detects_a_count_change(tmp_path: Path) -> None:
    """A changed row count fails the contract."""
    data = _copy_data(tmp_path)
    path = data / "bec_variants.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    failures = authority.check_bec_authority(data, data / "bec_sources.json")
    assert any("229 rows" in item for item in failures)


def test_bec_authority_detects_a_digest_change(tmp_path: Path) -> None:
    """A changed file digest fails the manifest check."""
    data = _copy_data(tmp_path)
    path = data / "bec_official.csv"
    path.write_text(path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    failures = authority.check_bec_authority(data, data / "bec_sources.json")
    assert any("digest changed" in item for item in failures)


def test_bec_authority_detects_a_missing_manifest(tmp_path: Path) -> None:
    """A missing source manifest is a failure, not a silent pass."""
    data = _copy_data(tmp_path)
    failures = authority.check_bec_authority(data, data / "missing.json")
    assert any("missing source manifest" in item for item in failures)


def test_bec_authority_main_reports_success() -> None:
    """The CLI entry point returns zero on a clean tree."""
    assert authority.main() == 0


def test_bec_authority_main_reports_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI entry point returns one and prints every failure."""
    module: ModuleType = authority
    monkeypatch.setattr(module, "check_bec_authority", lambda: ["bad table"])
    assert authority.main() == 1
    assert "FAIL bad table" in capsys.readouterr().out


def test_bec_authority_detects_table_contract_changes(tmp_path: Path) -> None:
    """Every authority table has a count and relationship contract."""
    data = _copy_data(tmp_path)
    official = data / "bec_official.csv"
    official.write_text(
        "\n".join(official.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8"
    )
    retired = data / "bec_retired.csv"
    retired.write_text(
        "\n".join(retired.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8"
    )
    counts = data / "tsa_bec_counts.csv"
    counts_frame = pd.read_csv(counts)
    counts_frame = counts_frame.drop(columns=["bec_level"]).iloc[:-1]
    counts_frame.to_csv(counts, index=False)
    official_crosswalk = data / "bec_official_crosswalk.csv"
    frame = pd.read_csv(official_crosswalk)
    frame.loc[0, "relationship"] = "bad"
    frame.to_csv(official_crosswalk, index=False)
    cciss = data / "bec_crosswalk_review.csv"
    frame = pd.read_csv(cciss)
    frame.loc[0, "relationship"] = "bad"
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    frame.to_csv(cciss, index=False)
    failures = authority.check_bec_authority(data, data / "bec_sources.json")
    for needle in (
        "219 unique current labels",
        "107 unique retired labels",
        "304 normalized variant rows",
        "variant-level support",
        "unexpected official crosswalk counts",
        "unexpected CCISS crosswalk counts",
        "duplicate label pairs",
    ):
        assert any(needle in item for item in failures), needle


def test_bec_authority_detects_manifest_coverage_gaps(tmp_path: Path) -> None:
    """A manifest that names a missing file or omits a table fails."""
    data = _copy_data(tmp_path)
    manifest = data / "bec_sources.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["files"]["missing.csv"] = {"sha256": "0"}
    payload["files"].pop("bec_variants.csv")
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    failures = authority.check_bec_authority(data, manifest)
    assert any("missing file" in item for item in failures)
    assert any("does not cover bec_variants.csv" in item for item in failures)
