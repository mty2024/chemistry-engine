"""Independent verification of chemistry-engine's chemistry (run ad hoc, not shipped)."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import urllib.request
from fractions import Fraction

from chemistry_engine import balance_equation, get_element, molar_mass, parse_formula, stoichiometry, Feed, ELEMENTS

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


# ---------------------------------------------------------------------------
# 1. Cross-check atomic masses against an independent data source (PubChem).
# ---------------------------------------------------------------------------
path = os.path.join(tempfile.gettempdir(), "pubchem_periodic.json")
if not os.path.exists(path):
    request = urllib.request.Request(
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/periodictable/JSON",
        headers={"User-Agent": "chemistry-engine-verify/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        open(path, "wb").write(response.read())

pubchem = json.load(open(path, encoding="utf-8"))
rows = pubchem["Table"]["Row"]
reference = {
    row["Cell"][1]: float(row["Cell"][3])
    for row in rows
}
max_deviation = 0.0
for element in ELEMENTS:
    pub_value = reference.get(element.symbol)
    if pub_value is None:
        continue
    deviation = abs(element.atomic_mass - pub_value) / pub_value
    max_deviation = max(max_deviation, deviation)
    if deviation > 0.02:
        failures.append(
            f"atomic mass mismatch for {element.symbol}: chemistry-engine={element.atomic_mass}, pubchem={pub_value}"
        )
print(f"atomic-mass cross-check vs PubChem: max relative deviation {max_deviation:.4%}")

# ---------------------------------------------------------------------------
# 2. Re-balance a battery of textbook equations and verify conservation from
#    the composition data, independently of the solver's own checks.
# ---------------------------------------------------------------------------
equations = [
    "H2 + O2 -> H2O",
    "Na + Cl2 -> NaCl",
    "Fe + O2 -> Fe2O3",
    "CH4 + O2 -> CO2 + H2O",
    "C3H8 + O2 -> CO2 + H2O",
    "C2H5OH + O2 -> CO2 + H2O",
    "KClO3 -> KCl + O2",
    "H2O2 -> H2O + O2",
    "KMnO4 + HCl -> KCl + MnCl2 + Cl2 + H2O",
    "Cu + HNO3 -> Cu(NO3)2 + NO + H2O",
    "Fe^2+ + MnO4^- + H^+ -> Fe^3+ + Mn^2+ + H2O",
    "Al + Fe2O3 -> Al2O3 + Fe",
    "Zn + HCl -> ZnCl2 + H2",
    "CaCO3 -> CaO + CO2",
    "NH3 + O2 -> NO + H2O",
    "CuSO4·5H2O -> CuSO4 + H2O",
    "N2 + H2 -> NH3",
    "P4 + O2 -> P4O10",
    "CaSO4·½H2O -> CaSO4 + H2O",
]

for text in equations:
    balanced = balance_equation(text)
    coefficients = balanced.coefficients
    check(all(isinstance(c, int) and c > 0 for c in coefficients), f"non-positive coefficient in {text}")
    common = 0
    for c in coefficients:
        common = c if common == 0 else math.gcd(common, c)
    check(common == 1, f"coefficients share a common factor in {text}: {coefficients}")

    left: dict[str, Fraction] = {}
    right: dict[str, Fraction] = {}
    left_charge = right_charge = 0
    for species in balanced.reactants:
        for symbol, count in species.formula.atom_counts.items():
            left[symbol] = left.get(symbol, Fraction(0)) + count * species.coefficient
        left_charge += species.formula.charge * species.coefficient
    for species in balanced.products:
        for symbol, count in species.formula.atom_counts.items():
            right[symbol] = right.get(symbol, Fraction(0)) + count * species.coefficient
        right_charge += species.formula.charge * species.coefficient
    check(left == right, f"atoms not conserved in {text}: {left} vs {right}")
    check(left_charge == right_charge, f"charge not conserved in {text}")
print(f"balanced {len(equations)} equations; all conserved and minimal")

# ---------------------------------------------------------------------------
# 3. Independent mass-conservation check for stoichiometry (mass feeds).
# ---------------------------------------------------------------------------
cases = [
    ("N2 + 3H2 -> 2NH3", [Feed("N2", 28, "g"), Feed("H2", 6, "g")]),
    ("CH4 + 2O2 -> CO2 + 2H2O", [Feed("CH4", 16, "g"), Feed("O2", 64, "g")]),
    ("2H2 + O2 -> 2H2O", [Feed("H2", 4, "g"), Feed("O2", 32, "g")]),
]
for text, feeds in cases:
    result = stoichiometry(text, feeds)
    feed_mass = sum(feed.amount for feed in feeds)
    product_mass = sum(result.product_masses.values())
    remaining_mass = sum(result.remaining_masses.values())
    relative = abs(feed_mass - product_mass - remaining_mass) / feed_mass
    check(relative < 1e-9, f"mass not conserved for {text}: {relative}")
    for amount in list(result.consumed.values()) + list(result.remaining.values()):
        check(amount >= -1e-12, f"negative amount for {text}")
    for amount in result.produced.values():
        check(amount >= -1e-12, f"negative product for {text}")
print(f"stoichiometry mass conservation checked on {len(cases)} feeds")

# ---------------------------------------------------------------------------
# 4. Known molar masses independent of the implementation's arithmetic order.
# ---------------------------------------------------------------------------
expected_masses = {
    "H2O": 18.015,
    "CO2": 44.009,
    "NH3": 17.031,
    "C6H12O6": 180.156,
    "NaCl": 58.44,
    "CaCO3": 100.086,
    "H2SO4": 98.076,
    "NaOH": 39.997,
    "CuSO4·5H2O": 249.677,
}
for formula, expected in expected_masses.items():
    actual = molar_mass(formula)
    check(abs(actual - expected) < 0.02, f"molar mass {formula}: {actual} != {expected}")
print(f"checked {len(expected_masses)} reference molar masses")

print()
if failures:
    print(f"FAILURES ({len(failures)}):")
    for item in failures:
        print(" -", item)
    sys.exit(1)
print("ALL INDEPENDENT CHECKS PASSED")
