#!/usr/bin/env python3
"""Deterministic, offline self-consistency audit for chemistry-engine.

The unit suite pins individual behaviours; this audit checks cross-cutting
invariants across the public API so a regression in one layer cannot hide in
another:

* periodic-table invariants;
* formula parsing, molar mass, and composition identities;
* exact balancing: positive integer coefficients, gcd 1, atom and charge
  conservation;
* stoichiometric mass conservation;
* the CLI JSON contract;
* representative error paths.

Run it directly or from the daily Chemistry audit workflow::

    python tools/audit_chemistry.py
"""
from __future__ import annotations

import json
import math
import random
import subprocess
import sys
from fractions import Fraction
from functools import reduce
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chemistry_engine import (  # noqa: E402
    ELEMENTS,
    Feed,
    balance_equation,
    elemental_analysis,
    mass_fractions,
    molar_mass,
    parse_formula,
    percent_composition,
    stoichiometry,
)
from chemistry_engine.errors import (  # noqa: E402
    FormulaParseError,
    StoichiometryError,
    UnbalanceableEquationError,
)

CHECKS = 0
FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(label)


def close_enough(left: float, right: float, tolerance: float = 1e-12) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def audit_elements() -> None:
    check(len(ELEMENTS) == 118, "periodic table has 118 elements")
    check(
        len({element.symbol for element in ELEMENTS}) == 118,
        "periodic-table symbols are unique",
    )
    check(
        len({element.atomic_number for element in ELEMENTS}) == 118,
        "periodic-table atomic numbers are unique",
    )
    for element in ELEMENTS:
        check(element.atomic_mass > 0, f"positive mass for {element.symbol}")
        if element.has_standard_atomic_weight:
            check(
                element.standard_atomic_weight is not None,
                f"standard weight present for {element.symbol}",
            )


def audit_formulas() -> None:
    corpus = [
        "H2O",
        "C6H12O6",
        "Ca(OH)2",
        "Al2(SO4)3",
        "K4[Fe(CN)6]",
        "CuSO4·5H2O",
        "CaSO4·½H2O",
        "[Cu(NH3)4]SO4",
        "Fe^3+",
        "SO4^2-",
        "NH4+",
        "SO4²⁻",
        "H₂O",
    ]
    for text in corpus:
        formula = parse_formula(text)
        check(formula.canonical_formula() != "", f"canonical formula for {text}")
        if formula.is_electron:
            continue
        mass = molar_mass(formula)
        check(mass > 0, f"positive molar mass for {text}")
        fractions = mass_fractions(formula)
        check(close_enough(sum(fractions.values()), 1.0), f"mass fractions sum for {text}")
        percentages = percent_composition(formula)
        check(close_enough(sum(percentages.values()), 100.0), f"percentages sum for {text}")
        contributions = elemental_analysis(formula)
        check(
            close_enough(sum(item.mass_g_per_mol for item in contributions), mass),
            f"elemental contributions sum to molar mass for {text}",
        )

    # Deterministic random formulas: exercising the parser and composition path
    # without any network or fixture files.
    rng = random.Random(20261112)
    symbols = ["H", "C", "N", "O", "Na", "Al", "Si", "S", "Cl", "Ca", "Fe"]
    for _ in range(30):
        parts = []
        for _ in range(rng.randint(1, 4)):
            symbol = rng.choice(symbols)
            count = rng.randint(1, 6)
            parts.append(symbol if count == 1 else f"{symbol}{count}")
        text = "".join(parts)
        formula = parse_formula(text)
        check(molar_mass(formula) > 0, f"positive molar mass for random {text}")
        check(
            close_enough(sum(mass_fractions(formula).values()), 1.0),
            f"mass fractions sum for random {text}",
        )


