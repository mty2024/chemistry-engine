"""Exact balancing of chemical equations.

The balance is solved over the rationals: build one row per element (plus a
charge row when ions are present), find the null space, and choose the smallest
strictly positive integer solution.  This makes coefficients exact — no
floating-point guessing — and works for ionic/redox equations too.

Most textbook equations have a one-dimensional solution space.  A few (e.g.
``C + O2 -> CO + CO2``) genuinely have several independent balances; in that
case the engine returns a smallest valid solution and sets ``is_unique=False``.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from math import gcd, lcm

from .elements import get_element
from .equations import Equation, Species, parse_equation
from .errors import UnbalanceableEquationError
from .formula import Formula

_MAX_BASIS_DIMENSION = 5
_SEARCH_BOUND = 6


@dataclass(frozen=True, slots=True)
class ElementBalance:
    """Conservation check for one element (or the net charge)."""

    symbol: str
    left: Fraction
    right: Fraction

    @property
    def balanced(self) -> bool:
        return self.left == self.right


@dataclass(frozen=True, slots=True)
class BalancedSpecies:
    """A species with its final, balanced coefficient."""

    formula: Formula
    coefficient: int
    side: str

    @property
    def text(self) -> str:
        return self.formula.text

    def term(self) -> str:
        prefix = "" if self.coefficient == 1 else str(self.coefficient)
        return prefix + self.formula.text


@dataclass(frozen=True, slots=True)
class BalancedEquation:
    """A balanced equation plus its conservation checks."""

    reactants: tuple[BalancedSpecies, ...]
    products: tuple[BalancedSpecies, ...]
    element_balances: tuple[ElementBalance, ...]
    charge_left: int
    charge_right: int
    is_unique: bool
    reversible: bool = False
    source: str = ""

    @property
    def formula(self) -> str:
        arrow = "⇌" if self.reversible else "->"
        left = " + ".join(species.term() for species in self.reactants)
        right = " + ".join(species.term() for species in self.products)
        return f"{left} {arrow} {right}"

    @property
    def coefficients(self) -> tuple[int, ...]:
        return tuple(
            species.coefficient
            for species in self.reactants + self.products
        )

    def __str__(self) -> str:
        return self.formula


def _rref(rows: list[list[Fraction]], columns: int) -> tuple[list[list[Fraction]], list[int]]:
    matrix = [[Fraction(value) for value in row] for row in rows]
    pivots: list[int] = []
    pivot_row = 0
    for column in range(columns):
        pivot = None
        for row in range(pivot_row, len(matrix)):
            if matrix[row][column] != 0:
                pivot = row
                break
        if pivot is None:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        pivot_value = matrix[pivot_row][column]
        matrix[pivot_row] = [value / pivot_value for value in matrix[pivot_row]]
        for row in range(len(matrix)):
            if row != pivot_row and matrix[row][column] != 0:
                factor = matrix[row][column]
                matrix[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(matrix[row], matrix[pivot_row])
                ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    return matrix, pivots


def _nullspace(rows: list[list[Fraction]], columns: int) -> list[list[Fraction]]:
    reduced, pivots = _rref(rows, columns)
    pivot_columns = set(pivots)
    free_columns = [column for column in range(columns) if column not in pivot_columns]
    basis: list[list[Fraction]] = []
    for free_column in free_columns:
        vector = [Fraction(0) for _ in range(columns)]
        vector[free_column] = Fraction(1)
        for row_index, pivot_column in enumerate(pivots):
            vector[pivot_column] = -reduced[row_index][free_column]
        basis.append(vector)
    return basis


def _primitive_integer(vector: list[Fraction]) -> list[int]:
    denominator = reduce(lcm, (value.denominator for value in vector), 1)
    integers = [int(value * denominator) for value in vector]
    divisor = reduce(gcd, (abs(value) for value in integers if value), 0)
    integers = [value // divisor for value in integers]
    for value in integers:
        if value:
            if value < 0:
                integers = [-item for item in integers]
            break
    return integers


def _positive_solution(
    basis: list[list[Fraction]], columns: int, equation_text: str
) -> tuple[list[int] | None, bool]:
    vectors = [_primitive_integer(vector) for vector in basis]
    if len(vectors) == 1:
        vector = vectors[0]
        if all(value > 0 for value in vector):
            return vector, True
        if all(value < 0 for value in vector):
            return [-value for value in vector], True
        return None, True
    if len(vectors) > _MAX_BASIS_DIMENSION:
        raise UnbalanceableEquationError(
            equation_text,
            f"the equation has {len(vectors)} independent balance solutions; "
            "it is too under-determined to solve reliably",
        )
    best: tuple[int, tuple[int, ...]] | None = None
    for combination in itertools.product(
        range(-_SEARCH_BOUND, _SEARCH_BOUND + 1), repeat=len(vectors)
    ):
        if not any(combination):
            continue
        candidate = [0] * columns
        for factor, vector in zip(combination, vectors):
            if factor:
                candidate = [
                    left + factor * right
                    for left, right in zip(candidate, vector)
                ]
        if any(value <= 0 for value in candidate):
            continue
        divisor = reduce(gcd, candidate)
        candidate = [value // divisor for value in candidate]
        score = (sum(candidate), tuple(candidate))
        if best is None or score < best:
            best = score
    if best is None:
        return None, False
    return list(best[1]), False


def _build_system(
    reactants: tuple[Species, ...], products: tuple[Species, ...]
) -> tuple[list[list[Fraction]], list[str]]:
    species = reactants + products
    symbols = sorted(
        {
            symbol
            for item in species
            for symbol in item.formula.atom_counts
        },
        key=lambda symbol: get_element(symbol).atomic_number,
    )
    rows: list[list[Fraction]] = []
    for symbol in symbols:
        row = [
            item.formula.count(symbol) for item in reactants
        ] + [
            -item.formula.count(symbol) for item in products
        ]
        if any(value != 0 for value in row):
            rows.append(row)
    if any(item.formula.charge for item in species):
        rows.append(
            [Fraction(item.formula.charge) for item in reactants]
            + [-Fraction(item.formula.charge) for item in products]
        )
    return rows, symbols


def balance_equation(equation: str | Equation) -> BalancedEquation:
    """Balance ``equation`` and return the smallest positive integer solution."""
    parsed = parse_equation(equation) if isinstance(equation, str) else equation
    equation_text = parsed.text
    reactants = parsed.reactants
    products = parsed.products
    columns = len(reactants) + len(products)

    rows, _symbols = _build_system(reactants, products)
    if not rows:
        raise UnbalanceableEquationError(
            equation_text, "the equation contains no atoms or charge to conserve"
        )
    basis = _nullspace(rows, columns)
    if not basis:
        raise UnbalanceableEquationError(
            equation_text,
            "no non-zero solution: the elements cannot be conserved "
            "(check the formulas and the reaction direction)",
        )
    solution, is_unique = _positive_solution(basis, columns, equation_text)
    if solution is None:
        raise UnbalanceableEquationError(
            equation_text,
            "no strictly positive integer coefficients balance this equation",
        )

    reactant_species = tuple(
        BalancedSpecies(item.formula, coefficient, "reactant")
        for item, coefficient in zip(reactants, solution[: len(reactants)])
    )
    product_species = tuple(
        BalancedSpecies(item.formula, coefficient, "product")
        for item, coefficient in zip(products, solution[len(reactants) :])
    )

    # Report the checks in the order the elements are first read in the
    # equation (reactants left-to-right, then products), which is far easier to
    # scan than a chemical-table sort.
    symbols: list[str] = []
    for item in reactants + products:
        for symbol in item.formula.atom_counts:
            if symbol not in symbols:
                symbols.append(symbol)
    balances: list[ElementBalance] = []
    for symbol in symbols:
        left = sum(
            (
                Fraction(species.coefficient) * species.formula.count(symbol)
                for species in reactant_species
            ),
            Fraction(0),
        )
        right = sum(
            (
                Fraction(species.coefficient) * species.formula.count(symbol)
                for species in product_species
            ),
            Fraction(0),
        )
        if left != right:  # pragma: no cover - internal invariant
            raise UnbalanceableEquationError(
                equation_text, f"internal error: {symbol} is not conserved"
            )
        balances.append(ElementBalance(symbol, left, right))

    charge_left = sum(
        species.coefficient * species.formula.charge for species in reactant_species
    )
    charge_right = sum(
        species.coefficient * species.formula.charge for species in product_species
    )
    if charge_left != charge_right:  # pragma: no cover - internal invariant
        raise UnbalanceableEquationError(
            equation_text, "internal error: net charge is not conserved"
        )

    return BalancedEquation(
        reactants=reactant_species,
        products=product_species,
        element_balances=tuple(balances),
        charge_left=charge_left,
        charge_right=charge_right,
        is_unique=is_unique,
        reversible=parsed.reversible,
        source=equation_text,
    )
