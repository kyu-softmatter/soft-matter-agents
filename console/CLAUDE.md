# console -- the person's window onto the four agents

Shows what the four agents and the bridge have on disk, and drafts plans the
person approves. **It designs nothing, runs nothing and knows nothing; it
shows.** It is not a fifth agent. The count of agents stays four, and this
is one more directory like `bridge/`: the bridge carries cards without owning
knowledge, and the console shows cards without owning anything. `plan.md` 15
and 11-25 are the specification; this file is the session's standing orders.

## Where it stands

The console's code arrived here from `microscope_agent/autofocus/` in
2026-10-18's three steps, after the cut from dino's engine (card 077):
- the additions, card 001;
- the rename to `sma_console`, card 002;
- the deletions, card 078.

The person then asked for the console to be pared down and redesigned
(I-20261022-office-04, `c84c0f32`) and finished (`7c33b8c3`). **Card 006, as
revised by 007, is the specification.** The canvas it cites is version 58.
The app cards run in 007's order, from 008 on. **Nothing under `console/`
other than these instructions is written before a card in `tasks/` names
it.**

## The four standing rules

These held where the console sat before and hold here unchanged (11-25).

1. **It writes nothing into this tree outside `console/`.** It reads
   `<agent>/questions/`, `<agent>/approvals/`, `<agent>/runs/` and
   `bridge/threads/` as data and writes none of them. A draft plan reaches
   `approvals/` only through the person, because `approvals/` is the
   person's.
2. **A draft is an ordinary plan card** -- `operation`, `trap_steps` or
   `focus_search` -- and passes the same schema as any other. There is no
   console-only shape. A draft the console's tests build is validated against
   `contracts/schemas/plan.schema.json`, not against a copy of it.
3. **Every command goes through the orchestrator.** The console never opens
   a Micro-Manager core and never calls a device module. What it may send to
   a run is the run interface in `contracts/schemas/run_interface.schema.json`
   and nothing else: a stop on the stop channel, a `get` on the frame tap,
   and a live-on request that names a list the person approved. A stop is a
   signal that can only stop; safety stays with deterministic code.
4. **A number the console shows carries its source**, with its provenance
   in words: measured, computed or guessed. A guess shown to the person is
   still labelled a guess. A pixel size read from a configuration's frame
   metadata is that configuration's, not a measurement.

## The engine was never the console's

The imported server was more than a reader, and that is why the cut comes
first. `server/__main__.py` could open a real Micro-Manager core
(`--backend mm-real` with `--mm-config`). `POST /api/commands` passed light
and motion operations -- `light_set`, `goto_xy`, `objective_change`,
`trap_move`, `pattern_run` among them -- to dino's own engine. Only dino's
`BENCH_MOTION = "LOCKED"` held the motion back, and light on and off was not
locked. That is a second execution path, which rule 3 forbids.

So, until the cut lands and after it:

- **Start the server only with `--backend placeholder`.** dino's
  `--backend mock` stays with the engine, because it is a simulated stage
  and lights that execute commands. The console's mock is the placeholder
  engine with `--store mock`. Never `mm-real`, `mm-demo` or `replay`, and
  never `--mm-config`.
- **Never with `--live-host` or `--live-host-file`.** Those reach the
  live-view host, and live view lights the sample.
- **`--store sma` is allowed against a scratch copy** (card 063's form), since
  the files are read and never written. Against the microscope computer's own
  working copy, it is the person's to start.
- **Connecting a console to a running plan, a live host or the bench is the
  person's act**, at the bench, never a session's.

The console's placeholder keeps a minimal engine protocol of its own until it
reads the run interface instead. That protocol answers status and events, and
carries no command kind: no light, motion, trap or pattern operation and no
command type. Replacing it with the run interface is this folder's work, by
card.

## The librarian's store

A console has no question, so it holds no `caller_id` and does not call the
librarian's service: a query that leaves a log line and no `kb_refs` on any
card is what the card contract exists to prevent. **What it may show is
`plan.md` 4.3.1's display sentence** (`527376c3`): the generated wiki pages
under `librarian_agent/kb/wiki/`, read as data and nothing else of the store.
- A page is shown as it stands, and the console says so when `kb/index.json`
  has moved past the version in the page's footer.
- Entries, the query log and exports are not shown.
- A link to an entry or a guide is shown as text and never followed.
- Nothing shown is kept or lands on a card. A fact is cited by its entry,
  never by a page.
- What an account may ask of the store is only the three requests of
  `plan.md` 7.1.1, and none reaches the librarian until that inbox is
  approved and open.

## Tier 0 only

This session has no instrument tools. `.claude/settings.json` denies the
server's hardware backends, the live host and the runtime's entry points by
command, and denies this seat its own instructions by path. A command denial
matches the text of a command, so it guards a session and not the code. What
guards the code is that the console's environment has no `pymmcore` and no
`torch` (its own `pyproject.toml`, `plan.md` 15), so nothing here can open a
core whatever it is told.

**Root this session at `console/`.** An inward denial resolves only from the
session's own root, so a console session started at the repository root
carries none of the guards in `.claude/settings.json`.

**A change to that file reached a running session once, and that is all that
is known.** On 2026-10-17 the console seat's session had been moved to
`console/` by the person in the app, not restarted. It ran a harmless line
through PowerShell before and after this file gained PowerShell denials. The
line ran before and was refused after, with no restart between. So
permission rules were seen to reload. Hooks, and the denial of the
librarian's tools, were not probed. After a change to `.claude/`, probe the
rule you need with a line that only prints. If the result is unclear,
restart.

## Talking to the person

Say what was found and what to do about it, in plain words: no section,
rule, check or seat codes, and no commit hashes unless asked. Keep what the
person acts with -- a file to open, a command to run, a value with its unit --
and keep provenance in words. Questions for the person, and results meant for
the person, go through the intake seat and not this window.

## What it must never do

Write outside `console/`. Write a card into the tree. Open a core, call a
device, start a hardware backend, reach a live host. Hold a `caller_id` or
call the librarian's service. Show a number without its source. Decide for
the person, or relay a decision as one.

## Before committing

```bash
uv run --offline --no-project --python 3.12 --with jsonschema python contracts/validate.py
```

That is the Office computer's form; for another computer, read the root
`CLAUDE.md` for the interpreter. Commit through
`contracts/tools/seat_commit.py`, never by hand. A commit from this seat
touches `console/` and nothing else (checks 35 and 41).
`console/CLAUDE.md`, `console/README.md`, `console/tasks/` and
`console/.claude/` are the manager's. A dead end goes in
`console/failures.jsonl`.

**Your identity is not written in this file.** Read it from
`contracts/seats.json`: the row whose `owns` holds `console`, and which the
person seated you as. This file is read by every console session at once, so
a name written here would hand one identity to all of them.
