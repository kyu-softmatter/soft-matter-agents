# 006 — one wrong error bar, two criteria, opposite directions

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Prerequisite to `004`'s §E, and carded separately because it is not
`004`'s.** An error model is neither pinned by the round ledger nor gated by a
revision bump, which is the same reason `plan_card.py` went outside `004` and
before it.

## What was found, and by measuring rather than reading

`simulation-4` put a standard error on the fit's intercept (`49da893`) and then
measured what both error bars are worth, across eight seeds:

| | |
|---|---|
| `D`, mean | `2.1448e-13` against an analytic `2.1461e-13` — **−0.06 %** |
| actual spread ÷ quoted SE | **`D` ≈ 41×**, intercept ≈ 8× |

**The estimator is sound and unbiased. Only the error bars are wrong**, and the
cause is ordinary: the fit treats a hundred MSD points as independent
observations when every lag is computed from the same trajectories. The weights
count how many displacements entered each lag and say nothing about the
correlation between lags.

## Why this blocks two criteria and not one

**The same understatement helps one criterion and breaks the other.** That is
the part worth carrying, and it is why fixing the model is prerequisite rather
than tidying:

| | quoted SE | honest SE |
|---|---|---|
| intercept consistent with zero | **6.4 σ — fails** | **0.0 σ — passes** |
| `statistics_met` (`rel. SE` vs target `0.1`) | 270× margin, passes | 6.6× margin, passes |

So `004`'s criterion 1 would be **declared against an error bar that makes it
fail on an artifact**, while `statistics_met` passes either way and **reports a
margin wrong by a factor of forty-one.**

`statistics_met` is not broken and this card does not ask for it to change.
What is wrong is the number it will record.

## Where that number lands, which is the reason to fix it first

`result.schema.json` **requires** `criteria_evaluation`, and each entry carries
`observed_number`. So the margin is not a transient print — **it goes into the
result card and stays there.** Write the result card before fixing the error
model and the repository gains a card that says `met: true` beside a number
that is wrong by 41×, with the four-part grade machinery wrapped around it.

**Nothing has recorded a wrong number yet, because nothing writes result cards.**
`criteria_evaluation` appears nowhere in `src/`. That is unbuilt work rather
than a defect, and it is also the window: the fix lands before the first result
card or after it, and only one of those is free.

## What the honest uncertainty is

**Seed-to-seed spread, and the ensemble already exists** — eight seeds were run
to measure this. How to report it is revision 2's design decision and **not a
fudge factor**: the measured ratios are recorded beside the code rather than
folded into it, which is the difference. Do not scale the quoted SE by 41 and
move on; that number is this operating point's, not the estimator's.

## What this card does not cover

**Nothing evaluates `success_criteria` today** — `operator.py` contains the
string zero times against four for `stop_criteria`, and the run log records
only the latter. That is **not a gap in the design**: check 6 requires the
criteria to be declared and well-formed, and `result.schema.json` requires the
evaluation, so the evaluation belongs to the result card and the result card is
unwritten. **It is worth knowing that check 6's coverage can read as more than
it is** — it makes sure the declaration exists, which from outside looks like
making sure it is checked.

So the smoke runs are **recorded and not done**, by this agent's own contract,
and will stay that way until something writes a result card.
