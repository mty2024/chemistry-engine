"""Tests for molar mass and elemental composition."""
from __future__ import annotations

import unittest

from chemistry_engine import (
    ELECTRON_MOLAR_MASS_G,
    elemental_analysis,
    mass_fractions,
    mass_from_moles,
    molar_mass,
    moles_from_mass,
    percent_composition,
)
from chemistry_engine.errors import ChemError


class MolarMassTests(unittest.TestCase):
    def test_common_molar_masses(self) -> None:
        expected = {
            "H2O": 18.015,
            "C6H12O6": 180.156,
            "NaCl": 58.44,
            "CaCO3": 100.086,
            "K4[Fe(CN)6]": 368.345,
            "CuSO4·5H2O": 249.677,
            "CaSO4·½H2O": 145.1415,
            "O2": 31.998,
            "Fe2O3": 159.687,
        }
        for formula, value in expected.items():
            with self.subTest(formula=formula):
                self.assertAlmostEqual(molar_mass(formula), value, places=3)

    def test_electron_molar_mass_is_negligible_but_not_zero(self) -> None:
        self.assertAlmostEqual(molar_mass("e^-"), ELECTRON_MOLAR_MASS_G, places=12)
        self.assertLess(molar_mass("e^-"), 0.001)

    def test_accepts_formula_objects(self) -> None:
        from chemistry_engine import parse_formula

        self.assertAlmostEqual(molar_mass(parse_formula("H2O")), 18.015, places=6)


class CompositionTests(unittest.TestCase):
    def test_water_percent_composition(self) -> None:
        percentages = percent_composition("H2O")
        self.assertAlmostEqual(percentages["H"], 11.1907, places=3)
        self.assertAlmostEqual(percentages["O"], 88.8093, places=3)
        self.assertAlmostEqual(sum(percentages.values()), 100.0, places=9)

    def test_glucose_percent_composition(self) -> None:
        percentages = percent_composition("C6H12O6")
        self.assertAlmostEqual(percentages["C"], 40.0019, places=3)
        self.assertAlmostEqual(percentages["H"], 6.7142, places=3)
        self.assertAlmostEqual(percentages["O"], 53.2839, places=3)

    def test_mass_fractions_sum_to_one(self) -> None:
        fractions = mass_fractions("Al2(SO4)3")
        self.assertAlmostEqual(sum(fractions.values()), 1.0, places=12)
        self.assertAlmostEqual(fractions["O"], 12 * 15.999 / molar_mass("Al2(SO4)3"))

    def test_elemental_analysis_order_and_mass(self) -> None:
        analysis = elemental_analysis("H2O")
        self.assertEqual([item.element.symbol for item in analysis], ["H", "O"])
        self.assertEqual(analysis[0].count, 2.0)
        self.assertAlmostEqual(analysis[0].mass_g_per_mol, 2.016, places=6)
        self.assertAlmostEqual(analysis[0].mass_fraction, 2.016 / 18.015, places=12)

    def test_elemental_analysis_uses_hill_order(self) -> None:
        self.assertEqual(
            [item.element.symbol for item in elemental_analysis("C6H12O6")],
            ["C", "H", "O"],
        )
        self.assertEqual(
            [item.element.symbol for item in elemental_analysis("NaCl")],
            ["Cl", "Na"],
        )
        self.assertEqual(
            [item.element.symbol for item in elemental_analysis("K4[Fe(CN)6]")],
            ["C", "Fe", "K", "N"],
        )

    def test_fractional_hydrate_analysis(self) -> None:
        analysis = elemental_analysis("CaSO4·½H2O")
        by_symbol = {item.element.symbol: item for item in analysis}
        self.assertEqual(by_symbol["O"].count, 4.5)
        self.assertAlmostEqual(by_symbol["H"].count, 1.0)

    def test_electron_has_no_elemental_analysis(self) -> None:
        self.assertEqual(elemental_analysis("e^-"), ())


class AmountConversionTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        moles = moles_from_mass("H2O", 18.015)
        self.assertAlmostEqual(moles, 1.0, places=6)
        self.assertAlmostEqual(mass_from_moles("H2O", moles), 18.015, places=6)

    def test_negative_inputs_rejected(self) -> None:
        with self.assertRaises(ChemError):
            moles_from_mass("H2O", -1.0)
        with self.assertRaises(ChemError):
            mass_from_moles("H2O", -1.0)


if __name__ == "__main__":
    unittest.main()
