#!/usr/bin/env python3
"""Check that the assistant panel disappears when the service has no agent.

Opt-in: requires Playwright and a Chromium build.
"""

from __future__ import annotations

import argparse
import sys


def check(  # pragma: no cover - needs a browser
    url: str, *, expected: str, wait_ms: int = 5000
) -> int:
    """Assert the assistant panel's visibility and recovered sidebar height.

    Parameters
    ----------
    url : str
        Service root.
    expected : str
        ``hidden`` for a service without --allow-agent, ``visible`` with it.
    wait_ms : int, optional
        Milliseconds to wait for the shell and agent status.

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
        metrics = page.evaluate(
            """() => {
              const panel = document.querySelector('#chat-panel');
              const splitter = document.querySelector('#chat-splitter');
              const body = document.querySelector('.sidebar-body');
              const map = document.querySelector('#map-wrap');
              return {
                panelHidden: Boolean(panel?.hidden),
                splitterHidden: Boolean(splitter?.hidden),
                panelHeight: panel ? panel.getBoundingClientRect().height : 0,
                sidebarBody: body ? body.getBoundingClientRect().height : 0,
                map: map ? map.getBoundingClientRect().height : 0,
              };
            }"""
        )
        page.screenshot(path="/tmp/opencode/p66-assistant.png")
        browser.close()
    print(metrics)
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
    hidden = expected == "hidden"
    ok = (
        metrics["panelHidden"] == hidden
        and metrics["splitterHidden"] == hidden
        and (hidden or (metrics["panelHeight"] > 0 and metrics["sidebarBody"] > 0))
        and metrics["map"] > 0
        and not errors
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the assistant visibility check from the command line.

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
    parser.add_argument("--expected", choices=("hidden", "visible"), default="hidden")
    parser.add_argument("--wait-ms", type=int, default=5000)
    args = parser.parse_args(argv)
    return check(args.url, expected=args.expected, wait_ms=max(1000, args.wait_ms))


if __name__ == "__main__":
    raise SystemExit(main())
