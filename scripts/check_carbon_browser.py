#!/usr/bin/env python3
"""Smoke-test the Carbon panel in a headless browser.

Opt-in: requires Playwright and a Chromium build, plus a service with a real carbon run.
"""

from __future__ import annotations

import argparse
import sys


def check(  # pragma: no cover - needs a browser
    url: str, run: str | None = None, *, wait_ms: int = 6000
) -> int:
    """Open Carbon, select an account, and assert provenance, chart, bars, and files.

    Parameters
    ----------
    url : str
        Service root.
    run : str or None, optional
        Run id to select; None keeps the page's preferred run.
    wait_ms : int, optional
        Milliseconds to wait for the run and carbon response.

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
        except Exception as exc:  # the browser may be absent
            print(f"chromium is not available: {exc}", file=sys.stderr)
            return 2
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.on(
            "console",
            lambda message: (
                errors.append(f"{message.type}: {message.text}")
                if message.type == "error"
                and not any(
                    marker in str(message.location)
                    for marker in ("favicon", "/api/land-base", "/api/runs/")
                )
                else None
            ),
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        if run:
            page.select_option("#run", run)
            page.wait_for_timeout(wait_ms)
        page.locator("#ws-data").click()
        page.locator("#sub-carbon").click()
        page.wait_for_timeout(1200)
        status = page.locator("#carbon-status").inner_text()
        meta = page.locator("#carbon-meta").inner_text()
        accounts = page.locator("#carbon-account option").count()
        chart = page.locator("#carbon-chart polyline").count()
        bars = page.locator(".carbon-bar-row").count()
        ledger = page.locator("#carbon-ledger").inner_text()
        files = page.locator("#carbon-files li").count()
        page.screenshot(path="/tmp/opencode/p61-carbon.png", full_page=True)
        browser.close()
    print(f"status: {status}")
    print(f"metadata: {meta.replace(chr(10), ' | ')}")
    print(f"accounts: {accounts} · chart lines: {chart} · bars: {bars} · files: {files}")
    print(f"ledger: {ledger}")
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
    ok = (
        "carbon accounts" in status
        and "Package" in meta
        and accounts > 0
        and chart > 0
        and files > 0
        and not errors
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the carbon browser check from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        The check's exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8020/")
    parser.add_argument("--run", default=None)
    parser.add_argument("--wait-ms", type=int, default=6000)
    args = parser.parse_args(argv)
    return check(args.url, args.run, wait_ms=max(1000, args.wait_ms))


if __name__ == "__main__":
    raise SystemExit(main())
