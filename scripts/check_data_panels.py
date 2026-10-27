#!/usr/bin/env python3
"""Smoke-test the LiDAR and Carbon data panels on real datasets.

Opt-in: requires Playwright and Chromium. Start one service with a registered LiDAR
dataset and another with a carbon run; the empty URL is normally c5 or TSA 46.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def wait_ready(page: Any) -> None:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Wait until the run context has loaded and the shell has chosen its workspace.

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


def open_data(page: Any, sub: str) -> None:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Open a Data sub-tab and wait for it to become visible.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Loaded shell page.
    sub : str
        ``lidar`` or ``carbon``.
    """
    page.locator("#ws-data").click()
    page.locator(f"#sub-{sub}").wait_for(state="visible", timeout=60000)
    page.locator(f"#sub-{sub}").click()


def check_lidar(page: Any, url: str, field: str) -> None:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Assert coverage, palette, legend, and missing-value treatment.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Browser page.
    url : str
        Service with registered LiDAR.
    field : str
        Preferred ``lidar_*`` field name; the first field is used when absent.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    wait_ready(page)
    open_data(page, "lidar")
    coverage_row = page.locator("#lidar-coverage-row")
    coverage_row.wait_for(state="visible", timeout=60000)
    coverage = page.locator("#lidar-coverage").inner_text()
    assert " / " in coverage, coverage
    assert "blocks" in coverage, coverage
    assert "%" in coverage, coverage
    note = page.locator("#lidar-coverage-note").inner_text()
    assert "dataset-wide" in note or "any LiDAR" in note, note
    options = page.locator("#lidar-field option").evaluate_all(
        "els => els.map(e => ({value: e.value, text: e.textContent}))"
    )
    values = [option["value"] for option in options if option["value"]]
    chosen = field if field in values else (values[0] if values else "")
    assert chosen, "no LiDAR field is available"
    page.select_option("#lidar-field", chosen)
    page.wait_for_function(
        "() => document.querySelector('#map-legend')?.textContent.includes('LiDAR')",
        timeout=60000,
    )
    legend = page.locator("#lidar-legend")
    legend.wait_for(state="visible", timeout=60000)
    title = page.locator("#lidar-legend-title").inner_text()
    assert title, "LiDAR legend has no title"
    minimum = page.locator("#lidar-min").inner_text()
    maximum = page.locator("#lidar-max").inner_text()
    assert minimum != "—", minimum
    assert maximum != "—", maximum
    swatch = page.locator(".lidar-missing-swatch")
    assert swatch.is_visible(), "missing-value swatch is not visible"
    gradient = page.evaluate(
        "element => getComputedStyle(element).backgroundImage",
        page.locator(".lidar-bar").element_handle(),
    )
    assert "rgb(68, 1, 84)" in gradient, gradient
    assert "rgb(253, 231, 37)" in gradient, gradient
    selected_coverage = page.locator("#lidar-coverage").inner_text()
    assert "%" in selected_coverage, selected_coverage
    map_legend = page.locator("#map-legend")
    map_legend.wait_for(state="visible", timeout=60000)
    map_text = map_legend.inner_text()
    assert "LiDAR" in map_text, map_text
    assert "Coverage" in map_text, map_text
    assert "No value" in map_text, map_text
    page.set_viewport_size({"width": 1024, "height": 768})
    page.wait_for_timeout(450)
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    ), "horizontal overflow at 1024x768"


def check_carbon(page: Any, url: str, run: str | None) -> None:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Assert human labels, units, axes, tooltips, and composition.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Browser page.
    url : str
        Service with a carbon run.
    run : str or None
        Run id to select; None keeps the page's preferred run.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    wait_ready(page)
    if run:
        page.select_option("#run", run)
        page.wait_for_timeout(10000)
        wait_ready(page)
    page.locator("#ws-data").click()
    page.locator("#sub-carbon").wait_for(state="visible", timeout=60000)
    page.locator("#sub-carbon").click()
    page.wait_for_function(
        "() => document.querySelectorAll('#carbon-chart .chart-point').length > 1",
        timeout=60000,
    )
    options = page.locator("#carbon-account option").evaluate_all(
        "els => els.map(e => e.textContent)"
    )
    assert options, "no carbon accounts"
    assert all("carbon." not in option for option in options), options
    assert any("tC" in option for option in options), options
    title = page.locator("#carbon-chart-title").inner_text()
    assert "tC" in title or "CO" in title, title
    current = page.locator("#carbon-chart-current").inner_text()
    assert "year" in current.lower(), current
    ticks = page.locator("#carbon-chart .chart-tick").evaluate_all(
        "els => els.map(e => e.textContent)"
    )
    assert len([tick for tick in ticks if tick]) >= 6, ticks
    assert any("Year" in tick for tick in ticks if tick), ticks
    point = page.locator("#carbon-chart .chart-point").nth(10)
    point.hover()
    page.wait_for_timeout(300)
    tooltip = page.locator("#carbon-tooltip")
    assert tooltip.is_visible(), "carbon tooltip is not visible"
    assert "Year" in tooltip.inner_text(), tooltip.inner_text()
    composition = page.locator("#carbon-composition")
    if composition.is_visible():
        assert "tC" in composition.inner_text(), composition.inner_text()
    page.set_viewport_size({"width": 1024, "height": 768})
    page.wait_for_timeout(450)
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    ), "horizontal overflow at 1024x768"


