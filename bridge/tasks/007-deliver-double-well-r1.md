# 007 — open and deliver the double well's first round

**For bridge-20260924-1**, from `manager-bridge-20260924-1`, 2026-09-25 about
10:25 PDT. This lifts card 006's "open no round" for **this one round only**.
Everything else in 006 still holds.

**The hand-over is the person's.** The payload is a **result**, so the round
opens with `trigger: human`, and a person has to hand it over. The person did
that in this seat's window, answering "Yes, send it now" to a direct question.
It was not taken from the architecture relay that asked for it. Name the person
as the trigger. Do not name this seat or architecture.

**The run does not wait for this delivery** (update, about 10:30 PDT). In the
architecture seat's window the person decided directly to "Start now".
`manager-microscope-20260924-1` is carding `microscope-20260924-6` onto the
measurement, citing the simulation's committed ask by id. **Still file r1,
without hurry**, so the thread exists and the microscope goal's `from_round`
can be linked afterwards. Say plainly in `r1_ask_experiment.md`, and in
`status.json` if it has a place for it, that **the run started before
delivery, on the person's decision**. Architecture is recording it in
`plan.md` 11-23. Do not rush the round to beat the bench, and do not
backdate anything.

## The round

| field | value |
|---|---|
| thread | `thr-double-well-001` (new) |
| round | 1 |
| card | `ask_experiment` |
| direction | `simulation_to_experiment` |
| trigger | `human` |
| payload_card | `simulation_agent/questions/sim-20260923-101/result_run-20260924-101-v3-hold.json`, **verbatim** |
| answerability | `well_occupancy` against `contracts/capabilities/microscope.json` |
| unit_consistency | `no_counterpart`, `compared_against: null` |
| value_comparison | `no_counterpart` |

**Recompute; do not copy this table's verdicts.** At `a768602` this seat ran
`derive_producible` and got `yes`, producing `transmitted`,
`widefield_inline`, `widefield_side` and `confocal`. The validator was
`0 failed` on `a768602` plus 1 uncommitted path [dirty f08be201]. Check 8
recomputes all of it from your tree, and your tree is what counts.

The source card must be **committed** before you hash it. The ledger pins
`card_id`, `revision` and `canon_sha` of the card as it stands in the sender's
directory; see `bridge/CLAUDE.md` for the hash command.

**One observable gates the round**: `well_occupancy`. That is the simulation
manager's proposal, and card 006 ruled it legal under the rule against opening
the same round twice. The other three observables ride in the payload
unchanged and are not gated.

## Write

```
bridge/threads/thr-double-well-001/
  r1_ask_experiment.json   the envelope
  r1_ask_experiment.md     for a person -- names the payload, restates no number
  r1_hashes.json           the source as read
  status.json              turn: microscope_agent
microscope_agent/inbox/thr-double-well-001/
  r1_ask_experiment.json   byte-identical to threads/
  r1_ask_experiment.md
```

No `status.json` in the inbox. Nothing is ever removed from an inbox. Commit
as `bridge-20260924-1` with the email from `contracts/seats.json`, using
`git commit -F <file> -- <paths>`, then push.

## Two things the envelope must not fix, and may say in words

These are the bridge's findings, and they are **not delivery blockers**: the
round gates on answerability, and every observable is still
`comparable: false`. Put them in `unit_consistency.note` in words, with no
numbers. The markdown carries no numbers either. They are routed separately to
`manager-simulation-20260924-1`.

1. **Residence time uses the wrong estimator.** The card says residence is "the
   mean completed dwell". The registered `well_residence_time` estimator is
   the renewal form, total assigned time over exits, and its entry says it is
   deliberately *not* the mean of completed dwells, because that mean reads
   low. Until one form is used on both sides, residence time cannot turn
   comparable.
2. **The barrier's unit is `1` and not `kT`.** `interwell_barrier_height`
   allows `kT`, `pJ` or `J`. The number is in thermal-energy units in
   substance, but not by its label. A later round's unit check will need the
   labels to match.

## After it lands

Tell `manager-microscope-20260924-1` the path. That seat writes the taking
card for `microscope-20260924-6`, whose goal carries
`from_round: thr-double-well-001:r1`. Report the commit to this seat.
