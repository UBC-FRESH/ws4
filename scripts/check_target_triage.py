#!/usr/bin/env python3
"""Smoke-test target summary, filters, edit preservation, and bulk pinning.

Opt-in: requires Playwright and Chromium. The service must expose a run with targets.
"""

from __future__ import annotations

import argparse
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


def main_rows(page: Any) -> Any:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Return all main target rows, including hidden ones.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Page with the Plan workspace open.

    Returns
    -------
    playwright.sync_api.Locator
        Main target rows.
    """
    return page.locator("#targets-table tbody tr:not(.target-detail)")


def visible_rows(page: Any) -> Any:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Return visible main target rows.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Page with the Plan workspace open.

    Returns
    -------
    playwright.sync_api.Locator
        Visible target rows.
    """
    return page.locator("#targets-table tbody tr:not(.target-detail):visible")


def checked_pins(page: Any) -> int:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Return the number of ticked account-pin checkboxes.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Page with the Plan workspace open.

    Returns
    -------
    int
        Number of pinned target rows.
    """
    count: int = page.locator("#targets-table td.account input[type='checkbox']:checked").count()
    return count


def check(  # pragma: no cover - needs a browser
    url: str, run: str | None = None, *, wait_ms: int = 7000
) -> int:
    """Assert summary, filters, edit preservation, and visible bulk pinning.

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
            page.locator("#ws-plan").click()
            page.locator("#targets-table").wait_for(state="visible", timeout=60000)
            page.wait_for_timeout(700)

            total = main_rows(page).count()
            assert total > 0, "no targets"
            summary = page.locator("#target-summary").inner_text()
            assert " targets" in summary, summary
            assert "failing" in summary, summary
            assert "met" in summary, summary
            assert page.locator("#target-filter-bar").is_visible(), "filter bar is hidden"
            assert page.locator("#target-filter-count").inner_text() == f"{total} visible"

            page.select_option("#target-filter-status", "failing")
            page.wait_for_timeout(250)
            failing = visible_rows(page).count()
            assert failing > 0, "no failing targets to filter"
            statuses = visible_rows(page).locator(".target-status").all_inner_texts()
            assert all(status in {"below min", "above max"} for status in statuses), statuses
            assert "visible" in page.locator("#target-filter-count").inner_text()

            first = visible_rows(page).first
            first_index = first.get_attribute("data-index")
            field = f'#targets-table input[data-field="minimum"][data-index="{first_index}"]'
            page.locator(field).fill("777777")
            accounts = visible_rows(page).evaluate_all(
                "rows => rows.map(row => row.dataset.account || '')"
            )
            term = "feature" if any("feature" in account.lower() for account in accounts) else "zzz"
            expected = sum(1 for account in accounts if term in account.lower())
            page.fill("#target-filter-search", term)
            page.wait_for_timeout(250)
            assert visible_rows(page).count() == expected, (term, expected)
            assert page.locator(field).input_value() == "777777", "filter lost an edit"
            page.fill("#target-filter-search", "")
            page.wait_for_timeout(200)
            assert page.locator(field).input_value() == "777777", "clearing search lost an edit"

            page.locator('#targets-table th .sort-button[data-sort="account"]').click()
            page.wait_for_timeout(250)
            assert visible_rows(page).count() == failing, "sorting changed the filter"
            assert page.locator(field).input_value() == "777777", "sorting lost an edit"

            page.click("#target-filter-clear")
            page.wait_for_timeout(200)
            assert visible_rows(page).count() == total, "clear did not restore all rows"
            page.click("#target-unpin-visible")
            page.wait_for_timeout(300)
            assert checked_pins(page) == 0, "unpinning all visible rows left pins"

            page.select_option("#target-filter-status", "failing")
            page.wait_for_timeout(200)
            page.click("#target-pin-failing")
            page.wait_for_timeout(400)
            assert checked_pins(page) == failing, "bulk pin did not pin every visible failing row"
            assert "chart" in page.locator("#target-chart-count").inner_text().lower()
            page.click("#target-unpin-visible")
            page.wait_for_timeout(400)
            assert checked_pins(page) == 0, "unpin visible left failing pins"
            page.click("#target-filter-clear")
            page.wait_for_timeout(200)

            page.set_viewport_size({"width": 1024, "height": 768})
            page.wait_for_timeout(450)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
            ), "horizontal page overflow at 1024x768"
            assert page.locator("#target-filter-bar").is_visible(), "filter bar hidden at 1024px"
            assert page.locator("#target-summary").is_visible(), "summary hidden at 1024px"
            assert not errors, errors
        except Exception as exc:
            print(f"target-triage check failed: {exc}", file=sys.stderr)
            print("\n".join(errors), file=sys.stderr)
            return 1
        finally:
            browser.close()
    print("target triage: summary, filters, edit preservation, bulk pin/unpin, 1024 px")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="service root, for example http://127.0.0.1:8033/")
    parser.add_argument("--run", help="run id to select")
    parser.add_argument("--wait-ms", type=int, default=7000)
    args = parser.parse_args()
    sys.exit(check(args.url, args.run, wait_ms=args.wait_ms))
