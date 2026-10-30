#!/usr/bin/env python3
"""Regenerate ``chemistry_engine/elements_data.py`` from the authoritative CIAAW tables.

Data sources
------------
* Abridged Standard Atomic Weights 2024
  https://www.ciaaw.org/abridged-atomic-weights.htm
* Radioactive Elements (most stable known isotopes, 2020 NUBASE evaluation)
  https://www.ciaaw.org/radioactive-elements.htm

The generated module is committed so the engine itself never needs the network.
Run this script only when refreshing the data::

    python tools/update_periodic_table.py

The script intentionally keeps the output deterministic (no timestamps) so a
refresh produces a clean diff.
"""
from __future__ import annotations

import html
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "chemistry_engine" / "elements_data.py"

ABRIDGED_URL = "https://www.ciaaw.org/abridged-atomic-weights.htm"
RADIOACTIVE_URL = "https://www.ciaaw.org/radioactive-elements.htm"

# CIAAW lists several near-equally long-lived isotopes for a few elements.
# For these we keep the bracket value used by the printed IUPAC periodic table.
MASS_NUMBER_OVERRIDES = {
    "Tc": 98,
}

_UNIT_SECONDS = {
    "s": 1.0,
    "ms": 1e-3,
    "min": 60.0,
    "h": 3600.0,
    "d": 86400.0,
    "a": 365.25 * 86400.0,
    "ka": 1e3 * 365.25 * 86400.0,
    "Ma": 1e6 * 365.25 * 86400.0,
}


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "chemistry-engine-data/1.0 (+periodic table refresh)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_table(page: str) -> list[list[str]]:
    match = re.search(
        r'<table[^>]*id=["\']mytable["\'][^>]*>(.*?)</table>', page, re.S | re.I
    )
    if not match:
        raise RuntimeError("could not find the CIAAW data table")
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", match.group(1), re.S | re.I):
        cells = [
            strip_tags(cell)
            for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S | re.I)
        ]
        if cells:
            rows.append(cells)
    return rows


def parse_abridged(page: str) -> dict[int, tuple[str, str, float | None]]:
    elements: dict[int, tuple[str, str, float | None]] = {}
    for cells in parse_table(page):
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        number = int(cells[0])
        symbol, name, weight_text = cells[1], cells[2], cells[3]
        weight: float | None = None
        match = re.match(r"^([0-9]+(?:\.[0-9]+)?)", weight_text)
        if match:
            weight = float(match.group(1))
        elements[number] = (symbol, name, weight)
    if len(elements) != 118:
        raise RuntimeError(f"expected 118 elements, parsed {len(elements)}")
    return elements


def parse_half_life_seconds(text: str) -> float:
    cleaned = text.replace("approx.", "").strip()
    match = re.match(
        r"^([0-9]+(?:\.[0-9]+)?)(?:\([0-9.]+\))?\s*(ms|min|s|h|d|ka|Ma|a)\b",
        cleaned,
    )
    if not match:
        return 0.0
    return float(match.group(1)) * _UNIT_SECONDS[match.group(2)]


def parse_radioactive(page: str) -> dict[int, tuple[str, str, int]]:
    """Return atomic number -> (symbol, name, mass number of longest-lived isotope).

    The CIAAW table uses ``rowspan`` for the Z/Symbol/Name cells when an element
    has several candidate isotopes; the follow-up rows only carry mass number and
    half-life, so parsing has to remember the current element.
    """
    candidates: dict[int, list[tuple[float, int]]] = {}
    meta: dict[int, tuple[str, str]] = {}
    current: tuple[int, str, str] | None = None
    for cells in parse_table(page):
        if len(cells) >= 5 and cells[0].isdigit():
            current = (int(cells[0]), cells[1], cells[2])
            mass_text, half_life_text = cells[3], cells[4]
        elif len(cells) == 2 and current is not None:
            mass_text, half_life_text = cells[0], cells[1]
        else:
            continue
        try:
            mass_number = int(mass_text)
        except ValueError:
            continue
        number, symbol, name = current
        meta[number] = (symbol, name)
        candidates.setdefault(number, []).append(
            (parse_half_life_seconds(half_life_text), mass_number)
        )
    result: dict[int, tuple[str, str, int]] = {}
    for number, options in candidates.items():
        symbol, name = meta[number]
        mass_number = max(options)[1]
        result[number] = (symbol, name, MASS_NUMBER_OVERRIDES.get(symbol, mass_number))
    return result


def main() -> int:
    abridged = parse_abridged(fetch(ABRIDGED_URL))
    radioactive = parse_radioactive(fetch(RADIOACTIVE_URL))

    lines: list[str] = []
    for number in range(1, 119):
        if number not in abridged:
            raise RuntimeError(f"missing element {number} in abridged table")
        symbol, name, weight = abridged[number]
        if weight is None:
            if number not in radioactive:
                raise RuntimeError(f"no mass number for radioactive element {symbol}")
            symbol2, name2, mass_number = radioactive[number]
            if symbol != symbol2:
                raise RuntimeError(f"symbol mismatch for Z={number}")
        else:
            mass_number = None
        display_name = name[:1].upper() + name[1:]
        weight_repr = "None" if weight is None else repr(weight)
        mass_repr = "None" if mass_number is None else str(mass_number)
        lines.append(
            f"    ({number}, {symbol!r}, {display_name!r}, {weight_repr}, {mass_repr}),"
        )

    content = (
        '"""Periodic-table data (generated; do not edit).\n'
        "\n"
        "Source: CIAAW/IUPAC Abridged Standard Atomic Weights 2024\n"
        "(https://www.ciaaw.org/abridged-atomic-weights.htm).  Elements without a\n"
        "standard atomic weight use the mass number of the longest-lived known\n"
        "isotope from https://www.ciaaw.org/radioactive-elements.htm.\n"
        "\n"
        "Regenerate with ``python tools/update_periodic_table.py``.\n"
        '"""\n'
        "\n"
        "# (atomic_number, symbol, name, abridged_standard_atomic_weight, most_stable_mass_number)\n"
        "ELEMENTS: tuple[tuple[int, str, str, float | None, int | None], ...] = (\n"
        + "\n".join(lines)
        + "\n)\n"
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(lines)} elements)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
