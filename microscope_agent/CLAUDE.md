# microscope_agent

Designs the conditions under which a given observation goal can actually be
measured on this instrument, and carries out the measurement under approval.
`plan.md` §4.1 and §4.5–4.6 are the specification; this file is the session's
standing orders.

**Milestone M1, built concurrently with the other three** (§9, changed
2026-09-17). There is no order, so do not wait for the librarian. This agent is
blocked on the observable vocabulary (§11-1) for screening and on a
human-written `envelope/safety.json` for execution, and on nothing else.

Two consequences. The librarian's service may arrive at any point, so both the
degraded and the normal path have to work from the start. And one pass with the
librarian **on** is a completion condition — `kb_refs` filled, `kb_gaps` filled,
`degraded` empty — because built concurrently it is the normal path, not the
degraded one, that risks never being walked (§9.1).

## What this session may write

`microscope_agent/` only. `contracts/` and `plan.md` are read here and written
by the design session (§6.2). The permission rules in `.claude/settings.json`
enforce that rather than relying on restraint, and check 35 catches a commit
that crosses the line.

## Where knowledge comes from

Not from here. This agent keeps **records** (`questions/`, `runs/`) and
**policy** (`envelope/safety.json`), never a knowledge store of its own (P14).

**The normal path.** The librarian publishes to `librarian_agent/kb/exports/`
and cannot write here (D11), so **this session copies the export into its own
`envelope/snapshot.json`**. The copy is deliberate: which KB version entered
this agent's envelope, and when, is then a fact in this agent's own commit
history. Check 26 compares each entry against the store by hash, so the copy
cannot silently diverge.

Query the service for anything a plan needs, and record both halves of the
answer. `kb_refs` holds what came back. **`kb_gaps` holds what was asked for and
did not** — with where it was looked for. An estimate made while the librarian
was reachable must name the gap it stands on (check 39), because
looked-for-and-absent and nobody-checked are not the same number.

**The degraded path, which must be walked at least once.** When the service is
unreachable, read the store's files directly — `kb/entries/` for atomic claims,
cited as `kb:<entry_id>` with the grade the store gives and never a better one
(check 21), and `kb/staging/` for the flat device and optical-path tables the
librarian has not decomposed yet (§11.1). Cards then carry
`degraded: ["librarian_agent"]`, which means *we do not know what we missed*:
no gap detection, no conflict detection, no external search.

§9 makes one such pass a completion condition for this milestone rather than an
accident of ordering. A degraded path nobody walks is a branch that stops
working without anyone noticing.

## Taking anything from the prior project

`agentic-microscope` has two branches, `main` and `version2`. The operator
asked for both, and attached the condition that makes it safe: **nothing is
transplanted as it stands.** Anything that claimed more than it knew is
trusted less here, and anything that does not help is dropped.

**Read the difference between the branches before reading either branch.**
What changed from `main` to `version2` is a record of what did not work the
first time, and it is the one reading that gives the most while inheriting the
least. A structure read whole is a structure adopted.

**`plan.md` §10.2 says which rows are open.** Go and read it; it is not copied
here, because two copies of a table drift and the drift is silent. A row is
open when our counterpart is frozen, not when a milestone arrives.

Every item that crosses is judged before it is written anywhere, into one of
three:

| | |
|---|---|
| **transfer** | It is a formula or a decision criterion that A1–A7 has a slot for. It is **rearranged into that slot**, not pasted. Numbers attached to it pass §10.3. |
| **downgrade** | Useful, but stated over there with more confidence than its source carries. A bare assertion becomes E5 and gains a falsifier. A calibration constant with no `run_id` of ours is E3 at best (§10.3 rule 1). A value a model produced is E6 and **enters nothing** (P2). An action whose state cannot be read back here is not automated here, whatever it was there — it goes to a manual sheet and needs an individual approval (§4.6.6 rule 5, §6.1). |
| **drop** | No slot in A1–A7; or it exists only as prose (§10.3 rule 3); or it is a safety limit, which never transfers at all (§10.3 rule 4). |

