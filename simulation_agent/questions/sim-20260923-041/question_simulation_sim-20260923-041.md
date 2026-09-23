# sim-20260923-041 — interacting active Brownian particles against free ones

*S2 output, for people. The record is `goal.json` beside this file (P3), and
the S3.0 verdict is `refusal_s30_sim-20260923-041.json`. Written by seat
simulation-10 (window 4) on 2026-09-23 from the person's question 4-1,
verbatim in `goal.json` `constraint_notes[0]`.*

## Where this stops, and why

**S2 branch (c): only a person can answer, asked back once**, and **S3.0:
zero capable configurations**, in numbers in the refusal card. Nothing below
is filled in by this seat; it is what has to exist before S3 can start,
sorted by who supplies it.

### 1. From the person

- **Purpose.** Proposed `characterize` (five parameters swept, `explore`,
  answers in decades). Say `compare` instead if the interest is interacting
  against non-interacting at one condition, and name the one variable.
- **The model.** Overdamped active Brownian dynamics — one orientation per
  particle diffusing at D_R, displacement at v0 along it, D_T on the
  position — plus a repulsion. "Hard-sphere-like" has to become one of:
  a steep soft potential (WCA is the standard stand-in), or an event-driven
  hard core. A1's timestep bound follows from the stiffness at contact, so
  the choice is not cosmetic. Hydrodynamic interactions neglected unless
  you say otherwise.
- **Dimensionality**, 2D or 3D. The persistence time is 1/D_R in 2D and
  1/(2 D_R) in 3D, so the same D_R means different dynamics.
- **A physical anchor.** Cards are authoritative in SI (D7): a particle
  diameter, v0 in µm/s, D_R in 1/s, D_T in µm²/s. Say whether D_T and D_R
  are thermally tied (D_R = 3 D_T / σ² for a sphere) or independent knobs.
- **Which axes are primary.** Three values per axis over five axes is 243
  operating points before seeds; A5 will refuse that against `local`. The
  natural reduction is two dimensionless axes — Péclet number v0/(σ D_R)
  and packing fraction — with the rest held.
- **Target accuracy** on each quantity, in decades under `explore`. Note
  that the qualitatively different regime the question anticipates
  (motility-induced clustering at high Péclet and density) is visible at
  decade resolution; a 20 % shift in D_eff is not.
- **Budget target.** `local` is the only one in `envelope/`.

### 2. From `manager-simulation` (writes to `contracts/`)

Register five observables; the estimator is part of each identity
(`observables.json` rule 2), so each entry has to choose:

| proposed id | window | the choice the estimator forces |
|---|---|---|
| `mean_squared_displacement` | yes | lag grid; averaged over particles and time origins; unwrapped coordinates |
| `effective_diffusivity` | yes | slope of the MSD at lags well above the persistence time, fit window declared |
| `persistence_time` | yes | fitted from the orientational autocorrelation, or taken as 1/((d−1) D_R) from the input — the first is a measurement, the second restates the input |
| `persistence_length` | yes | v0 × persistence_time, or fitted from the MSD crossover |
| `dynamical_crossover_time` | yes | where the log-log slope of the MSD passes a stated value between 2 and 1 |

Declare two configurations: `abp_free` (the reference arm, the same request
another seat's question makes) and `abp_pairwise` (with the declared
repulsion). `output_independent_of_input` is **false** for `abp_free` — its
MSD is closed-form in the inputs — and **true** for `abp_pairwise`.
`temperature_realisation` stays constitutive: no velocity is represented.

### 3. From the librarian

Three `kb_query` calls at `kbv-4b981dc870d3` under this question's S2 id
came back **absent** with no near names. The store does not close this as
already known. The free active Brownian MSD is closed-form in the literature
and is the reference every interacting result is read against; it should
enter the store as a graded `literature:` entry before any run is compared
to it. This seat does not write it from memory (E6).

## Dependency on 042

The box against the persistence length is 042's measurement and 041's A3
premise. Landing 042 first turns an assumption in 041 into a citation.

## What S3 will do once the above exists

A1 bounds `dt` by the contact stiffness and by 1/D_R, not only by the
diffusive time. A2 bounds seeds × length for the error on D_eff at lags
above the persistence time. A3 bounds the box against the persistence
length and, at high density, against cluster size. A4 resolves lags below
the persistence time without aliasing. A5 costs the reduced sweep. A7
abstains, undriven, and says so.
