"""Exception hierarchy for :mod:`chemistry_engine`.

All errors raised deliberately by the engine derive from :class:`ChemError`, so
callers (and the CLI) can distinguish "the user gave us something impossible"
from genuine bugs.
"""
from __future__ import annotations


class ChemError(Exception):
    """Base class for every deliberate chemistry-engine error."""


class UnknownElementError(ChemError, ValueError):
    """Raised when an element symbol, name, or atomic number cannot be resolved."""

    def __init__(self, key: object) -> None:
        super().__init__(f"unknown element: {key!r}")
        self.key = key


class FormulaParseError(ChemError, ValueError):
    """A formula could not be parsed.

    Carries the offending text and the 0-based position so callers can render a
    caret under the problem, which the CLI does.
    """

    def __init__(self, formula: str, position: int, message: str) -> None:
        position = max(0, min(position, len(formula)))
        pointer = " " * position + "^"
        super().__init__(
            f"invalid formula {formula!r} at column {position + 1}: {message}\n"
            f"  {formula}\n"
            f"  {pointer}"
        )
        self.formula = formula
        self.position = position
        self.message = message


class EquationParseError(ChemError, ValueError):
    """An equation string could not be parsed into reactants and products."""

    def __init__(self, equation: str, message: str) -> None:
        super().__init__(f"invalid equation {equation!r}: {message}")
        self.equation = equation
        self.message = message


class UnbalanceableEquationError(ChemError, ValueError):
    """No strictly positive integer set of coefficients balances the equation."""

    def __init__(self, equation: str, message: str) -> None:
        super().__init__(f"cannot balance {equation!r}: {message}")
        self.equation = equation
        self.message = message


class StoichiometryError(ChemError, ValueError):
    """Invalid feed for a stoichiometry calculation."""
