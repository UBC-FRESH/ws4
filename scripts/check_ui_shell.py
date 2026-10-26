#!/usr/bin/env python3
"""Smoke-test the WS4 shell at desktop and iPad Pro landscape sizes.

Opt-in: requires Playwright and a Chromium build. Phone widths are deliberately not
tested; the supported planning surfaces start at 1024 CSS pixels in landscape.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TypedDict


class RestoredState(TypedDict):
    """The URL state restored after reload."""

    view: str | None
    dataset: bool
    period: str | None


class ShellResult(TypedDict):
    """One viewport's shell measurements."""

    width: int
    height: int
    viewport: int
    body: int
    map: int
    workspaces: list[str]
    selected: list[str]
    roles: bool
    data_visible: bool
    dataset_visible: bool
    restored: RestoredState
    keyboard_plan: str | None


def check(  # pragma: no cover - needs a browser
    url: str, *, wait_ms: int = 4000
) -> int:
    """Check navigation, overflow, URL restore, and keyboard tabs.

    Parameters
    ----------
    url : str
        Service root.
    wait_ms : int, optional
        Milliseconds to wait for the initial run and map shell.

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
    sizes = [(1500, 1000), (1366, 1024), (1194, 834), (1024, 768)]
    results: list[ShellResult] = []
    errors: list[str] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # the browser may be absent
            print(f"chromium is not available: {exc}", file=sys.stderr)
            return 2
        for width, height in sizes:
            page = browser.new_page(viewport={"width": width, "height": height})
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
                  const workspaces = [...document.querySelectorAll('.workspaces [role="tab"]')];
                  const selected = workspaces.filter(
                    (button) => button.getAttribute('aria-selected') === 'true'
                  );
                  return {
                    body: document.body.scrollWidth,
                    viewport: innerWidth,
                    map: document.querySelector('#map-wrap')?.getBoundingClientRect().width ?? 0,
                    workspaces: workspaces
                      .filter((button) => !button.hidden)
                      .map((button) => button.textContent.trim()),
                    selected: selected.map((button) => button.textContent.trim()),
                    roles: workspaces.every((button) => button.getAttribute('role') === 'tab'),
                  };
                }"""
            )
            page.locator("#ws-data").click()
            page.wait_for_timeout(300)
            data_visible = page.locator("#workspace-data").is_visible()
            dataset_visible = page.locator("#tab-dataset").is_visible()
            # URL restore: data/dataset and the first period.
            page.evaluate("() => history.replaceState({}, '', '?view=data&sub=dataset&period=0')")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            restored = page.evaluate(
                """() => ({
                  view: document.querySelector('#ws-data')?.getAttribute('aria-selected'),
                  dataset: !document.querySelector('#tab-dataset')?.hidden,
                  period: document.querySelector('#year')?.value,
                })"""
            )
            # Keyboard navigation from Map to Plan.
            page.locator("#ws-map").click()
            page.locator("#ws-map").focus()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(200)
            keyboard = page.evaluate(
                "() => document.querySelector('#ws-plan')?.getAttribute('aria-selected')"
            )
            page.screenshot(path=f"/tmp/opencode/p63-shell-{width}x{height}.png")
            results.append(
                {
                    "width": width,
                    "height": height,
                    "viewport": metrics["viewport"],
                    "body": metrics["body"],
                    "map": round(float(metrics["map"])),
                    "workspaces": metrics["workspaces"],
                    "selected": metrics["selected"],
                    "roles": metrics["roles"],
                    "data_visible": data_visible,
                    "dataset_visible": dataset_visible,
                    "restored": restored,
                    "keyboard_plan": keyboard,
                }
            )
            page.close()
        browser.close()
    print(json.dumps(results, indent=2))
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
    ok = (
        all(
            item["body"] <= int(item["viewport"]) + 1
            and int(item["map"]) >= 500
            and item["workspaces"] == ["Map", "Plan", "Results", "Data"]
            and item["roles"]
            and item["data_visible"]
            and item["dataset_visible"]
            and item["restored"]["view"] == "true"
            and item["restored"]["dataset"]
            and item["restored"]["period"] == "0"
            and item["keyboard_plan"] == "true"
            for item in results
        )
        and not errors
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the shell check from the command line.

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
    parser.add_argument("--wait-ms", type=int, default=4000)
    args = parser.parse_args(argv)
    return check(args.url, wait_ms=max(1000, args.wait_ms))


if __name__ == "__main__":
    raise SystemExit(main())
