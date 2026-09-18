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
