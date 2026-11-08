"""Behaviour tests for the 3D projection helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

APP = Path(__file__).resolve().parents[1] / "ws4" / "web" / "static" / "app.js"


def _run_helpers() -> dict[str, object]:
    """Evaluate the pure 3D helpers with Node."""
    source = APP.read_text(encoding="utf-8")
    start = source.index("function estate3dHeight")
    end = source.index("function estate3dRings")
    helpers = source[start:end]
    script = f"""
{helpers}
const transform = {{ cx: 10, cy: 20, scale: 2, yaw: 0, width: 100, height: 80, flatten: 0.5 }};
console.log(JSON.stringify({{
  untreated: estate3dHeight({{}}),
  treated: estate3dHeight({{ treated: true, current: true }}),
  aged: estate3dHeight({{ treated: true, age: 100 }}),
  center: estate3dProject(10, 20, transform),
  shifted: estate3dProject(20, 20, transform),
}}));
"""
    completed = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    # The Node harness emits a JSON object of helper outputs.
    return cast("dict[str, object]", json.loads(completed.stdout))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_3d_height_and_projection_are_bounded() -> None:
    """Treated/aged blocks are taller and the center projects to the viewport center."""
    result = _run_helpers()
    assert float(str(result["treated"])) > float(str(result["untreated"]))
    assert float(str(result["aged"])) > float(str(result["treated"]))
    assert result["center"] == [50.0, 40.0]
    assert result["shifted"] == [70.0, 40.0]
