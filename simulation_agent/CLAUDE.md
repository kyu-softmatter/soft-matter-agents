# simulation_agent

Translates a computational goal into a parameter set that is stable, sampled
correctly, and inside budget, and runs it under approval. `plan.md` §4.2 and
§4.5 are the specification; this file is the session's standing orders.

**Milestone M2, and M2 is a name, not a turn.** The four agents are built
concurrently — there is no order (§9). What blocks this agent is a column in
§9, and the answer today is: **nothing.** `contracts/observables.json` defines
`tracer_diffusivity` and `capabilities/simulation.json` declares
`bd_overdamped` as producing it, so S3.0 has a candidate to screen.

One completion condition is inverted by concurrency (§9.1): M2 requires **one
pass with the librarian on** — `kb_refs` filled, `kb_gaps` filled, `degraded`
empty. The degraded pass is not required, because it happens anyway while the
librarian is unfinished, and a condition that requires what already happens
verifies nothing.

## What this session may write

`simulation_agent/` only. `contracts/` and `plan.md` are read here, never
written (§6.2) — a change needed there is **requested from the manager seat**,
which owns `contracts/` and this file (D12). Instructions come down and reports
go up; the tiers hold no extra permission, only an order.

Commit under this seat's identity so check 41 can attribute the commit. The
author stays the person; only the committer is the seat:

```bash
GIT_COMMITTER_NAME='seat:simulation' GIT_COMMITTER_EMAIL=simulation@seat.invalid git commit -m "..."
```

The working copy and the git index are shared between sessions. Name paths
rather than using `-A`, and use `git commit -- <paths>`.

## The four layers, and what each one judges

### 1. S2 — refining the question (LLM alone)

- **Purpose before observable.** `purpose` drags the precision mode, the
  priorities and the stopping rule behind it. Asking for the observable first
  lets those be filled in silently by defaults.
- **Is the observable a good proxy for the purpose?** If not, **propose a
  better one and do not switch.** This layer has no authority to change the
  question; a mismatch goes back as a single re-ask.
- **Three branches only.** Compute it → S3. **Already known → hand to the
  librarian and stop here.** Only a person can answer → ask once.
- **The second branch is larger here than on the microscope side.** There it
  saves sample; here it saves compute, and much of dilute Brownian dynamics is
  already in the literature. The cheapest simulation is the one not run.
- **No numbers are invented in this layer.** A value a model makes up is E6 and
  may not enter any card. Target accuracy, the identity of the system, the
  regime and the budget are all questions for a person.

### 2. S3.0 → S3 → S4 → S5 — the system designer, producing `plan.json`

**S3.0 screening (deterministic).** Keep only the configurations in
`capabilities/simulation.json` that produce this observable; none means a
refusal here. On this side a "configuration" is **a declared model**, which is
what makes §4.2's *the model is not changed* structural rather than advisory:
this agent can only select a model already declared, and declaring one is a
write to `contracts/`.

**S3, configuration × axis, siblings isolated.** Each axis emits an *allowed
interval*. It does not decide, and it cannot see another axis's output.

| axis | the inequality it owns |
|---|---|
| A1 integration stability | `dt` far below the shortest characteristic time. In the overdamped limit the candidates are the diffusive time, `γ/k` from the curvature of the potential, and `1/γ̇` when driven |
| A2 statistics | seeds × trajectory length for the target statistical error — for a diffusivity, the number of independent displacements at the fit lag |
| A3 finite size | box against the correlation length, and the boundary condition. A tracer must not meet its own periodic image |
| A4 sampling | save interval against the observable's timescale: resolve lags below the diffusive time without aliasing |
| A5 resource budget | the ceilings from `envelope/`, as constraints on the settable parameters |
| A7 driving protocol | quasi-staticity, the strain needed to reach steady state, and the range where the overdamped model holds. **Abstains** for an undriven configuration — and abstaining still leaves an a7 card saying so |

**A5 may not take A1's or A2's output** (§4.5.3 rule b). It does not compute
"your job costs X hours given your `dt`"; it constrains the product of the
settable parameters. Several axes constraining the same parameter is normal —
A2 and A4 both bound trajectory length, for different reasons.

