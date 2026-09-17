# microscope_agent

Designs the conditions under which a given observation goal can actually be
measured on this instrument, and carries out the measurement under approval.
`plan.md` §4.1 and §4.5–4.6 are the specification; this file is the session's
standing orders.

**Milestone M1.** This directory is a skeleton. Nothing here runs yet.

## What this session may write

`microscope_agent/` only. `contracts/` and `plan.md` are read here and written
by the design session (§6.2). The permission rules in `.claude/settings.json`
enforce that rather than relying on restraint, and check 35 catches a commit
that crosses the line.

## Where knowledge comes from

Not from here. This agent keeps **records** (`questions/`, `runs/`) and
**policy** (`envelope/safety.json`), never a knowledge store of its own (P14).

Until the librarian agent exists at M3, read the store directly:

- `librarian_agent/kb/entries/` — atomic claims, cite them as `kb:<entry_id>`
  and copy the grade the store gives, never a better one (check 21)
- `librarian_agent/kb/staging/devices.v0.json` — control channels: how each is
  driven, whether it can be automated, whether its state can be read back
- `librarian_agent/kb/staging/optical_paths.v0.json` — which configurations
  deliver light to a detector, and what must be set for each

Every card written here carries `degraded: ["librarian_agent"]` while that is
true, and it means *we do not know what we missed* — no gap detection, no
conflict detection, no external search.

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
