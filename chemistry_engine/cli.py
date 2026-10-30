"""Command-line interface (``chem`` / ``python -m chemistry_engine``)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from fractions import Fraction
from typing import Any, Sequence

from . import __version__
from .balance import balance_equation
from .elements import ELEMENTS, get_element
from .errors import ChemError
from .formula import Formula, parse_formula
from .properties import elemental_analysis, molar_mass
from .stoichiometry import Feed, stoichiometry

_FEED_RE = re.compile(
    r"^\s*(?P<species>.+?)\s*=\s*"
    r"(?P<amount>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*"
    r"(?P<unit>[A-Za-zµμ]*)\s*$"
)


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------
def _fmt(value: float, significant: int = 6) -> str:
    return f"{value:.{significant}g}"


def _format_count(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return _fmt(value)


def _fraction_out(value: Fraction) -> int | float:
    return int(value) if value.denominator == 1 else float(value)


def _configure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_element(args: argparse.Namespace) -> int:
    element = get_element(args.key)
    payload = {
        "symbol": element.symbol,
        "name": element.name,
        "atomic_number": element.atomic_number,
        "standard_atomic_weight": element.standard_atomic_weight,
        "most_stable_isotope_mass_number": element.most_stable_isotope_mass_number,
        "atomic_mass_g_per_mol": element.atomic_mass,
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"{element.symbol}  {element.name}  (Z={element.atomic_number})")
    if element.has_standard_atomic_weight:
        print(f"standard atomic weight : {element.standard_atomic_weight} g/mol")
    else:
        print(
            "standard atomic weight : none; most stable isotope mass number "
            f"{element.most_stable_isotope_mass_number}"
        )
        print(f"mass used by chemistry-engine : {_fmt(element.atomic_mass)} g/mol")
    return 0


def cmd_elements(args: argparse.Namespace) -> int:
    payload = [
        {
            "atomic_number": element.atomic_number,
            "symbol": element.symbol,
            "name": element.name,
            "atomic_mass_g_per_mol": element.atomic_mass,
            "standard_atomic_weight": element.standard_atomic_weight,
            "most_stable_isotope_mass_number": element.most_stable_isotope_mass_number,
        }
        for element in ELEMENTS
    ]
    if args.json:
        _print_json(payload)
        return 0
    print(f"{'Z':>3}  {'Sym':<3} {'Name':<14} {'Mass (g/mol)':>13}  Note")
    for element in ELEMENTS:
        note = (
            ""
            if element.has_standard_atomic_weight
            else f"most stable isotope [{element.most_stable_isotope_mass_number}]"
        )
        print(
            f"{element.atomic_number:>3}  {element.symbol:<3} {element.name:<14} "
            f"{element.atomic_mass:>13.6g}  {note}"
        )
    return 0


def cmd_mass(args: argparse.Namespace) -> int:
    results = []
    for text in args.formulas:
        formula = parse_formula(text)
        results.append({"formula": text, "molar_mass_g_per_mol": molar_mass(formula)})
    if args.json:
        _print_json(results)
        return 0
    width = max(len(item["formula"]) for item in results)
    for item in results:
        print(f"{item['formula']:<{width}}  {_fmt(item['molar_mass_g_per_mol'])} g/mol")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    formula = parse_formula(args.formula)
    payload = {
        "formula": formula.text,
        "canonical": formula.canonical_formula(),
        "charge": formula.charge,
        "is_electron": formula.is_electron,
        "molar_mass_g_per_mol": molar_mass(formula),
        "atoms": {
            symbol: _fraction_out(formula.atom_counts[symbol])
            for symbol in formula.hill_order()
        },
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"formula    : {formula.text}")
    if formula.canonical_formula() != formula.text:
        print(f"canonical  : {formula.canonical_formula()}")
    print(f"charge     : {formula.charge:+d}" if formula.charge else "charge     : 0")
    if formula.is_electron:
        print("atoms      : (electron — no atoms)")
    else:
        counts = ", ".join(
            f"{symbol} {_fraction_out(formula.atom_counts[symbol])}"
            for symbol in formula.hill_order()
        )
        print(f"atoms      : {counts}")
    print(f"molar mass : {_fmt(molar_mass(formula))} g/mol")
    return 0


def cmd_composition(args: argparse.Namespace) -> int:
    formula = parse_formula(args.formula)
    contributions = elemental_analysis(formula)
    payload = {
        "formula": formula.text,
        "molar_mass_g_per_mol": molar_mass(formula),
        "elements": [
            {
                "symbol": item.element.symbol,
                "name": item.element.name,
                "atoms": _fraction_out(Fraction(item.count).limit_denominator()),
                "mass_g_per_mol": item.mass_g_per_mol,
                "mass_fraction": item.mass_fraction,
                "mass_percent": item.percent,
            }
            for item in contributions
        ],
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"formula    : {formula.text}")
    print(f"molar mass : {_fmt(payload['molar_mass_g_per_mol'])} g/mol")
    if not contributions:
        print("elements   : (none)")
        return 0
    print()
    symbol_width = max(4, max(len(item.element.symbol) for item in contributions))
    name_width = max(4, max(len(item.element.name) for item in contributions))
    print(
        f"{'Elem':<{symbol_width}}  {'Name':<{name_width}}  "
        f"{'Atoms':>7}  {'Mass (g/mol)':>13}  {'Mass %':>8}"
    )
    for item in contributions:
        print(
            f"{item.element.symbol:<{symbol_width}}  {item.element.name:<{name_width}}  "
            f"{_format_count(item.count):>7}  {_fmt(item.mass_g_per_mol):>13}  "
            f"{_fmt(item.percent):>8}"
        )
    return 0


def cmd_balance(args: argparse.Namespace) -> int:
    balanced = balance_equation(args.equation)
    payload = {
        "source": balanced.source,
        "equation": balanced.formula,
        "reactants": [
            {"formula": species.text, "coefficient": species.coefficient}
            for species in balanced.reactants
        ],
        "products": [
            {"formula": species.text, "coefficient": species.coefficient}
            for species in balanced.products
        ],
        "elements": [
            {
                "symbol": check.symbol,
                "left": _fraction_out(check.left),
                "right": _fraction_out(check.right),
                "balanced": check.balanced,
            }
            for check in balanced.element_balances
        ],
        "charge": {"left": balanced.charge_left, "right": balanced.charge_right},
        "is_unique": balanced.is_unique,
        "reversible": balanced.reversible,
    }
    if args.json:
        _print_json(payload)
        return 0
    print(balanced.formula)
    if not balanced.is_unique:
        print(
            "\nnote: more than one independent balance exists; "
            "showing the smallest positive integer solution."
        )
    print("\nAtom check (elements in equation order):")
    for check in balanced.element_balances:
        print(f"  {check.symbol}: {_fraction_out(check.left)} = {_fraction_out(check.right)}")
    if balanced.charge_left or balanced.charge_right:
        print(f"Charge: {balanced.charge_left} = {balanced.charge_right}")
    else:
        print("Charge: neutral (0 = 0)")
    return 0


def _parse_feed(specification: str) -> Feed:
    match = _FEED_RE.match(specification)
    if match is None:
        raise ChemError(
            f"invalid feed {specification!r}; expected SPECIES=AMOUNT[UNIT], "
            "e.g. 'N2=28 g' or 'H2=3 mol'"
        )
    return Feed(
        species=match.group("species").strip(),
        amount=float(match.group("amount")),
        unit=match.group("unit") or "mol",
    )


def cmd_stoich(args: argparse.Namespace) -> int:
    feeds = [_parse_feed(item) for item in args.feed]
    result = stoichiometry(args.equation, feeds)
    payload = {
        "equation": result.equation.formula,
        "extent_mol": result.extent,
        "limiting_reagents": list(result.limiting),
        "feed_moles": result.feed_moles,
        "consumed_moles": result.consumed,
        "remaining_moles": result.remaining,
        "produced_moles": result.produced,
        "product_masses_g": result.product_masses,
        "remaining_masses_g": result.remaining_masses,
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"Balanced equation: {result.equation.formula}")
    print(f"Reaction extent  : {_fmt(result.extent)} mol")
    print(f"Limiting reagent : {', '.join(result.limiting)}")
    print("\nReactants:")
    print(
        f"  {'Species':<12} {'Fed (mol)':>10} {'Consumed (mol)':>15} "
        f"{'Remaining (mol)':>16} {'Remaining (g)':>14}"
    )
    for species in result.equation.reactants:
        label = species.formula.text
        print(
            f"  {label:<12} {_fmt(result.feed_moles[label]):>10} "
            f"{_fmt(result.consumed[label]):>15} "
            f"{_fmt(result.remaining[label]):>16} "
            f"{_fmt(result.remaining_masses[label]):>14}"
        )
    print("\nProducts:")
    print(f"  {'Species':<12} {'Produced (mol)':>15} {'Mass (g)':>12}")
    for species in result.equation.products:
        label = species.formula.text
        print(
            f"  {label:<12} {_fmt(result.produced[label]):>15} "
            f"{_fmt(result.product_masses[label]):>12}"
        )
    return 0


# ---------------------------------------------------------------------------
# parser / entry point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chem",
        description="A real chemistry engine: formulas, molar mass, equations, stoichiometry.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="emit JSON",
    )

    element = subparsers.add_parser(
        "element", parents=[common], help="look up one element"
    )
    element.add_argument("key", help="atomic number, symbol, or English name")
    element.set_defaults(handler=cmd_element)

    elements = subparsers.add_parser(
        "elements", parents=[common], help="list all 118 elements"
    )
    elements.set_defaults(handler=cmd_elements)

    mass = subparsers.add_parser(
        "mass", parents=[common], help="molar mass of one or more formulas"
    )
    mass.add_argument("formulas", nargs="+")
    mass.set_defaults(handler=cmd_mass)

    inspect = subparsers.add_parser(
        "inspect", parents=[common], help="parse a formula and show its composition"
    )
    inspect.add_argument("formula")
    inspect.set_defaults(handler=cmd_inspect)

    composition = subparsers.add_parser(
        "composition", parents=[common], help="elemental mass percentages"
    )
    composition.add_argument("formula")
    composition.set_defaults(handler=cmd_composition)

    balance = subparsers.add_parser(
        "balance", parents=[common], help="balance a chemical equation"
    )
    balance.add_argument("equation", help="e.g. 'Fe + O2 -> Fe2O3'")
    balance.set_defaults(handler=cmd_balance)

    stoich = subparsers.add_parser(
        "stoich", parents=[common], help="limiting reagent and product amounts"
    )
    stoich.add_argument("--equation", required=True, help="balanced or unbalanced equation")
    stoich.add_argument(
        "--feed",
        action="append",
        required=True,
        metavar="SPECIES=AMOUNT[UNIT]",
        help="reactant feed, e.g. 'N2=28 g' or 'H2=3 mol' (repeatable)",
    )
    stoich.set_defaults(handler=cmd_stoich)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except ChemError as error:
        print(f"chem: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
