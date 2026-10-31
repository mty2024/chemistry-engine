#!/usr/bin/env python3
"""Validate the static GitHub Pages site with the standard library.

Checks:

* every local ``href`` / ``src`` resolves to a real file;
* every HTML page has a non-empty ``<title>``;
* the generated element data has all 118 entries with the expected keys;
* the required site assets exist.

Run after ``python tools/build_site.py``::

    python tools/check_site.py
"""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REQUIRED_PAGES = (
    "index.html",
    "404.html",
    "docs/index.html",
    "docs/cli.html",
    "docs/library.html",
    "docs/examples.html",
)
REQUIRED_ASSETS = (
    "assets/styles.css",
    "assets/site.js",
    "assets/logo.svg",
    "assets/elements.json",
)
SKIP_PREFIXES = ("http://", "https://", "mailto:", "data:", "javascript:", "#")


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.links.append((tag, value))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def resolve_local_link(page: Path, raw: str) -> Path | None:
    raw = raw.strip()
    if not raw or raw.startswith(SKIP_PREFIXES):
        return None
    parsed = urlsplit(raw)
    path = unquote(parsed.path)
    if not path:
        return None
    if path.startswith("/"):
        # Site-root relative (not used today, but handle sensibly).
        return SITE / path.lstrip("/")
    return (page.parent / path).resolve()


def check_html_pages(errors: list[str]) -> int:
    checked = 0
    for page in sorted(SITE.rglob("*.html")):
        checked += 1
        parser = LinkCollector()
        parser.feed(page.read_text(encoding="utf-8"))
        if not parser.title.strip():
            errors.append(f"{page.relative_to(ROOT)}: missing <title>")
        for tag, raw in parser.links:
            target = resolve_local_link(page, raw)
            if target is None:
                continue
            if not target.exists():
                errors.append(
                    f"{page.relative_to(ROOT)}: <{tag}> points at missing "
                    f"{target.relative_to(ROOT)}"
                )
    return checked


def check_required_files(errors: list[str]) -> None:
    for relative in REQUIRED_PAGES + REQUIRED_ASSETS:
        if not (SITE / relative).is_file():
            errors.append(f"missing required site file: site/{relative}")


def check_element_data(errors: list[str]) -> None:
    path = SITE / "assets" / "elements.json"
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        errors.append(f"site/assets/elements.json: invalid JSON ({error})")
        return
    elements = payload.get("elements")
    if not isinstance(elements, list) or len(elements) != 118:
        errors.append("site/assets/elements.json: expected 118 elements")
        return
    for element in elements:
        for key in ("z", "symbol", "name", "mass", "standard"):
            if key not in element:
                errors.append(
                    f"site/assets/elements.json: element {element!r} is missing {key!r}"
                )
                return


def main() -> int:
    errors: list[str] = []
    if not SITE.is_dir():
        print("missing site/ directory", file=sys.stderr)
        return 1
    check_required_files(errors)
    html_count = check_html_pages(errors)
    check_element_data(errors)
    if errors:
        print(f"site validation failed ({len(errors)} problem(s)):")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"site OK: {html_count} HTML pages, {len(REQUIRED_ASSETS)} required assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
