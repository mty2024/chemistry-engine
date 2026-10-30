"""chemistry-engine — a real chemistry engine for formulas, equations, and stoichiometry.

Public API
----------
::

    from chemistry_engine import parse_formula, molar_mass, percent_composition
    from chemistry_engine import balance_equation, stoichiometry, Feed

    parse_formula("CuSO4·5H2O")
    molar_mass("C6H12O6")                 # 180.156 g/mol
    balance_equation("Fe + O2 -> Fe2O3").formula
    stoichiometry("N2 + 3H2 -> 2NH3", [Feed("N2", 1, "mol"), Feed("H2", 2, "mol")])
"""
from __future__ import annotations

from .balance import BalancedEquation, BalancedSpecies, ElementBalance, balance_equation
from .elements import ELEMENTS, Element, get_element, try_get_element
from .equations import Equation, Species, parse_equation
from .errors import (
    ChemError,
    EquationParseError,
    FormulaParseError,
    StoichiometryError,
    UnbalanceableEquationError,
    UnknownElementError,
)
from .formula import Formula, parse_formula
from .properties import (
    ELECTRON_MOLAR_MASS_G,
    ElementContribution,
    elemental_analysis,
    mass_fractions,
    molar_mass,
    moles_from_mass,
    mass_from_moles,
    percent_composition,
)
from .stoichiometry import Feed, StoichiometryResult, stoichiometry

__version__ = "0.1.0"

__all__ = [
    "ELEMENTS",
    "ELECTRON_MOLAR_MASS_G",
    "BalancedEquation",
    "BalancedSpecies",
    "ChemError",
    "Element",
    "ElementBalance",
    "ElementContribution",
    "Equation",
    "EquationParseError",
    "Feed",
    "Formula",
    "FormulaParseError",
    "Species",
    "StoichiometryError",
    "StoichiometryResult",
    "UnbalanceableEquationError",
    "UnknownElementError",
    "__version__",
    "balance_equation",
    "elemental_analysis",
    "get_element",
    "mass_fractions",
    "mass_from_moles",
    "molar_mass",
    "moles_from_mass",
    "parse_equation",
    "parse_formula",
    "percent_composition",
    "stoichiometry",
    "try_get_element",
]
