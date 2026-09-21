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
**CORRECTED 2026-09-20. The three lines that were here were impossible and
this seat wrote them.** They asked `configs.json` to be `VALIDATED` and to
carry `kb_refs` and `kb_gaps`. `screening.schema.json` sets
`additionalProperties: false` and declares none of the three, so **any of
them fails check 1** — `microscope-4` measured it rather than arguing it.

The mistake was a category one: **`configs.json` is an ARTIFACT, not a
card.** Cards carry `card`, `status`, `kb_refs` and `kb_gaps`; artifacts
carry `artifact` and their own shape. And S3.0 asks the store nothing, so
there is nothing for a `kb_ref` to hold — §9.1's condition is met by **axis
cards carrying a `caller_id`**, which this stage does not produce.

So the completion condition is what the schema already says: the artifact
validates, `degraded` is honest about whether the service was consulted
(here it was not, and `[]` is correct), and the fan-out is issued **only if
the cap resolved**.

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

`questions/mic-20260919-001/configs.json` exists and **validates** — not
`VALIDATED`, which is a card's word and not an artifact's; see the correction
above.

Then one sentence up: how many configurations survived, and which
discriminator rejected each that did not.

## Not this task

**The axis fan-out** — carded after this. **`mic-20260918-001`** in any form.
**The goal card's own `degraded`**, which is a fact about when it was written
and does not get rewritten.


## The cap will not resolve by a discriminator, and that is the answer

`microscope-4` reports the cap unresolved at four and asks for three fields
on goal r2. All three are needed and **none of them will cut**, which is
worth knowing before they are written:

- **`sample_contrast`** — the card's own open item. Write it; the sample is
  fluorescent and `particles_show_on_the_green_605_path` (E2) is what says so
- **a `contrast` term in `priority`** — `apply_cap` reaches the discriminator
  branch only through this term, so filling `sample_contrast` alone does
  nothing. **This omission is invisible from the `sample_contrast` value**,
  which is why it is listed separately
- **`configuration_preference`** — and the person answered this on
  2026-09-19: **`widefield_inline`**

**Then it still will not cut.** All four survivors declare
`requires_contrast` in `{label_free, fluorescence}`, so on a fluorescent
sample the contrast screen removes nobody. `mic-20260918-001` is the
demonstration: it carried both fields and resolved `cap_resolved_by:
preference` anyway.

**So expect the preference to resolve it, and record that it did.** §4.5.1(c)
is the route and it has already been walked once on this instrument.
`configs.json` should say the cap was resolved by preference rather than by a
discriminator, so M5 can tell the two apart later.

**And a preference is not evidence.** It picks which capable configurations
to spend the fan-out on. It raises no grade, backs no number, and S4 must not
cite it — the artifact has `preference_is_not_evidence` for exactly this.

This is the same shape as card 019's `lock_group`: **a field that looks like
it should cut and does not.** Both cost time because the shape was not
written down. It is now.


## The payload this round carries is revision 1, and revision 2 exists

Reported by `manager-simulation` on 2026-09-21 and confirmed here against
the inbox file. `r1_ask_experiment.json`'s `payload_card` is
`plan-sim-20260917-001` **revision 1**:

```
max_lag_time    2 s        assumed:a_window          E5     -> revision 2 says 30 s
bead_diameter   2 um       assumed:a_sample          E5     -> revision 2 says 5 um, kb E2
diffusivity     0.2 um^2/s computed:stokes_einstein  E5     -> revision 2 says 0.09
```

**The envelope is not wrong and must not be edited** — §7.1 rule 8 makes it
immutable and writing into your own inbox is forging a delivery. What is
missing is a signal, and there is none: the payload is frozen with a hash
over it and only `bridge/threads/…/status.json` moves.

**Two halves, and only one of them is a problem.**

The **bead diameter fixes itself**: the store now carries `calibration:` E2
for it, an axis queries and gets that, and the payload's E5 never enters a
card of ours. `goal.json` here already carries no payload numbers, which is
P3 working.

**`max_lag_time` does not fix itself.** It is the sending side's *design
choice*, so no store entry contradicts it and no query corrects it. On this
side the window is **record length**, and exposure count, photodamage and
drift budget all hang off it. **A 2 s window and a 30 s window are different
experiments and neither one fails.**

**So do not take `max_lag_time` from this payload as if it were current.**
If a bound needs it, cite it as *the round's revision 1 value* and record
that revision 2 exists. Whether the right answer is a round 2 or a
correction to round 1 is **the bridge's call** and has been raised there —
not this card's, and not the simulation side's to push.

This is the same shape as yesterday's A6 gap: **the name matched and the
answer changed.** Matching a name and not looking at the answer is what
lets it through quietly.


### And a round 2 is not available yet — the bridge says so

`manager-bridge` verified the pin independently and added the half neither
this seat nor the simulation side had:

**r1 cannot be amended.** A round is an event, not a mutable statement. The
delivered copy must match the thread copy byte for byte by `canon_sha`, the
ledger pins revision 1, and P1 says the delivery happened and the file is
its record. So the correction has to be a **round 2**.

**And the wire refuses one today.** Check 8 treats a second round with the
same direction and the same observable as a **repeat** (§4.4 rule 5). That
rule exists to stop a question being re-asked after it was answered, and
this is not that: **the source moved under the round.** It is a gap in the
contract, it is `manager-bridge`'s, and it is with architecture.

**So the practical instruction for this card is narrow and it is a stop.**

**Do not design an acquisition against `mic-20260919-001` until r2 exists.**
Screening and the cap can proceed — they do not touch `max_lag_time`. What
must not happen is a record length, an exposure count, a photodamage budget
or a drift budget derived from a 2 s window, because **an acquisition built
for 2 s answers a 30 s question without failing.** It becomes a different
experiment, and that is the failure mode that leaves nothing behind.

**If design work has already been spent at 2 s, it is not wasted for the
reason it looks.** It is not wrong arithmetic; **the question changed under
it.** Write that in the failure record rather than deleting the work, and
say which revision it was against — the next seat will otherwise read it as
an error and look for the mistake.

### The shape underneath, because it will recur

**The delivery path exists and the retraction path does not.** An inbox
envelope is immutable by design (§7.1 rule 8), `status.json` is not ours to
read, and no field anywhere says *the sender has moved on*. So a round going
stale in our hands has **no channel at all**.

It was carried to us by a chat message, out of band, leaving no record —
which is precisely what check 50 was written about, one level on. **This
paragraph is the record**, and it is here rather than in a reply for that
reason.
