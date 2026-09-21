# 010 — S3.0 for `mic-20260919-001`, the bridge round's question

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**REASSIGNED to `microscope-5` on 2026-09-20.** `microscope-4` holds no
commit in the last twenty and the round has been sitting since 02:53Z, so
the card moves rather than the work waiting on a seat that is not there.
**This is the only way a card changes hands** — it is edited, not relayed:
a chat message is not an assignment (see `CLAUDE.md`). `microscope-4` is not
to pick this up; if that seat returns, report up and I will card it
something else.

**DO NOT RE-COPY THE ENVELOPE while this runs.** `microscope-1` is finishing
a1 on `mic-20260920-001`, whose fan-out is pinned to `kbv-1dabfd5ad58d`, and
`pin_kb_version()` now reads the envelope. Moving it would pin a1 to a
different store from its six siblings and check 58 would refuse the set.
Your S3.0 mints a **new** fan-out, so it pins to whatever the envelope holds
and collides with nothing — that is why this card can run now and the re-pin
cannot.

~~This card was `microscope-4`'s~~, minted today and active in
`contracts/seats.json`. Confirm that yourself before committing — a seat named
in chat is not a seat until the registry says so, and this card cannot give
you one (§6.2.2).

## Why this one, and why it is safe to run now

`mic-20260919-001` holds **only a `goal.json`**. S3.0 has never run for it, so
there is no `configs.json` and no fan-out. It came from the bridge:
`from_round: thr-tracer-diffusivity-001:r1`, and what is asked of this side is
the counterpart measurement to the simulation's `plan-sim-20260917-001`.

**It does not collide with card 008.** That card is re-pinning
`mic-20260918-001` under another seat, in a different question directory. Two
microscope seats are working at once and the surfaces you share are listed at
the bottom — read them before you start, not after.

## The task

**S3.0 only. Produce `configs.json` and stop.**

Screen `contracts/capabilities/microscope.json` for configurations that
declare `tracer_diffusivity`, apply the discriminators §4.5.3 allows at this
stage, and write the screening card with the fan-out's `caller_id`s. Do not
write an axis card; the fan-out is a separate task and will be carded once
this lands.

**Pin to the store as it stands when you run**, and say which version in the
card. This is a fresh question with no siblings to agree with, so nothing
constrains the pin — unlike `mic-20260918-001`, which is mid-re-pin and must
not be touched from here.

**`caller_id`s carry the revision**: `mic-20260919-001:v1:<config>:<axis>`,
seven of them, one per axis. The form without `v<N>` is the old one and is
being retired.

## What is different from the first question

**The store is much larger than when `mic-20260918-001` was screened.** That
one was pinned at 25 entries; the store is now in the eighties. Facts that
were absent then are present now — the tracer diameter is `calibration:` E2,
the filter passbands are in, the calibrated pixel sizes are in. **Do not carry
over conclusions from the other question's `configs.json`;** re-derive. Its
screening is a record of what was knowable in the store of 2026-09-18.

**The goal card is `degraded: ["librarian_agent"]`** — written before the
service answered. Your screening is not: the service is up, so
`configs.json` should have `degraded: []` and its `kb_refs` and `kb_gaps`
filled from real calls. That is §9.1's condition and this question has not
met it yet.

**`configs.json` is S3.0's card, so it is yours to write here.** The usual
rule that you do not touch it applies to a fan-out already running.

## What holds

**Three configurations at most** (§4.5.3). If more survive, **stop and ask** —
do not cut on a discriminator S3.0 cannot evaluate. The goal's priority terms
(`physical_feasibility`, `target_accuracy`, `evidence_grade`, `cost`) are all
things S3 produces, so none of them can decide what S3 runs on. That was
settled after a seat tried it.

**`perturbation` configurations do not screen on observables.** They produce
none by definition; they compose onto an imaging configuration when the goal
asks for driving. This goal asks for diffusivity and drives nothing, so expect
`trapping` to be rejected with that reason rather than silently dropped.

**Preference is not evidence.** If the person has stated a configuration
preference, honour it and record it as a preference — it does not become a
ground.

## Surfaces you share with the seat running 008

- **`envelope/snapshot.json`** — that seat is copying a fresh export into it.
  **Read it if you must; do not write it.** Your screening does not need to.
- **`src/axis_common.py`** — do not edit. Helpers go in your own module, and
  if something genuinely belongs in common, say so and I will card it.
- **`questions/mic-20260918-001/`** — not yours at all this round.
- Commit with `git commit -- <paths>`, and **run `git diff -- <paths>` first**:
  naming a path is not naming a change, and another seat's edit to a file you
  name rides in under your identity. That happened twice in one hour on
  2026-09-19.

## Done when

`questions/mic-20260919-001/configs.json` exists and is `VALIDATED`, it names
the version it pinned, `degraded` is `[]` and honest, `python3
contracts/validate.py` ends `0 failed`, and one commit as your seat.

Then one sentence up: how many configurations survived, and which
discriminator rejected each that did not.

## Not this task

**The axis fan-out** — carded after this. **`mic-20260918-001`** in any form.
**The goal card's own `degraded`**, which is a fact about when it was written
and does not get rewritten.
