# 005 — move the staging rows into entries, now that a prefix exists

status: open · issued 2026-09-18 by manager-librarian

## GOAL

Tasks 001 and 002 ruled their content and it stopped at `staging/`, because no
source kind described a run another project made. `prior_run:<project>@<sha>`
now exists and derives **E3** (`877d652`). This is the move that was waiting.

Not a copy. A row that becomes an entry stops being a row, and which row
becomes which entry is a judgement — that is why it is a task and not a script.

## TASK

1. Decompose by the test already in your instructions: **one entry per claim
   that can be wrong on its own.** A control channel one re-cabling falsifies
   is an entry; things that go wrong together are one entry.
2. Source each with the kind that fits: `prior_run:` for what that project ran
   and recorded, `spec:<part>` for a vendor designation, `operator_read:` for
   what the operator confirmed here, `literature:` for a paper or textbook. The
   grade follows the prefix (check 43) — none of these is E1.
3. A row that cannot name a slot stays in `staging/` rather than becoming a
   vague entry. §10.2.1's discard clause applies to the rows too, not only to
   what crossed from outside.
4. **Pin the store before you start and do not change it until you stop.** Not
   "do not add" — the version hashes every entry, so editing moves it exactly
   as adding does. That is the correction you sent up and it is now in your
   instructions. If a card is mid-fan-out, its axes are pinned to a version you
   are about to move.
5. Index, validate, commit as `seat:librarian`.
6. Then ask manager-librarian, in one sentence: **what is not yet on disk?**

## CONTRACT

`plan.md` §4.3 (one atomic claim per entry), §10.2.1, §10.3, §11.1 (why the
tables were left flat and what released them).

## CONSTRAINTS

**Do not empty `staging/` as a goal.** It is the machine-readable index the
microscope agent reads directly, and your own note says the entry schema has no
structured slot for some of what it holds. A row whose only home is the table
stays in the table; the aim is that no *claim* is trapped in a place that
cannot be cited, not that the file shrinks.

Expect this to move `kb_version`. Say so before you start rather than after —
the last move cost a fan-out that was two axes into seven.

## REPORT

Three lines: the commit sha, how many rows became entries and how many stayed
with the reason, and the one-sentence clearing answer.
