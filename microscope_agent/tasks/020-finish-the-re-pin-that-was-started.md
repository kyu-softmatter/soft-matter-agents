# 020 — finish the re-pin somebody started, in one commit

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-5`.** You proposed this as 017's step 3 and you are
the seat that is here. **Re-read this file immediately before you commit** —
two cards changed hands yesterday and the edit did not reach a running
session either time.

## The tree is in a state nothing refuses

A previous `microscope-1` session began re-pinning `mic-20260920-001` at
`c7793a4` and the session ended. What is on disk now:

```
configs.json     kbv-e8f4a5610aa6   fan_out 21   (3 configs x 7 axes)
axis cards x7    kbv-1dabfd5ad58d   revision 1   (widefield_inline only)
```

**And the validator says `0 failed`.** Checks 33 and 58 compare cards to
**each other** and never to the screening artifact — I read both. So a
question whose screening issued 21 ids, holds 7 cards, and pins them to a
different store than the artifact does, is green.

**It is not green when you run it.** S4 does not refuse, which is worse than
refusing: it returns `chosen None` and lists `confocal` with zero of
everything, because the fan-out promises three configurations and one exists.
A synthesis that chooses nothing looks like a hard question and is actually
a half-finished migration.

## What to do

**Re-derive all seven axes at the screening artifact's pin, and commit
`configs.json` and all seven cards together in ONE commit.**

The ids are already issued — `configs.json`'s `fan_out` carries all 21.
**Do not mint ids and do not re-run S3.0.** Take the seven for
`widefield_inline`.

**One commit, not seven.** A re-pin that lands card by card puts the tree
through six states in which the set disagrees with itself, and this card
exists because one of those states was left behind. It is the same rule
architecture wrote yesterday for a check and its fixtures: **the things that
are only correct together land together.**

## What the newer store gives you

`kbv-e8f4a5610aa6` holds 106 entries against the old pin's 98. What A1 and
A6 were abstaining on:

| | |
|---|---|
| `read_noise` | **four entries, one per camera mode.** Unit is `e`, not `count` |
| `quantum_efficiency` | a peak and a curve |
| `sensor_active_area` | camera sensor geometry → A6's `field_of_view` |
| `refractive_index` | air and water, keyed `identifiers.immersion` → A6's `depth_of_field` |
| `tracer_diffusivity_expected` | the one 015 could not close from the old pin |
| `tracer_diameter` | **`calibration:` E2 with a CV upper bound of 0.02** |

**Two rulings you do not have to make.**

**`read_noise` is four values and stays four.** The store cannot say which
mode, and **A1 must not pick one.** Emit an `allowed_set` over `camera_mode`
or a per-mode interval — the same shape A6 already uses for
`objective_zoom_pair`. An axis that collapses it to one number is doing
S4's job (§4.5.4).

**Take the CV.** `tracer_diameter_measured` carries
`tracer_diameter_cv_upper_bound` 0.02 as a second number. Nothing on this
side has a spread for the diameter, and **A2's statistics is where a spread
earns its keep** — a `frame_count` derived from a diameter with no spread is
a number pretending to a precision it has not got.

**And the diameter is E2 now, not `operator_recall:` E5.** The 5 µm / 2 µm
dispute is closed and this side is the one that was behind. The lot number
is **not** coming — `bottle_label_states_no_product` is a confirmed negative
— and the measurement lands **above** what a lot would have given anyway.

## One thing that will look like a regression and is not

`A4.read_published()` refuses when the envelope's version and the card's pin
disagree — by design, and `microscope-5` built it that way. The envelope is
at `kbv-e8f4a5610aa6`, so **after this re-pin the two agree and A4's three
published-table reads work for the first time.** Before it, they read as
"the envelope is X and the fan-out is Y". That resolves here; it was never
a defect.

`019`'s `lock_group` change is in the A4 module and not yet in a card for
the same reason. **Re-deriving A4 is what carries it into the card** — expect
`lock_group` to come back as a `precondition` rather than an `allowed_set`,
and that is the fix landing, not a new problem.

## Done when

```bash
python3 contracts/validate.py
python3 microscope_agent/src/synthesis.py --qid mic-20260920-001
python3 microscope_agent/src/plan_card.py  --qid mic-20260920-001
```

`0 failed`, and **read the tree the run names with it.**

S4 must name a chosen configuration rather than `None`, and the seven cards
and `configs.json` must all read `kbv-e8f4a5610aa6`. **Read the pins off the
run, not off this card.**

S5 will still refuse on the fields that wait on the person — how long to
record, and the target. **Do not force a plan**; report which fields are
open and why. If the count of refused fields drops, say what closed it.

**Tell me when it lands.** A check that compares the screening artifact's
pin against its cards' is written and held out of the tree, because it fails
on exactly this state and on nothing else. That is the fourth time a check
has waited on the defect it found, and each time the defect was real.
