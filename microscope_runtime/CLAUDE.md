# microscope_runtime

Runs the microscope. This folder holds the system operator (S6): the
operator, the orchestrator, `devices/`, live view, the run lock, the focus
search's gate and decider and the copied focus core, the run-time watcher,
and the bench kit, with their tests. It also holds the person's safety policy
and approvals, and the run records. `plan.md` sections 4.6 and 15 are the
specification; this file is the session's standing orders.

**This folder is being filled.** On 2026-10-17 the person decided that
execution leaves `microscope_agent/` for its own folder (plan.md 15). Until
the move commit lands, the code still runs from `microscope_agent/src/`, and
until the person moves them, the safety policy and approvals still sit in
`microscope_agent/`. Read plan.md 15's order before touching anything here.

## Who writes here

- **The runtime seat**, which the person opens in this folder and seats in
  that window. Its `paths` in `contracts/seats.json` are
  `microscope_runtime/`, and check 41 refuses it anywhere else.
- **manager-microscope** writes `tasks/`, this file and `.claude/`. A seat
  that can edit its own orders has none.
- **The person** writes `envelope/safety.json` and `approvals/`, by hand.
  No session writes either, ever.

A planning seat, narrowed to `microscope_agent/`, is refused here. The two
folders are one boundary divided by seat, and the line between them is the
one the design already draws: the design plans, the runtime runs what the
person approved.

## What this session may write

`src/`, `tests/`, `runs/` through the operator, `findings/` for bench
findings, and `failures.jsonl`, on a card in `tasks/` that names you. Take
no card that does not name you.

**Never** `envelope/safety.json`, `approvals/`, `tasks/`, this file or
`.claude/`. The settings deny all five, anchored at this folder, and the
commit gate refuses them whatever the settings say. **Never** another
agent's folder, `contracts/` or `plan.md`.

## Rules that do not move with the code

- **Safety is code, not judgement (P0).** Ambiguity stops. An unverified
  state does not proceed. Shutters close before power ramps down. Z
  retracts before a turret rotates. A return code is not a read-back.
  `plan.md` 2.1 is the list.
- **One execution path, one Micro-Manager core, one run lock.** Every
  command goes through the orchestrator, derived from an approved plan's
  fields, each with its `from`. There is no second command path anywhere
  in this repository (plan.md 15).
- **A missing policy or approval refuses.** Nothing falls back to the old
  path in `microscope_agent/`. Between the code's move and the person's
  move of their files, nothing can run, which is the direction a late step
  has to fail in.
- **The knowledge snapshot stays in `microscope_agent/envelope/snapshot.json`**,
  one copy, read by both folders, so a plan and the run that executes it
  stand on the same store version. Read it by that explicit path.
- **A citation of a file in either microscope folder names the commit it
  was read at** (plan.md 15), because paths moved.

## Talking to the person

Questions for the person, and results meant for them, go to the intake seat,
`architecture-office-20261017-2`, not to this window (plan.md 6). A decision
said there counts once its line is committed in `docs/ideas/`, and you cite
that commit. Three acts stay the person's own, in their own place: signing a
plan's hash, writing a safety value, and handing over the bench.

## Before committing

Commit and push through `contracts/tools/seat_commit.py`, naming paths, as
the root `CLAUDE.md` says. Run the validator under the interpreter that file
names for this computer. Never `--no-verify`, `--amend` or force.
