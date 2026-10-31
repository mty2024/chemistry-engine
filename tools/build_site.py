#!/usr/bin/env python3
"""Generate the data files consumed by the GitHub Pages site.

Currently this writes ``site/assets/elements.json`` from the engine's own
periodic table, so the interactive element explorer cannot drift from the
library.  Run before deploying the site::

    python tools/build_site.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
ASSETS = SITE / "assets"

sys.path.insert(0, str(ROOT))
from chemistry_engine import ELEMENTS, __version__  # noqa: E402


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": __version__,
        "source": "CIAAW Abridged Standard Atomic Weights 2024",
        "elements": [
            {
                "z": element.atomic_number,
                "symbol": element.symbol,
                "name": element.name,
                "mass": element.atomic_mass,
                "standard": element.has_standard_atomic_weight,
            }
            for element in ELEMENTS
        ],
    }
    target = ASSETS / "elements.json"
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {target.relative_to(ROOT)} ({len(payload['elements'])} elements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
