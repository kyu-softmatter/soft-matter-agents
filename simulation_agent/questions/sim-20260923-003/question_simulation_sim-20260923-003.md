# sim-20260923-003 — active Brownian particles, and where the screen stops

*For people. The record is `refusal_s30_sim-20260923-003.json` beside this file
(P3); if the two disagree the JSON wins. Written by seat `simulation-9` on
2026-09-23 from the person's question, quoted verbatim in the card's
`refused_what`.*

## The verdict

**Refused at S3.0, `no_capable_configuration`.** Not held, not deferred: the
screen keeps the configurations in `contracts/capabilities/simulation.json`
that produce the asked observable, and it kept none.

There are two separate blockages and they are not the same kind of thing.

### 1. The model is not declared — this is the refusal

`contracts/capabilities/simulation.json` declares exactly one configuration.
`bd_overdamped` is *overdamped Brownian dynamics of spherical tracers in an
implicit solvent, **undriven***, and it integrates a position-only Wiener
increment:

    positions += normal(0, sqrt(2*D*dt)),   D = k_B*T/(3*pi*eta*d)

An active Brownian particle carries an orientation that diffuses at `D_R` and
is displaced along that orientation at `v0`. There is no orientation in
`bd_overdamped` to diffuse, and `A7` abstains in it **by declaration**. So
`v0` and `D_R` are not parameters this agent can set — they are a different
physical model.

§4.2 puts a change of physical model with a person, and
`contracts/capabilities/simulation.json` is where that becomes a permission
boundary instead of a promise: this seat cannot write `contracts/` at all
(§6.2, checks 35 and 41). **That is the boundary working, not a tool failing.**

### 2. The observables are not registered — this is an ordering, not a refusal

Six quantities are asked for and `contracts/observables.json` holds none of
them:

| asked | in the vocabulary |
|---|---|
| mean squared displacement, as a curve | no |
| persistence time | no |
| persistence length | no |
| effective translational diffusivity | no |
| time-resolved `D_eff(t)` and its log-log slope | no |
| Péclet number | no |

§11-1 settled that the vocabulary is never finished: **an unregistered name is
an instruction to register it, not a refusal.** Check 40 says the same in
code — a card naming something the vocabulary does not define is a reference
to nothing, so the entry comes first.

Registering is not clerical here. **The estimator is part of an observable's
identity** (observables.json rule 2), and every one of these six has a real
choice inside it that two seats would otherwise answer differently:

- **MSD** — the lag grid, averaging over particles and over time origins, and
  whether overlapping origins are counted as independent. The existing
  `tracer_diffusivity` entry already pays for this lesson: equal weights over
  whole-record lags gave a 7 % bias at 0.16 % reported error.
- **persistence time** — read off `D_R` analytically, or fitted from the decay
  of the orientational autocorrelation. These are the same number only if the
  model is exactly right, and the second one is the one that can disagree.
- **persistence length** — `v0` times that time, or fitted from where the MSD
  bends. Same warning.
- **`D_eff`** — over which window. It is `window_required` for certain: read
  too early it is `D_T`, read too late it is the plateau, and the whole
  question is the crossover between them.
- **`D_eff(t)`** — `MSD(t)/(2*d*t)` or the local derivative `dMSD/dt/(2*d)`.
  These differ by exactly the amount the log-log slope is being asked to
  resolve, so naming one is not a detail.
- **Péclet** — there is more than one convention in circulation. Which length
  divides `v0` has to be fixed in the entry or the collapse is not reproducible.

## What this seat could not do, and would not do quietly

Writing the backend would have been possible — `simulation_agent/src/` is this
seat's. **It was not done.** Building an undeclared model and presenting a
working sweep is the declaration made by fait accompli, one level down, and it
is the shape this tree keeps catching itself in.

## The three alternatives, and one of them is substantive

They are in the card's `alternatives[]`. The middle one is the real finding:

**S2's second branch applies.** For non-interacting active Brownian particles
the mean squared displacement is known in closed form, so the dependences the
question asks for are *already determined* by `v0`, `D_R` and `D_T` — the run
does not discover them. That is exactly the `output_independent_of_input:
false` situation `bd_overdamped` is already declared under, and a new
configuration for free active particles would have to declare the same.

**This does not make the run worthless, and it does change what it means.** The
sweep is worth running as a check that the integrator, the estimator and the
crossover are right, the way `run-20260920-001` checked `bd_overdamped` against
Stokes-Einstein to 0.8 %. It is not worth running as a measurement of how the
dynamics depend on `v0` and `D_R`. **Interactions, confinement or crowding
would change that answer**, because then the output stops being fixed by the
inputs — and two of the questions opened today (`-001` and `-002`) are about
exactly such a system.

So the honest framing for whoever declares this: **the configuration's
`output_independent_of_input` is `false` if the active particles are free, and
the question of whether that is worth compute is the person's, not this seat's.**

## What unblocks it

In order, and all three are `contracts/` writes that `manager-simulation`
makes and this seat requests:

1. `contracts/quantities.json` — the six names, so check 60 can resolve them.
2. `contracts/observables.json` — the six entries, each with the estimator
   choice above pinned, `window_required` and `window_parameter` set.
3. `contracts/capabilities/simulation.json` — one new configuration with
   `produces[]`, `devices[]`, `executed_by`, and an
   `output_independent_of_input` ruling.

Then re-ask, and S3.0 has something to keep.

**One more decision is the person's and cannot be inferred:** whether the
propulsion is a fixed speed along the orientation or a fixed force with the
speed emerging. They are different models with different A7 cards, and the
declaration has to say which.

## Two notes on how this was recorded

**The qid moved.** This card was first written under `sim-20260923-001` and
that number was already `simulation-11`'s, committed at `9afc3ff` for a
different question. Five simulation seats share one working copy and nothing
allocates question ids, so the collision was mine to find and it was found by
reading the tree rather than by any check. Only this seat's own file was moved;
nothing of the other seat's was touched. `9afc3ff` keeps a copy of this card
attributed to `simulation-11`, and that is not repairable: rewriting history
would turn *someone who did not write it is named* into *nobody wrote it*.
It stays, and only the silence around it goes.

`manager-simulation` has since fixed the convention that makes this
structurally impossible: **window N takes `sim-YYYYMMDD-N01`, `-N02`, …**,
which stays inside the schema's three-digit pattern. It starts at the next
question; today's three keep the numbers they have, because moving this one
twice would be pure loss.

**The store was not consulted and `degraded` is empty anyway.** That is not the
`degraded: []` claim check 45 tests: the card carries no `caller_id` and no
`kb_refs`, because the refusal is deterministic over two files in `contracts/`
and no knowledge was asked for. A `caller_id` was not minted for it — the
launcher issues those, and inventing an issued-looking one is the specific
crossing recorded in the root `CLAUDE.md`.
