# Changelog

All notable changes to `chemistry-engine` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-30

### Added

- Periodic table for all 118 elements, using the CIAAW/IUPAC Abridged Standard
  Atomic Weights 2024 and longest-lived-isotope mass numbers for elements
  without a standard atomic weight.
- Formula parser with nested groups, hydrates/adducts (including fractional
  multipliers), ionic charges in caret / Unicode / bare-sign notation, Unicode
  subscripts, and the electron `e^-`.
- Molar mass, elemental mass fractions and mass percentages in Hill order.
- Exact equation balancing over `fractions.Fraction`, including charge
  conservation for ionic and redox equations, electron half-reactions, and
  detection of equations with multiple independent balances.
- Stoichiometry: limiting reagent (including ties), consumed / remaining /
  produced amounts, and product / excess masses from mol or mass feeds.
- `chem` CLI (`python -m chemistry_engine`) with JSON output for every command.
- `tools/update_periodic_table.py` to regenerate the shipped periodic-table data
  from CIAAW, and `tools/verify_chemistry.py` for independent cross-checks.
- `tools/build_dist.py` builds a deterministic pure-Python wheel and sdist for releases.
- Test suite (`python -m unittest discover -s tests -v`) covering the table,
  formula grammar, known molar masses, textbook balancing, and stoichiometry.

### Changed

- Project renamed to `chemistry-engine` (import package `chemistry_engine`).

### Verification

- 82 unit tests passing.
- Atomic masses cross-checked against the PubChem periodic-table snapshot.
- 19 textbook equations re-balanced and checked independently for atom and
  charge conservation.
- Stoichiometric mass conservation checked to < 1e-9 relative error.