**The discriminator: a transferred item names the A1–A7 slot it lands in and
the §10.3 rule it passed.** An item that cannot name a slot is dropped. That
is what "not transplanted as it stands" means in a form a reviewer can check,
and it is why our decomposition has to be the thing that survives: an item
that will not fit it does not come.

One precedent, already caught: the prior project's `20.078x`. A nominal
magnification wearing a value back-derived from a calibrated pixel size — a
designation given a precision it never had. §5.3's nominal-designation rule
now refuses it, and the device registry records why. Expect more of that
shape, and downgrade rather than argue with it.

## The pipeline, in order

S2 refines the question (LLM alone, **no numbers invented**) → S3.0 screens
configurations against `capabilities/` → S3 fans out over configuration × axis,
siblings isolated → S4 intersects per configuration and chooses → S5 emits the
plan → a human approves → S6 executes. §4.5 and §4.6.

Two boundaries inside that are not negotiable:

- The **system designer** (S3–S5) holds Tier 0 only. It plans; it does not run.
- The **operator** (S6) is the only part with Tier 1–2, and on the normal path
  it is pure Python. Commands are derived from `plan.json` fields, each logged
  with a `from` provenance field. The model interprets what the plan did not
  foresee, and writes the deviation report, after the abort has happened.

## What is unbuilt, and in what order

Both ends of the pipeline stand and the middle is empty. `src/` holds
`screening.py` (S3.0) and `operator.py` / `orchestrator.py` / `devices/`
(S6). **S3, S4 and S5 do not exist.** `questions/` is empty, so no card has
ever been produced here.

**The bridge is waiting on one `plan` card**, not a result. An envelope
carries a `plan` or a `result` (§4.4), so the first round trip needs no
execution, no `envelope/safety.json` and no approval. S5's output is enough,
and that is the shortest path to a working round.

**0. Done (`ace46ff`) — the contrast discriminator.** Kept here as the record
of what was wrong, because the middle one is the kind that would have passed
review: three mismatches, and only one of them visible.

- The code tests `"contrast" in configuration` and reads
  `configuration.get("contrast")`. The field capabilities actually declares is
  **`requires_contrast`**. Today that mismatch is inert: the test is always
  false, the term is recorded as not evaluable, and the cap stays unresolved.
- It reads the sample's side from `goal["sample"]["contrast"]`. What the goal
  card should carry is **`sample_contrast`, a list**, because a sample offers a
  set rather than a single mechanism.
- **It compares with `==`, and that is wrong in a way that hides itself.** A
  fluorescent bead still has refractive contrast, so it satisfies
  `label_free` too. Equality against `"fluorescence"` keeps the three
  fluorescence configurations and drops `transmitted` — three, inside the cap,
  so the cap reads as resolved and the fan-out proceeds one candidate short.
  A configuration was removed on a comparison that was never about capability.
  The rule is **membership**: a configuration survives when its
  `requires_contrast` is in the sample's set.

With membership and a fluorescent sample all four survive, the cap stays
unresolved, and a person picks once (§4.5.1 branch c). That is the correct
outcome and it is worth stating plainly: on this instrument the contrast field
cuts only for label-free samples. It was never going to cut for every question,
and a cut that appears for the wrong reason is worse than no cut.

**0b. Done (`693ce13`, `5500639`) — the operator's tie-break.** The cap stops on a fluorescent sample because all four configurations stay
valid, and §4.5.1 branch (c) resolves that by asking the person once. It has
been asked: **`widefield_inline`**.

That answer is carried on the goal card as **`configuration_preference`, an
ordered list**, and S3.0 uses it **only when the cap is unresolved**. It is a
tie-break, not an instruction. A configuration the screen rejected on
capability stays rejected — if a preference names something that cannot
produce the observable, or that the vocabulary or the composition test threw
out, the screen refuses rather than honouring it. Otherwise a goal card could
route around the one stage whose whole job is to say what the instrument
cannot do.

