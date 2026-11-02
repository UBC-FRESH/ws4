"""Contract tests for the AU Explorer shell wiring."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "ws4" / "web" / "static"


def test_index_has_the_sdmd_workspace() -> None:
    """The shell exposes a fifth workspace and the AU Explorer controls."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for marker in (
        'id="ws-sdmd"',
        'id="workspace-sdmd"',
        'id="sdmd-canvas"',
        'id="sdmd-region"',
        'id="sdmd-au"',
        'id="sdmd-regime-editor"',
        'id="sdmd-save"',
        'id="sdmd-yield-chart"',
        'id="sdmd-diagram"',
        'id="sdmd-provenance"',
        'id="sdmd-interpretation"',
        'id="sdmd-yield-metric"',
        'id="sdmd-reset"',
        'id="sdmd-diagram-legend"',
    ):
        assert marker in html


def test_app_js_wires_the_sdmd_api() -> None:
    """The browser calls the read endpoints and the validated write endpoint."""
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    for marker in (
        "api/sdmd/regions",
        "api/sdmd/aus",
        "/constraint-preview",
        "/trajectory?regime_id=",
        "/constraints",
        "function renderSdmd",
        "function saveSdmdConstraints",
        "function loadSdmdAvailability",
        "function renderSdmdInterpretation",
        "sdmd-iso-height",
        "sdmd-trajectory",
    ):
        assert marker in javascript


def test_javascript_parses_when_node_is_available() -> None:
    """A syntax error in the shell would make the tab unusable."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--check", str(STATIC / "app.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
