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

## The person ruled: fixed speed

Asked on 2026-09-23 whether the propulsion is a prescribed speed along the
orientation or a prescribed force with the speed emerging, the person answered
**fixed speed**. That was the one thing S2 could not decide, and it is now
decided. It is recorded in `goal.json` `constraint_notes[1]`, and the
declaration that acts on it is still a `contracts/` write.

**For this question as asked, the ruling changes nothing physical.** These
particles are free: no pair potential, no wall and no obstacle is part of the
question. For a free overdamped particle a fixed force `F` along the
orientation produces a velocity `F/gamma` along the orientation, of fixed
magnitude, so fixed speed and fixed force give the same trajectory. The two
models separate only when there is something to push against, because then the
fixed-speed particle holds its speed and the fixed-force one slows down.

So the ruling **pins the declaration** and **will matter to the interacting
questions** `-001`, `-002`, `-041` and `-042`. It does not change what this
run would compute. That is said here so a later reader does not take the
answer to have settled more than it did.

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

---

# Axis physics for `abp_free`, measured rather than asserted

*Added 2026-09-23 after the vocabulary and `abp_free` landed (`8a0d036`,
`389cdeb`) and S3.0 began keeping a candidate. Everything below is a property
of the declared model's closed form, computed here and checked numerically. It
is **not** a result about the world and **no run produced it.* The A1 bias
figures come from a scratch reference integrator, which is **not** the declared
backend; they bound a discretisation error, they do not measure a diffusivity.
This section moves into `src/configs/abp_free.py` when that file's interface is
settled, and lives here until then so it is on disk rather than in a message.*

## The question has three regimes, not two

The question asks for "the crossover from persistent or ballistic motion to
long-time diffusive motion", which reads as one crossover between two regimes.
The free model has **two crossovers and three regimes**, and the earliest one
is easy to miss:

| regime | where | log-log slope |
|---|---|---|
| thermal diffusive | below `tau_1 = D_T/v0^2` | 1 |
| ballistic | between | up to 2 |
| effective diffusive | above `tau_R = 1/((d-1)*D_R)` | 1 |

At the very shortest lags the translational noise dominates the propulsion,
because the distance propelled goes as `t` while the diffused distance goes as
`sqrt(t)`. So the MSD starts at slope 1, bends **up** toward 2, then bends back
down to 1. Reading the first resolved lag as "the short-time regime" gives
slope 1 and the wrong conclusion.

**The ballistic window is a factor `Lambda` wide in time**, where

    Lambda = v0^2/((d-1)*D_R*D_T) = peclet_number_thermal^2

because `tau_R/tau_1` is exactly that ratio. This is the same group that
collapses the whole curve, arriving a second way.

## That bounds what the sweep can show, before any run

The ballistic slope of 2 is a limit, approached from below and never reached.
How close depends only on `Lambda`:

| `Lambda` | 1 | 10 | 100 | 1e3 | 1e4 | 1e6 |
|---|---|---|---|---|---|---|
| max log-log slope | 1.12 | 1.47 | 1.79 | 1.93 | 1.98 | 2.00 |

Inverted, which is the form the person needs to pick ranges:

| to see a slope of | 1.5 | 1.8 | 1.9 | 1.95 | 1.99 |
|---|---|---|---|---|---|
| `Lambda` must reach | 12 | 112 | 492 | 2052 | 5.3e4 |
| `peclet_number_thermal` must reach | 3.5 | 10.6 | 22 | 45 | 230 |

**A sweep that stays below `Pe_thermal` of about 20 never shows a ballistic
regime at all**, whatever its resolution, because the regime is not there to
resolve. That is a fact about the model and not about the run, so no amount of
compute changes it.

## A1 -- integration stability

`tau_d` is **not** this configuration's shortest time and A1's present module
would use it. A free active particle has **no length**: no pair potential, no
wall, no obstacle, no diameter. So there is no displacement-per-step
constraint, and the only discretisation error is from holding the orientation
fixed across a step while it rotates. The inequality A1 owns here is therefore

    D_R * dt << 1

with `v0` and `D_T` absent. Measured, at `T = 5/D_R`, five seeds, 30000
particles, against the closed form:

| `D_R*dt` | 1.0 | 0.5 | 0.2 | 0.1 | 0.05 | 0.02 |
|---|---|---|---|---|---|---|
| relative bias | +12.1% | +2.9% | +0.61% | +0.45% | +0.12% | +0.02% |

Standard error is about 0.2%, so the bias is below the noise from `D_R*dt` of
0.05 down. **This makes A1's resolution factor a derivation and not a
judgement here**, which is a better position than `bd_overdamped` is in: that
module's docstring says its own factor "is a judgement rather than a
derivation" and enters as an estimate with a falsifier.

Two controls, and they are not the same kind of evidence:

- Varying `D_R` and `v0` together by a factor of 64 at fixed `D_R*dt` left the
  bias identical to five decimals. That is **not** an independent measurement:
  the problem is exactly scale-invariant under that rescaling, so identical
  numbers are what a correct scaling argument predicts. It confirms the
  reduction, not the bound.
- Varying `D_T` over four decades at fixed `D_R*dt` moved the bias from
  +0.603% to +0.621%, inside the standard error. That one **is** independent,
  because the noise draws change, and it is what rules `D_T` out.

## A3 -- finite size: abstains

**A3 has nothing to constrain for `abp_free`, and it abstains rather than
being pruned.** The declaration is one particle, no pair interaction, no wall,
no obstacle, unwrapped coordinates. A box exists because the engine needs one;
nothing physical depends on its size, and a non-interacting particle cannot
meet its own periodic image in any way the recorded coordinates see. An A3
card is still emitted saying so, the way A7's abstention is (§4.5.3).

This is worth stating because A3's present bound would compare a box against a
correlation length and return a number that looks like a constraint. For
`abp_wca_2d` A3 is real and the length is the persistence length `v0/D_R`, not
a correlation length.

## A4 -- sampling

The save interval has to resolve the **ballistic window**, not the diffusive
time. Sampling the closed form on a lag grid of spacing `S`:

| `S*D_R` | 2 | 1 | 0.5 | 0.2 | 0.05 |
|---|---|---|---|---|---|
| best slope recovered at `Lambda=1e4` | 1.41 | 1.63 | 1.79 | 1.91 | 1.97 |

against a true maximum of 1.977. So `S*D_R` of about 0.05 recovers the slope
to under half a per cent, and `S*D_R` of 1 loses a fifth of it.

**And the lower end matters too, which the upper bound alone hides.** The
first lag must sit below `tau_R` to catch the bend, and above `tau_1` to be in
the ballistic regime at all. At `Lambda=100` a first lag of `0.01/D_R` returns
slope 1.26 -- not an error, but the thermal regime correctly reported, which
looks like a failure if the three-regime structure is not expected.
