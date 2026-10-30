"""Tests for chemical formula parsing."""
from __future__ import annotations

import unittest
from fractions import Fraction

from chemistry_engine import Formula, parse_formula
from chemistry_engine.errors import FormulaParseError


def counts(formula: str) -> dict[str, Fraction]:
    return dict(parse_formula(formula).atom_counts)


class FormulaParsingTests(unittest.TestCase):
    def test_simple_formulas(self) -> None:
        self.assertEqual(counts("H2O"), {"H": Fraction(2), "O": Fraction(1)})
        self.assertEqual(
            counts("C6H12O6"),
            {"C": Fraction(6), "H": Fraction(12), "O": Fraction(6)},
        )
        self.assertEqual(counts("NaCl"), {"Na": Fraction(1), "Cl": Fraction(1)})
        self.assertEqual(counts("O2"), {"O": Fraction(2)})

    def test_case_sensitivity_is_chemical(self) -> None:
        self.assertEqual(counts("Co"), {"Co": Fraction(1)})
        self.assertEqual(counts("CO"), {"C": Fraction(1), "O": Fraction(1)})

    def test_parentheses_and_brackets(self) -> None:
        self.assertEqual(
            counts("Ca(OH)2"), {"Ca": Fraction(1), "O": Fraction(2), "H": Fraction(2)}
        )
        self.assertEqual(
            counts("Al2(SO4)3"),
            {"Al": Fraction(2), "S": Fraction(3), "O": Fraction(12)},
        )
        self.assertEqual(
            counts("K4[Fe(CN)6]"),
            {
                "K": Fraction(4),
                "Fe": Fraction(1),
                "C": Fraction(6),
                "N": Fraction(6),
            },
        )
        self.assertEqual(
            counts("[Cu(NH3)4]SO4"),
            {
                "Cu": Fraction(1),
                "N": Fraction(4),
                "H": Fraction(12),
                "S": Fraction(1),
                "O": Fraction(4),
            },
        )
        self.assertEqual(
            counts("Ca3(PO4)2"),
            {"Ca": Fraction(3), "P": Fraction(2), "O": Fraction(8)},
        )

    def test_hydrates(self) -> None:
        expected = {
            "Cu": Fraction(1),
            "S": Fraction(1),
            "O": Fraction(9),
            "H": Fraction(10),
        }
        self.assertEqual(counts("CuSO4·5H2O"), expected)
        self.assertEqual(counts("CuSO4.5H2O"), expected)
        self.assertEqual(counts("CuSO4*5H2O"), expected)
        self.assertEqual(
            counts("Na2CO3·10H2O"),
            {
                "Na": Fraction(2),
                "C": Fraction(1),
                "O": Fraction(13),
                "H": Fraction(20),
            },
        )

    def test_fractional_hydrate(self) -> None:
        gypsum = parse_formula("CaSO4·½H2O")
        self.assertEqual(gypsum.count("Ca"), 1)
        self.assertEqual(gypsum.count("S"), 1)
        self.assertEqual(gypsum.count("O"), Fraction(9, 2))
        self.assertEqual(gypsum.count("H"), 1)

    def test_charges(self) -> None:
        cases = {
            "Fe^3+": 3,
            "Fe^2+": 2,
            "NH4+": 1,
            "OH^-": -1,
            "SO4^2-": -2,
            "SO4²⁻": -2,
            "NH4⁺": 1,
            "[Fe(CN)6]^4-": -4,
            "H^+": 1,
        }
        for formula, charge in cases.items():
            with self.subTest(formula=formula):
                self.assertEqual(parse_formula(formula).charge, charge)
        self.assertEqual(parse_formula("H2O").charge, 0)

    def test_unicode_subscripts(self) -> None:
        self.assertEqual(counts("H₂O"), {"H": Fraction(2), "O": Fraction(1)})
        self.assertEqual(
            counts("(NH₄)₂SO₄"),
            {"N": Fraction(2), "H": Fraction(8), "S": Fraction(1), "O": Fraction(4)},
        )

    def test_electron(self) -> None:
        electron = parse_formula("e^-")
        self.assertTrue(electron.is_electron)
        self.assertEqual(electron.charge, -1)
        self.assertEqual(dict(electron.atom_counts), {})
        self.assertTrue(parse_formula("e⁻").is_electron)

    def test_whitespace_is_ignored(self) -> None:
        self.assertEqual(counts(" H2 O "), {"H": Fraction(2), "O": Fraction(1)})

    def test_text_and_canonical_form(self) -> None:
        formula = parse_formula("CuSO4·5H2O")
        self.assertEqual(formula.text, "CuSO4·5H2O")
        self.assertEqual(parse_formula("OH2").canonical_formula(), "OH2")
        self.assertEqual(parse_formula("SO4^2-").canonical_formula(), "SO4^2-")
        self.assertEqual(
            parse_formula("CuSO4·5H2O").canonical_formula(), "CuSO4·5H2O"
        )
        self.assertEqual(parse_formula("e^-").canonical_formula(), "e^-")

    def test_parse_accepts_formula_instance(self) -> None:
        formula = parse_formula("H2O")
        self.assertIs(parse_formula(formula), formula)

    def test_errors(self) -> None:
        bad = [
            "",
            "   ",
            "Xx2",
            "H2O)",
            "(H2O",
            "H0",
            "2H2O",
            "H2O^",
            "H2O^2",
            "()",
            "H2O·",
            "H2O·0H2O",
            "H2O++",
            "H2O^0+",
        ]
        for formula in bad:
            with self.subTest(formula=formula):
                with self.assertRaises(FormulaParseError):
                    parse_formula(formula)

    def test_error_points_at_problem(self) -> None:
        with self.assertRaises(FormulaParseError) as caught:
            parse_formula("H2Xx")
        self.assertEqual(caught.exception.position, 2)
        self.assertIn("unknown element symbol 'Xx'", caught.exception.message)

    def test_formula_is_immutable(self) -> None:
        formula: Formula = parse_formula("H2O")
        with self.assertRaises(TypeError):
            formula.atom_counts["H"] = Fraction(9)  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
