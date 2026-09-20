# 017 — undo 015, and be precise about how far it goes back

status: closed · **verified on disk 2026-09-20** (1951300) — all four: identity link entry, refuted_by both ways, diameter at E2, renames · issued 2026-09-19 by manager-librarian · **ruling from the person** · start here

## THE RULING

**The bottle IS the Abvigen product. The vendor page is wrong.** 015 is
reversed and marked SUPERSEDED; do not execute it.

**What decided it was not the measurement, it was the asymmetry.** Both
explanations predict green-excited, ~605-visible particles, so the fluorescence
alone never separated them. What separates them is that the Abvigen page has
**two unrelated documented errors** already on record — a monoclonal-antibody
filing, and a product name in the "Particle Size" field. That makes *the data
sheet is wrong* a far cheaper explanation than *the bottle is not the product*.
And 015's only evidence, a silent label, **is equally consistent with both**.

The execution seat found this in the prior repository and stopped before
anything built on 015. That is why this costs one reversal instead of a week.

## Undo it — but not all of it comes back, and not at the grade it left at

`8646426` touched nine entries and added two. Three groups:

**① The identification comes back at E5, not E3.** The label is still silent.
"This bottle is that product" is now **the person's judgement**, supported by
two independent measurements agreeing — but those say *it behaves like a
Cy3-class dye*, not *it is this catalogue number*. It becomes E3 the day
someone reads a label.

**② Material and diameter come back, at E5.** A specification is E3 **about the
type**; applying it to this bottle runs through the link in ①, so §5.8 gives
the chain its worst input. So the eight polystyrene refractive indices apply
here again — and they apply at the strength of the link, not at their own.

**③ Emission and excitation do not come back. They are refuted.**
`tracer_emission_peak` 680 and `tracer_excitation_peak` 620 are not one side of
a live disagreement any more: **two independent observations on two
instruments in two projects** say otherwise. Keep them (rule 8) and record them
as **refuted**, not as contested.

## This is exactly the shape 016 was built for

Architecture's instance / type / link ruling now has its first real content:

```
instance   the bottle on this bench          the sample table (016)
type       AFR-0500-COOH and its spec sheet   ordinary entries, spec:, E3
the link   "this bottle is that product"      E5  <- everything hangs here
```

**Everything in ② hangs off the link's grade.** That is not bookkeeping: it is
why the reversal restores the facts without restoring their confidence, and it
is why 016 and this task are one piece of work rather than two.

## What crosses from the prior repository, and what does not

Your §10.2.1 rulings were right and I am recording them as accepted:

- **TRANSFER** — *the Abvigen page is unreliable*. Slot: a KB entry. §10.3 rule
  1, capped E3. It is a claim about **a published document**, not about any
  bottle, and we hold that document, so it is checkable here. **This is the
  entry the reversal rests on — it has to exist.**
- **DOWNGRADE / do not enter** — their 589–610 measurement. Their bottle, so a
  same-stock assumption at E5 rides on top, and **our own E2 says the same
  thing better.** Adding a weaker echo buys nothing.
- **DISCARD** — their ADU figures. Instrument-specific, no slot here.

## CONSTRAINTS

- ~~Do not let the diameter come back as E3 — it gets weak support, not
  resolution.~~ **STALE, corrected 2026-09-19.** That was written before the
  person measured it at 19:41: **5 µm, CV within 2%, `calibration:` E2**
  (`48f8239`, §11-13). It is higher than the E3 a lot number would have given,
  and because it is an **instance** measurement it **does not pass through the
  E5 link** — it is about this bottle directly. So the diameter is resolved,
  and the simulation's `assumed:` 2 µm is now disagreeing with an E2.
  The execution seat caught that this file was written after the measurement
  and still carried the old constraint.
- **The diameter entry does not exist yet, and that is a P14 inversion** —
  `plan.md` holds a fact `kb/entries/` does not. It was blocked on
  `calibration:` requiring a `validity` that an instance-scoped measurement has
  no interval shape for; **that is fixed as of `a675c4e`**: a `sample` subject
  now satisfies the requirement, because the instance is the subject rather
  than a condition. File it.
- The CV is an interval, not a point value — upper bound, dimensionless, needs
  a `basis`. CV is lot-dependent, which the prior repository's own file says
  out loud, so `valid_until` carries the lot event.
- Record the reversal itself. Rule 8's spirit applies to tasks: what was
  decided, on what evidence, and what overturned it.

## REPORT

Entry by entry for the eleven, with the grade each landed at. Then two things:

**Whether anything outside `librarian_agent/` acted on 015 and needs telling.**
I know of `81e9fb8` and `dd5ee3c` in the simulation seat and have written to
them; say if you see others.

**And the count you owe from 015's report, which still stands**: entries that
were true, well sourced, and about the wrong object. The answer changed — it
is now closer to two than to seven — but the lesson you wrote in `d9d0c29` is
what caught it either way.
