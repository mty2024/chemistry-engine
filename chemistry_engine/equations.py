"""Parsing of chemical equations into reactants and products.

The parser accepts the usual arrow spellings (``->``, ``→``, ``⟶``, ``=>``,
``=``) and the reversible arrows (``⇌``, ``↔``, ``<=>``, ``<->``).  Species are
separated by ``+``; a leading integer is kept as the *written* coefficient, but
balancing ignores it and re-derives the stoichiometry.

Ionic species need an explicit charge so that ``+`` is unambiguous as a
separator: write ``Na^+ + Cl^- -> NaCl`` (or put spaces around the separator).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import EquationParseError
from .formula import Formula, parse_formula

_ARROW_REPLACEMENTS = (
    ("⟶", "->"),
    ("⟹", "->"),
    ("→", "->"),
    ("⇌", "->"),
    ("↔", "->"),
    ("<=>", "->"),
    ("<->", "->"),
)
_SPECIES_COEFFICIENT_RE = re.compile(r"^\s*(\d+)\s*(.*)$", re.S)


@dataclass(frozen=True, slots=True)
class Species:
    """One formula together with the coefficient written in the input."""

    formula: Formula
    coefficient: int | None = None

    @property
    def text(self) -> str:
        return self.formula.text


@dataclass(frozen=True, slots=True)
class Equation:
    """A parsed, not necessarily balanced, equation."""

    reactants: tuple[Species, ...]
    products: tuple[Species, ...]
    text: str
    reversible: bool = False

    def all_species(self) -> tuple[Species, ...]:
        return self.reactants + self.products


def _normalize_arrows(text: str) -> tuple[str, bool]:
    normalized = text
    reversible = False
    for token in ("⇌", "↔", "<=>", "<->"):
        if token in normalized:
            reversible = True
        normalized = normalized.replace(token, "->")
    for token, replacement in _ARROW_REPLACEMENTS:
        normalized = normalized.replace(token, replacement)
    normalized = re.sub(r"-+>", "->", normalized)
    normalized = re.sub(r"=+>", "->", normalized)
    return normalized, reversible


def _starts_species(text: str, index: int) -> bool:
    """Heuristic used to tell a '+' separator from a '+' charge suffix."""
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text):
        return False
    character = text[index]
    if character.isupper() or character.isdigit() or character in "([{":
        return True
    if character == "e" and index + 1 < len(text) and text[index + 1] in "^-":
        return True
    return False


def _split_species(side: str, side_name: str, equation: str) -> list[str]:
    depth = 0
    start = 0
    parts: list[str] = []
    for index, character in enumerate(side):
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
            if depth < 0:
                raise EquationParseError(
                    equation, f"unbalanced brackets on the {side_name} side"
                )
        elif character == "+" and depth == 0 and _starts_species(side, index + 1):
            parts.append(side[start:index])
            start = index + 1
    if depth != 0:
        raise EquationParseError(
            equation, f"unbalanced brackets on the {side_name} side"
        )
    parts.append(side[start:])
    return [part.strip() for part in parts]


def _parse_species(raw: str, equation: str) -> Species:
    if not raw:
        raise EquationParseError(equation, "empty species between '+' separators")
    match = _SPECIES_COEFFICIENT_RE.match(raw)
    if match is None:
        return Species(parse_formula(raw), None)
    coefficient = int(match.group(1))
    if coefficient <= 0:
        raise EquationParseError(equation, f"coefficient must be positive in {raw!r}")
    formula_text = match.group(2).strip()
    if not formula_text:
        raise EquationParseError(equation, f"missing formula after coefficient in {raw!r}")
    return Species(parse_formula(formula_text), coefficient)


def _split_arrow(text: str, equation: str) -> tuple[str, str, bool]:
    normalized, reversible = _normalize_arrows(text)
    if normalized.count("->") == 1:
        left, right = normalized.split("->")
        return left, right, reversible
    if normalized.count("->") > 1:
        raise EquationParseError(equation, "more than one reaction arrow")
    if normalized.count("=") == 1:
        left, right = normalized.split("=")
        return left, right, reversible
    raise EquationParseError(
        equation, "missing reaction arrow (use '->' or '=')"
    )


def parse_equation(equation: str) -> Equation:
    """Parse ``equation`` into reactants, products, and flags."""
    if not isinstance(equation, str):
        raise TypeError(f"equation must be a string, got {type(equation).__name__}")
    if not equation.strip():
        raise EquationParseError(equation, "empty equation")
    left, right, reversible = _split_arrow(equation, equation)
    if not left.strip():
        raise EquationParseError(equation, "missing reactants")
    if not right.strip():
        raise EquationParseError(equation, "missing products")
    reactants = tuple(
        _parse_species(part, equation) for part in _split_species(left, "reactant", equation)
    )
    products = tuple(
        _parse_species(part, equation) for part in _split_species(right, "product", equation)
    )
    _reject_duplicates(reactants, equation, "reactant")
    _reject_duplicates(products, equation, "product")
    return Equation(
        reactants=reactants,
        products=products,
        text=equation.strip(),
        reversible=reversible,
    )


def _reject_duplicates(
    species: tuple[Species, ...], equation: str, side_name: str
) -> None:
    seen: set[tuple[tuple[tuple[str, object], ...], int]] = set()
    for item in species:
        key = item.formula.composition_key()
        if key in seen:
            raise EquationParseError(
                equation,
                f"duplicate species {item.text!r} on the {side_name} side; "
                "combine the coefficients",
            )
        seen.add(key)
