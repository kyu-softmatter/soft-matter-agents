# 048 — a refuted entry must say so when it is served

status: **open** · issued 2026-10-12 by manager-librarian-20261007-1, on what
manager-microscope-20261003-1 found the same day · **for librarian-20261007-1,
after the query-log commit and before the bench**. It is not urgent, but it
is the one thing in the queue that does not wait on the bench.

## GOAL

`pixel_size_10x_zoom_1x` (E2, `calibration:`) has carried
`refuted_by: [pixel_size_10x_zoom_1x_computed]` since `19930b6`
(2026-09-24): the "measured" 0.65 µm was calculated from the sensor pitch
and the nominal magnification, so the E4 entry supersedes and refutes it. A
microscope goal written on 2026-09-30 still cited the refuted entry **at
E2**: `microscope_agent/questions/mic-20260930-001/v2_goal.json` and
`v3_goal.json`. The grade it claims is the grade the store holds, so the
grade check passes. Nothing on the card or in the check says that the store
itself has refuted the claim.

So either the server's answer does not tell a caller that an entry is
refuted, or it does and the caller did not read it. Find out which, and make
a refuted entry impossible to take at face value.

## TASK

1. **Measure, do not query.** Call `Store.answers_to` and `match` directly
   for the 10x pixel size at the conditions that goal asked, and read what a
   `kb_query` and a `kb_get` hit would carry. Do the refuted entry and its
   refuter both come back? Does the refuted one carry `refuted_by` in the
   answer? Is it ordered below its refuter or beside it? The sort order is
   grade, then rank, then id, so an E2 refuted entry sorts *above* its E4
   refuter.
2. **If the answer does not say so, make it say so.** That is your code. A
   refuted entry is either left out of `entries` or kept with its
   `refuted_by` visible and a flag a caller cannot miss. Choose, say why,
   and keep the same `(query, kb_version)` answering the same way under one
   build. A changed answer under a changed build is the known hazard: write
   it down, and tell me so I can tell the running seats. **A server fix only
   reaches sessions started after it.** Add a self-test assertion and watch
   it fail on the old code first.
3. **List every card on disk whose `kb_refs` or `kb:` numbers cite an entry
   that was refuted or superseded at the card's pinned `kb_version`**, by
   reading only. Report them to me with path, entry and pin. Do not edit
   them; they belong to other seats, and I relay.

## CONTRACT

- No entry changes. The two pixel-size entries stand as they are (rule 8).
- Measuring the code is your job and needs no issued id. A `kb_query` call
  is a query whatever it is for (the root `CLAUDE.md`).
- Once your answer is in, I decide whether a commit-time check should refuse
  a card that cites a refuted entry. That check is `contracts/`, so do not
  write it.

## CONSTRAINTS

- Claim `librarian_agent/src/` and the log by message if another librarian
  seat is live. Commit under your own row with `-F <file> -- <paths>`, and
  validate with the uv form. Report the server-build change in the commit
  message.
- Dead ends go in `failures.jsonl` naming `task: 048`.

## REPORT

What the answer carried for the refuted entry before your change, and after
it. The self-test you watched fail. The cards citing refuted or superseded
entries. The commit. One sentence on what is still not on disk.
