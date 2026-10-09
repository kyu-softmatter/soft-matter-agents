# 067 — take the bridge rounds waiting in the inbox

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261007-1`, after card 060's preparation.** Monday
comes first. If you are not that seat, take nothing from this card and report
up.

**This widens card 064 for you by three folders, and only these:**
`questions/mic-20260925-001/`, `questions/mic-20260930-001/` and
`questions/mic-20260919-001/`. Microscope 1 writes none of them. You still
write no `src/`, `tests/`, `rulings.jsonl` or `failures.jsonl`, and never
`inbox/`, which is the bridge's. If a step needs a per-question failure
record, use that question folder's own `failures.jsonl`.

## Why

The bridge manager reported on 2026-10-07 (recorded at `2c48f3d`; found by
`contracts/bridge_board.py`) that two rounds delivered to `inbox/` are linked
from no microscope card's `from_round`. **Only this side can write
`from_round`.** Until it does, the bridge cannot see that either round was
taken, and check 74 cannot compare either goal with its round. A third round
is on its way.

Read this agent's `CLAUDE.md` section on rounds before starting:

- the envelope in the inbox is the turn;
- **copy no payload number into a goal card**;
- cite the sending side's design choices **as the round's, with its
  revision**;
- nothing is removed from the inbox.

## 1. `thr-double-well-001` r1 into `mic-20260925-001`

Delivered since 2026-10-01. The goal there already cites the payload by id,
and says `from_round` "is linked when the bridge files it". It is filed.
**Write the next goal revision** in that folder, following the folder's own
naming: a `v<N>_goal.json` beside `goal.json` if that is how its revisions
go. It carries `from_round: "thr-double-well-001:r1"` and changes nothing else
that the round does not change. Read the round's envelope, not its Markdown,
and say in the revision which of its design choices you cite, with the
round's revision.

## 2. `thr-bleach-recovery-diffusivity-001` r1 into `mic-20260930-001`

**Card 053 is reassigned to you.** It was written for
`microscope-kyuhwan-macbook-20260930-2`, a seat that no longer runs. Take card
053 as written: the round becomes the question's next goal revision with
`from_round: "thr-bleach-recovery-diffusivity-001:r1"`. Then re-run the axes
the round's values move, pinning the current store version, and compare
without adopting. Card 053 lists what still waits on the person. Leave
those waiting, and say which of them the round changes.

## 3. `thr-tracer-diffusivity-001` r3 into `mic-20260919-001`, once it lands

`bridge-20261007-1` is writing round 3. It carries the simulation plan's
revision 3 and supersedes round 2, which `v2_goal.json` took. **Do nothing
until the r3 envelope is in `inbox/thr-tracer-diffusivity-001/`.** Then
write `v3_goal.json` with `from_round: "thr-tracer-diffusivity-001:r3"`, and
say what changed from round 2 to round 3 that this goal now cites.

## Not yours, and left alone

The validator reports one LOST item on check 66: `plan-mic-20260920-001`
revisions overwritten under existing run logs. It is history, and nothing in
this card rewrites it.

## Boundaries and commits

Goal cards are written `DRAFT` and raised to `VALIDATED` only after the
validator passes, as this agent's `CLAUDE.md` says. Commit under your seat
with `git diff HEAD -- <paths>`, then `git commit -F <file> -- <paths>`,
naming each new file. The hooks are installed; a held `index.lock` is someone
else's commit. Push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat, 5 lines at most:

- each goal revision's path and commit;
- the `from_round` it carries;
- for card 053, which axes were re-run and which waiting items the round
  changes;
- whether round 3 had landed.
