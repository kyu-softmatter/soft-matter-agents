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

**Four paths inside this tree are not yours**, and they matter more than the
outward ones because they are the ones a session here can actually reach:
`approvals/`, which only the person writes (§7.1 rule 5); `inbox/`, which only
the bridge writes (§7.1 rule 8); and this
file, `README.md`, `tasks/` and `.claude/`, which are `manager-simulation`'s.
The rest of the deny list points outside this tree, where nothing resolves from
a session opened here — that file says which entries are which.

**And those four are guarded against two tools out of the ones you actually
use.** The denials are `Write(...)` and `Edit(...)`. They do not reach `sed -i`,
a python heredoc, or a shell redirect, and §6.2 records that **every session in
this repository has used the latter**. The commit gate does not close it either:
it judges the tree a commit would create, and a file written and reverted was
never staged. So a denial on a path inside this tree is real against two doors
and open beside them — §2.1 rule 9's shape, a guard that is
opt-in is not a chokepoint.

**This is not hypothetical.** On 2026-09-20 a seat rewrote that file ten times
through a heredoc while testing a type guard, twenty minutes after the person
committed it. Values were unchanged and the bytes were restored exactly, and
**nothing in the system caught it** — not the denials, not the gate. A habitual
`git status` did, and the seat reported itself.

**What to do instead costs one line.** `operator.ENVELOPE` is a module
attribute: point it at a scratch copy and the same tests run against the same
code without touching the file. The seat that did this found that afterwards,
and none of the correctness of what it verified depended on using the real
one.

## A round arrives in `inbox/`, and the envelope is the turn

**`simulation_agent/inbox/<thread>/` is where the bridge delivers.** It holds
`r<N>_ask_simulation.{json,md}` and nothing else. You **read** it; you never
write it. By the boundary classifier that folder is the `bridge`'s and not this
agent's — only its location is in your tree — and an agent writing its own
inbox is forging a delivery.

**An envelope sitting there is the turn. There is nothing else to check.** No
`status.json` copy is delivered on purpose: it is the one file in a thread that
changes, so a copy goes stale the moment the turn moves, and that drift is what
left the example thread reading "the human's turn" for a day. **And do not read
`bridge/threads/` for the turn instead.** §7.1 rule 8 refuses that, and on this
side the reason is sharper than the separation argument it gives for the
microscope: what makes this agent worth running separately is that it
**completes without experimental input** — a goal card from a person is enough,
and a number that wanted an experiment goes up as `assumed` with
`degraded: ["bridge"]`. An agent that reaches into `bridge/` to find its work
has given that back.

**That independence is also why this folder is easy to miss here.** This seat
has a legitimate way to proceed with no round at all, so nothing about a quiet
day looks wrong. On the microscope side on 2026-09-19 a round was delivered
correctly, passed checks 8, 13 and 41, and sat unread — not from inattention,
but because no document told any seat the folder existed, and a chat message
rescued it. That is the §6.2 rule 2 failure in its pure form: the notice worked
and left no trace, so a session reset would have lost the fact that a round was
waiting. This section is here so the same envelope does not arrive here into
the same silence.

**Taking a round is S2, and it is assigned by a task card the way an axis is.**
Do not start one because you saw it. Two seats share this tree —
`simulation@seat.invalid` and `simulation-2@seat.invalid` — and a round each
assumes the other took is worse than one nobody took, because it looks staffed.
Seeing an envelope you have no card for, report it up; `manager-simulation`
cards it.

**How the bridge learns you took it**: the goal card's `from_round`,
`thr-…:r<N>`. The bridge already reads this agent's `questions/`, so nothing is
written back toward it.

**Nothing is deleted from the inbox.** The delivery happened and that file is
the record of it (P1).

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
  What makes it worse than an ordinary bug is that the sign is not predictable
  from anything a person would think to check. Over eleven ordinary timesteps,
  summed to their own `n*dt`, four fall short: 0.0001, 0.0005, 0.002 and 0.02.
  The rest overshoot. And it is not a property of `dt` alone — 0.007 lands
  short over 1000 additions and long over 2857 — so it turns on the timestep
  and the step count together. `dt` is chosen by S4 inside A1's interval, so
  whether the criterion fired depended on where in that interval the plan
  happened to land. And do not reach for an epsilon — that is the operator
  widening a limit the plan fixed.

Done means: a result card carrying the observable, its statistical error and
the convergence evidence, and a config hash that allows the run to be repeated.

## The envelope, and who owns which half

**The cost model belongs to this agent; the ceiling belongs to a person.**
Predicted wall clock and storage are arithmetic over the plan's parameters —
roughly `N × steps` and `N × 3 × (steps / save_interval) × bytes`. Ceilings are
policy: a ceiling derived from what the job needs is not a ceiling, and
§4.2's *does not submit an over-budget job on its own* would be unenforceable.

