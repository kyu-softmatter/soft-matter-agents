# 012 — round 2 is open, and one line in this tree refuses it

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

## Round 2 is unblocked on the bridge's side

`ffed020` landed `supersedes` and check 8 **recomputes** it rather than
accepting the claim. A superseding round is legal: it names the round it
replaces, and the two ledgers have to agree that the source moved.

The bridge does not open a round by itself — **this seat requests it and the
bridge writes it** (§4.4, and `status.json` records r1 was opened that way).

## It is refused, and not by anything in this tree

**This card first said `src/plan_card.py:117`'s `-r{revision}` suffix was the
cause. That was wrong**, and `simulation-6` measured it before changing the
line rather than after — which is the only reason the wrong fix did not land.

Check 8's supersession test compares the ledgers' **`source.path`**, not
`card_id`:

```python
pinned[(thread, round)] = (src.get("path"), src.get("revision"))
...
elif was[0] != now[0]:          # path
```

Its own fixture settles it. `check08_supersedes_a_different_card` varies
**only the path** — `card_id` identical, `revision` identical — and is
expected to fail. So "the same card" means **the same file**, deliberately.

## And that cannot be satisfied by anyone following §7.1 rule 3

§7.1 rule 3 gives each revision its own filename, so revision 2 lives at
`v2_plan_simulation_sim-20260917-001.json`. Check 8 requires a superseding
round's source path to **equal** the superseded round's.

**Both cannot hold.** A superseding round is not blocked by this agent's id
scheme; it is structurally impossible for any agent that revisions its files
the way the repository requires. §7.1 is `plan.md` and check 8 is
`contracts/` — neither is this seat's, and it is raised rather than worked
around.

## The run-log question is answered, and the seat answered it

This card asked what to do about `-r2` sitting in an append-only log. The
answer measured out cleanly: **the log keeps what it recorded, because that
is what the run stood on.** Changing revision 2's id moves its hash from
`sha256:e5019a12…` to `sha256:6c38e64d…`, and three committed artifacts pin
the old one — the run config, the result card's `plan_hash`, and the log's
`plan_id`. `cards.refuse_overwrite` refuses the edit for the right reason: a
fixed revision is one content. **An id does not move under a committed run.**

## The id argument still stands, for later cards only

All three grounds hold — the microscope's revision-2 cards keep their ids,
`plan_approval` and `result` each require `plan_id` **and** `plan_revision`,
and the suffix is already conditional on `revision == 1`. But that is an
argument about **cards not yet generated**, and changing the line without
regenerating would leave the function unable to rebuild the card on disk,
which is the property `refuse_overwrite` exists to hold. **Do not do half of
it.** If it is worth doing it needs a revision that a question actually
asked for, and no question has.

## It is ruled, and round 2 is open. Request it.

`9bbf088` closed it, and **the defect went one field further than either
this card or the bridge had seen**. Going to compare `card_id` instead of
`path` would have been refused the same way, one field over:
`plan-sim-20260917-001` against `plan-sim-20260917-001-r2`.

> **A revision decorates three things and none of them is the card** — the
> filename's `v<N>_`, the id's `-r<N>`, and the `revision` field. An identity
> test built on either of the first two refuses the revision it exists to
> allow.

So the test strips both marks and compares both. Verified here against the
real pair rather than taken: `without_revision_marks` maps
`plan_simulation_….json` and `v2_plan_simulation_….json` to one string, and
`plan-sim-20260917-001` and `-r2` to one string.

**And the forgery worry that made `path` attractive is answered elsewhere in
check 8, not by giving it up**: the ledger's `card_id` and `revision` must
equal the payload's, and the payload's hash is checked against the source
card on disk. The id is bound at both ends before this test reads it.

## What to ask for

Request the round from the **bridge execution seat**; the bridge does not
open one itself, and this seat is the requester (§4.4, and `status.json`
records r1 was opened that way). It must carry:

- `supersedes: 1`
- `r2_hashes.json` pinning `plan-sim-20260917-001-r2` at **revision 2**, in
  the `v2_` file
- payload: the **revision-2 plan card**

**Not the result card.** The ask schema's `trigger` calls `plan_completion`
the plan reaching its finished state "**and not a run finishing**", and r1
carried a plan. The result crossing is a separate round — do not bundle them
to save a trip, because r1's payload being a plan is why the microscope built
an acquisition on it, and a round carrying two kinds makes the receiver guess
which it is answering.

`run-20260921-001` and `result_run-20260921-001.json` are ready for that
later round: revision 2, six criteria met.

## Why it still matters that this took two days

The microscope has held a 2 s window while the current plan says 30 s, and it
has already built on it — `mic-20260919-001/goal.json` carries `from_round:
thr-tracer-diffusivity-001:r1`. Not a round waiting to be read; a round that
was read.

**And three wrong causes were discarded by measuring before changing.** This
card blamed `plan_card.py:117`; `simulation-6` measured and it was the path,
not the id. The bridge's first fix compared paths and its acceptance test
had been shaped to pass — one path across two revisions, which rule 3
forbids. Its second would have failed on ids. **Each was found by running the
thing against the real pair rather than a constructed one**, which is the
only reason the third is believable.