**A human tie-break is not evidence.** It settles which of several capable
configurations to spend the fan-out on, and it justifies nothing inside the
plan: it raises no grade, supports no number, and is not an assumption with a
falsifier, because there is nothing to falsify in a preference. S4 must not
cite it. What it does deserve is a record — the reason behind this particular
pick was not given, and `configs.json` should say that the cap was resolved by
preference rather than by a discriminator, so M5 can tell the two apart later.

**Start here → 1. S3, the seven axes.** §4.5.3 defines A1–A7; read it there rather than
from a copy. Each axis states a **range** and never a point — choosing inside
it is S4's, and an axis that chose would produce as many plans as there are
axes, none combinable. An axis with no grounds abstains and says why (P5); it
does not guess. A1 and A7 have the most already available: the disk-period
constraint is an entry, the objectives carry NA and working distance, and A7's
escape inequality is the one row §10.2 leaves open for transfer.

**1b. A7's formulas, already ruled (§10.2.1).** `agentic-microscope`
`version2` was read for the axis row only. Every item below names the slot it
lands in and the §10.3 rule it passed; anything that could not name a slot was
dropped, and the dropped list is as much of the result as the kept one.

| | item | slot / rule |
|---|---|---|
| transfer | `gamma = 6*pi*eta*a`, Stokes drag, unbounded medium | A7 — a formula, no number crosses |
| transfer | `x_eq = gamma*v/kappa`, and its inverse `v = x_eq*kappa/gamma` | A7 — **this is our escape relation**, generalised |
| transfer | `x_min = sigma_loc / target_relative_error` | A7 — the floor, derived from the target, not chosen |
| transfer | `settling = ln(1/target)` time constants | A7 → feeds A5 as an input, not as A5's own bound |
| transfer | `f_c = kappa/(2*pi*gamma)`; sampling needs `f_s >= 10*f_c` | A7 — rule (a): `kappa` ties it to the escape inequality |
| downgrade | `U/kT >~ 10` for stable trapping | A7, **E5 with a falsifier**. Its own source calls it a rule of thumb; it is not a gate constant |
| downgrade | water viscosity, CRC table 0–40 C | knowledge, not code (P14). Cite the CRC Handbook, not the prior repo (§10.3 rule 2), capped E3. `water_viscosity_293k` already holds it |
| drop | the seven parallel `gate.py` / `checks.py` / `cli.py` / `setup.py` packages, `LIMITS`, `TrapSetup` | no slot in A1–A7. Our axes are functions that emit a card, not lenses with their own gate and CLI |
| drop | trap-heating and room-vs-focus temperature decisions | already ours: `lab_ambient_temperature` and `sample_temperature_not_actuated` |

**What version2 added over main is the whole point.** `velocity/` does not
exist on `main`; it was written second. So the thing the first attempt lacked
was **motion**, and adding it turned a one-sided escape bound into a window:

```
   x_min * kappa / gamma   <=   v   <=   x_max * kappa / gamma
   └ offset must be resolvable      └ beyond this the bead leaves
```

That is what an axis is supposed to emit — a range, not a point — and it
arrives already in that shape. Keep the shape.

**Two limits come across with it, and both must be said out loud in the card.**
The drag is the unbounded-medium value: near the coverslip the real `gamma` is
larger, and the prior project decided not to correct it by formula but to
absorb it by calibrating in situ, because a measured corner frequency returns
`kappa` and the wall-corrected `gamma` together. And `x_max` is bounded by
where the ray-optics model stops being defined, not by where a bead actually
escapes — so it is a **lower** bound on the true limit.

**Not taken, and worth knowing it exists**: the ray-optics `trap_force` model
that predicts `kappa` from beam geometry. It would let A7 state a `kappa`
where the store has none, at E5 with a falsifier. It is a whole model and the
first plan card does not need it. Decide it separately rather than letting it
arrive as a side effect.

**2. S4, the intersection.** Per configuration, intersect the axis ranges and
choose inside the result, recording why. An empty intersection is a refusal
with the numbers that emptied it, not a shrug.

