#!/usr/bin/env python3
"""Smoke-test live MapLibre blocks and target charts during a real solver run.

Opt-in: requires Playwright, Chromium, and a service started with ``--allow-runs``.
The run is stopped at the end; it writes a run directory, so use a scratch service.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def wait_ready(page: Any) -> None:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Wait for the initial run context and map.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Loaded shell page.
    """
    page.wait_for_function(
        """() => {
            const status = document.querySelector('#status');
            const run = document.querySelector('#run');
            return status && run && run.value && !status.textContent.startsWith('loading');
        }""",
        timeout=90000,
    )
    page.wait_for_timeout(1200)


def chart_achieved(page: Any) -> str:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Return the first pinned chart's achieved readout.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Page with the Plan workspace open.

    Returns
    -------
    str
        Readout text, or an empty string when no chart is present.
    """
    readout = page.locator(".target-chart-readout").first
    return readout.inner_text() if readout.count() else ""


def check(  # pragma: no cover - needs a browser
    url: str, run: str | None = None, *, wait_ms: int = 12000
) -> int:
    """Start a short run and assert live map counts plus target-chart updates.

    Parameters
    ----------
    url : str
        Service root with ``--allow-runs``.
    run : str or None, optional
        Run id to select; None keeps the page's preferred run.
    wait_ms : int, optional
        Milliseconds to wait after selecting a run.

    Returns
    -------
    int
        ``0`` on success, ``1`` on a failed assertion, and ``2`` when the browser is
        unavailable.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed; run `pip install playwright` first", file=sys.stderr)
        return 2
    errors: list[str] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            print(f"chromium is not available: {exc}", file=sys.stderr)
            return 2
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            page.on(
                "console",
                lambda message: (
                    errors.append(f"{message.type}: {message.text}")
                    if message.type == "error" and "Failed to load resource" not in message.text
                    else None
                ),
            )
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            wait_ready(page)
            if run:
                page.select_option("#run", run)
                page.wait_for_timeout(wait_ms)
                wait_ready(page)
            baseline = page.locator("#n-treated").inner_text()
            page.locator("#ws-plan").click()
            page.wait_for_timeout(800)
            chart_before = chart_achieved(page)
            page.fill("#run-iterations", "0")
            page.fill("#run-islands", "1")
            page.fill("#run-years", "50")
            page.fill("#run-time-limit", "00:00:30")
            page.click("#start-run")
            page.locator("#ws-map").click()
            page.wait_for_function(
                "() => document.querySelector('#status').textContent.startsWith('live')",
                timeout=90000,
            )
            page.wait_for_function(
                """() => Number(
                    document.querySelector('#n-treated').textContent.replaceAll(',', '')
                ) > 0""",
                timeout=90000,
            )
            live_counts = page.locator("#n-treated").inner_text()
            live_status = page.locator("#status").inner_text()
            assert live_status != baseline or live_counts != baseline, "map counts did not change"

            canvas = page.locator("#maplibre-map canvas")
            box = canvas.bounding_box()
            assert box is not None, "map canvas is missing"
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 100, y + 50, steps=8)
            page.mouse.up()
            page.wait_for_timeout(3500)
            assert page.locator("#status").inner_text().startswith("live"), "pan left live mode"
            assert page.locator("#n-treated").inner_text() != "0", "pan dropped live colours"

            page.locator("#ws-plan").click()
            page.wait_for_timeout(1200)
            chart_after = chart_achieved(page)
            assert chart_before, "no pinned target chart"
            assert chart_after, "target chart has no readout"
            assert chart_after != chart_before, (chart_before, chart_after)

            page.locator("#ws-map").click()
            page.wait_for_timeout(700)
            assert page.locator("#status").inner_text().startswith("live"), "map left live mode"
            assert page.locator("#n-treated").inner_text() != "0", "live count reset"

            toggle = page.locator("#map-legend input[type='checkbox']")
            assert toggle.count() == 1, "live/static toggle is missing"
            toggle.uncheck()
            page.wait_for_function(
                """() => {
                    const text = document.querySelector('#status').textContent;
                    return !text.startsWith('live') && !text.startsWith('loading');
                }""",
                timeout=60000,
            )
            static_count = page.locator("#n-treated").inner_text()
            assert static_count != "", "static count is empty"
            assert static_count != "0", "static count is zero"
            page.locator("#map-legend input[type='checkbox']").check()
            page.wait_for_function(
                "() => document.querySelector('#status').textContent.startsWith('live')",
                timeout=60000,
            )
            page.wait_for_timeout(1000)
            assert page.locator("#n-treated").inner_text() != "0", "live toggle cleared counts"

            if page.locator("#stop-run").is_visible():
                page.locator("#stop-run").click()
            page.wait_for_function(
                "() => !document.querySelector('#status').textContent.startsWith('live')",
                timeout=60000,
            )
            assert not errors, errors
        except Exception as exc:
            print(f"live-map check failed: {exc}", file=sys.stderr)
            print("\n".join(errors), file=sys.stderr)
            return 1
        finally:
            browser.close()
    print("live map: counts change, target chart changes, run stops and static map returns")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="service root with --allow-runs")
    parser.add_argument("--run", help="run id to select")
    parser.add_argument("--wait-ms", type=int, default=12000)
    args = parser.parse_args()
    sys.exit(check(args.url, args.run, wait_ms=args.wait_ms))
