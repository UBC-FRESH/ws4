#!/usr/bin/env python3
"""Smoke-test the tiled map in a headless browser.

This is an opt-in check, not a CI gate: it needs Playwright and a Chromium
build. Install them with ``pip install playwright`` and
``python -m playwright install chromium``.

The check opens a running service, waits for the map, and fails when the
MapLibre vector source makes no ``.mvt`` request or the shell reports a console
error. It asserts the observable contract, not the implementation.
"""

from __future__ import annotations

import argparse
import sys


def check(url: str, *, wait_ms: int = 12000) -> int:  # pragma: no cover - needs a browser
    """Open a service and assert that the map requests at least one MVT tile.

    Parameters
    ----------
    url : str
        Service root, for example ``http://127.0.0.1:8017/``.
    wait_ms : int, optional
        Milliseconds to wait for the map and its tiles.

    Returns
    -------
    int
        ``0`` when at least one ``.mvt`` request succeeded and no console error
        appeared, ``1`` otherwise.
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
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.on(
            "request",
            lambda request: requests.append(request.url) if "/tiles/" in request.url else None,
        )
        page.on(
            "console",
            lambda message: (
                errors.append(f"{message.type}: {message.text}")
                if message.type == "error"
                else None
            ),
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        status = page.locator("#status").inner_text()
        treated = page.locator("#n-treated").inner_text()
        untreated = page.locator("#n-untreated").inner_text()
        browser.close()
    print(f"status: {status}")
    print(f"counts: {treated} treated / {untreated} untreated")
    print(f"mvt requests: {len(requests)}")
    for request_url in requests[:5]:
        print(f"  {request_url}")
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
        return 1
    if not requests:
        print("no .mvt request was made", file=sys.stderr)
        return 1
    if "MVT" not in status:
        print("the shell did not report MVT mode", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the browser smoke from the command line.

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
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8017/")
    parser.add_argument("--wait-ms", type=int, default=12000)
    args = parser.parse_args(argv)
    return check(args.url, wait_ms=args.wait_ms)


if __name__ == "__main__":
    raise SystemExit(main())
