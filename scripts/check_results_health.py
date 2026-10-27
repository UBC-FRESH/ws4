#!/usr/bin/env python3
"""Smoke-test the Results run-health card and target cross-links.

Opt-in: requires Playwright and Chromium. The service must expose at least two runs so the
Compare subsection has a target-status table.
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Any


def wait_ready(page: Any) -> None:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Wait for the run context and the initial workspace choice.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Loaded shell page.
    """
    page.wait_for_function(
        """() => {
            const status = document.querySelector('#status');
            const run = document.querySelector('#run');
            return status && run && run.value && !status.textContent.startsWith('loading');
        }""",
        timeout=60000,
    )
    page.wait_for_timeout(800)


def check(  # pragma: no cover - needs a browser
    url: str, run: str | None = None, *, wait_ms: int = 7000
) -> int:
    """Assert run-health counts, Plan actions, Compare links, and 1024 px layout.

    Parameters
    ----------
    url : str
        Service root.
    run : str or None, optional
        Run id to select; None keeps the page's preferred run.
    wait_ms : int, optional
        Milliseconds to wait after run selection.

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
        except Exception as exc:
            print(f"chromium is not available: {exc}", file=sys.stderr)
            return 2
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            page.on(
                "console",
                lambda message: (
                    errors.append(f"{message.type}: {message.text}")
                    if message.type == "error" and "Failed to load resource" not in message.text
                    else None
                ),
            )
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            wait_ready(page)
            if run:
                page.select_option("#run", run)
                page.wait_for_timeout(wait_ms)
                wait_ready(page)
            page.locator("#ws-results").click()
            page.locator("#run-health").wait_for(state="visible", timeout=60000)
            assert page.locator("#run-health-run").inner_text(), "health has no run id"
            meta = page.locator("#run-health-meta").inner_text()
            assert " · " in meta, meta
            badges = page.locator("#run-health-badges").inner_text()
            assert "targets" in badges, badges
            assert "failing" in badges, badges
            assert "chart" in badges, badges
            assert "LiDAR" in badges, badges
            assert "Carbon" in badges, badges
            failing_match = re.search(r"(\d+) failing", badges)
            assert failing_match is not None, badges
            failing = int(failing_match.group(1))

            page.locator("#run-health-failing").click()
            page.wait_for_timeout(600)
            workspace = page.evaluate(
                "document.querySelector('.workspaces button.active')?.dataset.workspace"
            )
            assert workspace == "plan", workspace
            assert page.locator("#target-filter-status").input_value() == "failing"
            assert page.locator("#targets-table").is_visible(), "Plan target table is hidden"
            assert page.locator("#targets-table tbody tr:not(.target-detail):visible").count() > 0
            plan_summary = page.locator("#target-summary").inner_text()
            assert f"{failing} failing" in plan_summary, (failing, plan_summary)

            page.locator("#ws-results").click()
            page.locator("#sub-comparison").click()
            page.locator("#compare-targets").wait_for(state="visible", timeout=60000)
            page.wait_for_timeout(700)
            rows = page.locator("#compare-targets tbody tr")
            rows.first.wait_for(state="visible", timeout=60000)
            assert rows.count() > 0, "Compare has no target rows"
            assert rows.first.locator("td").count() == 8, "Compare target row is not eight columns"
            account = rows.first.locator("td.account")
            assert account.get_attribute("role") == "button", "account is not a link"
            account_text = account.inner_text()
            account.scroll_into_view_if_needed()
            account.click()
            page.wait_for_timeout(600)
            workspace = page.evaluate(
                "document.querySelector('.workspaces button.active')?.dataset.workspace"
            )
            assert workspace == "plan", workspace
            assert page.locator("#target-filter-search").input_value() == account_text

            page.locator("#ws-results").click()
            page.set_viewport_size({"width": 1024, "height": 768})
            page.wait_for_timeout(450)
            assert page.locator("#run-health").is_visible(), "health hidden at 1024px"
            assert page.evaluate(
                "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
            ), "horizontal page overflow at 1024x768"
            assert not errors, errors
        except Exception as exc:
            print(f"results-health check failed: {exc}", file=sys.stderr)
            print("\n".join(errors), file=sys.stderr)
            return 1
        finally:
            browser.close()
    print("results health: counts, failing action, compare account link, 1024 px")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="service root, for example http://127.0.0.1:8035/")
    parser.add_argument("--run", help="run id to select")
    parser.add_argument("--wait-ms", type=int, default=7000)
    args = parser.parse_args()
    sys.exit(check(args.url, args.run, wait_ms=args.wait_ms))