**3. S5, the plan.** One card. Its `observable.name` must be an id in
`contracts/observables.json`, and because both current observables have
`window_required`, the plan carries the window as a condition or check 40
rejects it. `thread` is `solo-<qid>`; the bridge adds its own prefix. Raise
`revision` on any edit — the ledger matches on `(card_id, revision, hash)` and
an edit under the same revision stops a round that has already gone out.

The sample's contrast is a fact about the experiment, not about the
instrument: it belongs in the goal card's `sample_contrast` with a source and a
grade, not in this file and not in the knowledge store.

## The control paths, ruled (§10.2.1)

That row of §10.2 is open and does not wait for `envelope/`: rewrapping a call
needs no safety limit. Numbers are a different row and still closed.

`agentic-microscope` `hardware/` is **byte-identical on `main` and
`version2`**. The layer that changed between attempts was the lens layer above
it, not this one — so this is the settled part of that project, and the part
worth reading.

**Only three channels have a driver of their own.** Cameras, the confocal
unit, the DMD and the widefield sources are all reached through Micro-Manager
configuration files, not Python. That is an independent corroboration of our
registry: the channels we record as `read_back: false` are exactly the ones
that escape Micro-Manager.

| our channel | theirs | wraps into |
|---|---|---|
| `stand_ti2e` | `microscope.py`, `focus.py` | Micro-Manager; read-back is real |
| `piezo_stage` | `piezo_stage.py`, `piezo_waveform.py`, vendor DLL | its own driver, readable |
| `optical_tweezers` | `optical_tweezers.py`, `tweezers_drive.py` | TCP text to a GUI, **not readable** |
| `laser_combiner` | `lunf_power.py` | its own driver, **not readable** |
| cameras · `confocal_csuw1` · `dmd` · widefield | `config/micromanager/*.cfg` | Micro-Manager; no wrapper to write |

**Never accumulate a duration to compare against a planned limit.** The
simulation seat found this in its own loop: adding a timestep ten thousand
times gave 19.999999999999794 against a planned 20, and a run that finished
correctly reported that it had not reached its planned duration. The error is
1e-14 and no physics cares -- but the number was not being used as a value,
it was sitting on the left of a `>=`, and **a comparison at a boundary is a
decision, not a measurement.** The size of the error and the size of the
consequence are unrelated.

It is worse than a bug that always fires, because it moves with the
parameters. Their measurements: a 0.002 s step lands low, 0.001 and 0.003
land high, 0.0001 lands low -- the direction flips with the step, and
`steps * dt` is exact in every case, because that rounds once instead of ten
thousand times. So whether the stop criterion works depends on where in the
axis interval S4 happened to choose.

Two rules follow, and the second matters more here.

**Derive from integer counts** -- frames, triggers, steps -- and multiply.
Never keep a running sum. **And do not add an epsilon**: the limit came from
the plan, and an operator that widens it is changing an approved number at
run time.

**On this instrument the accumulated software time was never the right source
anyway.** §4.6.9 already makes trigger counters and hardware timestamps
authoritative for any quantity physics depends on, and software offsets order
the log and nothing else. `orchestrator.Clock.offset()` is a subtraction from
one `t0`, so it rounds once and is correct as written -- the trap is not there
today. It is waiting in the acquisition loop nobody has written yet, which is
the natural place to total up exposures and compare against `record_length`.

**A plan names a channel or an element, and the orchestrator resolves which.**
"Set the dia lamp" is the true statement; "set `stand_ti2e`" would lose which
of that channel's ten elements was meant. Check 38 accepts both against the
registry as of `f78d339`. `orchestrator.py` does **not** — `preflight` looks
names up in `self.channels` only, so a plan naming `dia_lamp` or `nosepiece`
raises `GapError` on a perfectly good card. Resolving element to channel is
this layer's job and it is missing.

**Two rules transfer, and both are P0-class.**

**A return code is not a verification.** On the tweezers a `0` means the GUI
accepted the text, not that the instrument did anything; the interface has
**no query command of any kind**, so readiness can only be inferred by sending
something and reading the code back. §2.1 already says an unreadable selector
is unverified — this is the sharper case, where a reply exists and still does
not answer the question asked.

