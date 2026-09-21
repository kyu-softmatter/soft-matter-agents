# 021 — the record is 60 s, and what that does and does not settle

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to the seat that lands `020`.** The re-pin and this are the same
run of S4 and S5, so splitting them across two seats would put the question
through a state where the operating point and the pins disagree. If you are
not holding `020`, report up instead of taking this.

**Small card. One number and one thing it does not settle.**

## The person answered

**Record length: 60 s.** At 100 ms exposure that is about 600 frames.
`assumed:a_operating_point` E5, the same source and grade as the other four
— it is a starting point the person chose, not a value any axis derived.
**Do not promote it** because it came from a person; a choice is not
evidence.

**The target was already in.** `goal.json` reached revision 4 carrying
`decade_resolution 1` for **both** `tracer_brightness` and `bleaching_rate`,
with the reasoning written out. Nothing to add — check it is still there
after the re-pin rather than re-adding it.

## What 60 s closes

Four of S5's seven refusals wanted a duration and nothing else:

| | |
|---|---|
| `actions` | the acquire action gets its record length |
| `stop_criteria` | a criterion can compare elapsed against a number in `numbers[]` |
| `cost` | wall clock is arithmetic over the plan now, not a number S5 invents |
| `conditions[*_window]` | **partly** — see below |

**Derive the frame count, do not accumulate it.** 600 is `record_length /
exposure_time`, computed once. A duration summed frame by frame lands a hair
off the boundary and reports a completed run as unfinished; the direction
flips with the step. **And do not add an epsilon** — the number came from
the person and an operator that widens it changes an approved value.

## What 60 s does NOT settle, and this is the card's point

**The two windows are not the record length.** `tracer_brightness` and
`bleaching_rate` both carry `window_required`, and a window is *which part
of the record the estimator ran over* — not how long the record is.

- **`bleach_window`** is the fit range and the full record is the natural
  answer: the decay is what the 60 s is for.
- **`brightness_window` is the hard one.** Brightness measured across a
  record in which the sample bleached is depressed by the bleaching, so the
  window wants to be short enough that decay over it is negligible — **and
  nothing knows the decay rate, because measuring it is what this run is
  for.**

**Do not resolve that by picking a number here.** State the window as a
declared fraction of the record, say in the card why that fraction, and
**let the bleach fit over the full 60 s report retroactively whether the
choice held.** If the decay over the brightness window turns out
non-negligible, the brightness is re-derived on a shorter window from the
same data — no second acquisition.

That is the honest shape: **a criterion declared before the run, and a
result that says whether the criterion was right.** What is forbidden is the
other order — reading the curve and then choosing the window that makes the
brightness look clean.

**If you would rather the person chose the fraction, ask through me.** That
is a legitimate answer and better than a fraction nobody can defend.

## Then run it

```bash
python3 microscope_agent/src/synthesis.py --qid mic-20260920-001
python3 microscope_agent/src/plan_card.py  --qid mic-20260920-001
python3 contracts/validate.py
```

S4 must name a chosen configuration. If S5 writes a plan, **mock it**:
`operator.run(..., backend="mock")` needs no instrument, no approval and no
MMCore, and it is M1's *one pipeline pass on the mock backend*.

**If S5 still refuses, do not force it.** Report which fields are open and
what each is waiting on. Seven went to five when the objective was resolved;
if this takes five to one or zero, say which closed and why — that count is
the progress and prose about it is not.

## Before you commit

`0 failed`, **and read the tree the run names with it.** Re-read this card
file immediately before committing: cards changed hands twice on 2026-09-20
and both times a running session held a version that had already moved.
