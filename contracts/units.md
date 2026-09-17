# Units and dimensionless groups

`units.json` is authoritative (P3). This file explains it.

## What lives here and what does not

`contracts/units.md` and `units.json` hold two things only:

1. **The allowed units per quantity.** A unit outside the registry cannot be
   checked for dimension, so it cannot be compared with anything, and check 2
   rejects it.
2. **The shape a dimensionless group entry must have.**

**The dimensionless groups themselves are not here.** They are knowledge, and
knowledge lives in the librarian's KB (P14, section 5.7). Pinning a list of
groups into the contract layer would give knowledge two homes, and the measured
subject of this instrument is deliberately left open, so no fixed list would
survive.

## Physical units are authoritative

Cards carry laboratory units: µm, s, pN, K, energies in J or pN·µm, viscosity in
Pa·s. Reduced units never appear in a card. Conversion to whatever a simulation
engine wants happens inside that engine's backend, so a plan does not become
invalid when the engine changes (D7, section 7.2 rule 2).

Dimensionless numbers are **derived**: computed from physical values and marked
`derived: true` with the formula in the card. The validator recomputes them
(check 17). They are never authoritative, which is why they cannot be
hand-edited into agreement.

## Reading the registry

Each unit carries a dimension vector and a factor to SI base units:

```json
"pN/um": { "si_factor": 1e-6, "dim": { "M": 1, "T": -2 } }
```

`L` length, `T` time, `M` mass, `Th` temperature, `A` angle, `N` count. The
factor is what multiplies a value to put it in SI, so a stiffness of 1 pN/µm is
1e-6 kg/s².

Composite units are listed explicitly rather than parsed. An explicit list is
auditable: you can read what is allowed. A parser would accept `pN/furlong`
without complaint.

### kT is the one special case

`kT` has the dimension of energy but no fixed factor, because the factor is
k_B·T. A card using `kT` must carry a number named `temperature` in K, or check
2 fails. This keeps the design's stated energy unit while refusing to let a
temperature-dependent conversion happen silently.

### Temperature is in kelvin only

Celsius is absent on purpose. It is an affine scale, so it cannot take part in
the multiplication and division that formula checking does: 2 × 20 °C is not
40 °C. Convert once, at the point where the number enters a card.

## Grades and formulas

A computed value cannot be better than E4, and it inherits the worst grade among
its inputs (section 5.3). The reason is in the formula rather than the inputs:
Stokes–Einstein assumes a sphere, in bulk, with no slip. Those assumptions stay
in the value however well the inputs were measured.

A formula in a card is arithmetic over the names of other numbers in the same
card, with `pi` and `k_B` available. Nothing else is reachable — no function
calls, no attribute access — so a formula cannot become a code path.

## Order of magnitude

In explore mode, which is the default, an E4 or E5 value is written to one
significant figure and compared at that precision. `tau_d = 0.0431 s` with an
estimate anywhere in its inputs is a false claim; `tau_d ~ 0.04 s` is a true
one. Check 28 counts significant figures, and check 17 compares a
one-significant-figure value against the recomputed result rounded the same way,
so the two checks cannot contradict each other.

## Adding a unit

Add it to `units.json` with its dimension and factor, and add it to the right
quantity list. That is a contract change: it belongs in the commit that needs
it, with the reason.
