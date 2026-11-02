"""Browser smoke test for the AU Explorer tab."""

from __future__ import annotations

import json
import shutil
import socket
import threading
import time
from pathlib import Path
from typing import Protocol

import pytest

pytest.importorskip("uvicorn")
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright
from ws4.web.app import create_app

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"
DIAGRAM = (
    Path(__file__).resolve().parents[1]
    / "ws4"
    / "sdmd"
    / "data"
    / "sdmd"
    / "idf-dk3-fdi-illustrative.json"
)
AU = "AU-IDFdk3-FDI"


class _Server(Protocol):
    """The uvicorn server surface the test controls."""

    started: bool
    should_exit: bool


def _store_dir(tmp_path: Path) -> Path:
    """Build a store directory from the fixture and the diagram."""
    root = tmp_path / "sdmd"
    shutil.copytree(FIXTURE, root)
    shutil.copy(DIAGRAM, root / "diagram.json")
    trajectory = root / "trajectories" / AU / "REG-A-CT60.json"
    trajectory.parent.mkdir(parents=True)
    trajectory.write_text(
        json.dumps({"points": [[2400.0, 0.214], [1700.0, 0.543]]}) + "\n",
        encoding="utf-8",
    )
    return root


def _free_port() -> int:
    """Return a free local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _server(tmp_path: Path) -> tuple[_Server, threading.Thread, str]:
    """Start the app in a background thread and return its URL."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    runs = tmp_path / "runs"
    run = runs / "run1"
    run.mkdir(parents=True)
    (run / "summary.json").write_text('{"status": "ok", "objective": 0.0}', encoding="utf-8")
    (run / "account_values.csv").write_text(
        "offset,account,value\n0,feature.Volume,1.0\n", encoding="utf-8"
    )
    (run / "schedule.csv").write_text("block_id,treatment,offset\n", encoding="utf-8")
    app = create_app(dataset=dataset, runs=runs, sdmd_dir=_store_dir(tmp_path))
    import uvicorn

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("the test server did not start")
    return server, thread, f"http://127.0.0.1:{port}"


def test_au_explorer_tab_renders(tmp_path: Path) -> None:
    """The SDMD workspace renders charts and the constraint editor."""
    server, thread, url = _server(tmp_path)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as error:  # pragma: no cover - browser not installed
                pytest.skip(f"chromium is not available: {error}")
            page = browser.new_page()
            page.goto(f"{url}/?run=run1&view=sdmd")
            page.wait_for_selector("#sdmd-canvas:not([hidden])", timeout=15000)
            page.wait_for_function(
                "document.querySelector('#sdmd-title').textContent.includes('AU-')",
                timeout=15000,
            )
            page.wait_for_function(
                "document.querySelectorAll('#sdmd-yield-chart path').length > 0",
                timeout=15000,
            )
            page.wait_for_function(
                "document.querySelectorAll('#sdmd-diagram circle').length > 0",
                timeout=15000,
            )
            page.wait_for_function(
                "document.querySelectorAll('#sdmd-regime-editor .sdmd-regime-row').length === 7",
                timeout=15000,
            )
            page.set_viewport_size({"width": 1024, "height": 768})
            assert page.locator("#sdmd-canvas").is_visible()
            assert page.locator("#sdmd-regime-editor .sdmd-regime-row").count() == 7
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
