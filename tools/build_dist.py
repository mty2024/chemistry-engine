#!/usr/bin/env python3
"""Build the release artifacts for chemistry-engine with the standard library.

The release environment used to cut v0.1.0 had no setuptools installed (and a
sandbox that blocked PEP 517 temporary directories), so this script constructs
ordinary PEP 427 wheel and PEP 517 sdist files directly.  It is deterministic:
fixed zip/tar timestamps and sorted entries, so rebuilding from the same tree
gives the same bytes.

Usage::

    python tools/build_dist.py

Writes ``dist/chemistry_engine-<version>-py3-none-any.whl`` and
``dist/chemistry_engine-<version>.tar.gz``.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import io
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
FIXED_ZIP_DATE = (2026, 1, 1, 0, 0, 0)
FIXED_MTIME = 0

sys.path.insert(0, str(ROOT))
from chemistry_engine import __version__  # noqa: E402


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def pyproject_value(pattern: str) -> str:
    text = read_text(ROOT / "pyproject.toml")
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise SystemExit(f"could not find {pattern!r} in pyproject.toml")
    return match.group(1)


NAME = pyproject_value(r'^name = "([^"]+)"')
SUMMARY = pyproject_value(r'^description = "([^"]+)"')
REPOSITORY = pyproject_value(r'^Repository = "([^"]+)"')
CHANGELOG_URL = pyproject_value(r'^Changelog = "([^"]+)"')
NORMALIZED_NAME = re.sub(r"[-_.]+", "_", NAME).lower()
VERSION = __version__


def metadata() -> str:
    readme = read_text(ROOT / "README.md")
    headers = [
        "Metadata-Version: 2.1",
        f"Name: {NAME}",
        f"Version: {VERSION}",
        f"Summary: {SUMMARY}",
        f"Home-page: {REPOSITORY}",
        "Author: chemistry-engine contributors",
        f"Project-URL: Repository, {REPOSITORY}",
        f"Project-URL: Changelog, {CHANGELOG_URL}",
        "Keywords: chemistry, stoichiometry, chemical-formula, balancing",
        "Classifier: Programming Language :: Python :: 3",
        "Classifier: Topic :: Scientific/Engineering :: Chemistry",
        "Requires-Python: >=3.10",
        "Description-Content-Type: text/markdown",
    ]
    return "\n".join(headers) + "\n\n" + readme


def package_entries() -> list[tuple[str, bytes]]:
    entries = [
        (path.relative_to(ROOT).as_posix(), path.read_bytes())
        for path in sorted((ROOT / "chemistry_engine").rglob("*.py"))
    ]
    if not entries:
        raise SystemExit("no files found under chemistry_engine/")
    return entries


def build_wheel() -> Path:
    dist_info = f"{NORMALIZED_NAME}-{VERSION}.dist-info"
    files: dict[str, bytes] = dict(package_entries())
    files[f"{dist_info}/METADATA"] = metadata().encode("utf-8")
    files[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Generator: chemistry-engine-build-dist\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")
    files[f"{dist_info}/entry_points.txt"] = (
        "[console_scripts]\n"
        "chem = chemistry_engine.cli:main\n"
    ).encode("utf-8")

    record_lines: list[str] = []
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
        record_lines.append(f"{name},sha256={digest},{len(data)}")
    record_name = f"{dist_info}/RECORD"
    record_lines.append(f"{record_name},,")
    files[record_name] = ("\n".join(record_lines) + "\n").encode("utf-8")

    wheel_path = DIST / f"{NORMALIZED_NAME}-{VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    validate_wheel(wheel_path)
    return wheel_path


def sdist_entries() -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = [
        ("PKG-INFO", metadata().encode("utf-8")),
        ("pyproject.toml", (ROOT / "pyproject.toml").read_bytes()),
        ("README.md", (ROOT / "README.md").read_bytes()),
        ("CHANGELOG.md", (ROOT / "CHANGELOG.md").read_bytes()),
        ("AGENTS.md", (ROOT / "AGENTS.md").read_bytes()),
        *package_entries(),
        *[
            (path.relative_to(ROOT).as_posix(), path.read_bytes())
            for path in sorted((ROOT / "tests").glob("*.py"))
        ],
        *[
            (path.relative_to(ROOT).as_posix(), path.read_bytes())
            for path in sorted((ROOT / "tools").glob("*.py"))
        ],
        *[
            (path.relative_to(ROOT).as_posix(), path.read_bytes())
            for path in sorted((ROOT / "docs" / "releases").glob("*.md"))
        ],
    ]
    return entries


def build_sdist() -> Path:
    sdist_path = DIST / f"{NORMALIZED_NAME}-{VERSION}.tar.gz"
    root_dir = f"{NORMALIZED_NAME}-{VERSION}"
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for relative, data in sorted(sdist_entries()):
                info = tarfile.TarInfo(f"{root_dir}/{relative}")
                info.size = len(data)
                info.mtime = FIXED_MTIME
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    sdist_path.write_bytes(raw.getvalue())
    return sdist_path


def validate_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        dist_info = f"{NORMALIZED_NAME}-{VERSION}.dist-info"
        for required in (
            f"{dist_info}/METADATA",
            f"{dist_info}/WHEEL",
            f"{dist_info}/entry_points.txt",
            f"{dist_info}/RECORD",
            "chemistry_engine/__init__.py",
            "chemistry_engine/cli.py",
        ):
            if required not in names:
                raise SystemExit(f"wheel is missing {required}")
        record = archive.read(f"{dist_info}/RECORD").decode("utf-8").splitlines()
        for line in record:
            if not line:
                continue
            relative, checksum, size = line.split(",")
            if relative.endswith("/RECORD"):
                continue
            data = archive.read(relative)
            expected = base64.urlsafe_b64encode(
                hashlib.sha256(data).digest()
            ).rstrip(b"=").decode("ascii")
            if checksum != f"sha256={expected}" or int(size) != len(data):
                raise SystemExit(f"wheel RECORD mismatch for {relative}")
        metadata_text = archive.read(f"{dist_info}/METADATA").decode("utf-8")
        if f"Name: {NAME}" not in metadata_text or f"Version: {VERSION}" not in metadata_text:
            raise SystemExit("wheel metadata name/version mismatch")


def main() -> int:
    DIST.mkdir(exist_ok=True)
    wheel = build_wheel()
    sdist = build_sdist()
    print(wheel.relative_to(ROOT))
    print(sdist.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
