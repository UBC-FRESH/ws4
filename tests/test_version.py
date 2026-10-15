"""The package version is declared in one place and stays consistent."""

from __future__ import annotations

import tomllib
from pathlib import Path

import ws4

ROOT = Path(__file__).resolve().parents[1]


def test_version_matches_pyproject() -> None:
    """``ws4.__version__`` matches the version in ``pyproject.toml``."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert ws4.__version__ == project["version"]


def test_version_is_release_shaped() -> None:
    """The version is a dotted release number."""
    parts = ws4.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
