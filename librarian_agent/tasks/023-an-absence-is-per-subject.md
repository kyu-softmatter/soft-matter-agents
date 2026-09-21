# 023 — an absence is per subject, and everything that watches is per name

status: **TRIGGER MET 2026-09-20, raised to architecture** · recorded and
updated 2026-09-20 by manager-librarian · still no work ordered by this file

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

## IT WAS THE SAME DAY. The second case, measured

Found by the librarian execution seat reading this file with an empty queue,
and produced by their own 024 work a few hours earlier.

**Measured through `Store.answers_to` and `match` directly rather than
`kb_query`**, by the seat at `42017f1` and re-measured here at `fdb08a4`,
both at `kbv-137828bc0b27` with 92 entries. No `kb_query` call means no log
line existed, so there was nothing to divert and no caller_id to invent.

The sha is pinned beside the version because 025 changed `match` today: the
same question against a pre-025 build answers the `oil` row differently. A
`kb_version` alone says which knowledge answered and not which code did.

*This file said "log diverted" until the seat corrected it. The first
verification here did divert a log, and did it by calling `kb_query` under a
made-up issued-looking caller_id — which is the thing 4.3.1 rule 3 forbids
and which this seat had said out loud, hours earlier, that it would not do.
Redone by the method above; the numbers are unchanged and the method is
not.*

```
CASE 1   kb_query('working_distance')                 5 entries, 0 gaps
         missing: objective_mrd77400, held as _min / _max

CASE 2   kb_query('refractive_index', 605nm/293.15K)  14 entries, 0 gaps
              full      1   water_refractive_index_605nm_293k
              disjoint 13   including all three air entries, on temperature
         A6 needs air, water and oil. water answered; air and oil recorded
         nowhere.
```

**Same shape, two different routes to the silence.** Case 1 has no
`condition_range`, so the gap clause that would fire cannot. Case 2 is
*covered* — one entry matched, so the clause is suppressed. A gap predicate
that can go quiet two independent ways is not one mechanism with a hole; it
is the shape this file named.

**And case 2 is the stronger one.** Case 1's missing value was in the store
under another name, so 022's `near_names` can point at it. Case 2's oil is
**not in the store at all** — there is no name to point at, and still no gap.
That is 022's mechanism measured out of reach rather than argued out of it.

## A fourth candidate appeared, was measured, and died

The seat proposed it and killed it in the same pass: leave the server
per-name and make the SUBJECT an addressable handle, turning a per-subject
question into a per-name one with no contract change — the trick that made
`immersion` work in 024. Measured:

```
kb_query('oil',   no conditions)   2 entries, 0 gaps
kb_query('oil',   605nm/293.15K)   2 entries, 0 gaps      <- nothing exists
kb_query('air',   605nm/293.15K)   6 entries, condition_mismatch
kb_query('water', 605nm/293.15K)   4 entries, 0 gaps      <- covered, correct
```

**Exactly inverted.** The medium that exists at the wrong temperature is
recorded; the medium that does not exist at all is not. The reason is
unpleasant: two oil LENSES answer the handle, so `returned` is not empty and
`absent` cannot fire, and the lenses share no condition with the query, so
`condition_mismatch` cannot fire either.

**The join that 024 built to make the hole visible is what hides it from the
record.** The seat's own note said the hole "is visible at the handle" and
that was true; visible and recorded are two things, and this file exists
because they are.

## What the two cases decide

Candidate 4 is dead. Candidates 1 and 2 are unchanged and still carry
`kb_group`'s objection. **The evidence points at candidate 3**: in both cases
the assumption was the caller's — six objectives in one, three media in the
other — and in neither could the server have known it. A party that did not
hold the assumption cannot record its failure.

Raised to architecture on 2026-09-20 rather than decided here: it is a
contract change across three seats, and this file has said from the first
line that it would not be settled on one case. It is now not being settled on
two, either — it is being handed up with two.

## Not in this file

The `--check` correction from the same report is in `5474b00`: the
store-to-export leg does exist in `export_snapshot.py`, and what was missing
is that it runs in no gate. Check 61 carries it now.
