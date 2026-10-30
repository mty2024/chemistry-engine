"""Tests for equation parsing and balancing."""
from __future__ import annotations

import unittest

from chemistry_engine import balance_equation, parse_equation
from chemistry_engine.errors import EquationParseError, UnbalanceableEquationError


class BalancingTests(unittest.TestCase):
    def test_water_formation(self) -> None:
        balanced = balance_equation("H2 + O2 -> H2O")
        self.assertEqual(balanced.coefficients, (2, 1, 2))
        self.assertEqual(balanced.formula, "2H2 + O2 -> 2H2O")
        self.assertTrue(balanced.is_unique)

    def test_iron_oxide(self) -> None:
        balanced = balance_equation("Fe + O2 -> Fe2O3")
        self.assertEqual(balanced.coefficients, (4, 3, 2))
        self.assertEqual(balanced.formula, "4Fe + 3O2 -> 2Fe2O3")

    def test_methane_combustion(self) -> None:
        balanced = balance_equation("CH4 + O2 -> CO2 + H2O")
        self.assertEqual(balanced.coefficients, (1, 2, 1, 2))

    def test_propane_combustion(self) -> None:
        balanced = balance_equation("C3H8 + O2 -> CO2 + H2O")
        self.assertEqual(balanced.coefficients, (1, 5, 3, 4))

    def test_permanganate_oxidation(self) -> None:
        balanced = balance_equation(
            "KMnO4 + HCl -> KCl + MnCl2 + Cl2 + H2O"
        )
        self.assertEqual(balanced.coefficients, (2, 16, 2, 2, 5, 8))
        self.assertEqual(
            [check.symbol for check in balanced.element_balances],
            ["K", "Mn", "O", "H", "Cl"],
        )

    def test_ionic_redox_balances_charge(self) -> None:
        balanced = balance_equation(
            "Fe^2+ + MnO4^- + H^+ -> Fe^3+ + Mn^2+ + H2O"
        )
        self.assertEqual(balanced.coefficients, (5, 1, 8, 5, 1, 4))
        self.assertEqual(balanced.charge_left, 17)
        self.assertEqual(balanced.charge_right, 17)
        self.assertTrue(all(check.balanced for check in balanced.element_balances))

    def test_half_reaction_with_electron(self) -> None:
        balanced = balance_equation("Fe^3+ + e^- -> Fe^2+")
        self.assertEqual(balanced.coefficients, (1, 1, 1))
        self.assertEqual(balanced.charge_left, 2)
        self.assertEqual(balanced.charge_right, 2)

    def test_input_coefficients_are_ignored(self) -> None:
        balanced = balance_equation("2H2 + O2 -> 2H2O")
        self.assertEqual(balanced.coefficients, (2, 1, 2))
        balanced = balance_equation("4H2 + 2O2 -> 4H2O")
        self.assertEqual(balanced.coefficients, (2, 1, 2))

    def test_already_balanced_equation(self) -> None:
        balanced = balance_equation("H2 + Cl2 -> 2HCl")
        self.assertEqual(balanced.coefficients, (1, 1, 2))

    def test_reversible_arrow_is_preserved(self) -> None:
        balanced = balance_equation("N2 + 3H2 <=> 2NH3")
        self.assertTrue(balanced.reversible)
        self.assertIn("⇌", balanced.formula)

    def test_multiple_independent_balances(self) -> None:
        balanced = balance_equation("C + O2 -> CO + CO2")
        self.assertFalse(balanced.is_unique)
        self.assertTrue(all(coefficient > 0 for coefficient in balanced.coefficients))
        self.assertTrue(all(check.balanced for check in balanced.element_balances))

    def test_arrow_spellings(self) -> None:
        for equation in (
            "H2 + O2 -> H2O",
            "H2 + O2 → H2O",
            "H2 + O2 => H2O",
            "H2 + O2 = H2O",
        ):
            with self.subTest(equation=equation):
                self.assertEqual(
                    balance_equation(equation).coefficients, (2, 1, 2)
                )

    def test_element_and_charge_checks(self) -> None:
        balanced = balance_equation("Al + Fe2O3 -> Al2O3 + Fe")
        checks = {check.symbol: check for check in balanced.element_balances}
        self.assertEqual(set(checks), {"Al", "Fe", "O"})
        self.assertEqual(checks["Al"].left, 2)
        self.assertEqual(checks["Al"].right, 2)


class UnbalanceableTests(unittest.TestCase):
    def test_element_cannot_be_conserved(self) -> None:
        with self.assertRaises(UnbalanceableEquationError):
            balance_equation("H2 -> O2")

    def test_missing_product_atoms(self) -> None:
        with self.assertRaises(UnbalanceableEquationError):
            balance_equation("CH4 + O2 -> CO2")

    def test_impossible_water_synthesis(self) -> None:
        with self.assertRaises(UnbalanceableEquationError):
            balance_equation("H2 -> H2O")

    def test_missing_arrow(self) -> None:
        with self.assertRaises(EquationParseError):
            balance_equation("H2 + O2")

    def test_missing_products(self) -> None:
        with self.assertRaises(EquationParseError):
            balance_equation("H2O ->")

    def test_duplicate_species_on_a_side(self) -> None:
        with self.assertRaises(EquationParseError):
            parse_equation("H2 + H2 -> H2")


if __name__ == "__main__":
    unittest.main()
