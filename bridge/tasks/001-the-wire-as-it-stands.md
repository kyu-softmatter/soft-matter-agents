# The wire, as it stands on 2026-09-19

Written by manager-bridge. This is the standing record; a message may point at
it but may not replace it (§6.2-2). If something here is wrong, send it up
rather than editing the file — `bridge/tasks/` is the manager's to write.

## What check 8 holds a round to

Read this before writing a round, and treat a refusal as a report worth
sending up rather than a puzzle to work around.

- The envelope is the bridge's and carries nothing of its own: `author: bridge`,
  and `numbers`, `assumptions`, `kb_refs` all empty.
- `direction`, the card kind and the payload's author agree, three ways.
- `qid` is the payload's. A `thr-` thread, never a `solo-` one. Round ≥ 1.
- `payload_hash` is the canonical hash of the payload exactly as carried.
- The answerability verdict is **derived** from `contracts/observables.json`
  and the receiving side's capabilities table. Claiming more than the tables
  say is refused. `no` belongs in a refusal card, never an envelope;
  `undeclared` holds the round and gives the turn to a person.
- `unit_consistency: no_counterpart` is the opening round only.
- One `(direction, observable)` per thread. A repeat is a substitution in
  `status.json`, not a second round.
- A delivered envelope (`VALIDATED`) needs `r<N>_hashes.json`, and the ledger's
  `source` has to match the payload by id, revision and status.
- `blocked_pairs` with one pair in two rounds means `escalated`, turn `human`,
  and no further round. A repeat visible in the thread's refusals but missing
  from the ledger fails too.
- The envelope carries the payload's `degraded`. A plan made without the
  librarian must not read as normal on the other side.
- Under `bridge/threads/<name>/`, the directory name is the thread.
- The markdown may not contain a number: the envelope's `numbers[]` is empty
  and check 9 requires every number in a markdown file to be in its card.

## Four things settled on 2026-09-19

**The ledger does not hash `status`.** It hashes the card with status removed
and records the status separately. Approving a carried plan used to change its
digest and make a correctly transported round report tampering — which would
have refused the approving commit and every commit after it.

**`plan_completion` is the plan, not the run.** §4.4 grants one automatic
trigger and that is it, so a finished run does not open a round: a person does,
under `human`. A plan crossing is not a comparison — M4 wants two results for
one observable, and carrying a plan is how the second side learns which run to
do.

**Rounds are `r<N>_`, revisions are `v<N>_`** (§7.1 rule 3). Check 13 reads each
against its own field.

**A result says which estimator it ran**, by naming the vocabulary version it
followed rather than copying the estimator text. Check 46 refuses a pin that
stood at no commit.

## Calling the librarian

The bridge's `caller_id` is `bridge:<thread>:r<N>` — for example
`bridge:thr-tracer-diffusivity-001:r1`. Declared in §4.3.1, and as of
2026-09-19 accepted by `common.schema.json`, which is the one place the pattern
lives now: `axis.schema.json` and `screening.schema.json` both point at it
rather than each carrying a copy, and they had already drifted apart on whether
the revision was part of the id.

The unit is a thread and a round rather than a question, because one thread
crosses two qids, one per side. The `bridge:` prefix is there so a parser
splits the id without knowing the namespace.

Until 2026-09-19 no id existed that this seat could legally use, so item 5 of
`bridge/CLAUDE.md` — duplicate blocking against the store, which is the whole
reason a round can be substituted rather than spent — could not be performed at
all. That is now open. What it means in practice:

- A round may only claim `degraded: []` when a query under its own `caller_id`
  is in `queries/log.jsonl`. Reading the store's files is not the service
  answering (§0.3), and a refused call leaves no line at all — so an empty log
  is indistinguishable from never having asked.
- `degraded: ["librarian_agent"]` remains the right entry whenever the tools
  are absent from a session, which is a fact about the seat and not about the
  store.

Do not invent an id to see what the server accepts. A fabricated `caller_id` in
the query log is the impersonation §4.3.1 rule 3 exists to prevent.

## Recorded

**2026-09-19, the first bridge session read `librarian_agent/src/mcp_server.py`
and `librarian_agent/queries/README.md`** while diagnosing the caller_id
rejection, and reported it. §6.2 rule 3 bars reading another agent's directory,
not only writing to it; the bridge's exception covers the two executing agents'
`questions/` and nothing else. Nothing was written and check 35 reads commits,
so nothing caught it — the seat did.

The part worth keeping is that the same answer was available inside the
boundary: the pattern is in `contracts/schemas/axis.schema.json` and the
grammar in `plan.md` §4.3.1, so the server file added nothing. The second
bridge window reached the same conclusion from §4.3.1 alone.

A dead end that produces no card belongs in `bridge/failures.jsonl` (§7, §8.1);
a seat without `questions/` writes only there. The validator did not know that
path until 2026-09-19 and now does.

## Two bridge sessions

A second execution session was opened on 2026-09-19. Allocation is by thread:

- `thr-tracer-diffusivity-001` belongs to the session that opened it. Another
  session does not touch it unless it is handed over here.
- A second session takes the next thread and says so here.

`status.json` is the collision point, because it is overwritten as the turn
moves rather than appended. Two sessions writing one thread lose a turn without
either seeing it.

The second session has no seat identity yet: `seats.json` lists one bridge
execution seat. **Do not commit under `bridge@seat.invalid` while holding a
different session** — one identity for two sessions is the hole that let three
commits go unattributed on 2026-09-17. Its registration was requested from the
architecture seat on 2026-09-19.
