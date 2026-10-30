"""Chemical formula parsing.

Supported grammar (all counts are exact :class:`fractions.Fraction` values):

* element symbols, e.g. ``H2O``, ``C6H12O6``
* nested groups with any of ``()``, ``[]``, ``{}``, e.g. ``K4[Fe(CN)6]``
* hydrate / adduct separators ``·`` (and the ASCII ``.`` / ``*``), with an
  optional integer or Unicode-fraction multiplier, e.g. ``CuSO4·5H2O``,
  ``CaSO4·½H2O``
* ionic charges in caret notation (``SO4^2-``), Unicode superscript
  (``SO4²⁻``), or a bare trailing sign (``NH4+``)
* Unicode subscript digits in formulas (``H₂O``)
* the electron ``e^-`` (zero atoms, charge -1), useful for half-reactions

Anything else raises :class:`chemistry_engine.errors.FormulaParseError` with a column
pointer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Mapping

from .elements import ELEMENTS_BY_SYMBOL, get_element
from .errors import FormulaParseError

_SUBSCRIPT_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUPERSCRIPT_TRANSLATION = str.maketrans(
    {
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
        "⁺": "+",
        "⁻": "-",
    }
)
_SUPERSCRIPT_CHARS = frozenset("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
_MINUS_VARIANTS = str.maketrans({"\u2212": "-", "\u2013": "-"})
_HYDRATE_DOTS = {"·", "⋅", "∙", "*"}
_ASCII_DIGITS = frozenset("0123456789")
_CHARGE_START = frozenset("^+-" + "".join(_SUPERSCRIPT_CHARS))
_OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
_CLOSERS = frozenset(_OPEN_TO_CLOSE.values())
_FRACTION_MULTIPLIERS = {
    "½": Fraction(1, 2),
    "⅓": Fraction(1, 3),
    "⅔": Fraction(2, 3),
    "¼": Fraction(1, 4),
    "¾": Fraction(3, 4),
    "⅕": Fraction(1, 5),
    "⅖": Fraction(2, 5),
    "⅗": Fraction(3, 5),
    "⅘": Fraction(4, 5),
    "⅙": Fraction(1, 6),
    "⅚": Fraction(5, 6),
    "⅛": Fraction(1, 8),
    "⅜": Fraction(3, 8),
    "⅝": Fraction(5, 8),
    "⅞": Fraction(7, 8),
}


@dataclass(frozen=True, slots=True)
class Formula:
    """A parsed chemical formula.

    ``atom_counts`` maps element symbols to exact atom counts (fractions only
    appear for fractional hydrate multipliers such as ``½H2O``).  ``charge`` is
    the net charge written on the formula.
    """

    text: str
    atom_counts: Mapping[str, Fraction]
    charge: int = 0

    @property
    def is_electron(self) -> bool:
        """True for the special ``e^-`` species (no atoms)."""
        return not self.atom_counts

    @property
    def elements(self) -> tuple[str, ...]:
        """Element symbols in periodic-table order."""
        return tuple(
            sorted(self.atom_counts, key=lambda s: get_element(s).atomic_number)
        )

    def hill_order(self) -> tuple[str, ...]:
        """Element symbols in Hill order — the conventional formula ordering.

        Carbon first, hydrogen second when carbon is present; otherwise
        alphabetical.  This is the order used when displaying elemental
        composition, so glucose reads C, H, O instead of H, C, O.
        """
        symbols = list(self.atom_counts)
        if "C" in symbols:
            ordered = ["C"]
            if "H" in symbols:
                ordered.append("H")
            ordered.extend(sorted(symbol for symbol in symbols if symbol not in ("C", "H")))
            return tuple(ordered)
        return tuple(sorted(symbols))

    @property
    def total_atoms(self) -> Fraction:
        return sum(self.atom_counts.values(), Fraction(0))

    def count(self, symbol: str) -> Fraction:
        """Atom count for one element (0 when absent)."""
        return self.atom_counts.get(symbol, Fraction(0))

    def composition_key(self) -> tuple[tuple[tuple[str, Fraction], ...], int]:
        """Hashable identity used to match the same species across an equation."""
        return (
            tuple((symbol, self.atom_counts[symbol]) for symbol in self.elements),
            self.charge,
        )

    def canonical_formula(self) -> str:
        """A normalized, input-independent rendering of the formula."""
        if self.is_electron:
            return "e^-"
        if any(separator in self.text for separator in ("·", "⋅", "∙", "*", ".")):
            # Hydrates flattening to a single composition would lose their
            # structure, so keep the user's notation.
            return self.text
        if any(count.denominator != 1 for count in self.atom_counts.values()):
            # Fractional counts (hemihydrates and similar) have no tidy
            # canonical spelling, so keep the user's original notation.
            return self.text
        parts: list[str] = []
        for symbol, count in self.atom_counts.items():
            if count == 1:
                parts.append(symbol)
            elif count.denominator == 1:
                parts.append(f"{symbol}{count.numerator}")
            else:
                parts.append(f"{symbol}({count})")
        text = "".join(parts)
        if self.charge:
            magnitude = "" if abs(self.charge) == 1 else str(abs(self.charge))
            text += "^" + magnitude + ("+" if self.charge > 0 else "-")
        return text

    def __str__(self) -> str:
        return self.text

    def __hash__(self) -> int:
        return hash((self.text, self.composition_key(), self.charge))


class _FormulaParser:
    def __init__(self, text: str) -> None:
        self.original = text
        self.text = self._normalize(text)
        self.position = 0
        self.length = len(self.text)

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = text.strip().translate(_SUBSCRIPT_DIGITS)
        normalized = normalized.translate(_MINUS_VARIANTS)
        for dot in _HYDRATE_DOTS:
            normalized = normalized.replace(dot, ".")
        return normalized

    # -- small helpers ----------------------------------------------------
    def _fail(self, message: str, position: int | None = None) -> None:
        raise FormulaParseError(
            self.original,
            self.position if position is None else position,
            message,
        )

    def _eof(self) -> bool:
        return self.position >= self.length

    def _peek(self) -> str:
        return "" if self._eof() else self.text[self.position]

    def _skip_spaces(self) -> None:
        while not self._eof() and self.text[self.position].isspace():
            self.position += 1

    def _read_integer(self) -> tuple[int, int]:
        start = self.position
        while not self._eof() and self.text[self.position] in _ASCII_DIGITS:
            self.position += 1
        raw = self.text[start : self.position]
        if raw.startswith("0"):
            self._fail("counts must be positive integers without leading zeros", start)
        value = int(raw)
        if value <= 0:
            self._fail("counts must be positive", start)
        return value, start

    # -- grammar ----------------------------------------------------------
    def parse(self) -> Formula:
        compact = "".join(self.text.split())
        if compact in {"e-", "e^-"} or compact.translate(_SUPERSCRIPT_TRANSLATION) == "e-":
            return Formula(self.original.strip(), MappingProxyType({}), -1)

        self._skip_spaces()
        if self._eof():
            self._fail("empty formula")
        if self._peek() in _ASCII_DIGITS:
            self._fail("a formula must not start with a coefficient")

        counts: dict[str, Fraction] = {}
        self._parse_component(counts, Fraction(1), "formula")
        self._skip_spaces()
        if self._peek() in _CLOSERS:
            self._fail(f"unmatched closing bracket {self._peek()!r}")

        while True:
            self._skip_spaces()
            if self._peek() != ".":
                break
            self.position += 1
            self._skip_spaces()
            if self._eof():
                self._fail("expected a formula after the hydrate separator")
            multiplier = self._parse_hydrate_multiplier()
            self._skip_spaces()
            if self._eof() or self._peek() == "." or self._peek() in _CHARGE_START:
                self._fail("expected a formula after the hydrate multiplier")
            self._parse_component(counts, multiplier, "hydrate component")

        charge = self._parse_charge()
        self._skip_spaces()
        if not self._eof():
            self._fail(f"unexpected trailing character {self._peek()!r}")
        if not counts:
            self._fail("formula contains no atoms")
        return Formula(
            self.original.strip(), MappingProxyType(dict(counts)), charge
        )

    def _parse_component(
        self, counts: dict[str, Fraction], multiplier: Fraction, context: str
    ) -> None:
        start = self.position
        found = False
        while True:
            self._skip_spaces()
            character = self._peek()
            if not character or character == ".":
                break
            if character in _CHARGE_START:
                break
            if character in _CLOSERS:
                break
            if character in _OPEN_TO_CLOSE:
                group = self._parse_group()
                count = self._parse_count()
                self._add(counts, group, Fraction(count) * multiplier)
                found = True
                continue
            if character.isupper():
                symbol = self._parse_element()
                count = self._parse_count()
                self._add(
                    counts, {symbol: Fraction(1)}, Fraction(count) * multiplier
                )
                found = True
                continue
            if character in _ASCII_DIGITS:
                self._fail(
                    "unexpected number; counts follow an element or a closing group"
                )
            self._fail(f"unexpected character {character!r}")
        if not found:
            self._fail(f"expected an element or group in {context}", start)

    def _parse_group(self) -> dict[str, Fraction]:
        opener_position = self.position
        opener = self.text[self.position]
        closer = _OPEN_TO_CLOSE[opener]
        self.position += 1
        counts: dict[str, Fraction] = {}
        self._parse_component(counts, Fraction(1), f"group {opener!r}")
        self._skip_spaces()
        if self._eof():
            self._fail(f"unclosed {opener!r}; expected {closer!r}", opener_position)
        if self._peek() != closer:
            self._fail(
                f"expected {closer!r} but found {self._peek()!r}", opener_position
            )
        self.position += 1
        return counts

    def _parse_element(self) -> str:
        start = self.position
        symbol = self.text[self.position]
        self.position += 1
        if not self._eof() and self.text[self.position].islower():
            symbol += self.text[self.position]
            self.position += 1
        if symbol not in ELEMENTS_BY_SYMBOL:
            self._fail(f"unknown element symbol {symbol!r}", start)
        return symbol

    def _parse_count(self) -> int:
        if self._eof() or self._peek() not in _ASCII_DIGITS:
            return 1
        value, _ = self._read_integer()
        return value

    def _parse_hydrate_multiplier(self) -> Fraction:
        character = self._peek()
        if character in _FRACTION_MULTIPLIERS:
            self.position += 1
            return _FRACTION_MULTIPLIERS[character]
        if character in _ASCII_DIGITS:
            value, _ = self._read_integer()
            return Fraction(value)
        return Fraction(1)

    def _parse_charge(self) -> int:
        self._skip_spaces()
        character = self._peek()
        if character == "^":
            caret_position = self.position
            self.position += 1
            self._skip_spaces()
            start = self.position
            while not self._eof() and self._peek() in _ASCII_DIGITS:
                self.position += 1
            digits = self.text[start : self.position]
            if digits.startswith("0"):
                self._fail("charge magnitude must be positive", start)
            sign = self._peek()
            if not sign or sign not in "+-":
                self._fail(
                    "a '^' charge needs an optional magnitude and a '+' or '-' sign",
                    caret_position,
                )
            self.position += 1
            magnitude = int(digits) if digits else 1
            if magnitude <= 0:
                self._fail("charge magnitude must be positive", start)
            return magnitude if sign == "+" else -magnitude
        if character in _SUPERSCRIPT_CHARS:
            start = self.position
            while not self._eof() and self._peek() in _SUPERSCRIPT_CHARS:
                self.position += 1
            translated = self.text[start : self.position].translate(
                _SUPERSCRIPT_TRANSLATION
            )
            match = re.fullmatch(r"(\d*)([+-])", translated)
            if match is None:
                self._fail(
                    "invalid superscript charge; expected digits followed by a sign",
                    start,
                )
            magnitude = int(match.group(1)) if match.group(1) else 1
            if magnitude <= 0:
                self._fail("charge magnitude must be positive", start)
            return magnitude if match.group(2) == "+" else -magnitude
        if character and character in "+-":
            self.position += 1
            return 1 if character == "+" else -1
        return 0

    @staticmethod
    def _add(
        target: dict[str, Fraction],
        source: dict[str, Fraction],
        multiplier: Fraction,
    ) -> None:
        for symbol, count in source.items():
            target[symbol] = target.get(symbol, Fraction(0)) + count * multiplier


def parse_formula(formula: str | Formula) -> Formula:
    """Parse ``formula`` (a :class:`Formula` is returned unchanged)."""
    if isinstance(formula, Formula):
        return formula
    if not isinstance(formula, str):
        raise TypeError(f"formula must be a string, got {type(formula).__name__}")
    return _FormulaParser(formula).parse()
