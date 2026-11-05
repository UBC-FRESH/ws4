"""Browser smoke test for the 3D Pareto solution-space workspace."""

from __future__ import annotations

import json
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


class _Server(Protocol):
    """The uvicorn server surface the test controls."""

    started: bool
    should_exit: bool


def _free_port() -> int:
    """Return a free local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _portfolio(tmp_path: Path) -> tuple[Path, Path]:
    """Create a run, a minimal target file, and a six-member portfolio."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    runs = tmp_path / "runs"
    run = runs / "run1"
    run.mkdir(parents=True)
    (run / "summary.json").write_text('{"status": "ok"}', encoding="utf-8")
    (run / "account_values.csv").write_text(
        "offset,account,value\n0,feature.Volume,1000\n1,feature.Volume,1100\n",
        encoding="utf-8",
    )
    (run / "schedule.csv").write_text("block_id,treatment,offset\n", encoding="utf-8")
    artifact = runs / "portfolio-demo"
    artifact.mkdir()
    members = []
    for index, (volume, old, cost) in enumerate(
        (
            (1100.0, 200.0, 800.0),
            (1050.0, 230.0, 760.0),
            (1000.0, 260.0, 720.0),
            (950.0, 290.0, 680.0),
            (900.0, 320.0, 640.0),
            (850.0, 350.0, 600.0),
        )
    ):
        label = f"member-{index:03d}"
        member = artifact / label / "seed-001"
        member.mkdir(parents=True)
        (member / "schedule.csv").write_text(
            "block_id,treatment,offset\n1,CC,0\n", encoding="utf-8"
        )
        (member / "summary.json").write_text(
            json.dumps({"status": "ok", "objective": float(index + 1)}), encoding="utf-8"
        )
        (member / "account_values.csv").write_text(
            f"offset,account,value\n0,feature.Volume,{volume}\n0,feature.Old,{old}\n",
            encoding="utf-8",
        )
        members.append(
            {
                "label": label,
                "seed": 1,
                "objective": float(index + 1),
                "metrics": {"volume": volume, "old": old, "cost": cost},
                "factors": {"feature.Volume": 1.0 + index / 10},
                "run_dir": str(member),
                "schedule": str(member / "schedule.csv"),
                "status": "ok",
            }
        )
    (artifact / "portfolio.json").write_text(
        json.dumps(
            {
                "metrics": ["volume", "old", "cost"],
                "directions": {
                    "volume": "max",
                    "old": "max",
                    "cost": "min",
                    "objective": "min",
                },
                "members": members,
                "front": [],
            }
        ),
        encoding="utf-8",
    )
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n"
        "  - account: feature.Volume\n    period: 1\n    minimum: 1000\n"
        "  - account: feature.Old\n    period: 1\n    minimum: 200\n",
        encoding="utf-8",
    )
    return runs, targets


def _server(tmp_path: Path) -> tuple[_Server, threading.Thread, str]:
    """Start the app in a background thread and return its URL."""
    runs, targets = _portfolio(tmp_path)
    app = create_app(dataset=tmp_path / "dataset", runs=runs, targets=targets)
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


