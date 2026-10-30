"""Periodic table access: :class:`Element`, lookups, and the canonical table.

The data lives in :mod:`chemistry_engine.elements_data` (generated from CIAAW/IUPAC
tables; see ``tools/update_periodic_table.py``).  This module adds behaviour and
lookup helpers, including tolerant name lookup and the IUPAC/ACS spelling
aliases (aluminium/aluminum, caesium/cesium, sulfur/sulphur).

Elements without a standard atomic weight (Tc, Pm, and everything heavier than
uranium except Th/Pa/U) expose the mass number of their longest-lived known
isotope; that value is what :attr:`Element.atomic_mass` uses for calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .elements_data import ELEMENTS as _RAW_ELEMENTS
from .errors import UnknownElementError


@dataclass(frozen=True, slots=True)
class Element:
    """One entry of the periodic table."""

    atomic_number: int
    symbol: str
    name: str
    standard_atomic_weight: float | None
    most_stable_isotope_mass_number: int | None

    @property
    def atomic_mass(self) -> float:
        """Mass in g/mol used for stoichiometric calculations.

        This is the abridged IUPAC standard atomic weight where one exists, and
        the mass number of the longest-lived known isotope otherwise.
        """
        if self.standard_atomic_weight is not None:
            return self.standard_atomic_weight
        if self.most_stable_isotope_mass_number is not None:
            return float(self.most_stable_isotope_mass_number)
        raise ValueError(f"no mass available for element {self.symbol}")

    @property
    def has_standard_atomic_weight(self) -> bool:
        return self.standard_atomic_weight is not None

    def __str__(self) -> str:
        return f"{self.symbol} ({self.name}, Z={self.atomic_number})"


ELEMENTS: Final[tuple[Element, ...]] = tuple(Element(*row) for row in _RAW_ELEMENTS)
ELEMENTS_BY_SYMBOL: Final[dict[str, Element]] = {e.symbol: e for e in ELEMENTS}
ELEMENTS_BY_NUMBER: Final[dict[int, Element]] = {e.atomic_number: e for e in ELEMENTS}
ELEMENTS_BY_NAME: Final[dict[str, Element]] = {e.name.lower(): e for e in ELEMENTS}

# Common alternative spellings -> canonical symbol.
_SYMBOL_ALIASES: Final[dict[str, str]] = {
    "aluminum": "Al",
    "aluminium": "Al",
    "cesium": "Cs",
    "caesium": "Cs",
    "sulphur": "S",
    "sulfur": "S",
    "wolfram": "W",
    "tungsten": "W",
}


def get_element(key: int | str) -> Element:
    """Resolve an element by atomic number, symbol, or English name.

    Lookup is case-insensitive for symbols and names (formula parsing is not —
    formulas are case-sensitive by design).  ``ValueError``/``UnknownElementError``
    is raised when nothing matches.
    """
    if isinstance(key, bool):
        raise UnknownElementError(key)
    if isinstance(key, int):
        element = ELEMENTS_BY_NUMBER.get(key)
        if element is None:
            raise UnknownElementError(key)
        return element
    text = str(key).strip()
    if not text:
        raise UnknownElementError(key)
    if text.isascii() and text.isdigit():
        return get_element(int(text))
    symbol = ELEMENTS_BY_SYMBOL.get(text)
    if symbol is not None:
        return symbol
    lowered = text.lower()
    for candidate in ELEMENTS:
        if candidate.symbol.lower() == lowered:
            return candidate
    element = ELEMENTS_BY_NAME.get(lowered)
    if element is not None:
        return element
    alias = _SYMBOL_ALIASES.get(lowered)
    if alias is not None:
        return ELEMENTS_BY_SYMBOL[alias]
    raise UnknownElementError(key)


def try_get_element(key: int | str) -> Element | None:
    """Like :func:`get_element`, but return ``None`` instead of raising."""
    try:
        return get_element(key)
    except UnknownElementError:
        return None


def is_element_symbol(text: str) -> bool:
    """True when ``text`` is exactly a valid, case-sensitive element symbol."""
    return text in ELEMENTS_BY_SYMBOL
