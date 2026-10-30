"""Tests for stoichiometry."""
from __future__ import annotations

import unittest

from chemistry_engine import Feed, stoichiometry
from chemistry_engine.errors import StoichiometryError


class LimitingReagentTests(unittest.TestCase):
    def test_ammonia_with_excess_nitrogen(self) -> None:
        result = stoichiometry(
            "N2 + 3H2 -> 2NH3",
            [Feed("N2", 1, "mol"), Feed("H2", 2, "mol")],
        )
        self.assertEqual(result.limiting, ("H2",))
        self.assertEqual(result.limiting_reagent, "H2")
        self.assertAlmostEqual(result.extent, 2 / 3, places=12)
        self.assertAlmostEqual(result.consumed["N2"], 2 / 3, places=12)
        self.assertAlmostEqual(result.consumed["H2"], 2.0, places=12)
        self.assertAlmostEqual(result.remaining["N2"], 1 / 3, places=12)
        self.assertAlmostEqual(result.remaining["H2"], 0.0, places=12)
        self.assertAlmostEqual(result.produced["NH3"], 4 / 3, places=12)
        self.assertAlmostEqual(result.product_masses["NH3"], (4 / 3) * 17.031, places=6)

    def test_stoichiometric_ratio_gives_a_tie(self) -> None:
        result = stoichiometry(
            "N2 + 3H2 -> 2NH3",
            [Feed("N2", 1, "mol"), Feed("H2", 3, "mol")],
        )
        self.assertEqual(result.limiting, ("N2", "H2"))
        self.assertIsNone(result.limiting_reagent)
        self.assertAlmostEqual(result.extent, 1.0, places=12)
        self.assertAlmostEqual(result.produced["NH3"], 2.0, places=12)

    def test_mass_feeds_are_converted(self) -> None:
        result = stoichiometry(
            "N2 + 3H2 -> 2NH3",
            [Feed("N2", 28.0, "g"), Feed("H2", 6.0, "g")],
        )
        self.assertEqual(result.limiting, ("H2",))
        self.assertAlmostEqual(result.feed_moles["N2"], 28.0 / 28.014, places=9)
        self.assertAlmostEqual(result.feed_moles["H2"], 6.0 / 2.016, places=9)
        self.assertAlmostEqual(result.product_masses["NH3"], 33.7917, places=3)

    def test_zero_feed(self) -> None:
        result = stoichiometry(
            "H2 + O2 -> H2O",
            [Feed("H2", 0, "mol"), Feed("O2", 5, "mol")],
        )
        self.assertAlmostEqual(result.extent, 0.0)
        self.assertIn("H2", result.limiting)
        self.assertAlmostEqual(result.produced["H2O"], 0.0)

    def test_feed_matches_by_composition_not_spelling(self) -> None:
        result = stoichiometry(
            "CH4 + 2O2 -> CO2 + 2H2O",
            [Feed("H4C", 1, "mol"), Feed("O2", 2, "mol")],
        )
        self.assertEqual(result.limiting, ("CH4", "O2"))
        self.assertAlmostEqual(result.produced["CO2"], 1.0, places=12)

    def test_hydrate_equation(self) -> None:
        result = stoichiometry(
            "CuSO4·5H2O -> CuSO4 + 5H2O",
            [Feed("CuSO4·5H2O", 1, "mol")],
        )
        self.assertAlmostEqual(result.produced["CuSO4"], 1.0, places=12)
        self.assertAlmostEqual(result.produced["H2O"], 5.0, places=12)
        self.assertAlmostEqual(result.product_masses["H2O"], 5 * 18.015, places=6)


class FeedValidationTests(unittest.TestCase):
    def test_missing_reactant_feed(self) -> None:
        with self.assertRaises(StoichiometryError):
            stoichiometry("N2 + 3H2 -> 2NH3", [Feed("N2", 1, "mol")])

    def test_feeding_a_product_is_rejected(self) -> None:
        with self.assertRaises(StoichiometryError):
            stoichiometry("H2 + O2 -> H2O", [Feed("H2O", 1, "mol")])

    def test_species_not_in_equation(self) -> None:
        with self.assertRaises(StoichiometryError):
            stoichiometry("H2 + O2 -> H2O", [Feed("H2", 1), Feed("O2", 1), Feed("N2", 1)])

    def test_negative_amount(self) -> None:
        with self.assertRaises(StoichiometryError):
            stoichiometry("H2 + O2 -> H2O", [Feed("H2", -1), Feed("O2", 1)])

    def test_unknown_unit(self) -> None:
        with self.assertRaises(StoichiometryError):
            stoichiometry("H2 + O2 -> H2O", [Feed("H2", 1, "pounds"), Feed("O2", 1)])

    def test_duplicate_feed(self) -> None:
        with self.assertRaises(StoichiometryError):
            stoichiometry(
                "H2 + O2 -> H2O",
                [Feed("H2", 1), Feed("H2", 2), Feed("O2", 1)],
            )

    def test_empty_feed_list(self) -> None:
        with self.assertRaises(StoichiometryError):
            stoichiometry("H2 + O2 -> H2O", [])


if __name__ == "__main__":
    unittest.main()
