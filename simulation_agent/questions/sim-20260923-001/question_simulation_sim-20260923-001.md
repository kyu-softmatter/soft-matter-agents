# sim-20260923-001 — structural relaxation from a random initial configuration

*S2 output, for people. The record is `goal.json` beside this file (P3). Written
by seat simulation-11 on 2026-09-23 from the person's question 5-1, verbatim
in `goal.json` `constraint_notes[0]`.*

## Where this stops, and why

**Branch (c) of S2: only a person can answer, asked back once.** Nothing below
is a refusal. It is the list of what has to exist before S3 can start, sorted
by who can supply it.

### 1. From the person

- **Purpose.** Proposed `characterize` (quantify a property over a swept range,
  intent `explore`, answers in decades). Confirm, or say `compare` and name the
  one variable that differs between arms.
- **The model.** Which interparticle potential — its functional form, whether
  it is purely repulsive or has an attractive well, and whether hydrodynamic
  interactions are neglected (overdamped BD as today) or not. This is a change
  of physical model and is yours to decide (§4.2); this agent can only select
  a model already declared.
- **What "relaxed" means.** The estimator is part of the observable's identity
  (`contracts/observables.json` rule 2). Candidates, in rough order of how
  cheaply each is computed from a trajectory:
  - the self-intermediate scattering function or overlap function decaying to
    a set fraction of its initial value (defines an alpha-relaxation time);
  - a bond-orientational order parameter (ψ6 in 2D, Q6 in 3D) approaching its
    plateau;
  - the height of the first peak of the pair correlation g(r), or of the
    structure factor S(k), approaching its plateau.
  These do not agree with each other in general, so one has to be named. The
  fraction or plateau criterion is a number and comes from you or the store,
  not from this seat.
- **Dimensionality**, 2D or 3D, and the boundary condition (periodic assumed
  unless you say otherwise; A3 owns it).
- **The swept ranges** — interaction strength, interaction range, density — as
  decades, and **target accuracy** on the relaxation time. Empty means "S3
  decides the bound", not "any value".
- **Budget target**: `local` is the only execution target in `envelope/`.

### 2. From `manager-simulation` (writes to `contracts/`)

- Register the observable, proposed id `structural_relaxation_time`, with
  `window_required: true` — the value depends on the decay threshold and on
  the fit window, so it is not one number (check 40's shape).
- Declare a configuration that produces it, proposed id `bd_pairwise`:
  overdamped BD with a declared pair potential, undriven. Its
  `output_independent_of_input` is **true** — unlike `bd_overdamped`, the
  output here is not fixed analytically by the inputs, so a run is evidence
  about the model. `temperature_realisation` stays `constitutive` as long as
  the integrator is Brownian and not Langevin.

### 3. From the librarian

Four `kb_query` calls at `kbv-4b981dc870d3` all came back **absent** with no
near names: `structural_relaxation_time`, `pair_potential` (this question) and
the two for 002. So the store does not close this as "already known". Whether
the literature does — Brownian crystallisation and glassy relaxation are both
heavily studied — is an external search the gap table's `absent` row points
at, and it should be done before compute is spent. That search is not this
seat's to answer from memory (E6).

## What S3 will do once the above exists

A1 bounds `dt` by the curvature of the chosen potential at contact, not only by
the diffusive time. A2 bounds seeds × length for the relaxation-time error.
A3 bounds the box against the correlation length that grows as the structure
orders — the hardest axis here, because that length is itself an output. A4
bounds the save interval against the decay to be resolved. A5 costs it. A7
abstains, undriven, and says so.
