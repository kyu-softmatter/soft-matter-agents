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

- **The runtime session**, which the person opens in this folder. It commits as `microscope`, the
  one name for the whole microscope boundary (contracts/seats.json; plan.md 6.2.1).
- **A design session** at the repository root writes `tasks/`, this file and `.claude/`, on the
  person's word. A session that can edit its own orders has none.
- **The person** writes `envelope/safety.json`, `envelope/console_login.json`
  and `approvals/`, by hand, and commits them. No session writes or commits
  any of them, ever. A console-signed approval is the one file another
  program writes there: the console's server, at the moment the person types
  the password (plan.md 15.1 item 4).

The planning session in `microscope_agent/` works on paper and does not write here by habit. The two
folders are one boundary under one name, and the line between them is the
one the design already draws: the design plans, the runtime runs what the
person approved.

## What this session may write

`src/`, `tests/`, `runs/` through the operator, `findings/` for bench
findings, and `failures.jsonl`, on a card in `tasks/` that names you. Take
no card that does not name you.

**Never** `envelope/safety.json`, `envelope/console_login.json`,
`approvals/`, `tasks/`, this file or `.claude/`. The settings deny all six,
anchored at this folder. The commit gate refuses a seat that commits the
person's three whatever the settings say (check 41, since `088fb2b0`;
before it, it did not), and the other three by boundary. **Never** another
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

**Questions for the person go to the intake session on this computer**, as "Talking to the person" in
the root `CLAUDE.md` says.
- Act on its committed line, citing the commit.
- If no intake session is running, ask in this window.

**The bench is the exception, and it never passes through the intake session.** Open a device only
after the person has said, in this window, that the bench is yours.

Four acts stay the person's own, in their own place: signing a plan's hash, writing a safety value,
handing over the bench, and paying.

## Before committing

Commit through `contracts/tools/seat_commit.py --seat microscope`, naming paths, as
the root `CLAUDE.md` says, and push only when the person says so. Run the validator under the interpreter that file
names for this computer. Never `--no-verify`, `--amend` or force.
