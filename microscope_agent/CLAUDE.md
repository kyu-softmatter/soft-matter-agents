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

**Two paths inside this tree are not yours**, and they are the two that matter
most because they are the ones a session here can actually reach:
`envelope/safety.json`, which only the person writes (P0 rule 7), and
`inbox/**`, which only the bridge writes (§7.1 rule 8). The rest of the deny
list points outside this tree, where nothing would resolve anyway.

## A round arrives in `inbox/`, and the envelope is the turn

**`microscope_agent/inbox/<thread>/` is where the bridge delivers.** It holds
`r<N>_ask_*.{json,md}` and nothing else. You **read** it; you never write it.
By the boundary classifier that folder is the `bridge`'s, not this agent's —
only its location is in your tree — and an agent writing its own inbox is
forging a delivery.

**An envelope sitting there is the turn. There is nothing else to check.**
Deliberately no status copy is delivered: `status.json` is the one file in a
thread that changes, so a copy of it goes stale the moment the turn moves, and
that drift is what left the example thread reading "the human's turn" for a
day. **And do not go read `bridge/threads/` for the turn instead.** That
breaks §7's separation path — detaching to the microscope PC takes
`microscope_agent/` and `contracts/` and leaves `bridge/` behind, so a round
read from there becomes invisible the moment the instrument is separated.

**Taking a round is S2, and it is assigned by a task card like an axis is.**
Do not start one because you saw it. Two seats share this tree and a round
that both might assume the other took is worse than one nobody took, because
it looks staffed. Seeing an envelope you have no card for, report it up;
`manager-microscope` cards it.

**How the bridge learns you took it**: the goal card's `from_round`,
`thr-…:r<N>`. The bridge already reads this agent's `questions/`, so nothing
is written back toward it.

**Nothing is deleted from the inbox.** The delivery happened and that file is
the record of it (P1).

This section exists because it did not. On 2026-09-19 the first real
cross-agent round was written, delivered, and sat unread — not from
inattention but because **no document told any seat that the folder existed**.
A chat message rescued it, which is the §6.2 rule 2 failure exactly: the
notice worked and left no trace, so a session reset would have lost the fact
that a round was waiting.

## Where knowledge comes from

Not from here. This agent keeps **records** (`questions/`, `runs/`) and
**policy** (`envelope/safety.json`), never a knowledge store of its own (P14).

**The normal path.** The librarian publishes to `librarian_agent/kb/exports/`
and cannot write here (D11), so **this session copies the export into its own
`envelope/snapshot.json`**. The copy is deliberate: which KB version entered
this agent's envelope, and when, is then a fact in this agent's own commit
history. **Check 26 does this now.** It was a stub when this paragraph was first
written — it returned PENDING whether a snapshot was present or absent, so a
diverged copy passed exactly as a sound one did, and the instruction here was
to verify the copy by hand. That is no longer needed. It reads each entry's
embedded text against `git show <built_from_commit>:librarian_agent/kb/
entries/<id>.json` and each table against the file its `from` names, against
that commit rather than against HEAD, so an older envelope stays honest.
Today it reports `1 envelope snapshots hold the bytes the commit they name
holds` — this agent's is its first consumer.

What it still does **not** recompute is `snapshot_hash` or the per-part
sha256s; both need the exporter's canonical form, and restating that here
would put one rule in two places. Comparing the text against the committed
bytes subsumes them.

**Copy only bytes that are committed.** If the export is modified in the
working copy, wait. A snapshot built from uncommitted bytes has no commit
behind it, and then the one thing the copy exists to establish — which KB
version entered this envelope, and when, as a fact of this agent's history —
is the thing it cannot show. Record in your commit message which commit of
the export you took.

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

**Every ruling is written down, including the ones that produce nothing.**
A dropped item leaves no artifact by definition, so unless it is recorded the
drops cannot be counted — and §9.3 asks exactly that of the two variants. As
of 2026-09-18 the store held five transfers and one downgrade, no drops at
all, and only two of those six named a slot. Both halves of that are the same
omission.

So: for each task that crosses anything, write a sibling file next to the
card, `tasks/NNN-rulings.md`, one line per item considered, in this shape:

```
transfer  | <item>            | slot A4 | 10.3 rule 1
downgrade | <item>            | E5      | 10.3 rule 2
drop      | <item>            | no slot in A1-A7
```

One line, greppable, so a count is a count and not a reading. **An item you
looked at and did not take is a line here** — that is the whole point of the
file, and the line costs less than the argument about why the drop was
invisible.

**You cannot write that file today, and this seat caused that.** The
paragraph above said the sibling file was yours; the deny list then closed
`tasks/**` to you, because that is where descending instruction lives and a
seat that can edit its own orders has none. Both are this seat's and they
contradict. Until it is resolved, **report your rulings up in the same
sentence that reports the task, and `manager-microscope` writes them into
`tasks/NNN-rulings.md`** — the judgement stays yours and is attributed to
you; only the hand that writes it changes.

Do not resolve it by asking for an allow rule. Deny wins over allow in this
harness, and cards and rulings share the `NNN-` prefix, so a glob that
separated them would be one rename away from failing open. The real fix is a
directory that is not `tasks/`, which is §7.1 and therefore architecture's;
it is raised.

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

## A standing preference: move the stage, not the trap

**Stated by the person on 2026-09-19.** Where a measurement needs relative
motion between the sample and the trapped object, **prefer moving the piezo
stage over steering the trap.** The reason is image analysis: with the trap
held still the object stays at one place on the sensor, so flat-field,
distortion and illumination non-uniformity stay constant instead of varying
along the trajectory. Drag calibration is the worked example — if the sample
has to move at 10 µm/s past the object, move the stage at 10 µm/s rather than
sweeping the trap.

**This is a preference and not evidence.** It says which actuator to reach for
first, not what the instrument can do. It does not become a number, it does
not relieve any axis of stating its bounds, and A7 may still return an
interval that refuses it — `preference_is_not_evidence`, the same rule S3.0
applies to a configuration preference.

**It chooses the actuator; it does not change the physics.** Two consequences
that are easy to get backwards:

- **The escape condition still binds.** `v_max ~ k·x_max/γ` is about the
  *relative* velocity between fluid and object. Driving that relative velocity
  from the stage instead of the trap produces the same drag and the same
  escape, so A7 owns the same inequality either way.
- **What changes is which limits enter it.** Stage-driven motion is bounded by
  the piezo's travel, bandwidth and settling time, and by the motorised
  stage's velocity, acceleration and backlash — not by the trap steering rate
  or the multiplexing update rate. A7's `stage_velocity` bound becomes the one
  that binds, and `trap_velocity` stops being the limiting term.

**Do not fetch the piezo travel range from the prior project.** It exists
there as the heading of that project's `SAFETY.md`, and §10.3 rule 4 makes
safety limits non-transferable — that project put the number in its safety
document because it was using it as a limit, and a travel range read as a
permission is exactly the failure the rule names. A stage-driven calibration
will want that number immediately; it comes from this instrument or from the
person, not from there.

## Some gaps close by acquiring, not by asking

**`tracer_brightness` and `bleaching_rate` are not in any store for a new
sample, and cannot be.** Stated by the person on 2026-09-19. They depend on
this dye, this lot, this illumination and this camera together, so no vendor
sheet and no prior run supplies them — for a sample that has been
characterised before they may be known, and ours has not been.

**The remedy is a named acquisition: image the particles alone.** Particles on
the coverslip, nothing else, under the illumination the real record will use.
That gives the photon rate per particle and the decay over time in one short
run. It is a **pre-measurement**, and it comes before the measurement it
unblocks.

**So the abstention must name the remedy, not only the missing input.** A gap
that waits on a person's decision and a gap that waits on a twenty-minute
acquisition are different things with different next actions, and `no_input`
with a `missing` list says neither. Write the acquisition into the reason:
*what would close this, and who does it.*

Six abstentions currently sit here — `tracer_brightness` in three A1 bounds,
`bleaching_rate` in A1's `record_duration` and A3's. When those are next
written, say that one bare-particle run closes all six. **A gap that names its
own remedy is one somebody can act on; a gap that names only its absence
waits for someone to work out what it wants.**

**And it interacts with a constraint already on the goal card.** *The sample is
consumed by the measurement and cannot be remounted.* A bare-particle run is
not that sample — it is particles without it — so it does not spend the one
mount. Say so, or the pre-measurement looks like it costs the thing it is
protecting.

