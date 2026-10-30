"""Tests for the ``chem`` command-line interface."""
from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from chemistry_engine.cli import main


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_version(self) -> None:
        with redirect_stdout(io.StringIO()) as stdout:
            with self.assertRaises(SystemExit) as caught:
                main(["--version"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("chem 0.1.0", stdout.getvalue())

    def test_mass_human(self) -> None:
        code, stdout, stderr = run_cli(["mass", "H2O", "C6H12O6"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("18.015 g/mol", stdout)
        self.assertIn("180.156 g/mol", stdout)

    def test_mass_json(self) -> None:
        code, stdout, _ = run_cli(["mass", "--json", "H2O"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload[0]["formula"], "H2O")
        self.assertAlmostEqual(payload[0]["molar_mass_g_per_mol"], 18.015)

    def test_json_flag_before_subcommand(self) -> None:
        code, stdout, _ = run_cli(["--json", "mass", "H2O"])
        self.assertEqual(code, 0)
        self.assertIn("molar_mass_g_per_mol", stdout)

    def test_composition(self) -> None:
        code, stdout, _ = run_cli(["composition", "H2O"])
        self.assertEqual(code, 0)
        self.assertIn("11.19", stdout)
        self.assertIn("88.809", stdout)

    def test_inspect(self) -> None:
        code, stdout, _ = run_cli(["inspect", "K4[Fe(CN)6]"])
        self.assertEqual(code, 0)
        self.assertIn("K 4", stdout)
        self.assertIn("368.345 g/mol", stdout)

    def test_balance(self) -> None:
        code, stdout, _ = run_cli(["balance", "Fe + O2 -> Fe2O3"])
        self.assertEqual(code, 0)
        self.assertIn("4Fe + 3O2 -> 2Fe2O3", stdout)
        self.assertIn("Fe: 4 = 4", stdout)
        self.assertIn("O: 6 = 6", stdout)

    def test_balance_json(self) -> None:
        code, stdout, _ = run_cli(["balance", "--json", "H2 + O2 -> H2O"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["equation"], "2H2 + O2 -> 2H2O")
        self.assertEqual([item["coefficient"] for item in payload["reactants"]], [2, 1])
        self.assertTrue(payload["is_unique"])

    def test_stoich(self) -> None:
        code, stdout, _ = run_cli(
            [
                "stoich",
                "--equation",
                "N2 + 3H2 -> 2NH3",
                "--feed",
                "N2=28 g",
                "--feed",
                "H2=6 g",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("Limiting reagent : H2", stdout)

    def test_stoich_json(self) -> None:
        code, stdout, _ = run_cli(
            [
                "stoich",
                "--json",
                "--equation",
                "N2 + 3H2 -> 2NH3",
                "--feed",
                "N2=1 mol",
                "--feed",
                "H2=2 mol",
            ]
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["limiting_reagents"], ["H2"])
        self.assertAlmostEqual(payload["extent_mol"], 2 / 3)

    def test_element_json(self) -> None:
        code, stdout, _ = run_cli(["element", "--json", "Fe"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["symbol"], "Fe")
        self.assertEqual(payload["atomic_number"], 26)
        self.assertAlmostEqual(payload["atomic_mass_g_per_mol"], 55.845)

    def test_elements_are_all_present(self) -> None:
        code, stdout, _ = run_cli(["elements", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(stdout)), 118)

    def test_invalid_formula_exits_with_error(self) -> None:
        code, stdout, stderr = run_cli(["mass", "Xx2"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("unknown element", stderr)
        self.assertIn("^", stderr)


if __name__ == "__main__":
    unittest.main()
