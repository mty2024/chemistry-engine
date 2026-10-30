"""Stoichiometry: limiting reagent, consumption, excess, and product amounts."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .balance import BalancedEquation, balance_equation
from .errors import StoichiometryError
from .formula import Formula, parse_formula
from .properties import molar_mass

_MASS_UNITS = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1e3,
    "mg": 1e-3,
    "ug": 1e-6,
    "µg": 1e-6,
    "μg": 1e-6,
}
_MOLE_UNITS = {
    "mol": 1.0,
    "mole": 1.0,
    "moles": 1.0,
    "mmol": 1e-3,
    "umol": 1e-6,
    "µmol": 1e-6,
    "μmol": 1e-6,
}


@dataclass(frozen=True, slots=True)
class Feed:
    """An amount of one reactant, in moles or in mass."""

    species: str
    amount: float
    unit: str = "mol"


@dataclass(frozen=True, slots=True)
class StoichiometryResult:
    """The full answer for a set of reactant feeds."""

    equation: BalancedEquation
    extent: float
    limiting: tuple[str, ...]
    feed_moles: dict[str, float]
    consumed: dict[str, float]
    remaining: dict[str, float]
    produced: dict[str, float]
    product_masses: dict[str, float]
    remaining_masses: dict[str, float]

    @property
    def limiting_reagent(self) -> str | None:
        """The limiting reagent's formula text (``None`` for a perfect tie)."""
        return self.limiting[0] if len(self.limiting) == 1 else None


def _to_moles(feed: Feed, formula: Formula) -> float:
    if not math.isfinite(feed.amount):
        raise StoichiometryError(f"amount must be finite, got {feed.amount!r}")
    if feed.amount < 0:
        raise StoichiometryError(f"amount must be non-negative, got {feed.amount!r}")
    unit = feed.unit.strip().lower()
    if unit in _MOLE_UNITS:
        return feed.amount * _MOLE_UNITS[unit]
    if unit in _MASS_UNITS:
        return feed.amount * _MASS_UNITS[unit] / molar_mass(formula)
    raise StoichiometryError(
        f"unknown unit {feed.unit!r}; use mol, mmol, umol, g, kg, mg, or ug"
    )


def stoichiometry(
    equation: str | BalancedEquation,
    feeds: list[Feed] | tuple[Feed, ...],
    *,
    tolerance: float = 1e-9,
) -> StoichiometryResult:
    """Compute the limiting reagent and the amounts consumed/produced.

    Every reactant in the equation must be fed; feeding a product is rejected.
    ``extent`` is the reaction extent in moles (mol of reaction as written).
    """
    balanced = balance_equation(equation) if isinstance(equation, str) else equation
    if not feeds:
        raise StoichiometryError("at least one reactant feed is required")

    reactant_by_key = {
        species.formula.composition_key(): species
        for species in balanced.reactants
    }
    product_keys = {
        species.formula.composition_key(): species for species in balanced.products
    }

    feed_moles: dict[str, float] = {}
    feed_formulas: dict[str, Formula] = {}
    for feed in feeds:
        formula = parse_formula(feed.species)
        key = formula.composition_key()
        reactant = reactant_by_key.get(key)
        if reactant is None:
            if key in product_keys:
                raise StoichiometryError(
                    f"{feed.species!r} is a product, not a reactant"
                )
            raise StoichiometryError(
                f"{feed.species!r} does not appear in this equation"
            )
        label = reactant.formula.text
        if label in feed_moles:
            raise StoichiometryError(f"duplicate feed for reactant {label!r}")
        feed_formulas[label] = formula
        feed_moles[label] = _to_moles(feed, formula)

    missing = [
        species.formula.text
        for species in balanced.reactants
        if species.formula.text not in feed_moles
    ]
    if missing:
        raise StoichiometryError(
            "missing feed for reactant(s): " + ", ".join(missing)
        )

    extents = {
        species.formula.text: feed_moles[species.formula.text] / species.coefficient
        for species in balanced.reactants
    }
    minimum = min(extents.values())
    limiting = tuple(
        species.formula.text
        for species in balanced.reactants
        if math.isclose(
            extents[species.formula.text],
            minimum,
            rel_tol=tolerance,
            abs_tol=tolerance * max(1.0, abs(minimum)),
        )
    )

    consumed = {
        species.formula.text: species.coefficient * minimum
        for species in balanced.reactants
    }
    remaining = {
        label: max(0.0, feed_moles[label] - consumed[label])
        for label in feed_moles
    }
    produced = {
        species.formula.text: species.coefficient * minimum
        for species in balanced.products
    }
    product_masses = {
        species.formula.text: produced[species.formula.text]
        * molar_mass(species.formula)
        for species in balanced.products
    }
    remaining_masses = {
        label: remaining[label] * molar_mass(feed_formulas[label])
        for label in remaining
    }

    return StoichiometryResult(
        equation=balanced,
        extent=minimum,
        limiting=limiting,
        feed_moles=feed_moles,
        consumed=consumed,
        remaining=remaining,
        produced=produced,
        product_masses=product_masses,
        remaining_masses=remaining_masses,
    )