**A missing reply is never retried. An explicit rejection may be.** Their
"busy" code is a refusal: the GUI answered, and its answer was *I did not run
this*, so re-sending is safe. A missing reply leaves the command's fate
unknown, and several trap commands are **relative** — re-sending one that did
land moves the trap twice. Our `orchestrator.py` has a timeout that aborts and
says nothing about retries; it must not grow one that treats those two cases
alike. Relative commands are the reason, and the reason belongs next to the
rule.

**Their readiness probe is worth copying as a shape, not as a list.** They
treat three codes as "up" and five as "up but unusable", and the second set
splits into *keep waiting* and *go fix it by hand* — which is precisely our
manual-sheet routing. One of the three "up" codes is there **on measurement,
not on the manual**: the vendor's reference implies one code and the
instrument answers another, and without that correction a healthy GUI reads as
absent. Take the shape; re-measure the codes here before trusting any of them.

**Downgrade — every constant in that file.** The command gap, the retry count,
the backoff and the reply timeout are all measured numbers with dates. They go
through §10.3 to the librarian at E3, cited to that measurement, and they do
**not** arrive as constants in our code. What arrives in code is the structure
that uses them.

**Drop** — their orchestrator, and the per-device GUI-session management. We
have our own single entry point and it is already written.

## What the operator still owes, and what each one unlocks

Kept here rather than in a card because these are not missing values -- a
missing value is a `kb_gap` and the axis cards already carry seven of them.
These are questions only the person can answer, and a session that clears
between tasks would otherwise carry them in context, which is where they
would quietly become nobody's.

| | unlocks |
|---|---|
| **Target relative error on the trap displacement** | A7's floor, `x_min = sigma_loc / target`. The goal's decade resolution and SNR target are neither: SNR is about detecting the bead, `x_min` about resolving how far it moved |
| **Bead lot number** | Not a value -- a source. The diameter is E5 on recall; a lot number makes it `spec:<lot>` at E3, and `gamma` rises with it |
| **Working height above the coverslip** | The wall correction scales with it. The +16% quoted in A7 is true only at 10 um, and nothing has said what the height is |

Take one off this list when it lands in a card with a source and a grade.

## Safety here is not advice

`plan.md` §2.1 is enforced by code, not by care. In this directory that means:

- Ambiguity stops. A selector whose state cannot be read back is not verified,
  and an unverified state does not proceed.
- Shutters close before any power ramps down, and the laser shutter is one of
  them.
- z retracts before a turret rotates. The objective can reach the sample.
- PFS is disabled across turret and path changes, and re-acquired after.
- Nothing acquires while the optical-path lock is held, or while the spinning
  disk is still coming up to speed.
- While a manual instruction sheet is open, this session issues **no** automatic
  command to that device group. The human closes the sheet.

Safety limits in `envelope/safety.json` are policy, written by a person who
confirmed them physically. They were deliberately not extracted from the prior
project (§10.3 rule 4). No plan, no scope approval, and no human approval may
exceed them.

## Before committing

```bash
python3 contracts/validate.py
```

Zero failures, and understand every UNDECIDED and PENDING line rather than
reading past it. An unchosen threshold is not a satisfied threshold.

**Commit under this seat's identity, read from `contracts/seats.json`.** This
seat is `microscope`, and the row there gives the committer address. The
author stays the person; only the committer is the seat, and check 41 reads
it.

```bash
GIT_COMMITTER_NAME='seat:microscope' GIT_COMMITTER_EMAIL=microscope@seat.invalid git commit -F msg -- <paths>
```

**Do not put that in the repository's git config.** §6.2.3 prescribes writing
it into a worktree's own config, and that prescription assumes D12's
per-session worktrees, which do not exist yet -- `git worktree list` reports
one shared checkout. An identity written there would be read by every other
session as its own, and a simulation session committing as `seat:microscope`
is worse than no attribution at all: check 41 would pass it. Set it per
command until each session has its own worktree.
