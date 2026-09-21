# 016 — image the particles alone, because the plan needs the run

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**The person's immediate goal is an end-to-end run.** This card is the
shortest path to one, and the only one that exists.

## Why a new question rather than finishing an old one

`mic-20260918-001` cannot produce a plan and neither can `mic-20260919-001`.
Both target `tracer_diffusivity`, and the chain is closed:

```
S5 refuses `actions`  <-  no exposure is bounded
                      <-  A1's SNR bound abstains
                      <-  tracer_brightness is missing
                      <-  for a new sample it CANNOT be asked for
```

The person settled that on 2026-09-19: brightness and bleaching depend on
this dye, this lot, this illumination and this camera **together**, so no
vendor sheet and no prior run holds one. **The plan needs a run and the run
needs a plan.** Run S4 and S5 yourself and read the refusal before starting;
it names all six fields.

This card breaks it from outside: a question whose observable **is** the
missing number.

## What the person supplied, which is what makes it possible

```
exposure_time   100 ms   ->  0.1 s
illumination    10%      ->  100, per-mille        <- CORRECTED 2026-09-20
```

**The illumination line above was wrong when this card was written and is
corrected here.** It said `0.1, unit 1`, which conflates the physical
fraction with the commanded value. `light_engine_line_intensity_is_per_mille`
(E3) says each line is two MMCore properties -- `<NAME>` at 0/1 and
`<NAME>_Intensity` on **0-1000**. The scale is per-mille, not percent, so the
person's 10% commands **100**. Writing `10` gives one per cent.

**That tenfold error already bit once**, over there: the same source records
5% written as 50 and warns that 5 gives 0.5%. The trap is the scale and not
the person's number.

**These are a starting point, not a derived optimum, and the difference has
to survive into the card.** No axis produced them and none could. They enter
as `operator_choice`-class numbers from the person, and every bound that
rests on them says so.

**And 10% is not `illumination_power`.** There is no calibration in the store
from a dial percentage to milliwatts, so writing it as a power would assert a
calibration nobody has done. It is a **commanded setting** on the source.
Name it as one, and record the missing mW as its own gap — that gap is what
`illumination_power_max` will one day be compared against.

**The range is not known either.** Whether the source's scale is 0–1, 0–100
or 0–255 is not in the store; 10% is not a number until it is. Requested
from the librarian with the MMCore property names. **If it has not arrived,
that is a `kb_gap` and not a guess.**

## Three things the store said after this card was written

All six entries below are `prior_run:agentic-microscope` at E3, published in
`kbv-1dabfd5ad58d`. **Re-copy the envelope first** -- it is at
`kbv-499312508852` and these are in the gap, so an old pin cannot see them.

**A master `State` gates every line, and it is silent.** Lines on, intensity
set, `State = 0`: no light, **no error, and both properties read back exactly
as written** (`light_engine_master_state_gates_every_line`). Over there the
first run produced a field whose median was below a dark frame and a ratio
computed from hot pixels -- **and it looked like a result.**

This acquisition is exactly what that failure imitates. It measures
brightness and bleaching, and with no light both come out "measured". **Put
the master state in the plan as a condition the run verifies**, and remember
a written-and-read-back property is this defect's symptom rather than its
refutation.

**Name `LightEngine`, not `widefield_source_a`** -- and this is what lets the
pre-measurement go before the branch gap closes. `getLoadedDevices()` returns
MM labels, so a plan naming `LightEngine` **is verified at preflight and
asserts nothing about the branch**. Naming `widefield_source_a` asserts the
disputed mapping, and `widefield_inline`'s own note says a plan that *"names
a source, sets its power, or patterns it with the DMD stands on this gap"* --
setting an intensity is precisely that.

MM labels are not product names: `LightEngine` is the Spectra III, `Aura` the
Aura III, `Kinetix_red` the Kinetix 22, `Nosepiece` the Ti2-E. Calling it
`SpectraIII` fails as *device not found*, which reads as the wrong stand
rather than the wrong name.

**Exposure and ROI are core calls, not properties** -- `setExposure`,
`setROI`. They are absent from the property list, so a preflight looking for
them there will not find them; only `Binning` is a device property. The
nosepiece is the same shape: a **state device**, read with `getStateLabel`,
with no `Position` property (`nosepiece_is_an_mmcore_state_device`).

