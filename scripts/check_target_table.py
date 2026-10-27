#!/usr/bin/env python3
"""Smoke-test the target table labels, units, status, sorting, and edit preservation.

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


def table_rows(page: Any) -> Any:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Return the main target rows, excluding detail editors.

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


def order(page: Any) -> list[str]:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Return the current target indices in display order.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Page with the Plan workspace open.

    Returns
    -------
    list of str
        Target indices.
    """
    result: list[str] = table_rows(page).evaluate_all("rows => rows.map(row => row.dataset.index)")
    return result


def check(  # pragma: no cover - needs a browser
    url: str, run: str | None = None, *, wait_ms: int = 7000
) -> int:
    """Assert the compact labels, units, status, and edit-safe sorting.

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
            rows = table_rows(page)
            assert rows.count() > 0, "no targets"
            headers = page.locator("#targets-table thead th").evaluate_all(
                "th => th.map(cell => cell.textContent.trim())"
            )
            assert "Account" in headers, headers
            assert "Target period" in headers, headers
            assert "Status" in headers, headers
            labels = page.locator(".target-account-label").all_inner_texts()
            assert labels, "no account labels"
            assert all(label and "carbon." not in label for label in labels), labels
            roots = page.locator(".account-root").all_inner_texts()
            assert roots, "no account roots"
            assert all(root for root in roots), roots
            units = page.locator(".account-unit").all_inner_texts()
            assert units, "no inferred units are displayed"
            periods = page.locator(".target-period-label").all_inner_texts()
            assert periods, "no period labels"
            assert all(period for period in periods), periods
            statuses = page.locator(".target-status").all_inner_texts()
            assert statuses, "no status values"
            assert all(status for status in statuses), statuses
            assert any(status in {"met", "below min", "above max", "off"} for status in statuses), (
                statuses
            )

            original = order(page)
            page.locator('#targets-table th .sort-button[data-sort="account"]').click()
            page.wait_for_timeout(250)
            account_order = order(page)
            assert account_order != original, "account sort did not reorder"
            account_header = page.locator(
                "#targets-table th", has=page.locator('[data-sort="account"]')
            )
            assert account_header.get_attribute("aria-sort") == "ascending"
            accounts = [
                table_rows(page).nth(index).get_attribute("data-account") or ""
                for index in range(table_rows(page).count())
            ]
            assert accounts == sorted(accounts, key=str.lower), accounts
            page.locator('#targets-table th .sort-button[data-sort="account"]').click()
            page.wait_for_timeout(250)
            assert account_header.get_attribute("aria-sort") == "descending"

            first_index = original[0]
            field = f'#targets-table input[data-field="minimum"][data-index="{first_index}"]'
            page.locator(field).fill("123456")
            page.locator('#targets-table th .sort-button[data-sort="status"]').click()
            page.wait_for_timeout(250)
            assert page.locator(field).input_value() == "123456", "sorting lost an edit"
            page.locator("#target-sort-reset").click()
            page.wait_for_timeout(250)
            assert order(page) == original, "file order did not restore"
            assert page.locator("#target-sort-status").inner_text() == "file order"

            page.set_viewport_size({"width": 1024, "height": 768})
            page.wait_for_timeout(450)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
            ), "horizontal page overflow at 1024x768"
            assert page.locator("#targets-table").is_visible(), "table hidden at 1024x768"
            assert not errors, errors
        except Exception as exc:
            print(f"target-table check failed: {exc}", file=sys.stderr)
            print("\n".join(errors), file=sys.stderr)
            return 1
        finally:
            browser.close()
    print("target table: labels, units, periods, status, sorting, edits, 1024 px")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="service root, for example http://127.0.0.1:8030/")
    parser.add_argument("--run", help="run id to select")
    parser.add_argument("--wait-ms", type=int, default=7000)
    args = parser.parse_args()
    sys.exit(check(args.url, args.run, wait_ms=args.wait_ms))
