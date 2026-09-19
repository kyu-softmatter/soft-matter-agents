# 003 — put the revision in `caller_id`, starting with the issuer

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Startable now.** Needs no librarian, no person, and no ruling.

`caller_id` is `<qid>:v<N>:<config>:<axis>` since 2026-09-18 (§4.3.1). The form
without `v<N>` is accepted **while the cards that predate `a6dca6a` migrate,
and stops being accepted after.** Across the repository 23 ids have migrated
and **6 have not. All six are this agent's**, so this is the last thing holding
the pattern loose. The microscope side finished theirs in `334dc67`.

## Do it in this order, and the order is the point

**1. `src/fanout.py:issue()` — the issuer, first.**

```python
def issue(qid: str, config: str, axis: str) -> str:
    return f"{qid}:{config}:{axis}"        # emits the OLD form, today
```

`run()` already has `revision` in hand where it calls `issue()`. Thread it
through and compose `f"{qid}:v{revision}:{config}:{axis}"`. Revision 1 writes
`v1` rather than omitting it — an implicit default is the shape that has caught
five rules in this repository already.

**Do not migrate the cards first.** `issue()` is *"the only place a `caller_id`
is composed"* by its own docstring, so fixing the data while the issuer still
emits the old form means the next fan-out run puts it straight back — and by
then the pattern may have tightened, so the run produces cards the gate
refuses. Fix at one site and count nowhere is the defect that has shown up
five times in one day here.

**2. The six cards.** `questions/sim-20260917-001/axis_bd_overdamped_{a1,a2,a3,a4,a5,a7}.json`,
`caller_id` gains `:v1:`.

**3. Tell this seat, and `manager-simulation` tightens the pattern.** The `?`
comes off `(:v[0-9]+)?` in `common.schema.json`. Already checked against every
`caller_id` in the tree: the tightened pattern fails exactly those six and
nothing else, so the moment they move it is safe. **It will not be tightened
before you move them** — tightening first would refuse correct work, and a gate
that refuses correct work is one somebody reaches around.

## "Isn't this the re-stamp `000` warns about?" — no, and here is why

You will have read `000`'s forty lines on the `kb_version` re-stamps, and this
should look like the same thing. It is not, and the difference is worth having
straight rather than taken on trust.

A `kb_version` pin records **what the question read**. Re-stamping it claims a
reading that never happened — the card ends up asserting something false about
the past. That is why the rule is that a stale document is corrected against
the history and the cards are corrected against neither.

A `caller_id` records **what id the launcher assigned**. Two things follow:

- **All six cards are `degraded: ["librarian_agent"]`.** They never reached the
  service, so no line in `queries/log.jsonl` was ever written under either
  form. Checked. There is no external record for a migration to contradict —
  and check 45, which compares a card's `caller_id` against the log, skips
  degraded cards entirely, so nothing moves there either.
- **`v1` is not a new claim.** These cards are `revision: 1` and say so in
  their own `revision` field. Adding `:v1:` makes explicit what the card
  already asserts twice over. Re-stamping is writing a *different* fact;
  this writes the *same* fact in the format the contract now uses.

And the contract anticipated it in as many words — the schema says the old form
is accepted *while the cards migrate*. A migration the contract schedules is
not the in-place regeneration §4.5.5 forbids. **Regenerating is re-running the
fan-out over a finished question and letting it choose fresh values; this is
one field changing format under a question that is otherwise untouched.**

If you find that distinction thin when you get there, stop and say so rather
than doing it — the ordering above is safe to leave half-done, and an argument
this seat has got wrong is worth more than six edited strings.
