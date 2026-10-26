#!/usr/bin/env python3
"""Exercise target-chart editing, saving, and reload.

Opt-in and destructive to the service's targets file: run it only against a temporary
service and a copy of the target YAML. It is not a CI gate.
"""

from __future__ import annotations

import argparse
import sys


def check(  # pragma: no cover - needs a browser
    url: str, run: str | None = None, *, value: float = 1234.5, wait_ms: int = 5000
) -> int:
    """Edit one bound, save, reload, and verify persistence and the inactive state.

    Parameters
    ----------
    url : str
        Service root.
    run : str or None, optional
        Run id to select.
    value : float, optional
        Minimum value to write to the first chart's first period.
    wait_ms : int, optional
        Milliseconds to wait for run and save operations.

    Returns
    -------
    int
        ``0`` on success, ``1`` on failed assertions, and ``2`` when the browser is
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
        card = page.locator(".target-chart-card").first
        if card.count() == 0:
            print("no target chart", file=sys.stderr)
            browser.close()
            return 1
        card.locator(".target-chart-controls select").first.select_option("minimum")
        card.locator(".target-chart-controls select").nth(1).select_option("period")
        card.locator(".target-chart-controls input[type=number]").fill(str(value))
        card.get_by_role("button", name="Apply").click()
        page.wait_for_timeout(400)
        if page.locator("#target-chart-save").is_disabled():
            print("save stayed disabled after editing", file=sys.stderr)
            browser.close()
            return 1
        page.locator("#target-chart-save").click()
        page.wait_for_timeout(wait_ms)
        saved = page.locator("#target-chart-status").inner_text()
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(wait_ms)
        if run:
            page.select_option("#run", run)
            page.wait_for_timeout(wait_ms)
        page.locator("#ws-plan").click()
        page.wait_for_timeout(1000)
        reloaded = page.locator(".target-chart-readout").first.inner_text()
        # Toggle the first account inactive and save, then verify the card style.
        card = page.locator(".target-chart-card").first
        card.locator(".target-chart-controls input[type=checkbox]").uncheck()
        page.locator("#target-chart-save").click()
        page.wait_for_timeout(wait_ms)
        inactive = page.locator(".target-chart-card.inactive").count()
        browser.close()
    print(f"save status: {saved}")
    print(f"reloaded readout: {reloaded}")
    print(f"inactive cards after toggle: {inactive}")
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
    ok = (
        "saved" in saved
        and (f"{value:,.1f}" in reloaded or f"{value:,.0f}" in reloaded)
        and inactive >= 1
        and not errors
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the target-editing smoke from the command line.

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
    parser.add_argument("--value", type=float, default=1234.5)
    parser.add_argument("--wait-ms", type=int, default=5000)
    args = parser.parse_args(argv)
    return check(args.url, args.run, value=args.value, wait_ms=max(1000, args.wait_ms))


if __name__ == "__main__":
    raise SystemExit(main())
