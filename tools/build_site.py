#!/usr/bin/env python3
"""Generate the data files consumed by the GitHub Pages site.

This writes:

* ``site/assets/elements.json`` from the engine's own periodic table;
* ``site/assets/engine.json`` describing the wheel the playground installs;
* ``site/assets/chemistry_engine-<version>-py3-none-any.whl`` — the actual
  pure-Python wheel that Pyodide installs in the browser.

The site therefore runs the exact same engine code as the CLI, not a port.
Run before deploying the site::

    python tools/build_site.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
ASSETS = SITE / "assets"
PYODIDE_VERSION = "0.29.5"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from chemistry_engine import ELEMENTS, __version__  # noqa: E402

try:
    from build_dist import build_wheel  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - only if the builder is unavailable
    build_wheel = None


def write_elements() -> None:
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


def write_engine_wheel() -> None:
    for stale in ASSETS.glob("chemistry_engine-*.whl"):
        stale.unlink()
    if build_wheel is not None:
        wheel = build_wheel()
    else:  # pragma: no cover
        candidates = sorted((ROOT / "dist").glob(f"chemistry_engine-{__version__}-*.whl"))
        if not candidates:
            raise SystemExit("no wheel available; run python tools/build_dist.py first")
        wheel = candidates[-1]
    target = ASSETS / wheel.name
    shutil.copy2(wheel, target)
    engine = {
        "version": __version__,
        "wheel": wheel.name,
        "pyodide": PYODIDE_VERSION,
    }
    (ASSETS / "engine.json").write_text(
        json.dumps(engine, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"copied {target.relative_to(ROOT)} ({target.stat().st_size} bytes)")


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    write_elements()
    write_engine_wheel()
    print(f"pyodide runtime: {PYODIDE_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
