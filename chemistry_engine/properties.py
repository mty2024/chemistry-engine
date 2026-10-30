"""Molar mass and elemental composition calculations."""
from __future__ import annotations

from dataclasses import dataclass

from .elements import Element, get_element
from .errors import ChemError
from .formula import Formula, parse_formula

#: Molar mass of the electron in g/mol (used only for ``e^-`` species).
ELECTRON_MOLAR_MASS_G = 5.48579909065e-4


@dataclass(frozen=True, slots=True)
class ElementContribution:
    """One element's share of a formula's mass."""

    element: Element
    count: float
    mass_g_per_mol: float
    mass_fraction: float

    @property
    def percent(self) -> float:
        return self.mass_fraction * 100.0


def _as_formula(formula: str | Formula) -> Formula:
    return parse_formula(formula)


def molar_mass(formula: str | Formula) -> float:
    """Molar mass in g/mol, using the abridged IUPAC atomic weights."""
    parsed = _as_formula(formula)
    if parsed.is_electron:
        return ELECTRON_MOLAR_MASS_G
    total = 0.0
    for symbol, count in parsed.atom_counts.items():
        total += float(count) * get_element(symbol).atomic_mass
    return total


def elemental_analysis(formula: str | Formula) -> tuple[ElementContribution, ...]:
    """Per-element atom counts, masses, and mass fractions, in Hill order."""
    parsed = _as_formula(formula)
    if parsed.is_electron:
        return ()
    total = molar_mass(parsed)
    contributions: list[ElementContribution] = []
    for symbol in parsed.hill_order():
        count = parsed.atom_counts[symbol]
        mass = float(count) * get_element(symbol).atomic_mass
        contributions.append(
            ElementContribution(
                element=get_element(symbol),
                count=float(count),
                mass_g_per_mol=mass,
                mass_fraction=(mass / total) if total else 0.0,
            )
        )
    return tuple(contributions)


def mass_fractions(formula: str | Formula) -> dict[str, float]:
    """Mass fraction of each element (values sum to 1)."""
    return {c.element.symbol: c.mass_fraction for c in elemental_analysis(formula)}


def percent_composition(formula: str | Formula) -> dict[str, float]:
    """Mass percentage of each element (values sum to 100)."""
    return {c.element.symbol: c.percent for c in elemental_analysis(formula)}


def moles_from_mass(formula: str | Formula, mass_g: float) -> float:
    """Convert a mass in grams to moles."""
    if mass_g < 0:
        raise ChemError(f"mass must be non-negative, got {mass_g!r}")
    parsed = _as_formula(formula)
    denominator = molar_mass(parsed)
    if denominator <= 0:
        raise ChemError("cannot convert mass to moles for a massless species")
    return mass_g / denominator


def mass_from_moles(formula: str | Formula, moles: float) -> float:
    """Convert moles to grams."""
    if moles < 0:
        raise ChemError(f"amount must be non-negative, got {moles!r}")
    return moles * molar_mass(formula)
