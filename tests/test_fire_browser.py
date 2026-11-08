"""Browser smoke test for the Fire workspace."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("uvicorn")
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright
from ws4.ecosystem.fire import FireConfig, FireRun, synthetic_grid
from ws4.scene import compile_fire_scene, synthetic_tree_inventory
from ws4.web.app import create_app


def _scene(run: Path, seed: int, scene_id: str) -> None:
    """Write one small deterministic fire scene into a run."""
    _grid, state, edges = synthetic_grid(2, 2)
    fire = FireRun(
        state,
        edges,
        FireConfig(ignition_rate_per_fragment_year=0.45, base_spread_probability=0.65),
        scenario_id=scene_id,
        seed=seed,
    ).run(3)
    trees = synthetic_tree_inventory(fire.state.fragment_areas, seed=seed, trees_per_ha=20.0)
    compile_fire_scene(
        fire,
        trees,
        scene_id=scene_id,
        particle_budget=300,
    ).write(run / "fire_scene")


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Create a dataset and two fire scenes."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    runs = tmp_path / "runs"
    for name, seed in (("run1", 11), ("run2", 12)):
        run = runs / name
        run.mkdir(parents=True)
        (run / "summary.json").write_text('{"status": "ok"}', encoding="utf-8")
        _scene(run, seed, f"{name}-scene")
    targets = tmp_path / "targets.yaml"
    targets.write_text("targets: []\n", encoding="utf-8")
    return dataset, runs


def _free_port() -> int:
    """Return a free local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_fire_workspace_opens_scene_and_comparison(tmp_path: Path) -> None:
    """The Fire workspace discovers scenes, inspects trees, and toggles comparison."""
    dataset, runs = _fixture(tmp_path)
    targets = tmp_path / "targets.yaml"
    app = create_app(dataset=dataset, runs=runs, targets=targets)
    import uvicorn

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("the test server did not start")
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
            page.goto(f"http://127.0.0.1:{port}/?run=run1&view=fire")
            page.wait_for_function(
                "document.querySelector('#ws-fire') && !document.querySelector('#ws-fire').hidden",
                timeout=15000,
            )
            page.wait_for_function(
                "document.querySelector('#fire-frame-a').src.includes('api/fire/runs/run1/viewer')",
                timeout=15000,
            )
            page.wait_for_function(
                "document.querySelector('#fire-summary').textContent.includes('run1-scene')",
                timeout=15000,
            )
            page.wait_for_function(
                "document.querySelectorAll('#fire-tree option').length > 0",
                timeout=15000,
            )
            frame = page.frame_locator("#fire-frame-a")
            frame.locator("#stat-trees").wait_for(state="attached", timeout=15000)
            page.check("#fire-compare")
            page.wait_for_function(
                "!document.querySelector('#fire-frame-card-b').hidden",
                timeout=15000,
            )
            page.wait_for_function(
                "document.querySelector('#fire-frame-b').src.includes('api/fire/runs/run2/viewer')",
                timeout=15000,
            )
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
