# 011 — the board's first use, and the tracer plan's revision 3

**For bridge-20261007-1**, the bridge execution seat on the Office computer,
from `manager-bridge-20261007-1`, 2026-10-08. Nobody else takes this card.
You read it; you do not edit it.

Why now: architecture-20261003-1 relayed that the person wants work to go on
until Monday 2026-10-12 without waiting on them. That relay grants nothing by
itself. **Everything below is work the bridge's own contract already allows
without a person**: a plan crossing on its completion, a superseding round,
and keeping `status.json` true. Nothing in this card carries a result across:
a result crosses only on a person's hand-over given in a window directly.

Read `bridge/CLAUDE.md` first. Two parts of it are new since `f9228ec`: *The
board* and *When the microscope finds its own focus*.

## Part 1 — run the board and make every ledger agree with it

```bash
uv run --offline --no-project --python 3.12 --with jsonschema python contracts/bridge_board.py
```

(On this computer bare `python` lacks the validator's libraries; the `uv`
form is the one that works, as in the root `CLAUDE.md`.)

At `f9228ec` it showed three threads, all with the turn on the microscope:

| thread | what the board saw |
|---|---|
| `thr-tracer-diffusivity-001` | round 2 taken as `mic-20260919-001/v2_goal.json`; the source plan is now revision 3 and the round carries revision 2 |
| `thr-double-well-001` | delivered, and no microscope card stands on it with `from_round` |
| `thr-bleach-recovery-diffusivity-001` | delivered, and no microscope card stands on it with `from_round` |

Re-run it; do not trust this table. For each thread, check that `status.json`
says what the cards say. **Where the ledger's note is out of date, append a
dated sentence to it**; change `turn` or `state` only on a fact on disk, never
on the board's wording. The two "not taken" lines are **not yours to fix**:
`from_round` is written by the microscope, and the double-well goal already
says it will be linked once filed. Report them to me and I carry them to the
microscope's manager.

If the board says something the cards do not, that is a defect in the board,
which is mine: report it with the path and stop on that thread.

## Part 2 — the superseding round for the tracer plan

`simulation_agent/questions/sim-20260917-001/v3_plan_simulation_sim-20260917-001.json`
is `plan-sim-20260917-001-r3`, VALIDATED since 2026-09-22 (`f8777c5`).
Round 2 of `thr-tracer-diffusivity-001` carries revision 2. Nothing in
`bridge/` or `plan.md` records a decision to hold revision 3 back; it simply
was not carried. Check 74 reports the staleness and says who owes the fix:
*the bridge writes the superseding round, not the receiver.*

Write round 3 with `supersedes: 2` and `trigger: plan_completion`, and
deliver it into `microscope_agent/inbox/thr-tracer-diffusivity-001/`. Before
wrapping, recompute every gate yourself:

1. **Still the same question.** Same observable as round 2, same goal lineage,
   same qid. If revision 3 changed the observable, it is not a supersession.
   **Hold**, write nothing to the inbox, and report.
2. **Still the latest.** No revision 4 on disk at the moment you hash it. Pin
   path, card id, revision, status and hash in `r3_hashes.json` with
   `canon_sha` / `card_sha` from the validator, as `bridge/CLAUDE.md` shows.
3. **Answerability** from `contracts/observables.json` and
   `contracts/capabilities/microscope.json`, derived and not chosen.
4. **Units against the counterpart.** This is round 3, so there is a
   counterpart and `no_counterpart` is a failure. Compare against the card the
   microscope wrote from round 2 and name it in `compared_against`.
5. **The librarian.** If your session has the librarian's tools, run the
   duplicate check under your own issued `caller_id`. If it does not, and on
   this computer it may not, the round goes on the degraded path with
   `degraded: ["librarian_agent"]`. That is legitimate, and the envelope must
   say it.
6. **Not an operation plan.** It is not, since it has a goal, but check 8 now
   refuses one, so confirm it rather than assume it.
7. **Carry, do not judge.** No number added or rounded; the markdown names the
   payload and carries no number. Update `status.json`: round 3, turn the
   microscope's, with a note saying what moved between revisions 2 and 3 in
   words and pointing at the two cards for the values.

The envelope already in the microscope's inbox for round 2 stays. Nothing is
removed from an inbox; round 3 beside it is how the microscope learns the
source moved.

## Out of scope

- Any result crossing, in either direction, including the seven simulation
  results the board lists as not crossed. Those wait on the person.
- `thr-double-well-001` r1's history: card 008 stays as written.
- Any comparison of focal planes. No card records one yet (`bridge/CLAUDE.md`).

## Mechanics

- Commit with `GIT_COMMITTER_NAME='seat:bridge-20261007-1'` and
  `GIT_COMMITTER_EMAIL` from your row in `contracts/seats.json`, read from the
  file. Check with `git var GIT_COMMITTER_IDENT`.
- `git diff HEAD -- <paths>`, then `git commit -F <file> -- <paths>` with new
  files added first by name; read the last lines and `git log -1`. Never
  `--amend`. A `fatal:` about `.git/index.lock` means another seat's gate is
  running and nothing was committed: wait and retry.
- Validate with the `uv` command in the root `CLAUDE.md`; it must end
  `0 failed` on a tree that names your commit.
- The branch is `feature/autofocus-ui`. Push with
  `git -c credential.helper=manager push origin feature/autofocus-ui`. Never
  force.
- Your paths are `bridge/threads/`, `bridge/failures.jsonl` and the inbox you
  deliver into. Never `git -A`, never `git checkout --` on a shared path.

## Report

To me by session message: after Part 1, which ledgers you appended to and
what the board showed; after Part 2, whether round 3 landed or held, under
which trigger, and whose turn `status.json` names.
