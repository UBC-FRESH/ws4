#!/usr/bin/env python3
"""Smoke-test the map palette, selection outline, legend, and treated-only filter.

Opt-in: requires Playwright and Chromium. The service must expose a run with block
geometry; the default uses the shell's preferred run.
"""

from __future__ import annotations

import argparse
import sys


def find_block(page) -> bool:  # pragma: no cover - needs a browser
    """Click likely block locations until the detail panel names one.

    Parameters
    ----------
    page : playwright.sync_api.Page
        Loaded shell page.

    Returns
    -------
    bool
        ``True`` when a block was selected.
    """
    for x, y in [(950, 450), (1000, 400), (900, 600), (1050, 500), (900, 350)]:
        page.mouse.click(x, y)
        page.wait_for_timeout(180)
        if page.locator("#detail").inner_text().strip():
            return True
    for x in range(700, 1400, 100):
        for y in range(240, 940, 100):
            page.mouse.click(x, y)
            page.wait_for_timeout(80)
            if page.locator("#detail").inner_text().strip():
                return True
    return False


def check(  # pragma: no cover - needs a browser
    url: str, run: str | None = None, *, wait_ms: int = 9000
) -> int:
    """Assert the neutral palette, legend, selected outline, and treated-only toggle.

    Parameters
    ----------
    url : str
        Service root.
    run : str or None, optional
        Run id to select; None keeps the page's preferred run.
    wait_ms : int, optional
        Milliseconds to wait for the run, map, and counts.

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
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.on(
            "console",
            lambda message: (
                errors.append(f"{message.type}: {message.text}")
                if message.type == "error"
                and not any(
                    marker in str(message.location)
                    for marker in ("favicon", "/api/land-base", "tile.openstreetmap.org")
                )
                else None
            ),
        )
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("#map-legend:not([hidden])", timeout=40000)
            page.wait_for_function(
                "() => !document.querySelector('#status').textContent.startsWith('loading')",
                timeout=40000,
            )
            page.wait_for_timeout(wait_ms)
            if run:
                page.select_option("#run", run)
                page.wait_for_selector("#map-legend:not([hidden])", timeout=40000)
                page.wait_for_function(
                    "() => !document.querySelector('#status').textContent.startsWith('loading')",
                    timeout=60000,
                )
                page.wait_for_timeout(wait_ms)

            legend = page.locator("#map-legend")
            assert legend.is_visible(), "on-map legend is not visible"
            text = legend.inner_text()
            assert "Treated" in text and "Untreated" in text, text
            treated_swatch = legend.locator(".map-legend-swatch.treated").first
            untreated_swatch = legend.locator(".map-legend-swatch.untreated").first
            assert page.evaluate(
                "element => getComputedStyle(element).backgroundColor",
                untreated_swatch.element_handle(),
            ) == "rgb(217, 228, 220)"
            assert treated_swatch.is_visible()

            map_box = page.locator("#map-wrap").bounding_box()
            legend_box = legend.bounding_box()
            assert map_box and legend_box
            assert legend_box["x"] >= map_box["x"] and legend_box["y"] >= map_box["y"]
            assert legend_box["x"] + legend_box["width"] <= map_box["x"] + map_box["width"]
            assert legend_box["y"] + legend_box["height"] <= map_box["y"] + map_box["height"]

            summaries = [text.lower() for text in page.locator("details.layer-group summary").all_inner_texts()]
            assert "unavailable layers" in summaries, summaries
            unavailable = page.locator("details.layer-group", has_text="Unavailable layers")
            assert unavailable.locator("input").count() == 0, "unavailable layers still use inputs"

            assert find_block(page), "could not select a block"
            assert page.locator("#map-wrap").get_attribute("data-selected-block"), "selection not recorded"
            assert page.locator("#detail").inner_text().startswith("Block "), "detail did not update"

            toggle = legend.locator("button")
            assert toggle.inner_text() == "Treated only", toggle.inner_text()
            toggle.click()
            page.wait_for_timeout(700)
            assert not page.locator("#show-untreated").is_checked(), "treated-only did not hide untreated"
            assert page.locator("#map-legend button").inner_text() == "Show all blocks"
            page.locator("#map-legend button").click()
            page.wait_for_timeout(700)
            assert page.locator("#show-untreated").is_checked(), "show-all did not restore untreated"

            page.locator("#ws-plan").click()
            page.wait_for_timeout(900)
            assert not page.locator("#map-wrap").is_visible(), "map remained visible in Plan"
            assert page.locator("#map-legend").is_visible() is False, "legend remained visible in Plan"
            page.locator("#ws-map").click()
            page.wait_for_timeout(700)
            assert page.locator("#map-legend").is_visible(), "legend did not return with the map"

            for width, height in [(1024, 768), (1194, 834), (1500, 1000)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(450)
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
                ), f"horizontal overflow at {width}x{height}"
                assert page.locator("#map-legend").is_visible(), f"legend hidden at {width}px"

            assert not errors, errors
        except Exception as exc:
            print(f"map hierarchy check failed: {exc}", file=sys.stderr)
            print("\n".join(errors), file=sys.stderr)
            return 1
        finally:
            browser.close()
    print("map hierarchy: neutral palette, selected outline, legend, treated-only, responsive")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="service root, for example http://127.0.0.1:8000/")
    parser.add_argument("--run", help="run id to select")
    parser.add_argument("--wait-ms", type=int, default=9000)
    args = parser.parse_args()
    sys.exit(check(args.url, args.run, wait_ms=args.wait_ms))