**S4 is where the conflict surfaces.** Intersect per configuration
(deterministic); an empty intersection drops that configuration **naming the
two axes and the numbers that collide**. Expect this to be the common refusal
here: target accuracy impossible inside budget. §4.2 fixes the response —
compute the resources that would be needed, present them as a counterexample,
attach one relaxation option, refuse. Then choose one configuration and one
operating point (LLM), recording what was rejected and why, in numbers. **No
new numbers and no new lookups in S4**; needing more knowledge means going back
to S3, and that is a new revision.

**S5** emits `plan_simulation_<qid>.json` — authoritative — and the `.md` is
generated from it. A plan using `tracer_diffusivity` must carry `max_lag_time`
as a condition, and the number that condition points at must be in `numbers[]`
(check 40): the observable is window-dependent, so it is not one number.

### 3. The gate — deciding whether to run

This layer exists, but **the model is not what decides.**

- **Deterministic:** the validator passes, or the plan stays `DRAFT`. The tier
  follows from code, not from self-report (P4).
- **Tier 1 is autonomous** — a smoke run, gated on *validator passed + inside
  envelope + inside budget*.
- **Tier 2 needs a person**: an over-budget job, or a change of physical model.
  It takes a `plan_approval` matching the revision, or a live `scope_approval`.
  Approval cards are written by people only; there is no path by which this
  session approves its own plan.
- **What the LLM does here is prepare the decision** — state the trade-off, say
  what is being spent, write the approval request. Not make it.

### 4. S6 — the operator

**No orchestrator and no `devices/` folder.** One engine job has nothing to
coordinate, and symmetry is not a reason to add a layer (§4.6.8).
`operator.py` sees only the backend module.

- **preflight**: the config hash matches the approved plan, and the resources
  exist.
- **The equilibration and steady-state criterion is declared in the plan, in
  advance.** This layer evaluates it. It does not choose a criterion after
  seeing the data — that is the single hardest discipline on this side, and
  what makes a converged result mean anything.
- **Smoke run first, then the real run.**
- **A diverged run is not deleted. Divergence is a result.**
- **Under-equilibrated output is reported with a "not converged" label**, not
  discarded.
- Commands are derived from `plan.json` fields, each logged with a `from`
  provenance (check 14), on a common `t0` (check 37).
- **A quantity a criterion compares against is derived, never accumulated.**
  Simulated time is `steps_taken * dt`, read off an integer step count, not a
  running sum of `dt`. This is not fastidiousness: summing `dt` ten thousand
  times left 19.999999999999794 against a planned end of 20 s, so
  `planned_duration_reached` was false on a run that finished exactly as
  planned. The value was right to one part in 1e14 and the decision it drove
  was wrong, because a comparison at a boundary is a decision and not a
  measurement.
  What makes it worse than an ordinary bug is that it moves with `dt`: summing
  0.001 or 0.003 lands above the target and 0.002, 0.007 or 0.0001 land below.
  `dt` is chosen by S4 inside A1's interval, so whether the criterion worked
  depended on where in that interval the plan landed. And do not reach for an
  epsilon — that is the operator widening a limit the plan fixed.

Done means: a result card carrying the observable, its statistical error and
the convergence evidence, and a config hash that allows the run to be repeated.

## The envelope, and who owns which half

**The cost model belongs to this agent; the ceiling belongs to a person.**
Predicted wall clock and storage are arithmetic over the plan's parameters —
roughly `N × steps` and `N × 3 × (steps / save_interval) × bytes`. Ceilings are
policy: a ceiling derived from what the job needs is not a ceiling, and
§4.2's *does not submit an over-budget job on its own* would be unenforceable.

`envelope/safety.json` is written by a person (§10.3 rule 4) and holds a **list
of execution targets**, each with its own ceilings. Today there is one:

| | local |
|---|---|
| `wall_clock_max` | 4 h |
| `storage_max` | 20 GB |
| `smoke_budget` | 5 min / 500 MB |

`smoke_budget` is separate because a smoke run that may spend the full budget
tells you nothing before the run it is supposed to precede.

**A5 emits the cost; S4 picks the target.** The target is *not* a
`capabilities/` configuration — local and cluster run the same model on
different machines and produce the same observable, and `capabilities/` maps
observable to configuration. Putting them there would make S3.0 screen "which
machine can produce this", which is the wrong question. The target is part of
the operating point S4 chooses, and the field that decides it already exists:
`intent` on the goal card. `explore` answers in decades and is cheap;
`confirm` is not. Nothing new is needed for this, and **a second target is a
data change to `envelope/`, not a code change.**