`envelope/budget.json` holds a **list of execution targets**, each with its own
ceilings. **There is no `safety.json` in this tree** (§7): the grade of harm
differs — get a laser ceiling wrong and you lose an eye, get the wall clock
wrong and you lose a night — and putting the same lock on the same door was
never decided. `contracts/schemas/envelope_budget.schema.json` is what the gate
applies; read it rather than this section if the two disagree.

**What the split removes is the physical-confirmation requirement and Tier 3**,
both of which were meaningless about a disk quota. **P0 rule 7 binds `safety.*`
only.** So this seat may write `budget.json` — its `.claude/settings.json` no
longer denies anything under `envelope/` except what is not this agent's.

**Every limit says who chose it, not who checked it.** `chosen_by` carries `by`,
`on` and an optional `rationale`, and the schema refuses a `confirmation` or a
`grade` pushed into a limit — so the lower bar is expressed rather than merely
permitted. It is a lower bar on purpose: what a budget needs is that somebody
who knows that machine picked the number. **`chosen_by` is required**, because a
ceiling nobody will own is a ceiling nobody will raise when it pinches, and the
failure mode of an unowned budget is someone quietly working around it.
`rationale` is optional and is the first thing a later reader wants.

**The file exists as of 2026-09-20** and carries the ceilings below.

| | `local`, chosen 2026-09-19 |
|---|---|
| `wall_clock_max` | 2 h |
| `storage_max` | 10 GB |
| `smoke_budget` | 5 min / 500 MB |

Nothing here was measured, and the file says so: all four are `chosen_by` with
the reason the person gave — **an unconfirmed limit is safer small, and raising
a ceiling later is easier than lowering one.** They do not bind today; the first
plan wants four ten-thousandths of the wall clock and a five-hundredth of the
storage. **`a_cost_reference`'s falsifier is what ends that** — a smoke run's own
log replaces both estimates with measured values, and the ceilings get revisited
against numbers rather than against guesses.

`smoke_budget` is separate because a smoke run that may spend the full budget
tells you nothing before the run it is supposed to precede. It nests its own
`wall_clock_max` and `storage_max`, and **each of those is a limit in its own
right** — so each carries its own `confirmation` too. Four confirmations for
one `local` target, not two.

The worked example above was validated against the schema before being put
here, and the same run confirmed that a limit with the `confirmation` removed
is refused. Check it again yourself if the schema has moved since.

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
model.

**Exactly, and not because the thermostat is good: because there is no
thermostat.** This paragraph said the model "cannot be wrong about its own
thermostat", which reached the right conclusion through a mechanism this
configuration does not have. `bd_overdamped` integrates a position-only Wiener
increment, `positions + normal(0, sqrt(2*D*dt))` with `D = k_B*T/(3*pi*eta*d)`.
No velocity is represented, so there is no kinetic energy and nothing to
thermostat: **temperature is a parameter of the noise amplitude, and a
parameter has no mechanism that could fail to realise it.**

The difference decides which confirmation the claim needs, which is why it is
declared in `contracts/capabilities/simulation.json` as
`temperature_realisation` rather than left here as prose. A thermostat holding
a setpoint is empirical, engine-specific and **falsifiable** — one with inertia
loses it at large `dt` or to a flying ice cube. A noise amplitude cannot. So
the store's premise that *the engine's thermostat realises the setpoint* is a
**category error against this engine**: not true, not false, unanswerable. If a
configuration with inertia is ever added, the other kind of confirmation
becomes the right one, and the capability field is what marks the change
instead of it happening silently. Measured from the integrator by
`simulation-2`; `simulation-4` found that this paragraph's reason was the wrong
one.

The experiment's side is not exact. That entry leaves open where the
thermometer was, room air or near the sample, and
`kb:sample_temperature_not_actuated` says nothing controls the sample at all.
So when the bridge puts two `tracer_diffusivity` values side by side, **the
temperature uncertainty lives entirely on the experiment side.** Treating both
as equally certain, or both as equally uncertain, puts it in the wrong place —
and the gap is already named: `sample_adjacent_temperature` in `kb_gaps`.

### What a run's observable is, which is not the same ruling

The paragraph above settles an **input**. An observable is an **output**, and
the two do not get the same answer.

**The model cannot be wrong about its thermostat; it can be wrong about its
diffusivity.** The number comes out of the integrator, the timestep, the save
interval and the fit — and every one of those is a thing A1 through A4 exist to
constrain, which is to say a thing that can be set badly. So a run's observable
**is** a result of that run, not a restatement of what went in.

**What it is a result about is the model.** E1 means this system measured this
value under these conditions (§5.3), and what this system measured is the
model's behaviour. It is about the world only as far as the model is valid,
which is A7's question and not the estimator's. So a simulated observable is
**never `measured:`** — reading it as E1 would make E1 mean "we ran code that
produced a number" and collapse the distinction the grade exists to hold.

