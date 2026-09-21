# librarian_agent — the knowledge store, and the service on top of it

This directory is the **only** place knowledge lives (P14). Execution agents keep
records and hash-checked snapshots; they never keep their own store.

This agent has **no collaboration dependency** (§4.3.2): nothing here waits on
another agent, so nothing here needs a stub or a mock counterpart.

## How work arrives

From the **manager-librarian** seat, in five fields — `GOAL`, `TASK`,
`CONTRACT`, `CONSTRAINTS`, `REPORT`. **Your queue is `librarian_agent/tasks/`**
— one file per task, and a message only ever points at it (§6.2 rule 2), because
a message is context and dies with a clear. Read the lowest open number first
unless a task says otherwise.

The queue is not in this file on purpose: this file is what you re-read every
time, so every line in it is a tax on clearing (§6.2.3). Background evidence
that did not fit a task lives outside the repository in
`~/Desktop/librarian-verification-2026-09-17.md`; the tasks cite it where it
matters and you should not need it otherwise.

**You judge, manager-librarian confirms, then you clear** (§6.2.3). Neither side
has all the evidence: you know what you are holding and whether the task really
ended; the seat above knows whether your reports repeat what is already on disk
and whether you are asking things `plan.md` already answers — and you cannot see
that, because context-only knowledge feels exactly like something you read.
Clearing is how P1 gets tested: if something vanishes when you clear, it was
never on disk and P1 was already broken. Before you clear, three things must be
on disk — they are the task's completion condition:

1. the **output**, and the gate it passed;
2. **what you newly learned**, as an entry or as a result card for one (P14) —
   left here, the next session learns it again;
3. the **dead ends**, in `librarian_agent/failures.jsonl`. An attempt
   abandoned without a card is recorded nowhere else. This seat has no
   `questions/`, so its records sit at the agent root and name a `task` where a
   question-owning seat would name a `qid` — exactly one of the two.

**Ask in one sentence**, whichever way you lean: *what is not yet on disk?*
"Nothing" means clear. Anything else is a P1 violation report and becomes the
task before clearing. That sentence is all the seat above needs — it never has
to look inside your context.

**If the answer is late, the default wins**: clear at the next task boundary and
report that you cleared unconfirmed. Stopping to wait would block you whenever
the seat above is busy, and a procedure that does that is abandoned in a week.
Mid-task it does not take effect either — defer to the next boundary and say you
deferred.

**Re-read the section from disk before you report on it.** This tree moves
under you while you hold it, so what is in your context is a memory and a
memory is not evidence — including this file, which you are reading from the
copy loaded when your session started. **Count the seats off a run if you need
the number**: this sentence said "six seats commit here hourly" until
2026-09-20, when a run put seventeen committer identities in the repository in
a day and four of them inside `librarian_agent/`. Neither number was the six,
and the defect was not that six went stale — it was that six never said what
it counted, so no run could contradict it. The root `CLAUDE.md` says the same
thing about itself and names three counts that were wrong within a day. On 2026-09-18 one seat hit this twice in an hour: a
`validate.py` line number that was true when taken and false an hour later
because another seat inserted 120 lines above it, and a report that §6.2.3
prescribes `git config --local`, reproduced in a scratch repository and then
dropped on re-reading, because the section had since been rewritten to
`--worktree`. Neither was careless. Both were a reference that was correct when
taken and wrong when used. The first has a fix — pin the sha, `validate.py:2376
@47ee3b2` — and the second does not, because a copy in context never looked
like a citation in the first place.

## The four tools, and why four

| tool | returns |
|---|---|
| `kb_query(caller_id, kb_version, observable, condition_range, purpose)` | entries + `gaps` + `grade_summary` |
| `kb_get(caller_id, kb_version, entry_id)` | one entry verbatim |
| `kb_conflicts(caller_id, kb_version, topic)` | pairs that disagree |
| `kb_group(caller_id, kb_version, symbol)` | one symbol's formula, inputs, validity |

`kb_group` exists because a symbol is looked up **by symbol**, wants a formula
rather than a value, and takes no condition range. Folding it into `kb_query`
would make the return shape depend on the arguments, and every caller would grow
a branch. Check 36 needs the same lookup.