def check_empty(page: Any, url: str) -> None:  # noqa: ANN401  # pragma: no cover - needs a browser
    """Assert unavailable data tabs stay compact and leave no chart chrome.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Browser page.
    url : str
        Service without LiDAR or carbon.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    wait_ready(page)
    page.locator("#ws-data").click()
    page.locator("#sub-lidar").wait_for(state="visible", timeout=60000)
    page.locator("#sub-lidar").click()
    page.wait_for_timeout(300)
    assert page.locator("#lidar-empty").is_visible(), "LiDAR empty state is missing"
    assert page.locator("#lidar-legend").is_visible() is False, "empty LiDAR legend is visible"
    assert page.locator("#lidar-coverage-row").is_visible() is False, (
        "empty coverage row is visible"
    )
    page.locator("#sub-carbon").click()
    page.wait_for_timeout(300)
    assert page.locator("#carbon-empty").is_visible(), "carbon empty state is missing"
    assert page.locator("#carbon-content").is_visible() is False, "empty carbon content is visible"
    assert page.locator("#carbon-chart").is_visible() is False, "empty carbon chart is visible"


def check(  # pragma: no cover - needs a browser
    lidar_url: str,
    carbon_url: str,
    empty_url: str,
    *,
    carbon_run: str | None = None,
    lidar_field: str = "lidar_chm_mean",
) -> int:
    """Run the three data-panel checks in one headless browser.

    Parameters
    ----------
    lidar_url : str
        Service with registered LiDAR.
    carbon_url : str
        Service with a carbon run.
    empty_url : str
        Service without LiDAR or carbon.
    carbon_run : str or None, optional
        Carbon run id to select.
    lidar_field : str, optional
        Preferred LiDAR field name.

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
            lidar_page = browser.new_page(viewport={"width": 1500, "height": 1000})
            lidar_page.on(
                "console",
                lambda message: (
                    errors.append(f"{message.type}: {message.text}")
                    if message.type == "error"
                    and "Failed to load resource" not in message.text
                    and not any(
                        marker in str(message.location)
                        for marker in ("favicon", "/api/land-base", "tile.openstreetmap.org")
                    )
                    else None
                ),
            )
            check_lidar(lidar_page, lidar_url, lidar_field)
            lidar_page.close()

            carbon_page = browser.new_page(viewport={"width": 1500, "height": 1000})
            carbon_page.on(
                "console",
                lambda message: (
                    errors.append(f"{message.type}: {message.text}")
                    if message.type == "error"
                    and "Failed to load resource" not in message.text
                    and not any(
                        marker in str(message.location)
                        for marker in ("favicon", "/api/land-base", "tile.openstreetmap.org")
                    )
                    else None
                ),
            )
            check_carbon(carbon_page, carbon_url, carbon_run)
            carbon_page.close()

            empty_page = browser.new_page(viewport={"width": 1500, "height": 1000})
            check_empty(empty_page, empty_url)
            empty_page.close()
            assert not errors, errors
        except Exception as exc:
            print(f"data-panel check failed: {exc}", file=sys.stderr)
            print("\n".join(errors), file=sys.stderr)
            return 1
        finally:
            browser.close()
    print("data panels: LiDAR coverage/palette/legend, carbon labels/axes/tooltip, empty tabs")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lidar-url", required=True, help="service with registered LiDAR")
    parser.add_argument("--carbon-url", required=True, help="service with a carbon run")
    parser.add_argument("--empty-url", required=True, help="service without LiDAR or carbon")
    parser.add_argument("--carbon-run", help="carbon run id to select")
    parser.add_argument("--lidar-field", default="lidar_chm_mean")
    args = parser.parse_args()
    sys.exit(
        check(
            args.lidar_url,
            args.carbon_url,
            args.empty_url,
            carbon_run=args.carbon_run,
            lidar_field=args.lidar_field,
        )
    )