## What the operator still owes, and what each one unlocks

Kept here rather than in a card because these are not missing values -- a
missing value is a `kb_gap` and the axis cards already carry seven of them.
These are questions only the person can answer, and a session that clears
between tasks would otherwise carry them in context, which is where they
would quietly become nobody's.

| | unlocks |
|---|---|
| **Target relative error on the trap displacement** | A7's floor, `x_min = sigma_loc / target`, and A2's `frame_count`. **Still owed** — on 2026-09-19 the person settled the *goal's* decade resolution, and this is not that. A decade says how coarsely the answer may land; `x_min` says how finely a displacement must be resolved. SNR is a third thing again |
| **Bead diameter** | The disputed number: `operator_recall:` 5 µm here against `assumed:` 2 µm on the simulation side. It goes as the cube, so `tau_d` differs **15.6×** — outside explore's tie band, and it is what holds the bridge round `thr-tracer-diffusivity-001` at `turn: human`. Also gates A2's and A3's `tracer_number_density`, which is a column in the vendor table until a diameter selects a row |
| **Bead lot number** | Not a value — a source. The diameter is E5 on recall; a lot makes it `spec:<lot>` at E3. Absent in the prior project too, where the schema says *record it* beside an empty field, so this can only come from the bottle |
| **Dilution factor** | The vendor sheet's 10 mg/ml is the **stock**. What is under the objective is nowhere on disk, so even a known diameter does not give a number density. **No card has asked for this yet**, which is why it would not surface on its own |
| **Filter wheel part designation, red path** | λ for A6's diffraction limit and axial range. The cube is multiband, so its `555/605` marking is not the band in use; single-band filters in the wheel select it. One designation is enough — the band then follows from the manufacturer at `spec:` E3, the way NA did, and with NA already E3 the diffraction limit computes at E3 |
| **Working height above the coverslip** | The wall correction scales with it. The +16% quoted in A7 is true only at 10 um, and nothing has said what the height is |

Take one off this list when it lands in a card with a source and a grade.

## Safety here is not advice

`plan.md` §2.1 is enforced by code, not by care. In this directory that means:

- Ambiguity stops. A selector whose state cannot be read back is not verified,
  and an unverified state does not proceed.
- Shutters close before any power ramps down, and the laser shutter is one of
  them.
- z retracts before a turret rotates. The objective can reach the sample.
  **Nothing does this for you on the path we will use.** The stand runs its
  own escape when a person rotates at the stand or in NIS; a Micro-Manager
  write to the nosepiece does not, so Z stays where it was and the incoming
  objective arrives at the outgoing one's height
  (`nosepiece_write_runs_no_escape`, E3). The retract is a step a plan issues
  and verifies, not a property it may assume. The same rotation silently
  invalidates two trap calibrations and neither is readable over TCP
  (`objective_change_invalidates_trap_calibration`).
- **A zero from the Tweez 300 is not a confirmation.** Its TCP interface has
  no read-back of any kind — no position, no force, no trap list, no
  calibration — and a return code of 0 means the GUI accepted the command,
  not that anything happened; six distinct ways a command can be ignored all
  return 0 (`tweez300_reports_nothing_back`, E3). This is what `read_back:
  false` means in the device table, and it is why the rule above about
  unverified state is not a formality here.
- PFS is disabled across turret and path changes, and re-acquired after.
- Nothing acquires while the optical-path lock is held, or while the spinning
  disk is still coming up to speed.
- While a manual instruction sheet is open, this session issues **no** automatic
  command to that device group. The human closes the sheet.

Safety limits in `envelope/safety.json` are policy, written by a person who
confirmed them physically. They were deliberately not extracted from the prior
project (§10.3 rule 4). No plan, no scope approval, and no human approval may
exceed them.

## A card names its seat, and that is not decoration

**Cards 012 to 016 named no seat, four microscope seats were alive, and on
2026-09-20 one card went to two of them.** Both wrote `questions/
mic-20260920-001/goal.json`. The second overwrote the first's revision in the
worktree, and the first then committed the overwrite under its own name
believing it was committing its own work -- `git commit -- <path>` takes the
worktree state of that path, so nothing refused it and no check saw it.

