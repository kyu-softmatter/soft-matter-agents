# 008 — file the double well's first round, which 007 asked for and nobody filed

**For bridge-kyuhwan-macbook-20260928-4**, from
`manager-bridge-kyuhwan-macbook-20260928-4`, 2026-09-29 about 22:30 PDT.
This re-issues card 007 to you. **Read 007 first: everything in it holds**
except what the four points below change. Card 006's "open no round" still
holds for every other round.

## Why it comes to you

007 asked `bridge-20260924-1` on 2026-09-25 to open and deliver
`thr-double-well-001` r1. It was never filed. At `54e4885`:

- `bridge/threads/thr-double-well-001/` does not exist;
- `microscope_agent/inbox/thr-double-well-001/` does not exist;
- `microscope_agent/questions/mic-20260925-001/goal.json` has no `from_round`.

The one trace is line 1254 of `librarian_agent/queries/log.jsonl`: a
`kb_query` for `well_occupancy` under `caller_id`
`bridge:thr-double-well-001:r1` at 2026-09-25T18:03:49Z, gaps `absent`, which
no card cites. The seat that made it has left, and a vacated identity is not
inherited, so the round is yours.

It is still owed. `plan.md` 11-23 records the person's decision: the bridge
files r1 **after the run**, the microscope goal's `from_round` is linked then,
and the thread says the run preceded delivery. The run took place on
2026-09-25, so the round is late, not early.

## What changes from 007

1. **The hand-over is still the person's, and it is the one 007 records**:
   "Yes, send it now", given on 2026-09-25 in `manager-bridge-20260924-1`'s
   window to a direct question. `trigger: human`, naming the person. Do not
   name this seat, 007's seat or architecture. It covers **that payload
   only**: `simulation_agent/questions/sim-20260923-101/result_run-20260924-101-v3-hold.json`,
   verbatim. No commit has touched the file since `735a1a0`. The simulation
   side says its re-prediction revision carries the two fixes 007 names
   (`simulation_agent/failures.jsonl` line 69); no such revision exists at
   `54e4885`, and if one lands before you file, it is **not** this round's
   payload. A different payload is a different hand-over, and that is the
   person's.

2. **Say the delay in words**, in `r1_ask_experiment.md` and in
   `status.json` if it has a place: the run started before delivery, on the
   person's decision (007 already asks for this), **and** the round was filed
   days after the hand-over because the seat first asked to file it left
   without doing so. Nothing is backdated: every time you write is the time
   you write it. The markdown still carries no number, so say it without
   dates.

3. **Recompute everything; copy no verdict from 007.** Its `yes` was computed
   at `a768602`. Neither `contracts/observables.json` nor
   `contracts/capabilities/microscope.json` has changed since, but check 8
   judges your tree and not this sentence. If answerability comes out
   `undeclared`, hold the round as `bridge/CLAUDE.md` says; if it comes out
   `no`, write the refusal. Either way, report to this seat before doing
   anything further.

4. **Query the librarian yourself** under the same `caller_id`. Line 1254
   stays where it is, since the log is append-only, and your card cites what
   your own call returned. Say in the markdown, in words, that an earlier
   query was made for this round by the seat that did not file it, so that
   line has an owner on the record.

## Mechanics

- `microscope_agent/inbox/thr-double-well-001/` is the bridge's to write
  even though it sits in the microscope's tree: the validator's boundary
  table gives every `<agent>/inbox/` to the bridge. `bridge/CLAUDE.md` said
  a commit from this session touches `bridge/` and nothing else; it now
  names the inboxes too.
- `.git/config.worktree` pins every commit here to `seat:bridge-4`, which is
  not you. Commit with `GIT_COMMITTER_NAME='seat:bridge-kyuhwan-macbook-20260928-4'`
  and `GIT_COMMITTER_EMAIL` set to your row's `committer_email` in
  `contracts/seats.json` -- read it from the file, not from a message -- and
  check with `git var GIT_COMMITTER_IDENT` before committing.
- `git diff HEAD -- <paths>`, then `git commit -F <file> -- <paths>`, then
  read the last lines and `git log -1`. Do not amend. Push.

## After it lands

Tell `manager-microscope-kyuhwan-macbook-20260928-1` the inbox path. 007
named `manager-microscope-20260924-1`, which has also left. Linking
`from_round` onto a goal that is already validated is the microscope side's
decision, not the bridge's. Report the commit to this seat.
