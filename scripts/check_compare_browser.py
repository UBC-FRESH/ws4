#!/usr/bin/env python3
"""Smoke-test the comparison view in a headless browser.

Opt-in: requires Playwright and a Chromium build. The service must be running with
two completed runs and the compare tiles enabled.
"""

from __future__ import annotations

import argparse
import sys


def check(  # pragma: no cover - needs a browser
    url: str, run_a: str, run_b: str, *, wait_ms: int = 12000
) -> int:
    """Open Compare, select two runs, and assert tiles and counts.

    Parameters
    ----------
    url : str
        Service root.
    run_a : str
        First run id.
    run_b : str
        Second run id.
    wait_ms : int, optional
        Milliseconds to wait for the page and tiles.

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
    tiles: list[str] = []
    errors: list[str] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # the browser may be absent
            print(f"chromium is not available: {exc}", file=sys.stderr)
            return 2
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.on(
            "request",
            lambda request: tiles.append(request.url) if "compare-tiles" in request.url else None,
        )
        page.on(
            "console",
            lambda message: (
                errors.append(f"{message.type}: {message.text}")
                if message.type == "error"
                and not any(
                    marker in str(message.location) for marker in ("favicon", "/api/land-base")
                )
                else None
            ),
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        page.locator("#ws-results").click()
        page.locator("#sub-comparison").click()
        page.wait_for_timeout(500)
        page.select_option("#compare-a", run_a)
        page.select_option("#compare-b", run_b)
        page.wait_for_timeout(wait_ms)
        summary = page.locator("#compare-summary").inner_text()
        headers = page.locator("#compare-targets thead th").all_inner_texts()
        ending = page.locator("#compare-ending tbody tr").count()
        browser.close()
    print(f"summary: {summary}")
    print(f"compare tiles: {len(tiles)}")
    print(f"target headers: {headers}")
    print(f"ending rows: {ending}")
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
    if not tiles:
        print("no compare tile was requested", file=sys.stderr)
        return 1
    if "A only" not in summary:
        print("the comparison counts are missing", file=sys.stderr)
        return 1
    if "Kind" not in headers:
        print("the target table has no Kind column", file=sys.stderr)
        return 1
    if errors:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the compare smoke from the command line.

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
    parser.add_argument("--run-a", required=True)
    parser.add_argument("--run-b", required=True)
    parser.add_argument("--wait-ms", type=int, default=12000)
    args = parser.parse_args(argv)
    return check(args.url, args.run_a, args.run_b, wait_ms=args.wait_ms)


if __name__ == "__main__":
    raise SystemExit(main())