**The manager seat could not tell them apart either.** It wrote to one seat
that `nosepiece_position` was already 5 while that seat's card said 1; it had
read the other seat's file at the same path. **The collision was visible in
the manager's own message and went unnoticed**, which is why the remedy is
not "look more carefully".

So: **take no card that does not name you**, and report up instead. A chat
message is not an assignment -- the card is, and if the card is silent the
assignment does not exist yet. Cards 000 and 004 through 011 already named
their seat; the gap was 012 onward and it is closed.

## Before committing

**A card that says the service answered cannot be committed before the
librarian has committed the query log.** Check 45 tests an empty `degraded`
against `queries/log.jsonl`, and the gate judges **the tree your commit would
create** -- so a card whose supporting line exists only in the shared working
copy passes here and fails there. On 2026-09-20 the log stood at 230 committed
lines against 547 on disk, and **every served card in every agent was
uncommittable** for as long as that held. Nothing had recorded the constraint,
and the seat that hit it could not fix it: `librarian_agent/` is outside this
boundary and check 35 refuses the write.

So before committing a card with `degraded: []`, check the line is in HEAD:

```bash
git show HEAD:librarian_agent/queries/log.jsonl | grep -c '<your caller_id>'
```

Zero means **wait and report upward**, not work around. The card is correct;
the ordering is what is not satisfied yet.

**`git commit -- <directory>` does not include untracked files inside it.**
Naming `questions/mic-20260920-001` committed the two tracked files and left
the new card behind. This is the other edge of *naming a path is not naming a
change*: there another seat's edit rides in, here **your own new file drops
out**. The gate prints what is going in, and reading that list is what caught
it. Name new files individually, or `git add` them first.

**`to_card()` writes DRAFT and every committed axis card is VALIDATED.** The
promotion has been done by hand each time and is written nowhere, which means
it depends on whoever is at the keyboard remembering. Until that is settled,
raise it deliberately after the validator passes and say in the commit message
that you did. It is raised as a question for this seat.


```bash
python3 contracts/validate.py
```

Zero failures, and understand every UNDECIDED and PENDING line rather than
reading past it. An unchosen threshold is not a satisfied threshold.

**Your identity is not written in this file. Read it from
`contracts/seats.json`.** More than one row there owns `microscope_agent` —
`microscope`, `microscope-1`, `microscope-2`, `microscope-3` — and which is
yours does not follow from anything here. It follows from the person having
seated you (§6.2.2); another session cannot tell you, and neither can this
file. Take the row, use its `committer_email`, and check the row is not
marked deferred.

**This file names no seat on purpose.** It is read by every microscope
session at once, so a name written here hands the same identity to all of
them — which is `one_identity_per_session`'s hole arriving by configuration
rather than by accident. Check 41 cannot tell two sessions apart under one
address and passes their mixture; that happened twice on 2026-09-17, and both
times the pass was the defect. This paragraph replaces two earlier ones that
named `microscope` and `microscope-1`, which between them were already giving
different answers to the same question.

The author stays the person. Only the committer is the seat, and check 41
reads it. With no worktree, set it per command:

```bash
GIT_COMMITTER_NAME='seat:<your-seat>' GIT_COMMITTER_EMAIL=<your-seat>@seat.invalid git commit -F msg -- <paths>
```

**If a worktree is made, move the identity into it** — there it survives a
context reset, and it is what §6.2.3 prescribes:

```bash
git config --worktree committer.name  'seat:<your-seat>'
git config --worktree committer.email <your-seat>@seat.invalid
git var GIT_COMMITTER_IDENT        # confirm before you rely on it
```

**Never `--local`.** In a linked worktree it writes to the shared
`.git/config`, where every other session reads it as its own — a simulation
session committing as a microscope seat is worse than no attribution, because
check 41 passes it. §6.2.3 prescribed `--local` by mistake until `44f368b`.

**More than one microscope session may be running.** Nothing refuses a
collision on the surfaces you share — `src/axis_common.py` and
`questions/<qid>/failures.jsonl` — so the division comes from the task cards
in `tasks/`, not from the tooling. Do not take an axis that a card has not
given you, and put helpers your axis needs in your own axis module rather
than in `axis_common.py` unless a card says otherwise.
