"""Release-metadata consistency checks."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import chemistry_engine

ROOT = Path(__file__).resolve().parents[1]


class ReleaseMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    def test_package_version_matches_pyproject(self) -> None:
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', self.pyproject)
        self.assertIsNotNone(match, "pyproject.toml has no [project].version")
        self.assertEqual(match.group(1), chemistry_engine.__version__)

    def test_console_script_entry_point(self) -> None:
        self.assertIn('chem = "chemistry_engine.cli:main"', self.pyproject)

    def test_changelog_mentions_release_version(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## [{chemistry_engine.__version__}]", changelog)

    def test_release_notes_exist_for_version(self) -> None:
        notes = ROOT / "docs" / "releases" / f"v{chemistry_engine.__version__}.md"
        self.assertTrue(notes.is_file(), f"missing release notes: {notes}")


if __name__ == "__main__":
    unittest.main()