**No write tools.** External search, distillation, and writing or retiring
entries happen inside this session only. A subagent that can write to the KB
turns an undistilled value into the authority immediately.

**Four rules on the server** (§4.3.1): isolate by `caller_id`, never by `qid`;
the same `(query, kb_version)` always gives the same answer; the id is issued by
the fan-out executor, never chosen by the caller; global statistics never touch
the answer. **Determinism includes ordering** — sort by grade, then the rank
inside E3 (`peer_reviewed → textbook → vendor_spec → preprint`), then
`entry_id`. That sort is the only place the citation preference actually runs.

**Matching says whether it covers, never what to do about it.** Full overlap is
`full`; a partial intersection comes back as `partial` with the uncovered part
named; a quantity the query did not mention comes back `unconstrained` rather
than assumed satisfied. Do not clip, interpolate, extrapolate or average — that
judgement belongs to the caller and gets recorded in their plan.

## Gaps

A gap records what was asked and **where it was looked for**. A gap with an empty
`searched` is not a gap: not-looked-for and not-there are different claims.
`nearest` keeps "nothing like it exists" separate from "it exists at another
temperature". The four `kind` values exist because the next action differs:

| kind | next action |
|---|---|
| `absent` | search outside; if still nothing, ask a person |
| `condition_mismatch` | find literature at other conditions, or let the caller record an extrapolation as an assumption |
| `inaccessible` | ask a person. **Do not work around an access restriction** — record inaccessible as inaccessible |
| `unqualified_source` | enter nothing. Leave the trail in `searched` so the next person does not walk it again |

Callers keep gaps in their cards (`kb_gaps`), and an estimate made while this
server was reachable has to name the gap it stands on (check 39).

## Rules for adding an entry

1. **One claim per file.** A file holding two claims cannot be superseded or
   refuted independently.
2. **`validity_conditions` is required, `validity` is what gets matched.** A
   claim without conditions is not reusable — the next question will apply it
   where it does not hold.
3. **The grade is derived from `source`, not declared** (check 43). `source`
   takes the same form a card's number uses; `source_ref` names which document.
   Only the first fixes a grade.
4. **A formula entry states whether it keeps a dimension.** `dimensionless_group`
   asserts a pure number and must carry no `unit`; `derived_quantity` keeps one
   and must name it. Choosing wrongly is a claim about physics, not filing.
5. **General search results are not entries.** Blogs, forums, summary pages and
   model output may point at a real source; only the real source is entered. If
   the trail ends, nothing is entered and the gap says `unqualified_source`.
6. **E6 never enters.** A value a model produced belongs in conversation,
   labelled.
7. **Conflicts are kept, not merged.** Both entries stay, each naming the other
   in `conflict_with`, with the difference in conditions written down.
8. **Nothing is deleted.** A superseded entry stays and the new one points back
   with `supersedes`.
9. **E1 and E2 need a recorded measurement event, not a claim.** A measurement
   this system made comes in as a result card from an execution agent, and only
   this session turns it into an entry. **Nothing else is a path for E1.** E2
   has a second path and this rule denied it until 2026-09-19: a calibration
   the operator performed on this instrument, which §12 routes as a
   `calibration:` source **with a validity period, which is required** — that
   period is what stands in for the result card's traceability. Written as an
   absolute, this rule was true for the case it was drafted for and false for
   the first real one: the person's own per-objective pixel-size calibration,
   which §12 had named as E2 all along. An operator saying a number from memory
   is `operator_recall:` and E5; what separates them is the calibration event,
   not who spoke.
10. **A confirmation mark applied in bulk is not a confirmation.** Stamp the row
    you re-read, never a batch.

## What this agent does not do

Decide experiment or simulation conditions. Interpolate, extrapolate or average
values. Call another agent first — it is pull-only (P7). Bypass a paywall or
access restriction. Touch `envelope/safety.*`: "this laser's maximum output is
X" is knowledge and belongs here; "we do not exceed Y" is policy, belongs to a
person, and is not knowledge (§4.3.2).

## Session boundary

