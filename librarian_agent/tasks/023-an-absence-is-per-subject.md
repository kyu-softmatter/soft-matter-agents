# 023 — an absence is per subject, and everything that watches is per name

status: **HELD, not open** · recorded 2026-09-20 by manager-librarian · no work
is ordered by this file

**Read this only when the queue is otherwise empty.** It is a question with no
answer yet, written down because the session that found it ended and the
session that could answer it does not exist. Nothing here is a task; the next
seat may read it and move on.

## The question

librarian-3 raised it closing 022, and 022 does not close it:

> A caller who ignores the suggestion records nothing. There is no gap for
> that lens, so **check 39 has nothing to bite on.**

022 made the neighbourhood speak on a partial answer. That reaches a caller
who reads the answer. It does not reach the record: `kb_gaps` is what a card
carries, a gap is what the server emits, and the server emits one only when
the whole answer is empty. So the 40× working distance — present in the store
under two other names, absent for that one lens — leaves no trace in any card
that failed to notice it.

**The shape: an absence is per SUBJECT, and every mechanism here is per NAME.**
The server is asked for `working_distance` and answers about the name. The
caller wanted it for `objective_mrd77400` and got a complete-looking five.

## Why this is not ordered as work

The obvious fix is to let `kb_query` take the subject, so it can answer "for
that lens, nothing" and emit a real gap. **That collides with the reason
`kb_group` exists as a separate tool at all** (`librarian_agent/CLAUDE.md`):
folding a differently-shaped question into `kb_query` makes the return shape
depend on the arguments, and every caller grows a branch. A subject argument
is exactly that shape of change, and the argument against it was written down
before this case arrived.

So there are at least three candidate moves and this seat does not know which
is right:

1. a subject argument on `kb_query`, accepting the branch;
2. a fifth tool, which repeats `kb_group`'s reasoning and its cost;
3. leaving the server per-name and making the CALLER declare the subject set
   it expected, so the shortfall is the caller's to notice and record — which
   moves the gap into the card, where `kb_gaps` already lives.

The third is the one this seat finds most interesting, because it is the only
one where the thing that was wrong (the caller assumed six and got five)
is stated by the party that held the assumption. But it is a contract change
across three seats and it is not being decided here on one case.

## What would unblock it

A second case. One case is where a mechanism gets designed for the case; two
is where it gets designed for the shape. If a caller misses a per-subject
absence again, under a different quantity, that is the day.

## Not in this file

The `--check` correction from the same report is in `5474b00`: the
store-to-export leg does exist in `export_snapshot.py`, and what was missing
is that it runs in no gate. Check 61 carries it now.
