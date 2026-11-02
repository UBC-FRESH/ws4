"""Tests for named scenario profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner
from ws4.cli import app
from ws4.opt.scenario_profiles import (
    ProfileError,
    get_profile,
    load_profiles,
)


def _library(tmp_path: Path) -> Path:
    """Write one valid profile library."""
    target = tmp_path / "targets.yaml"
    target.write_text("targets: []\n", encoding="utf-8")
    (tmp_path / "profiles").mkdir()
    library = tmp_path / "profiles" / "profiles.yaml"
    library.write_text(
        "base_dir: ..\n"
        "profiles:\n"
        "  - name: base\n"
        "    description: base profile\n"
        "    targets: targets.yaml\n"
        "    accounts: [feature.total]\n"
        "    schedule_out: runtime/base.csv\n"
        "  - name: control\n"
        "    targets: targets.yaml\n",
        encoding="utf-8",
    )
    return library


def test_profile_library_resolves_paths(tmp_path: Path) -> None:
    """Profiles resolve target and schedule paths from base_dir."""
    library = _library(tmp_path)
    profiles = load_profiles(library)
    assert set(profiles) == {"base", "control"}
    base = get_profile(profiles, "base")
    assert base.targets == (tmp_path / "targets.yaml").resolve()
    assert base.schedule_out == (tmp_path / "runtime" / "base.csv").resolve()
    assert base.accounts == ("feature.total",)


def test_profile_library_rejects_duplicates_and_missing_targets(tmp_path: Path) -> None:
    """Duplicate names and missing target files fail loudly."""
    library = _library(tmp_path)
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        "profiles:\n"
        "  - name: x\n"
        "    targets: targets.yaml\n"
        "  - name: x\n"
        "    targets: targets.yaml\n",
        encoding="utf-8",
    )
    with pytest.raises(ProfileError, match="duplicate"):
        load_profiles(duplicate)
    with pytest.raises(ProfileError, match="does not exist"):
        load_profiles(library.parent / "missing.yaml")


def test_scenario_profiles_cli_lists_json_and_shell(tmp_path: Path) -> None:
    """The CLI can discover, show, and emit shell exports for profiles."""
    library = _library(tmp_path)
    runner = CliRunner()
    listed = runner.invoke(
        app,
        ["scenario-profiles", "--profiles", str(library), "--json"],
    )
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.stdout)
    assert [item["name"] for item in payload] == ["base", "control"]
    shown = runner.invoke(
        app,
        ["scenario-profiles", "--profiles", str(library), "--name", "base", "--json"],
    )
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.stdout)["accounts"] == ["feature.total"]
    shell = runner.invoke(
        app,
        ["scenario-profiles", "--profiles", str(library), "--name", "base", "--shell"],
    )
    assert shell.exit_code == 0, shell.output
    assert "export TARGETS=" in shell.stdout
    assert "export ACCOUNTS=feature.total" in shell.stdout