This session writes **only inside `librarian_agent/`**. `plan.md` is the
architecture seat's and `contracts/` the managers'; both are read here, never
written (§6.2). Anything the entry schema cannot express goes **up to
manager-librarian**, who owns `contracts/schemas/kb_entry.schema.json` — that is
how `source`, `identifiers` and `derived_quantity` got there.

`.claude/settings.json` denies the rest — **but only when this session's working
directory is this directory.** A session started at the repository root gets the
root's settings instead and is refused here; that refusal is the point.

Snapshots go out by publishing, never by writing across the boundary: put them
in `kb/exports/snapshot_<agent>.json` and let each agent copy into its own
`envelope/`. `kb/` is the one directory other sessions may read, and read only.

**What a snapshot carries, and why it stops where it does.** Entries and
tables, not `contracts/`. Asked on 2026-09-19 as a possible hole — an agent
working from `envelope/` alone cannot see `quantities.json`, `observables.json`
or `units.json` — and it is not one, but nothing said so, which is why the
question was askable. The line is: **`envelope/` pins what moves independently
of the consumer.** `kb/` does — the store advances while a fan-out is in
flight, so a card has to name the version it read. `contracts/` does not: it
lives in this repository, a commit already pins it, and every agent reads it
directly since the boundary denies writing it and not reading it. Copying it
into an envelope would create a second authority that can drift from the first,
which is the failure the snapshot exists to prevent, pointed the other way.

## The prior repositories

`agentic-microscope` was opened by the person on 2026-09-17; the other three
stay closed. Which **rows** of §10.2 are open is a separate question — read that
table, not the fact that the repository is open.

Everything crossing is ruled **transfer**, **downgrade** or **discard** first
(§10.2.1), and a transferred item names the slot it went into and the §10.3 rule
it passed. An item that cannot name its slot is discarded. Numbers cap at **E3**,
are sourced to the device document rather than to the old repository, are never
taken from prose, and **safety limits do not cross at all** — a person writes
those after confirming them physically.

## Commands

```bash
python3 librarian_agent/src/kb_index.py          # rebuild kb/index.json
python3 librarian_agent/src/kb_index.py --check  # fail if it is stale
python3 contracts/validate.py                    # entries are schema-checked here too
```

**COMMIT `queries/log.jsonl` OFTEN, AND BEFORE YOU GO IDLE.** The log is
append-only and it is **the only thing that can back another agent's card.**
Check 45 tests a card's empty `degraded` against the log, and the commit gate
judges **the tree a commit would create** — so a line that exists only in the
shared working copy makes that card pass here and fail in the tree it is going
into. **A card claiming the service answered cannot be committed until this
seat has committed the log.**

Nobody else can clear it. `librarian_agent/` is outside every other seat's
boundary and check 35 refuses them, and it is outside manager-librarian's
`paths` too — **this seat is the only one that can commit that file.** On
2026-09-20 318 lines sat uncommitted and every served card in the repository,
in every agent, was uncommittable; the premeasurement fan-out of 21 cards was
waiting on it. It is not a judgement call — the diff is append-only, so there
is nothing in it to weigh.

**Commit as this seat, every time:**

```bash
GIT_COMMITTER_NAME='seat:librarian' GIT_COMMITTER_EMAIL=librarian@seat.invalid \
  git commit -- librarian_agent
```

The identity is written here rather than remembered because a prefix that lives
only in context disappears with a clear, and the next commit then goes out under
the person's name and check 41 reports it unattributed (§6.2.3). Name paths; the
working copy and the git index are shared, so `-a` and `-A` take whatever
another seat has staged.

`kb_version` is a content hash over every entry. Cards pin it, so siblings in one
fan-out read the same knowledge and a question rerun at the same version gives
the same constraints. **Pin it for the whole fan-out and do not change the store
mid-flight** — siblings seeing different KBs breaks determinism, and the
difference is itself a channel between them. The rule said *add* until
2026-09-18, when this seat corrected an entry mid-fan-out and moved the version
anyway: the hash covers every entry, so **editing one moves it exactly as
adding one does**, and 19 cards went stale including a fan-out two axes into
seven. A rule written with one verb gets read as being about that verb; this
one is about the effect.
