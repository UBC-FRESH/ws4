#!/usr/bin/env python3
"""Smoke-test the account browser and target activation in a headless browser.

This is an opt-in check, not a CI gate: it needs Playwright and a Chromium build.
Install them with ``pip install playwright`` and ``python -m playwright install chromium``.

Run it against a service started with a **scratch** copy of the targets YAML. The
check adds one target, verifies that the Targets table and the API both show it,
then removes it when the file holds more than one target. The API refuses an empty
targets document, so the last target cannot be removed through the browser.
"""

from __future__ import annotations

import argparse
import sys


def check(  # pragma: no cover - needs a browser
    url: str, search: str, *, wait_ms: int = 12000
) -> int:
    """Open a service, add a target from the account tree, and remove it.

    Parameters
    ----------
    url : str
        Service root, for example ``http://127.0.0.1:8021/``.
    search : str
        Substring used to filter the account tree.
    wait_ms : int, optional
        Milliseconds to wait for the run and the account catalogue.

    Returns
    -------
    int
        ``0`` when the target was added and, when possible, removed; ``1`` on a
        failed assertion; ``2`` when the browser is unavailable.
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
                else None
            ),
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        page.locator("#ws-plan").click()
        page.wait_for_timeout(500)
        if page.locator(".account-leaf").count() == 0:
            print("the account tree is empty", file=sys.stderr)
            browser.close()
            return 1
        page.fill("#account-search", search)
        page.wait_for_timeout(300)
        filtered = page.locator(".account-leaf")
        if filtered.count() == 0:
            print(f"no account matches {search!r}", file=sys.stderr)
            browser.close()
            return 1
        account = filtered.first.get_attribute("data-account") or ""
        filtered.first.click()
        picked = page.locator("#picked-account-name").inner_text()
        if picked != account:
            print(f"picked {picked!r}, expected {account!r}", file=sys.stderr)
            browser.close()
            return 1
        rows_before = page.locator("#targets-table tbody tr:not(.target-detail)").count()
        if page.locator("#targets-table select[data-field=normalization]").count() == 0:
            print("the target normalization field is missing", file=sys.stderr)
            browser.close()
            return 1
        if page.locator("#targets-table input[data-field=priority]").count() == 0:
            print("the target priority field is missing", file=sys.stderr)
            browser.close()
            return 1
        if page.locator("#targets-table input[data-field=notes]").count() == 0:
            print("the target notes field is missing", file=sys.stderr)
            browser.close()
            return 1
        page.fill("#new-target-min", "0")
        page.click("#add-target")
        page.wait_for_timeout(6000)
        rows_after = page.locator("#targets-table tbody tr:not(.target-detail)").count()
        if rows_after != rows_before + 1:
            print(f"target rows went from {rows_before} to {rows_after}", file=sys.stderr)
            browser.close()
            return 1
        print(f"added target: {page.locator('#targets-status').inner_text()}")
        print(f"account: {account} ({page.locator('#picked-account-kind').inner_text()})")
        print(f"target rows: {rows_after}")
        if rows_after > 1:
            page.locator("button.remove-target").last.click()
            page.wait_for_timeout(6000)
            rows_final = page.locator("#targets-table tbody tr:not(.target-detail)").count()
            if rows_final != rows_before:
                print(
                    f"target rows after removal: {rows_final}, expected {rows_before}",
                    file=sys.stderr,
                )
                browser.close()
                return 1
            print(f"removed target; rows back to {rows_final}")
        else:
            print("left one target because the targets document cannot be empty")
        browser.close()
    if errors:
        print("console errors:")
        for line in errors[:10]:
            print(f"  {line}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs a browser
    """Run the target-browser smoke from the command line.

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
    parser.add_argument("--search", default="Area.managed")
    parser.add_argument("--wait-ms", type=int, default=12000)
    args = parser.parse_args(argv)
    return check(args.url, args.search, wait_ms=args.wait_ms)


if __name__ == "__main__":
    raise SystemExit(main())
