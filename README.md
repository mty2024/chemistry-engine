# chemistry-engine

[Website](https://mty2024.github.io/chemistry-engine/) · [Documentation](https://mty2024.github.io/chemistry-engine/docs/) · [Release v0.1.0](https://github.com/mty2024/chemistry-engine/releases/tag/v0.1.0)

A real chemistry engine in pure Python — no third-party dependencies.

It does the chemistry a computation engine should get exactly right:

- **Periodic table** — all 118 elements with the CIAAW/IUPAC abridged standard
  atomic weights (2024), plus the longest-lived-isotope mass numbers for the
  elements that have no standard atomic weight.
- **Formula parsing** — element symbols, nested groups (`Ca(OH)2`,
  `K4[Fe(CN)6]`), hydrates and adducts (`CuSO4·5H2O`, `CaSO4·½H2O`), ionic
  charges (`SO4^2-`, `SO4²⁻`, `NH4+`), Unicode subscripts (`H₂O`), and the
  electron (`e^-`).
- **Molar mass and elemental composition** — g/mol, mass fractions, mass
  percentages, per-element contributions (Hill order: C, H, then alphabetical).
- **Equation balancing** — exact rational linear algebra (no floating-point
  guessing), with charge conservation for ionic and redox equations and a
  smallest-positive-integer solution. Conservation checks are listed in the
  order the elements are read in the equation. Equations with several
  independent balances are detected and flagged.
- **Stoichiometry** — limiting reagent (with ties), consumed / remaining /
  produced amounts, and product / excess masses, from mol or mass feeds.

```console
$ chem mass "CuSO4·5H2O"
CuSO4·5H2O  249.677 g/mol

$ chem balance "KMnO4 + HCl -> KCl + MnCl2 + Cl2 + H2O"
2KMnO4 + 16HCl -> 2KCl + 2MnCl2 + 5Cl2 + 8H2O
Atom check (elements in equation order):
  K: 2 = 2
  Mn: 2 = 2
  O: 8 = 8
  H: 16 = 16
  Cl: 16 = 16
Charge: neutral (0 = 0)

$ chem stoich --equation "N2 + 3H2 -> 2NH3" --feed "N2=28 g" --feed "H2=6 g"
Balanced equation: N2 + 3H2 -> 2NH3
Reaction extent  : 0.992063 mol
Limiting reagent : H2
...
```

## Install

Python 3.10+ is required. Prebuilt wheels are attached to each
[GitHub release](https://github.com/mty2024/chemistry-engine/releases).

```bash
python -m pip install -e .
chem --version
```

You can also run it without installing, from the repository root:

```bash
python -m chemistry_engine mass H2O
```

## CLI

| Command | Purpose |
| --- | --- |
| `chem element Fe` | look up an element by symbol, name, or atomic number |
| `chem elements` | list all 118 elements |
| `chem mass H2O C6H12O6` | molar mass of one or more formulas |
| `chem inspect "CuSO4·5H2O"` | parsed atom counts, charge, molar mass |
| `chem composition H2O` | elemental mass percentages |
| `chem balance "Fe + O2 -> Fe2O3"` | balance an equation |
| `chem stoich --equation ... --feed ...` | limiting reagent and amounts |

Add `--json` anywhere for machine-readable output:

```bash
chem mass --json H2O
chem --json balance "H2 + O2 -> H2O"
```

## Library

```python
from chemistry_engine import (
    Feed,
    balance_equation,
    molar_mass,
    parse_formula,
    percent_composition,
    stoichiometry,
)

parse_formula("CuSO4·5H2O").atom_counts  # {'Cu': 1, 'S': 1, 'O': 9, 'H': 10}
molar_mass("C6H12O6")                     # 180.156
percent_composition("H2O")                # {'H': 11.19..., 'O': 88.80...}

reaction = balance_equation("Fe + O2 -> Fe2O3")
reaction.formula        # '4Fe + 3O2 -> 2Fe2O3'
reaction.coefficients   # (4, 3, 2)

result = stoichiometry(
    "N2 + 3H2 -> 2NH3",
    [Feed("N2", 1, "mol"), Feed("H2", 2, "mol")],
)
result.limiting          # ('H2',)
result.extent            # 0.6666666666666666
result.product_masses    # {'NH3': 22.708...}
```

Ionic equations carry their charge through the balance:

```python
reaction = balance_equation("Fe^2+ + MnO4^- + H^+ -> Fe^3+ + Mn^2+ + H2O")
reaction.formula      # '5Fe^2+ + MnO4^- + 8H^+ -> 5Fe^3+ + Mn^2+ + 4H2O'
reaction.charge_left  # 17
reaction.charge_right # 17
```

## Data and correctness

**Atomic weights.** The generated module `chemistry_engine/elements_data.py` contains the
[CIAAW Abridged Standard Atomic Weights 2024](https://www.ciaaw.org/abridged-atomic-weights.htm).
For elements without a standard atomic weight (Tc, Pm, and most elements heavier
than uranium), the mass number of the longest-lived known isotope is used, from
the [CIAAW radioactive-elements table](https://www.ciaaw.org/radioactive-elements.htm)
(2020 NUBASE evaluation); Tc keeps the conventional bracket value `[98]`.
`Element.atomic_mass` is the value used for every calculation, and
`Element.has_standard_atomic_weight` tells them apart.

Refresh the table with the committed generator (network needed only here):

```bash
python tools/update_periodic_table.py
```

**Balancing.** The solver builds one conservation row per element (and a charge
row when ions are present), reduces the system over `fractions.Fraction`, and
picks the smallest strictly positive integer null-space vector. Results are
exact; no coefficient is ever guessed. When the null space has more than one
dimension (`C + O2 -> CO + CO2` is the classic case), the engine returns a
smallest valid integer solution and sets `is_unique=False`.

**Tests.** The suite runs with the standard library only:

```bash
python -m unittest discover -s tests -v
```

It covers the periodic table, formula grammar and error positions, molar masses
against known values, textbook balancing cases (combustion, permanganate
oxidation, ionic redox, half-reactions with electrons), multi-solution
equations, and stoichiometry including hydrate and mass feeds.

A separate cross-check (network required for the PubChem snapshot) verifies the
atomic masses against an independent source, re-balances a battery of textbook
equations, and checks stoichiometric mass conservation:

```bash
python tools/verify_chemistry.py
```

## Limitations

- **Balancing and stoichiometry only.** No reaction prediction, equilibrium,
  thermodynamics, kinetics, or acid–base calculations.
- **No molecular graph / cheminformatics.** No SMILES, InChI, 3D coordinates, or
  substructure search. Formulas are compositions, so structural isomers are
  indistinguishable by formula.
- **No isotope labels** (`^13C`) or nuclide data.
- Hydrate multipliers support integers and common Unicode fractions (`½`, `¼`,
  `⅓`, …); decimal multipliers such as `0.5H2O` are not accepted.
- Under-determined equations are searched for a small positive solution; an
  exotic equation that needs very large coefficients may exhaust the search
  bound instead of solving.
- Molar masses use the abridged five-significant-figure atomic weights; the
  engine does not propagate their uncertainty.

## Project layout

```
chemistry_engine/
  elements.py        periodic table access + aliases
  elements_data.py   generated CIAAW data (do not edit by hand)
  formula.py         formula grammar and Formula
  properties.py      molar mass, composition, amount conversions
  equations.py       equation parsing (arrows, species, charges)
  balance.py         exact rational balancing + conservation checks
  stoichiometry.py   limiting reagent and amounts
  cli.py             argparse CLI (chem)
tests/               unittest suite
tools/               periodic-table generator + independent chemistry checks
```

## Changelog and releases

- [CHANGELOG.md](CHANGELOG.md) — notable changes per version.
- [docs/releases/](docs/releases/) — per-release notes.
