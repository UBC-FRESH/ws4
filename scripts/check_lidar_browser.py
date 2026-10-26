#!/usr/bin/env python3
"""Smoke-test the LiDAR panel in a headless browser.

Opt-in: requires Playwright and a Chromium build, plus a service started over a dataset
with registered LiDAR block fields.
"""

from __future__ import annotations

import argparse
import sys


def check(  # pragma: no cover - needs a browser
    url: str, field: str = "lidar_slope_mean", *, wait_ms: int = 8000
) -> int:
    """Open the LiDAR panel, select a field, and assert the join and block detail.

    Parameters
    ----------
    url : str
        Service root.
    field : str, optional
        Canonical LiDAR field to select.
    wait_ms : int, optional
        Milliseconds to wait for the map and field response.

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
    requests: list[str] = []
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
            lambda request: requests.append(request.url) if "lidar=1" in request.url else None,
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
        page.get_by_role("button", name="LiDAR").click()
        page.wait_for_timeout(500)
        status = page.locator("#lidar-status").inner_text()
        options = page.locator("#lidar-field option").all_inner_texts()
        page.select_option("#lidar-field", field)
        page.wait_for_timeout(wait_ms)
        legend = page.locator("#lidar-legend").is_visible()
        page.get_by_role("button", name="Legend").click()
        page.wait_for_timeout(300)
        page.locator('input[name="map-engine"][value="svg"]').check()
        page.wait_for_timeout(1000)
        page.evaluate(
            "() => document.querySelector('[data-block=\"1\"]')"
            "?.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}))"
        )
        page.wait_for_timeout(300)
        detail = page.locator("#detail").inner_text()
        page.screenshot(path="/tmp/opencode/p59-lidar.png", full_page=True)
        browser.close()
    print(f"status: {status}")
    print(f"field options: {options}")
    print(f"lidar map requests: {len(requests)}")
    print(f"legend visible: {legend}")
    print(f"detail: {detail.splitlines()[-3:]}")
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
    ok = (
        "fields" in status
        and any("Slope mean" in option for option in options)
        and bool(requests)
        and legend
        and "Slope mean" in detail
        and not errors
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the browser check from the command line.

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
    parser.add_argument("--field", default="lidar_slope_mean")
    parser.add_argument("--wait-ms", type=int, default=8000)
    args = parser.parse_args(argv)
    return check(args.url, args.field, wait_ms=max(1000, args.wait_ms))


if __name__ == "__main__":
    raise SystemExit(main())