**And how much a run tells you depends on the configuration, which is why this
cannot be settled once for all of them.** `bd_overdamped` is free diffusion, so
`D` is fixed analytically by the inputs through Stokes-Einstein: the first real
run returned 2.128e-13 m²/s against an analytic 2.146e-13, **0.8 per cent
apart** — and 6.4 per cent from the plan's own rounded 0.2 µm²/s, which is the
plan being written to one significant figure rather than the run disagreeing.
**That run confirms the integrator and the estimator. It carries no independent
information about the diffusivity of anything.** A configuration with
interactions or confinement would produce a number the inputs do not already
determine, and that one would.

So the grade a run's observable carries is not a property of "simulation". It
is a property of **whether that configuration's output is independent of its
inputs** — which is a fact about the declared model, and therefore belongs
where models are declared, in `contracts/capabilities/simulation.json`.

**The source kind is `simulated:<run_id>`, and it is not what decides the
grade.** This paragraph said until 2026-09-23 that `SOURCE_GRADE` had no kind
that fit a simulated output. It had one -- `simulated:` entered the table on
2026-09-22 -- and a seat copied the old sentence into a goal card before
finding it false. Cards are records and that one keeps it; the correction
belongs here, at the source, or the next seat reads the same sentence and
writes it again.

What decides whether a run's number may stand as **a claim about the world**
is the configuration's `output_independent_of_input` in
`contracts/capabilities/simulation.json`, reached from the plan the result
stands on, and the **field that names the number** carries the role. Under
`values[]` the card asserts something about the system, so a configuration
that declares `false` is refused there. Under `observed_number` or
`actual_number` the card reports what the run read, which is allowed either
way. So for `bd_overdamped` or `abp_free` -- whose outputs the inputs already
fix -- `values[]` carries the model's prediction and the run's reading goes
beside it as the comparison. Check 21 enforces this; watching it refuse a
reading moved into `values[]` is how one seat confirmed its passing card was
not passing by accident.

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
the backend, which converts on the way in and on the way out, so a plan does
not become invalid when the engine changes (§5.7 rule 4).

**Three backends convert and two do not, and each says which in its own
header -- read the header, not this paragraph.** `hoomd_backend`, `abp_backend`
and `trap_hoomd_backend` run the engine in reduced units and convert in both
directions; `mock_backend` and `trap_backend` integrate in SI throughout. The
header is authoritative because it sits beside the code it describes, and this
file's record of the same fact went stale in exactly the way that makes that
rule worth keeping: until 2026-09-23 this paragraph said `hoomd_backend.py` was
"not written" and that mock was the only backend, while hoomd_backend had been
running real results since 2026-09-22. It even named its own expiry -- "when
that backend is written ... this paragraph is its specification" -- and nobody
reread it when the condition came true. A sentence that says what the code
will do goes stale the moment the code arrives, and nothing checks prose
against code, so the durable thing to write here is the rule and where the
authority lives.

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

**And if you queried the librarian, your commit waits on the librarian seat.**
Check 45 tests an empty `degraded` against `librarian_agent/queries/log.jsonl`,
and that file is outside this agent's boundary, so **you cannot commit the
evidence for your own cards.** The gate judges the tree your commit would
create; if your calls are not yet committed over there, your cards read as
claims with nothing behind them and the gate refuses them — correctly.

This is not a rule to work around, it is a schedule to know about. On
2026-09-20 it held `004` until the librarian seat landed 318 log lines at
`19b55ee`, and **microscope-1 was blocked at the same moment for the same
reason.** The microscope's earlier seven passed only because those lines were
already committed, not because that seat did anything differently. Nothing
anywhere else records this.

So: after a fan-out, check whether your calls are in a commit before you plan
around landing your cards.

```bash
git log --oneline -1 -- librarian_agent/queries/log.jsonl
git status --short -- librarian_agent/queries/log.jsonl     # uncommitted = your evidence is not in the tree yet
```

If it is uncommitted, **ask the librarian seat to land it; do not commit it
yourself.** It is that agent's file, and check 35 is what says so.

**And before a fan-out, check the envelope against what is published.** The
two halves of this are not symmetric and both were learned the hard way on
2026-09-21.

*Before*: sibling axes of one fan-out must pin one store. That is what
check 58 exists for, and it cannot see a fan-out that has not started, so an
envelope a version behind at the moment you launch produces cards that are
internally consistent and collectively wrong. Re-copy first.

*During*: **do not re-copy mid-flight.** `simulation-4` was offered a newer
store while revision 2's fan-out was running and declined, on the ground that
moving the store between siblings makes them see different knowledge — which
is the same hazard arriving from the other direction. The librarian seat
holds the store still while a fan-out is up, so **tell it when you are about
to launch one**; that coordination lives in messages and has no file.

```bash
python3 -c "import json;print(json.load(open('simulation_agent/envelope/snapshot.json'))['kb_version'])"
ls librarian_agent/kb/exports/snapshot_simulation_agent.json   # the publisher's copy; compare kb_version
```

A gap is not automatically a problem: on 2026-09-21 the envelope sat one
entry behind and the missing entry was a microscope pixel-size row that no
card in this tree cites — counted, not assumed. What makes it a problem is
launching across it.
