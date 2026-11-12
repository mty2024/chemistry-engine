#!/usr/bin/env python3
"""Real-browser smoke test for the GitHub Pages playground.

Loads the deployed playground with Playwright, lets Pyodide install the wheel,
and asserts that the auto-running balance example produces a conservation
check. This is the "playability" check used by the daily audit workflow.

Requires the optional Playwright dependency::

    pip install playwright
    python -m playwright install --with-deps chromium
    python tools/check_playground.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_URL = (
    "https://mty2024.github.io/chemistry-engine/playground.html?demo=balance"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=600,
        help="how long to wait for Pyodide + the wheel (default: 600s)",
    )
    parser.add_argument("--screenshot", default="playground-audit.png")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is not installed. Run: pip install playwright && "
            "python -m playwright install --with-deps chromium",
            file=sys.stderr,
        )
        return 2

    screenshot = Path(args.screenshot)
    screenshot.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.set_default_timeout(90_000)
        status = ""
        output = ""
        failure = ""
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_function(
                """() => {
                    const status = document.querySelector('[data-engine-status]');
                    const output = document.querySelector('[data-playground-output]');
                    const statusText = status ? status.textContent : '';
                    const outputText = output ? output.textContent : '';
                    return statusText.startsWith('Engine ready') ||
                        outputText.includes('Could not compute') ||
                        outputText.includes('Could not start') ||
                        outputText.includes('Engine failed');
                }""",
                timeout=args.wait_seconds * 1000,
            )
            status = page.locator("[data-engine-status]").inner_text()
            output = page.locator("[data-playground-output]").inner_text()
        except Exception as error:  # noqa: BLE001 - report browser failures plainly
            failure = f"{type(error).__name__}: {error}"
            try:
                status = page.locator("[data-engine-status]").inner_text()
                output = page.locator("[data-playground-output]").inner_text()
            except Exception:
                pass
        finally:
            try:
                page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                pass
            browser.close()

    print("playground status:", status or "(unknown)")
    print("playground output:")
    print(output or "(empty)")
    if failure:
        print("browser failure:", failure, file=sys.stderr)

    ok = (
        not failure
        and status.startswith("Engine ready")
        and "Atom check" in output
    )
    if screenshot.exists():
        print(f"screenshot: {screenshot}")
    if not ok:
        print("playground smoke test FAILED", file=sys.stderr)
        return 1
    print("playground smoke test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