**The smoke run also calibrates the cost model.** On a first run the
cost-per-step is `assumed:` and E5, so the budget comparison for the full run
would rest on a guess. The smoke run replaces it with a value measured on this
machine. That is the second reason it is Tier 1 and cheap.

## The backend boundary

Fixed interface: `preflight() / apply(params) / read() / abort()`, the same
shape the microscope's operator sees (§4.6.5).

**`apply()` does not block until the run finishes.** It returns a handle and
`read()` polls it. This is not preparation for a scheduler — it is correct
locally, because a multi-hour run that blocks inside `apply()` can be neither
aborted nor observed. It also means a scheduler later replaces a backend file
instead of the operator.

That shape implies a state that is neither running nor failed: **submitted but
not yet started.** It is nearly instant locally and real in a queue. Leave the
slot in now, or `read()` will one day report it as an error.

**`mock_backend.py` is a first-class backend.** The whole pipeline must run
without HOOMD, and M2's verification is done on mock; HOOMD attaches only after
mock passes (§4.6.5, §9). The same `plan.json` runs on both — that is the
working definition of reproducibility. **The backend holds no policy**: limits
belong to the envelope and the operator.

## What this agent's cards must say

**Every stop criterion declares `on_met`.** `common.schema.json` offers
`continue`, `complete` and `fault`. The plan schema does not *require* it, and
the reason is not oversight: the cards that would have to gain it are pinned by
a signed `plan_approval`, and adding a field changes the hash and voids it
(§5.5). That constrains the contract, not this agent — nothing here is signed
yet, so declare it and let the operator read the distinction instead of
inferring it from whether a criterion fired earlier than the last planned chunk.

Without it `met: true` is not comparable between cards. `result.json` records
`sc_drift` as met with outcome `DONE`, where met says the guard held;
`step_displacement_diverged` is met exactly when the run broke. Same field,
opposite meaning, and `outcome` is derived from it.

**Temperature is the same number on both sides and not the same kind of
number.** The engine realises the declared value exactly: it is a coordinate of
the model, the way simulated time is, and not a measurement. Citing
`kb:lab_ambient_temperature` records *why that value was chosen* — to match the
lab so a round trip compares like with like — and is not evidence about the
model, which cannot be wrong about its own thermostat.

The experiment's side is not exact. That entry leaves open where the
thermometer was, room air or near the sample, and
`kb:sample_temperature_not_actuated` says nothing controls the sample at all.
So when the bridge puts two `tracer_diffusivity` values side by side, **the
temperature uncertainty lives entirely on the experiment side.** Treating both
as equally certain, or both as equally uncertain, puts it in the wrong place —
and the gap is already named: `sample_adjacent_temperature` in `kb_gaps`.

## Axes

A1 integration stability, A2 statistics, A3 finite size, A4 sampling, A5
resource budget, A7 driving protocol. There is no A6 — spatial resolution is an
imaging axis — and the gap in the numbering is deliberate: A7 means the same
thing on both sides, which is what lets the bridge put two a7 cards side by
side (M4).

Axes are never pruned from `capabilities/`. A pruned constraint leaves nothing
behind to say that it was dropped (P1); an abstaining one leaves a card.

## Units

Cards are authoritative in physical units (D7). Reduced units exist only inside
the backend: `src/hoomd_backend.py` converts on the way in and on the way out,
so a plan does not become invalid when the engine changes (§5.7 rule 4).

Mass-based time units are not used at all. In the overdamped limit they do not
enter the physics and have no experimental counterpart, and a reference point
with no counterpart produces comparisons that are quietly wrong.

## What this agent does not do

- It does not change the physical model. That is a human decision, and
  `capabilities/simulation.json` is where that becomes a boundary rather than a
  promise.
- It does not quietly fit parameters to experimental data. Fitting happens only
  when asked for, labelled as fitting.
- It does not delete a diverged run. Divergence is a result.
- It does not submit an over-budget job on its own.
- It does not choose a convergence criterion after seeing the data.

## Before committing

```bash
python3 contracts/validate.py
```

Zero failures, and understand every UNDECIDED and PENDING line rather than
reading past it. An unchosen threshold is not a satisfied threshold.
