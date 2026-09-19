# 002 — move the target inline, and keep the axis's margin beside it

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**HELD until this question is at revision 2.** Lifted by the seat that makes
revision 2 — you, not this one. The two things this card originally waited on
did land, and then a third turned up that neither seat had looked for. The
procedure below is correct and is what revision 2 does; what is wrong is doing
it in place.

```bash
# The hold is real while this prints a mismatch at revision 1:
python3 -c "
import sys,json; sys.path.insert(0,'contracts')
from validate import card_sha
h = json.load(open('bridge/threads/thr-tracer-diffusivity-001/r1_hashes.json'))
c = json.load(open(h['source']['path']))
print('ledger rev', h['source']['revision'], '| card rev', c['revision'],
      '| hash matches', card_sha(c) == h['source']['sha256'])"
```

`goal.schema.json` now carries the inline target, and its `$comment` on the
superseded branch names **this agent's `goal.json`** as one of exactly two
cards keeping that branch alive. So this is not tidying: a shape the contract
wants deleted stays in the schema until this card moves.

## What the contract decided

A target is a **decision**, so it carries no source and no grade — the same
reason a ceiling in `envelope/safety.json` carries none. A grade says how far a
claim can be trusted; a decision is correct by being made, and grading a
person's own goal E5 says they might be misremembering what they want.

It is **inline rather than by reference** so that a grade is not merely absent
but *inexpressible*. `common.schema.json#/$defs/target` is `{metric, kind,
value, unit}` with an optional `note` and `additionalProperties: false`. That
last word is the mechanism: §2.1 rule 9 — an opt-in guard is not a chokepoint.

A `decision:` source kind was proposed and **rejected**, because `SOURCE_GRADE`
is a function from source to grade and a source yielding no grade punches a
hole in P2.

## Why this group is stuck, and it is not the approval

`3646fb7` found a wall: a card pinned by a signed `plan_approval` can neither
gain nor lose a field (§5.5), because the `plan_hash` moves and the approval
stops covering it. Not should-not — **cannot**, short of asking a person to
re-approve work they already approved.

`sim-20260917-001` has no approval. `goal.json` reads `approval_id: null`,
`status: VALIDATED`, and no `plan_approval` names the plan. `manager-bridge`
surveyed for exactly that and reported this group free.

**It is not free. A delivered round pins the plan, and a round is a hash too.**
`bridge/threads/thr-tracer-diffusivity-001/r1_hashes.json` records
`plan_simulation_sim-20260917-001.json` at `revision: 1` with
`sha256:e3ab814b…`, and it **matches today** — checked with the validator's own
`card_sha`. Check 8 reads that pair:

```python
if on_disk.get("revision") != src.get("revision"):
    continue          # the source moved on; the round is not comparable
if card_sha(on_disk) != src.get("sha256"):
    ... FAIL "Stop the round; do not repair it (4.4 failure table)"
```

Migrate in place at revision 1 and the hash moves, check 8 fails, **and the
finding is filed against `r1_hashes.json` — `manager-bridge`'s tree.** The seat
that caused it cannot fix it there, the seat that owns it did not cause it, and
the message tells whoever finds it not to repair the round. The gate runs the
whole validator, so every session stops meanwhile.

**The escape is in the code's own first line: a revision bump makes the round
non-comparable and the check skips it.** Verified by simulating both. So this
migration happens at **revision 2**, which `000` already has scheduled as the
librarian re-run — nothing extra is being asked for.

`goal.json` is pinned by nothing. It still cannot move alone: checks 12 and 52
tie a plan's carried number and carried target to the goal's, so **both cards
or neither, one commit**. The unit of migration is the qid group.

**The general shape, which is worth more than this instance:** the
approval-pins-a-card argument was attached to approvals, and a hash does not
care what wrote it. Anything that records a card's hash pins that card —
approvals, round ledgers, and whatever records one next. Ask *what holds a hash
of this card*, not *is there an approval*.

## The four places, and the one that is a judgement

1. **`goal.json` → `targets[]`.** `{"metric": "tracer_diffusivity", "number":
   "target_decade_resolution", "kind": "decade_resolution"}` becomes
   `{"metric": "tracer_diffusivity", "kind": "decade_resolution", "value": 1,
   "unit": "count"}`, carrying the existing note.
2. **`plan_simulation_sim-20260917-001.json`** carries its own copy — pinned,
   not referenced, because a `plan_approval` fixes the plan and not the goal.
   Check 52 compares the copy against the goal's.
3. **`plan_simulation_sim-20260917-001.md`** is generated (P3). Regenerate; do
   not hand-edit.
4. **`src/plan_card.py`** names `target_decade_resolution` as a literal in four
   places. Fix the code before the data, for the reason `003` gives at length.

**The judgement is `a_target`, and it is the interesting part.** Its statement
is *"Screening accuracy is one decade"* and its falsifier is *"a question
needing the coefficient rather than its decade restates this target and
switches the intent to confirm."*

Read that falsifier again. It does not say what observation would show the
assumption **false**. It says when somebody would **change their mind**. That
is not an assumption with a weak falsifier; it is a decision that had nowhere
else to live, so it was dressed as an assumption because `assumptions[]` was
the only container that would take it. Now there is a container. When the
target moves inline, `a_target` and `target_decade_resolution` should go with
it — but check what still cites them first, and say what you found.

A success criterion that compared against this number now has `target:
<metric>` as its alternative to `number`; check 6 resolves either, so the
guarantee moved containers rather than being dropped.

## Do not delete the `0.1`

`axis_bd_overdamped_a2.json` carries `target_relative_error = 0.1`,
`assumed:a_statistics`, E5, noted *"ten per cent, which is well inside the one
decade the goal asks for"*. That note puts **two facts in one number**: the
decade is the person's goal, the ten per cent is this axis's own tightening.

The tempting edit, once the person's target is properly recorded, is to replace
the axis's number with the person's because one is more authoritative. That
collapses the fact that costs money. **`0.1` stays, as the axis's margin, and
it stays an assumption** — unlike the target, it *is* one, and a falsifier can
be written for it.

Statistical error goes as `1/sqrt(N)`, so sampling goes as `1/ε²`: ten per cent
against thirty is **nine times the sampling**. It is free today only because A5
says this job is far too small for the budget axis to bind. **Record why it is
free, not just that it is.** The day a real budget exists, a `0.1` chosen while
no target existed at all is where the compute goes, and by then nobody will
know it was never examined.

## One thing still open, and it does not block this

§11-14 — recording in `plan.md` that *the person decided one decade* — is still
open, because the answer reached the architecture seat through another seat's
user and §6.2.2 does not let a relayed answer stand as the person's. **That is
about the record, not about the shape.** The contract's ruling that a target
carries no grade holds for every target, confirmed or not, and the value here
does not change: `1 count`, `decade_resolution`, exactly as it reads today. So
nothing in this card waits on §11-14.