**None of this bites on mock.** It goes in the plan now anyway: fixing it
when real light arrives is late, and the master-state failure is the kind
where the fault looks like a result.

## The question

New qid, **`mic-20260920-001`**. Purpose `characterize`, intent `explore`.

Observables: **`tracer_brightness`** and **`bleaching_rate`**, both registered
in `contracts/observables.json` as of `e878e19` — with estimators, with
`window_required`, and `producible_by: ["experiment"]` only. That last is not
an omission: a simulation has no dye and no camera, so the bridge will refuse
to ask the other side, which is correct.

A plan card carries **one** observable. The two come off **one acquisition** —
the bleaching estimator is the brightness estimator applied frame by frame —
so decide whether this is one plan with the second as a declared by-product,
or two revisions over one record, **and say which in the goal card.** Do not
leave it implied.

Configuration: `widefield_inline`, which the person already tie-broke. Run
S3.0 properly anyway; a preference is not a screen.

## Four things this run must carry

**1. `nosepiece_position`.** Today a Tier 1 plan was refused for lacking it —
`objective_clearance_min` resolves from the objective in the path and cannot
without it. I ran all six positions: they resolve 4 mm, 0.8 mm, 0.16 mm,
0.15 mm, 0.13 mm, and position 6 refuses because the turret is indexed
**from 0**. Put the number in `numbers[]`.

**2. The window.** Both observables are `window_required`, so the plan carries
`brightness_window` and `bleach_window` as conditions or check 40 rejects it.

**3. The criterion before the data.** `bleaching_rate`'s estimator declares a
single exponential **before the run**. If the residual says that is wrong,
**that is a result** — do not swap in a better-fitting curve afterwards. This
is the one place in this card where the discipline is not ordinary
engineering.

**4. Mock first.** `operator.run(..., backend="mock")` writes a run log with
no instrument. That is M1's *one pipeline pass on the mock backend*, and it
is finished before anything moves. Check 66 reads `verification` on the
dispatch; a bare-particle acquisition is reversible, so nothing here needs a
`physical` limit — but write the field honestly anyway.

## What this does not cost

**The sample is not spent.** The goal card's constraint is that the sample is
consumed by the measurement and cannot be remounted. **Bare particles are not
that sample** — particles without it. Say so in the goal card, or the
pre-measurement looks like it costs the thing it is protecting.

## One gap that may be under this card rather than beside it

`widefield_source_a`'s registry row says its own branch assignment is
**unconfirmed** — `unconfirmed: ["branch_assignment"]`, `confirmed_by: null`,
`gap_ref: lapp_branch_assignment`, and the role text says outright that which
branch it is, inline or side-coupled, is not confirmed.

This question runs `widefield_inline`. **If source_a is not confirmed to be
the inline branch, the run does not know which configuration it is.** That is
a fact about the optical path and not a label. Raised with the librarian.
**Carry it as a `kb_gap` on the goal card and proceed on mock** — mock moves
nothing, so the ambiguity costs nothing until real light. It must be closed
before the instrument runs.

## What comes back

The two numbers leave as **result cards for the librarian** (P14, §4.3.2).
This agent keeps records, never its own store. They will carry the
illumination setting with them — a bleaching rate without its illumination
cannot be used by another plan, and the observable's note says so.

When they land, **six abstentions close**: `tracer_brightness` in three of
A1's bounds, `bleaching_rate` in A1's `record_duration` and A3's. Then
`mic-20260918-001` can be re-derived and the real measurement planned.

## Rulings

Nothing needs to cross from `agentic-microscope` for this. The MMCore labels
were requested **as entries through the librarian**, not as a file: the cfg's
facts already crossed — the registry rows carry `source: mm_config` at E3 —
and the file itself describes one machine's cabling at one moment, which is
what §10.2.1 refuses. If you reach for anything else, rule it and report it
up in the same sentence; I write `tasks/NNN-rulings.md`.

## Done when

```bash
python3 contracts/validate.py
python3 microscope_agent/src/synthesis.py  --qid mic-20260920-001
python3 microscope_agent/src/plan_card.py  --qid mic-20260920-001
```

`0 failed`, and read the tree the run names with it. Then a mock run and a
run log on disk. **Read every count off the run.**

If S5 still refuses, **do not force it** — report which of the six fields is
open and why. A refusal that names its cause is this pipeline working; a plan
assembled around one is the failure it exists to prevent.