def test_pareto_workspace_renders_and_filters(tmp_path: Path) -> None:
    """The 3D workspace loads a portfolio, renders points, and filters its view."""
    server, thread, url = _server(tmp_path)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=["--use-gl=swiftshader", "--enable-webgl"],
                )
            except Exception as error:  # pragma: no cover - browser not installed
                pytest.skip(f"chromium is not available: {error}")
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{url}/?run=run1&view=pareto")
            page.wait_for_function(
                "document.querySelector('#pareto-status').textContent.includes('members')",
                timeout=15000,
            )
            assert page.locator("#pareto-wrap").is_visible()
            assert page.locator("#pareto-canvas").is_visible()
            assert "exact front" in page.locator("#pareto-status").inner_text()
            assert page.locator("#pareto-artifact").input_value() == "portfolio-demo"
            page.select_option("#pareto-dominance", "front")
            page.wait_for_timeout(200)
            assert "VISIBLE" in page.locator("#pareto-stats").inner_text()
            page.select_option("#pareto-filter-dim", label="volume")
            page.locator("#pareto-filter").evaluate(
                "element => { element.value = '50'; "
                "element.dispatchEvent(new Event('input', { bubbles: true })); }"
            )
            page.wait_for_timeout(200)
            assert "filter volume" in page.locator("#pareto-legend").inner_text()
            page.select_option("#pareto-size", label="old")
            page.select_option("#pareto-opacity", label="cost")
            page.select_option("#pareto-x", label="cost")
            page.select_option("#pareto-y", label="volume")
            page.select_option("#pareto-z", label="old")
            page.select_option("#pareto-member", index=1)
            page.wait_for_function(
                "document.querySelector('#pareto-info').textContent.includes('member-')",
                timeout=15000,
            )
            page.click("#pareto-pin")
            assert "member-" in page.locator("#pareto-compare").inner_text()
            assert not page.locator("#pareto-open").is_disabled()
            with page.expect_popup():
                page.click("#pareto-open")
            page.click("#pareto-open-run")
            page.wait_for_function(
                "document.querySelector('#run').value.startsWith('pareto-')",
                timeout=20000,
            )
            page.wait_for_function(
                "!document.querySelector('#map-wrap').hidden",
                timeout=20000,
            )
            assert page.locator("#run").input_value().startswith("pareto-")
            page.set_viewport_size({"width": 1024, "height": 768})
            assert page.locator("#map-wrap").is_visible()
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_search_builds_a_scan_and_opens_the_explorer(tmp_path: Path) -> None:
    """The guided scan writes the vary expression and the 3D cross-link loads it."""
    server, thread, url = _server(tmp_path)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=["--use-gl=swiftshader", "--enable-webgl"],
                )
            except Exception as error:  # pragma: no cover - browser not installed
                pytest.skip(f"chromium is not available: {error}")
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{url}/?run=run1&view=results&sub=search")
            page.wait_for_function(
                "document.querySelectorAll('#scan-account option').length >= 2",
                timeout=15000,
            )
            page.locator("details.search-run").filter(has_text="Build a weight scan").evaluate(
                "element => { element.open = true; }"
            )
            page.select_option("#scan-account", label="feature.Volume")
            page.click("#scan-add")
            page.select_option("#scan-account", label="feature.Old")
            page.fill("#scan-factors", "0.5,1")
            page.click("#scan-add")
            assert "2 dimensions" in page.locator("#scan-summary").inner_text()
            page.click("#scan-use")
            assert "feature.Volume=0.5,1,2" in page.locator("#portfolio-vary").input_value()
            assert "feature.Old=0.5,1" in page.locator("#portfolio-vary").input_value()
            page.wait_for_function(
                "!document.querySelector('#search-explore').disabled",
                timeout=15000,
            )
            page.click("#search-explore")
            page.wait_for_function(
                "document.querySelector('#pareto-status').textContent.includes('members')",
                timeout=15000,
            )
            assert page.locator("#pareto-wrap").is_visible()
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_two_pinned_members_open_the_spatial_comparison(tmp_path: Path) -> None:
    """Pinned members are promoted and handed to the existing comparison workspace."""
    server, thread, url = _server(tmp_path)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=["--use-gl=swiftshader", "--enable-webgl"],
                )
            except Exception as error:  # pragma: no cover - browser not installed
                pytest.skip(f"chromium is not available: {error}")
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{url}/?run=run1&view=pareto")
            page.wait_for_function(
                "document.querySelector('#pareto-status').textContent.includes('members')",
                timeout=15000,
            )
            for index in (1, 2):
                page.select_option("#pareto-member", index=index)
                page.click("#pareto-pin")
            page.click("#pareto-compare-pinned")
            page.wait_for_function(
                "!document.querySelector('#tab-comparison').hidden",
                timeout=20000,
            )
            assert page.locator("#compare-a").input_value().startswith("pareto-")
            assert page.locator("#compare-b").input_value().startswith("pareto-")
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
