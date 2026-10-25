#!/usr/bin/env python3
"""Smoke-test the Solve and Stop controls in a headless browser.

This is an opt-in check, not a CI gate: it needs Playwright and a Chromium build.
Install them with ``pip install playwright`` and ``python -m playwright install chromium``.

Run it against a service started with ``--allow-runs`` and a **scratch** targets
file. By default the check leaves **Max iters** blank, asserts that the run is
continuous with no time limit, and stops it. Pass a positive ``--iterations`` to
check a bounded run instead.
"""

from __future__ import annotations

import argparse
import json
import sys


def check(  # pragma: no cover - needs a browser
    url: str, *, wait_ms: int = 12000, iterations: int = 0
) -> int:
    """Click Solve, assert the run request and control state, then Stop.

    Parameters
    ----------
    url : str
        Service root, for example ``http://127.0.0.1:8022/``.
    wait_ms : int, optional
        Milliseconds to wait for the initial run and map.
    iterations : int, optional
        Iterations per island for a bounded check. ``0`` leaves the field blank
        and expects a continuous run.

    Returns
    -------
    int
        ``0`` when the controls start and stop a run, ``1`` on a failed assertion,
        and ``2`` when the browser is unavailable.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed; run `pip install playwright` first", file=sys.stderr)
        return 2
    posts: list[tuple[int, str]] = []
    errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # the browser may be absent
            print(f"chromium is not available: {exc}", file=sys.stderr)
            return 2
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.on(
            "console",
            lambda message: (
                errors.append(f"{message.type}: {message.text}")
                if message.type == "error"
                else None
            ),
        )
        page.on("pageerror", lambda exc: page_errors.append(f"pageerror: {exc}"))
        page.on(
            "response",
            lambda response: (
                posts.append((response.status, response.text()))
                if response.request.method == "POST" and "/api/runs" in response.url
                else None
            ),
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        page.get_by_role("button", name="Targets").click()
        page.wait_for_timeout(500)
        if iterations > 0:
            page.fill("#run-iterations", str(iterations))
        elif page.locator("#run-iterations").input_value() != "":
            print("the default Max iters field is not blank", file=sys.stderr)
            browser.close()
            return 1
        page.fill("#run-islands", "1")
        page.click("#start-run")
        page.wait_for_timeout(5000)
        if not posts:
            print("Solve made no POST /api/runs request", file=sys.stderr)
            browser.close()
            return 1
        status, body = posts[-1]
        if status != 200:
            print(f"POST /api/runs returned {status}: {body}", file=sys.stderr)
            browser.close()
            return 1
        if iterations <= 0:
            payload = json.loads(body)
            if not payload.get("continuous"):
                print(f"the default run is not continuous: {body}", file=sys.stderr)
                browser.close()
                return 1
            if payload.get("time_limit"):
                print(f"the default run has a time limit: {body}", file=sys.stderr)
                browser.close()
                return 1
        button = page.locator("#start-run").inner_text()
        if "Pause" not in button and "Solve" not in button:
            print(f"the start button is in an unexpected state: {button!r}", file=sys.stderr)
            browser.close()
            return 1
        print(f"POST /api/runs: {status} {body}")
        print(f"run detail: {page.locator('#run-detail').inner_text()}")
        if page.locator("#stop-run").is_visible():
            page.click("#stop-run")
            stopped = False
            for _ in range(20):
                page.wait_for_timeout(1000)
                if page.locator("#start-run").inner_text().strip() == "Solve":
                    stopped = True
                    break
            print(f"after Stop: {page.locator('#start-run').inner_text()}")
            if not stopped:
                print("Stop did not return the control to Solve", file=sys.stderr)
                browser.close()
                return 1
        browser.close()
    if page_errors:
        print("page errors:")
        for line in page_errors[:10]:
            print(f"  {line}")
        return 1
    if errors:
        print("console resource errors (not fatal for this control check):")
        for line in errors[:10]:
            print(f"  {line}")
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the run-control smoke from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` on success, ``1`` on a failed check, and ``2`` when the browser is
        unavailable.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8022/")
    parser.add_argument("--wait-ms", type=int, default=12000)
    parser.add_argument("--iterations", type=int, default=0)
    args = parser.parse_args(argv)
    return check(args.url, wait_ms=args.wait_ms, iterations=args.iterations)


if __name__ == "__main__":
    raise SystemExit(main())
