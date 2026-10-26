#!/usr/bin/env python3
"""Smoke-test the Patchworks-style target charts in a headless browser.

Opt-in: requires Playwright and a Chromium build. The service must have a run with a
targets file so at least one chart can be pinned.
"""

from __future__ import annotations

import argparse
import sys


def check(  # pragma: no cover - needs a browser
    url: str, run: str | None = None, *, wait_ms: int = 6000
) -> int:
    """Open Plan and assert the chart zones, line, readout, table, and period click.

    Parameters
    ----------
    url : str
        Service root.
    run : str or None, optional
        Run id to select; None keeps the page's preferred run.
    wait_ms : int, optional
        Milliseconds to wait for the run and chart data.

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
                    marker in str(message.location) for marker in ("favicon", "/api/land-base")
                )
                else None
            ),
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        if run:
            page.select_option("#run", run)
            page.wait_for_timeout(wait_ms)
        page.locator("#ws-plan").click()
        page.wait_for_timeout(1200)
        charts = page.locator(".target-chart-card").count()
        zones = page.locator(".target-min-zone, .target-max-zone").count()
        lines = page.locator(".target-chart-line").count()
        readout = page.locator(".target-chart-readout").first.inner_text()
        page.locator(".target-chart-table summary").first.click()
        rows = page.locator(".target-chart-table tbody tr").first.count()
        before = page.locator("#year").input_value()
        target_index = 0 if before != "0" else 1
        page.locator(".target-chart-period").nth(target_index).click()
        page.wait_for_timeout(300)
        after = page.locator("#year").input_value()
        page.screenshot(path="/tmp/opencode/p64-target-charts.png", full_page=True)
        browser.close()
    print(f"charts: {charts} · zones: {zones} · lines: {lines}")
    print(f"readout: {readout}")
    print(f"all-period rows: {rows}")
    print(f"period click: {before} -> {after}")
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
    ok = (
        charts >= 1
        and zones >= 1
        and lines >= 1
        and "min" in readout
        and "max" in readout
        and "achieved" in readout
        and rows >= 1
        and before != after
        and not errors
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the target-chart smoke from the command line.

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
    parser.add_argument("--url", default="http://127.0.0.1:8022/")
    parser.add_argument("--run", default=None)
    parser.add_argument("--wait-ms", type=int, default=6000)
    args = parser.parse_args(argv)
    return check(args.url, args.run, wait_ms=max(1000, args.wait_ms))


if __name__ == "__main__":
    raise SystemExit(main())