def audit_balancing() -> None:
    equations = [
        ("H2 + O2 -> H2O", (2, 1, 2)),
        ("Fe + O2 -> Fe2O3", (4, 3, 2)),
        ("C3H8 + O2 -> CO2 + H2O", (1, 5, 3, 4)),
        ("KMnO4 + HCl -> KCl + MnCl2 + Cl2 + H2O", (2, 16, 2, 2, 5, 8)),
        (
            "Fe^2+ + MnO4^- + H^+ -> Fe^3+ + Mn^2+ + H2O",
            (5, 1, 8, 5, 1, 4),
        ),
        ("Fe^3+ + e^- -> Fe^2+", (1, 1, 1)),
        ("P4 + O2 -> P4O10", (1, 5, 1)),
        ("CaSO4·½H2O -> CaSO4 + H2O", (2, 2, 1)),
    ]
    for text, expected in equations:
        balanced = balance_equation(text)
        coefficients = balanced.coefficients
        check(coefficients == expected, f"expected coefficients for {text}")
        check(all(isinstance(value, int) and value > 0 for value in coefficients), f"positive ints for {text}")
        common = reduce(math.gcd, coefficients)
        check(common == 1, f"primitive coefficients for {text}")
        check(
            all(item.balanced for item in balanced.element_balances),
            f"atom conservation for {text}",
        )
        check(balanced.charge_left == balanced.charge_right, f"charge conservation for {text}")

    multi = balance_equation("C + O2 -> CO + CO2")
    check(multi.is_unique is False, "multi-solution equation is flagged")
    check(all(value > 0 for value in multi.coefficients), "multi-solution coefficients are positive")
    check(
        all(item.balanced for item in multi.element_balances),
        "multi-solution atoms are conserved",
    )


def audit_stoichiometry() -> None:
    result = stoichiometry(
        "N2 + 3H2 -> 2NH3",
        [Feed("N2", 28.0, "g"), Feed("H2", 6.0, "g")],
    )
    check(result.limiting == ("H2",), "limiting reagent is H2")
    check(close_enough(result.extent, (6.0 / 2.016) / 3, tolerance=1e-9), "reaction extent")
    total_feed = 34.0
    total_products = sum(result.product_masses.values())
    total_remaining = sum(result.remaining_masses.values())
    check(
        close_enough(total_feed, total_products + total_remaining, tolerance=1e-9),
        "stoichiometric mass conservation",
    )

    hydrate = stoichiometry(
        "CuSO4·5H2O -> CuSO4 + 5H2O",
        [Feed("CuSO4·5H2O", 1.0, "mol")],
    )
    check(close_enough(hydrate.extent, 1.0), "hydrate extent")
    check(close_enough(hydrate.produced["H2O"], 5.0), "hydrate produces 5 H2O")
    total = sum(hydrate.product_masses.values())
    check(close_enough(total, molar_mass("CuSO4·5H2O"), tolerance=1e-9), "hydrate mass conservation")


def audit_cli() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "chemistry_engine", "mass", "--json", "H2O"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    check(completed.returncode == 0, "CLI mass --json exit code")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        check(False, "CLI mass --json emits JSON")
        return
    check(
        isinstance(payload, list) and payload and close_enough(payload[0]["molar_mass_g_per_mol"], 18.015),
        "CLI mass --json value",
    )


def audit_errors() -> None:
    try:
        parse_formula("Xx2")
    except FormulaParseError:
        check(True, "invalid element raises FormulaParseError")
    else:
        check(False, "invalid element raises FormulaParseError")

    try:
        balance_equation("H2 -> O2")
    except UnbalanceableEquationError:
        check(True, "impossible equation raises UnbalanceableEquationError")
    else:
        check(False, "impossible equation raises UnbalanceableEquationError")

    try:
        stoichiometry("N2 + 3H2 -> 2NH3", [Feed("N2", 1.0, "mol")])
    except StoichiometryError:
        check(True, "missing reactant feed raises StoichiometryError")
    else:
        check(False, "missing reactant feed raises StoichiometryError")


def main() -> int:
    audit_elements()
    audit_formulas()
    audit_balancing()
    audit_stoichiometry()
    audit_cli()
    audit_errors()

    if FAILURES:
        print(f"chemistry audit FAILED ({len(FAILURES)} of {CHECKS} checks)")
        for failure in FAILURES:
            print(f" - {failure}")
        return 1
    print(f"chemistry audit OK: {CHECKS} invariant checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
