# 012 — round 2 is open, and one line in this tree refuses it

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

## Round 2 is unblocked on the bridge's side

`ffed020` landed `supersedes` and check 8 **recomputes** it rather than
accepting the claim. A superseding round is legal: it names the round it
replaces, and the two ledgers have to agree that the source moved.

The bridge does not open a round by itself — **this seat requests it and the
bridge writes it** (§4.4, and `status.json` records r1 was opened that way).

## It would be refused today, and the reason is here

Check 8 compares the two ledgers' **card id**:

> *a superseding round carries a later revision of the SAME card; a different
> card is a different question*

```
r1_hashes.json  card_id  plan-sim-20260917-001        revision 1
revision 2      id       plan-sim-20260917-001-r2     revision 2
```

`src/plan_card.py:117`:

```python
f"plan-{qid}" + ("" if revision == 1 else f"-r{revision}"),
```

**Revision 1 has no suffix and revision 2 does**, so the two revisions of one
plan are two card ids, and the supersession reads as a different question.

## The id should be stable, and three things say so independently

- **The microscope's revision-2 cards keep their id.** All six
  `v2_axis_widefield_inline_*` carry `revision: 2` with the id unchanged.
  Ours is the only card in the repository whose id moves with its revision.
- **`plan_approval` and `result` each require `plan_id` AND `plan_revision`
  as separate fields.** If the id carried the revision, the second would be
  redundant — and worse, an approval naming `plan-sim-20260917-001` at
  revision 2 would match no card at all. There are no approval cards yet
  because every run has been Tier 0-1, so this has not bitten; it is waiting
  for the first Tier 2 plan.
- **Revision 1 itself.** The suffix is conditional on `revision == 1`, which
  means the scheme already agrees the bare form is the card's name and then
  stops using it.

## What it touches — six files, and one of them is append-only

```
src/plan_card.py                              the generator
questions/…/v2_plan_simulation_….json         the card
questions/…/v2_plan_simulation_….md           generated, follows the JSON (P3)
questions/…/result_run-20260921-001.json      plan_id
runs/run-20260921-001/config.json             plan_id
runs/run-20260921-001/log.json                plan_id  ← append-only (7.1 rule 9)
failures.jsonl                                a row mentions it in prose
```

**The run log is the hard one and this card does not rule on it.** §7.1
rule 9 makes it append-only, and `011` just showed the line that distinguishes
a rewrite from a key correction: nothing there was wrong, the field was
missing. Here the field is not missing — the value would change, and the value
is what the run actually stood on at the time. That is a different case from
`011` and possibly from `555317b` too, where a wrong count was fixed by a new
row rather than in place.

**Work out the least-bad path and say which you took and why.** If the honest
answer is that the log keeps `-r2` because that is what was true when it ran,
then the ledger for r2 has to pin the plan card and not the log, and that is
worth writing down. If regenerating revision 2 changes its hash, say what that
does to `result_run-20260921-001.json`'s `plan_hash` and to the run that
cites it — **a card whose hash moved under a result is the thing `plan_hash`
exists to catch**, so do not let it pass silently.

## Then request round 2

The payload is the **revision-2 plan card**, not the result card. The ask
schema's `trigger` says `plan_completion` is the plan reaching its finished
state "**and not a run finishing**", and r1 carried a plan. r2 must carry
`supersedes: 1` and its own `r2_hashes.json` pinning the same card at
revision 2; the bridge writes both and verified the accepting path in an
isolated tree.

**The result card crossing is a separate round and not this one.** Do not
bundle it to save a trip — r1's payload being a plan is why the microscope
built an acquisition on it, and a round that carries two kinds of card at
once makes the receiver guess which one it is answering.

## Why this is worth the detour

The microscope has been holding a 2 s window for over a day while the current
plan says 30 s, and it has already built on it: `mic-20260919-001/goal.json`
carries `from_round: thr-tracer-diffusivity-001:r1`. That is not a round
waiting to be read, it is a round that was read. Every day this stays open is
a day of acquisition design against a superseded bead.
