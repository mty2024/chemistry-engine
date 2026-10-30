"""Tests for the periodic table and element lookup."""
from __future__ import annotations

import unittest

from chemistry_engine import ELEMENTS, get_element, try_get_element
from chemistry_engine.errors import UnknownElementError


class ElementTableTests(unittest.TestCase):
    def test_all_118_elements_in_order(self) -> None:
        self.assertEqual(len(ELEMENTS), 118)
        self.assertEqual([element.atomic_number for element in ELEMENTS], list(range(1, 119)))
        self.assertEqual(len({element.symbol for element in ELEMENTS}), 118)
        self.assertEqual(len({element.name for element in ELEMENTS}), 118)

    def test_abridged_iupac_weights(self) -> None:
        expected = {
            "H": 1.008,
            "C": 12.011,
            "N": 14.007,
            "O": 15.999,
            "Na": 22.990,
            "S": 32.06,
            "Cl": 35.45,
            "Ar": 39.95,
            "Fe": 55.845,
            "Cu": 63.546,
            "Zr": 91.222,
            "I": 126.90,
            "Pb": 207.2,
            "U": 238.03,
        }
        for symbol, weight in expected.items():
            element = get_element(symbol)
            self.assertTrue(element.has_standard_atomic_weight, symbol)
            self.assertAlmostEqual(element.atomic_mass, weight, places=6, msg=symbol)

    def test_elements_without_standard_weight_use_most_stable_isotope(self) -> None:
        expected = {
            "Tc": 98,
            "Pm": 145,
            "Po": 209,
            "At": 210,
            "Rn": 222,
            "Fr": 223,
            "Ra": 226,
            "Ac": 227,
            "Np": 237,
            "Pu": 244,
            "Am": 243,
            "Cm": 247,
            "Bk": 247,
            "Cf": 251,
            "Es": 252,
            "Fm": 257,
            "Md": 258,
            "No": 259,
            "Lr": 266,
            "Rf": 267,
            "Db": 268,
            "Sg": 269,
            "Bh": 270,
            "Hs": 269,
            "Mt": 277,
            "Ds": 281,
            "Rg": 282,
            "Cn": 285,
            "Nh": 286,
            "Fl": 290,
            "Mc": 290,
            "Lv": 293,
            "Ts": 294,
            "Og": 294,
        }
        for symbol, mass_number in expected.items():
            element = get_element(symbol)
            self.assertIsNone(element.standard_atomic_weight, symbol)
            self.assertEqual(element.most_stable_isotope_mass_number, mass_number, symbol)
            self.assertEqual(element.atomic_mass, float(mass_number), symbol)

    def test_lookup_by_number_symbol_and_name(self) -> None:
        iron = get_element(26)
        self.assertEqual(iron.symbol, "Fe")
        self.assertIs(get_element("Fe"), iron)
        self.assertIs(get_element("fe"), iron)
        self.assertIs(get_element("iron"), iron)
        self.assertIs(get_element("  Iron  "), iron)
        self.assertIs(get_element("26"), iron)

    def test_name_aliases(self) -> None:
        self.assertIs(get_element("aluminum"), get_element("Al"))
        self.assertIs(get_element("aluminium"), get_element("Al"))
        self.assertIs(get_element("cesium"), get_element("Cs"))
        self.assertIs(get_element("caesium"), get_element("Cs"))
        self.assertIs(get_element("sulphur"), get_element("S"))
        self.assertIs(get_element("wolfram"), get_element("W"))

    def test_unknown_elements_raise(self) -> None:
        for key in ("Xx", "", 0, -1, 119, "not-an-element"):
            with self.subTest(key=key):
                with self.assertRaises(UnknownElementError):
                    get_element(key)
                self.assertIsNone(try_get_element(key))

    def test_symbol_is_str(self) -> None:
        self.assertEqual(str(get_element("Fe")), "Fe (Iron, Z=26)")


if __name__ == "__main__":
    unittest.main()
