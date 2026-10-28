#!/usr/bin/env python3
"""Smoke-test attaching to a solver started outside the browser.

Opt-in: requires Playwright, Chromium, and a service started with ``--allow-runs``. The
script starts a one-minute run through the service API, then opens the shell without a run
query so the automatic live-run selection has to find it.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import urllib.request
from typing import Any


def request_json(url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a JSON response from the service.

    Parameters
    ----------
    url : str
        Absolute endpoint URL.
    body : dict or None, optional
        JSON request body; omitted for GET.

    Returns
    -------
    dict
        Decoded response.
    """
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result: dict[str, Any] = json.loads(response.read())
        return result


def check(  # pragma: no cover - needs a browser
    url: str, *, seed: int = 17, wait_ms: int = 9000
) -> int:
    """Start an external run, open the shell, and verify attach and refresh.

    Parameters
    ----------
    url : str
        Service root with ``--allow-runs``.
    seed : int, optional
        Seed for the external run.
    wait_ms : int, optional
        Milliseconds to wait after the initial page load.

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
    base = url.rstrip("/") + "/"
    try:
        run = request_json(
            base + "api/runs",
            {
                "iterations": 0,
                "patience": 0,
                "time_limit": "00:02:00",
                "seed": seed,
                "years": 50,
                "islands": 1,
            },
        )
    except Exception as exc:
        print(f"could not start the external run: {exc}", file=sys.stderr)
        return 1
    run_id = str(run["id"])
    for _attempt in range(20):
        try:
            listing = request_json(base + "api/summary")
        except Exception:
            listing = {}
        if any(item.get("id") == run_id for item in listing.get("runs", [])):
            break
        import time

        time.sleep(0.5)
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
            page.goto(f"{base}?run={run_id}", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(wait_ms)
            selected = page.locator("#run").input_value()
            assert selected == run_id, (selected, run_id)
            page.locator("#ws-plan").click()
            page.wait_for_timeout(1000)
            assert page.locator("#target-chart-live").is_visible(), "live badge is hidden"
            assert page.locator(".target-chart-card").count() > 0, "no target charts"
            readout = page.locator(".target-chart-readout").first
            page.wait_for_function(
                """() => {
                    const readout = document.querySelector('.target-chart-readout');
                    return readout && !readout.textContent.includes('achieved —');
                }""",
                timeout=60000,
            )
            before = readout.inner_text()
            page.wait_for_timeout(5000)
            after = readout.inner_text()
            assert "achieved" in after, after
            assert after != before or "achieved —" not in after, (before, after)

            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            assert page.locator("#run").input_value() == run_id, "refresh lost the live run"
            page.locator("#ws-plan").click()
            page.wait_for_timeout(800)
            assert page.locator("#target-chart-live").is_visible(), "refresh lost live badge"
            assert page.locator(".target-chart-card").count() > 0, "refresh lost charts"
            page.locator("#ws-map").click()
            page.wait_for_function(
                "() => document.querySelector('#status').textContent.startsWith('live')",
                timeout=60000,
            )
            page.wait_for_timeout(1500)
            assert page.locator("#n-treated").inner_text() != "", "map has no counts"
            assert not errors, errors
        except Exception as exc:
            print(f"live-attach check failed: {exc}", file=sys.stderr)
            print("\n".join(errors), file=sys.stderr)
            return 1
        finally:
            with contextlib.suppress(Exception):
                request_json(
                    base + f"api/runs/{run_id}/control",
                    {"action": "stop"},
                )
            browser.close()
    print("live attach: external run selected, charts update, refresh attaches, map live")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="service root with --allow-runs")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--wait-ms", type=int, default=9000)
    args = parser.parse_args()
    sys.exit(check(args.url, seed=args.seed, wait_ms=args.wait_ms))
