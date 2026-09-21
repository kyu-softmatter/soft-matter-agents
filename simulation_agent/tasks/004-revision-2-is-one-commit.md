# 004 — revision 2, and it is one commit

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Startable when `003` is done** — the issuer has to emit `:v2:` before a
revision 2 fan-out runs, or the new cards carry the wrong ids from birth.

Four separate things have collected on revision 2. They are one piece of work,
not four, because **one pin blocks all of them and one revision bump releases
all of them.** Doing them separately means the same pin argument four times and
four revisions of a question nobody has run.

| | |
|---|---|
| A | `bead_diameter` 2 → 5 µm, and everything the arithmetic drags with it |
| B | the target stated inline instead of by reference into `numbers[]` |
| C | the librarian re-run — `kb_refs`, `kb_gaps`, `degraded` empty (§9.1) |
| D | `caller_id` at `:v2:`, which falls out of `003` |

## Before you start: confirm the pin is still what it was

```bash
python3 -c "
import sys,json; sys.path.insert(0,'contracts')
from validate import card_sha
h = json.load(open('bridge/threads/thr-tracer-diffusivity-001/r1_hashes.json'))
c = json.load(open(h['source']['path']))
print('ledger rev', h['source']['revision'], '| card rev', c['revision'],
      '| hash matches', card_sha(c) == h['source']['sha256'])"
```

A delivered round pins the plan at revision 1 by hash, and §5.3.1 generalised
that on 2026-09-19: **a recorded hash pins a card and it does not matter who
recorded it** — a person signing an approval or the bridge delivering a round.
Editing in place moves `card_sha` and fails check 8 in `manager-bridge`'s tree,
where nobody can fix it. The exit is the next revision, which is this card.

## A. The diameter, and the source kind changes with it

**Seven files carry `bead_diameter`**, and this card said six until the
execution seat counted them: `goal.json`, the plan JSON, `synthesis.json`,
axes **a1, a3, a4** — and `plan_simulation_sim-20260917-001.md`. The markdown
was named in §D and left out of the count here, so the checklist was complete
only if both sections were read, and a seat editing the six the number names
leaves the seventh to check 9.

**2 µm → 5 µm, and it is a measurement.** The person measured the particles
directly on 2026-09-19: **5 µm, CV within 2 per cent**, which is
`calibration:` at **E2** — *above* the E3 a lot specification would have
supplied. The question this has been putting to a person was answered by
measurement, and answered better than it was asked.

So use `calibration:` at E2. Not `assumed:`, and not `operator_recall:` either
— this card said `operator_recall:` E5 for several hours on the reasoning that
a weak claim beats a blank, and that reasoning is now obsolete rather than
wrong. **The argument shortens to "a measurement beats a blank."**

**The product thread no longer decides this, and it moved twice while this
card was being written.** Identification was withdrawn (issue 015), then
reversed when the person ruled the bottle is that product and the vendor page
is wrong — the asymmetry being that the Abvigen page already had two unrelated
errors on record, so *the datasheet is wrong* is a far cheaper explanation than
*the bottle is not that product*, and a silent label cannot tell the two apart.
**None of that matters for the diameter any more.** A measured value does not
need the catalogue that was standing in for it. It still matters for the
brightness — see below.

**On this side the lot vanishes, and this card said it narrows.** The
narrowing is real on the microscope side — `agentic-microscope` recorded that
size CV *and* dye loading vary lot to lot, size CV is now measured, dye loading
is not, and that is `tracer_brightness`. **But `tracer_brightness` is in no
card of this question.** It lives in the microscope's A1, which is SNR; *this*
agent's A1 is integration stability and has no use for dye loading. Checked.
The lot reached this question through `bead_diameter` and nothing else, so
measuring the diameter cut its last grip here.

So the consequence runs the other way: **do not open a `kb_gaps` entry for the
lot on this side.** It would record a gap that nothing in this question rests
on — the false-gap failure check 49 exists for, reached from the opposite end.
This card had borrowed the microscope's framing without checking it applied.

**`a_sample` goes, and it is a deletion rather than an edit.** Its `numbers`
list is exactly `["bead_diameter"]`, so once that number stops being assumed
the assumption has no numbers left. That is what carries §11-2's unit from
seven distinct rationales to six.

**Its falsifier did not fire, and the reason generalises.** It reads *"a bead
lot specification replaces this with an E3 value"* — which names **a document
that would arrive**, not **a state that would obtain**. A direct measurement
satisfied the underlying condition by a better route, E2 above the E3 the
falsifier anticipated, and the falsifier had nothing to match. That is `002`'s
diagnosis of `a_target` one step milder: `a_target`'s says when somebody would
change their mind, `a_sample`'s says which piece of paper would settle it, and
**both name a route instead of a state.** *"A measured or specified size at E3
or better exists"* would have fired either way. Found by the execution seat,
and worth carrying into how falsifiers are written here.

## B. What the diameter drags, and what it quietly does not

`τ_d = d²/D` and `D = k_BT/(3πηd)`, so **τ goes as d³** — the factor of ~15.6
that §11-13 recorded as a discrepancy between two sides arrives here as
arithmetic. **Do not hand-edit any of it and do not take a number from this
card or from a peer's message.** These are `computed:` with formulas; re-run
the fan-out and let the modules derive them. Check 17 recomputes, so a
hand-edited value is caught — but being caught is not the same as being right.

**Six numbers are forced by a declared formula**, by transitive closure over
`inputs`: `diffusivity`, `tau_d`, `integration_timestep_max`,
`box_length_min_dilution`, `box_length_min_images`, and the diameter itself.

**The rest is the part worth your attention, because nothing forces it.**

`max_lag_time` is `assumed:a_window`, 2 s, **no formula and no inputs**, so the
dependency graph does not move it. Its statement is *"The fit window sits below
the diffusive time so the free regime is what is sampled."* At τ_d ≈ 20 s, 2 s
was a tenth of it. At the new τ_d it is well under one per cent. **The sentence
stays true and the choice stops making sense** — you would sample only the
shortest lags and throw the run away. A statement that goes stale while its
number sits still is not caught by anything here.

Everything under it inherits that: `save_interval_max` and
`total_simulated_time_min` both derive from `max_lag_time`.
`total_simulated_time_point` and `integration_timestep_point` are S4's chosen
operating point, picked against intervals that have now moved.
`a_cost_reference` estimates cost *"over a window of a few seconds"*, which the
window no longer is.

So A4 genuinely re-decides the window, S4 genuinely re-picks the point, and A5
re-costs it. That is a fan-out, not a patch — which is what makes this a
revision.

## The evidence does improve, and this section said the opposite

**This section said until 2026-09-19 that revision 2 would change the physics
and not one grade.** That was written while the diameter was going from one E5
source kind to another. Then the person measured it, and it is false.

`bead_diameter` becomes E2, and §5.8 re-grades everything downstream to its
worst input:

| | was | becomes | why |
|---|---|---|---|
| `bead_diameter` | E5 `assumed:` | **E2** `calibration:` | measured |
| `diffusivity` | E5 | **E3** | capped by `viscosity` and `temperature`, both `kb:` E3 |
| `tau_d` | E5 | **E3** | same cap, through `diffusivity` |

Across the question that is **24 E5 numbers down to 22**, and for the plan
§11-2's unit goes **7 distinct rationales to 6** — `a_sample` stops being a
rationale because the number stops being assumed. Check 3 will report that on
its own; check 56 compares recomputed counts, so it follows the cards.

**The two that improve are the two that are the physics.** Everything still E5
is a *choice* — `dt_resolution_factor`, `max_lag_time`, `box_margin_factor`,
the ensemble size. So the honest summary inverts: **the physics stops being an
estimate and the choices stay choices**, which is a much better place to be
than where this section had you.

**And the binding constraint moves.** The weakest link in this agent's physics
was the bead; now it is `lab_ambient_temperature` and `water_viscosity_293k`,
both `kb:` E3. That is worth noticing rather than passing over: the temperature
is a thermometer reading of **the room**, not the sample, and this question
already carries `sample_adjacent_temperature` as an open gap. **The gap that
was second-order behind the diameter is now the one holding the grade.**

## Every verdict this question carries is an E5 tie, and stays one

§5.8.1 landed on 2026-09-19 (`3113a37`): **a tie verdict carries a grade, and
it is the worse of the two values compared.** A computed value inherits the
worst input, so a comparison inherits it too — no new threshold, and it closes
the misleading case exactly: an ungraded tie is what misleads, and a graded one
says what it is worth.

Counted across this question's axis cards:

| | verdict today | grade carried | §5.8.1 would give |
|---|---|---|---|
| a1 | `feasible` | **none** | E5 |
| a2 | `feasible` | **none** | E5 |
| a3 | `feasible` | **none** | E5 |
| a4 | `feasible` | **none** | E5 |

a5 and a7 abstain, so they have nothing to grade.

**And the measurement does not move one of them.** Re-run with `bead_diameter`
at E2 and `diffusivity` and `tau_d` at E3: **all four stay E5**, each held there
by a choice rather than by the physics —

- **a1** by `dt_resolution_factor`
- **a2** by `target_relative_error`, `n_particles`, `independent_samples_min`,
  `lag_to_record_ratio_max`
- **a3** by `box_margin_factor`, `spacing_factor`, `particles_per_edge`
- **a4** by `lag_coverage_factor`

That is the sharpest form of what §B says: **the physics stops being an estimate
and not one verdict improves.** Anyone reading revision 2 as a firmer plan has
the wrong picture, and a `feasible` with no grade on it is what would let them.

**`max_lag_time` holds three of the four.** It is the single highest-leverage
number in this question — and it is `assumed:a_window`, the one whose *reason*
goes stale when `tau_d` moves (§B). So the window is not just a number A4
re-decides; it is what three feasibility verdicts rest on. Fix it well.

**Check 63 is `manager-bridge`'s**, so do not implement the grading. What is
yours is that revision 2's cards should carry it, and that the cards can say it
before a check demands it.

## Choosing 2 µm is still allowed, if it is recorded as a choice

Architecture's wording, which is better than this card's earlier framing and
replaces it: **a model may run at a diameter that is not on the bench, as long
as the choice is recorded as a choice.** What changed on 2026-09-19 is not that
2 µm became wrong — it is that `assumed:a_sample` became **a decision taken in
the presence of a measurement**, and such a decision has to be *made* rather
than inherited.

So aligning is the expected move and it is not the only legal one. If revision 2
keeps a different diameter, it says so in the open, names the measurement it is
departing from, and gives the reason. What is no longer available is carrying
2 µm because it was already there.

## Polydispersity, which nobody was accounting for

A point value became a distribution and that settles something downstream that
was never argued. **Ignoring polydispersity is safe.** Derive the margin
yourself before writing it down, because the version in circulation — this
card's included, until it was checked — does not follow from its own reason.

`D = k_BT/3πηd`, so `ln D = const − ln d` and `δD/D = −δd/d`: **`D ∝ 1/d`
transfers relative spread one-to-one.** A 2 per cent CV in diameter is a
**2 per cent** CV in diffusivity, not 4. Confirmed numerically as well as
analytically. Four per cent is what "within 2 per cent" gives if it is read as
**±2 per cent**, i.e. a 4 per cent full width — a different quantity, needing a
different sentence. `plan.md` §11-13 and this card both said *twice the spread
in diameter, since `D` goes as `1/d`*, and `1/d` is precisely what makes it
one-to-one. Raised with architecture.

**The conclusion does not move**: 2 and 4 per cent are both far inside explore's
tie band, where differences under 10× are ties (P15). But this section's
deliverable **is** the reason, so a reason that does not produce its own number
is the one thing it must not carry.

**Take the CV from the store, not from here — and not yet.**
`tracer_diameter_measured` holds `tracer_diameter_cv_upper_bound` as
`value: 2, unit: "1"`, which is dimensionless 2, i.e. **200 per cent**; the
note says per cent and a note is prose (issue 019). Whatever writes this margin
must read a value/unit pair that comes out right without the note, so wait for
that entry to be fixed rather than hand-copying either number.

So ignoring polydispersity is **safe, and until 2026-09-19 nothing said why**.
A2 is where independent displacements are counted, so that is where the reason
belongs. Write it down even though it changes no number — an unstated safety
margin is indistinguishable from an oversight, and the next person to widen the
CV has nothing to check against.

## C. The target, and your plan does not have one

`5e3ea6a` is the worked example; copy its shape. But **check your own tree
first, because it differs from the example and from what you may be told**:
`plan_simulation_sim-20260917-001.json` has **no `targets` key at all**.
Verified. It does not migrate a target — it **acquires** one.

- `goal.json` states the decision inline: `{metric, kind, value, unit}`,
  required exactly those four, `additionalProperties: false`. No source, no
  grade — a target is a decision, and inline is what makes a grade
  inexpressible rather than merely absent (§2.1 rule 9).
- the **plan** gains its own copy, pinned to what the goal decided rather than
  referencing it, because a `plan_approval` fixes the plan and not the goal.
  Check 52 compares the two.
- `target_decade_resolution` leaves `numbers[]` and `a_target` goes with it —
  see `002` for why that was never an assumption.
- the criterion `within_target_decade` uses `target: <metric>` in place of
  `number:`. Check 6 resolves either, since `d5af7b1`.

The person confirmed one decade (`ad38bb0`, §11-14 closed), so **the value does
not move.** What moves is that it stops being this agent's E5 assumption.

## E. Revision 2 declares a convergence criterion, and it is not an equilibration one

**The person instructed this and §9's M2 condition records it.** Revision 1 has
none: `stop_criteria` are `planned_duration_reached` and
`step_displacement_diverged`, `success_criteria` are accuracy and statistical
error, and the strings `equilib` and `converg` appear nowhere in the card.
Both smoke runs ended by reaching their planned duration.

**First, what this configuration does not need.** `bd_overdamped` is free,
non-interacting Brownian motion. **There is nothing to equilibrate** — no
interactions, no structure to relax, no initial configuration that decays into
a steady one. Writing an equilibration criterion here would be theatre, and
this seat would rather say so than produce a number that looks like diligence.
**That is a fact about this configuration and not about simulation**: a config
with interactions or confinement has a real transient and would need one, and
`capabilities/simulation.json` is where that difference is declared.

**What it does need is a free-regime criterion**, and the two are not the same
thing. `relative_standard_error = 3.7e-4` is the **tightness of the line**, not
evidence that the line was fitted to the right thing. A fit can be precise and
wrong — sample lags where the MSD is not linear and it will be both.

**The estimator already names the diagnostic.** `observables.json` says the
intercept is *"left free so that localisation error stays out of the slope"*.
So for a backend with **no localisation error** — and `mock_backend` integrates
exactly and reads coordinates straight — **the intercept should be consistent
with zero.** It is the one number in the fit that says whether the free regime
is what was sampled.

**Run 002's is not obviously zero, and nobody can say whether that matters.**
`intercept = 1.89e-15 m²`, which is **7 to 10 per cent** of the MSD at the
shortest lag depending on dimensionality, and 0.1 per cent at the longest.
**`observables.json` reports no standard error for the intercept**, only for
the slope — so there is no way to tell sampling noise from a short-lag artifact.
**Do not read this as a defect: read it as unjudgeable.** Reporting the
intercept's uncertainty is the first thing revision 2 needs, because without it
the criterion below cannot be evaluated at all.

**Two criteria, and design them rather than take them:**

1. **The intercept is consistent with zero**, scaled against the MSD at the
   shortest lag rather than absolutely — an absolute threshold is meaningless
   across diffusivities. Needs the intercept's standard error.
2. **The fit is insensitive to the window.** `D` over the first half of the lag
   range against `D` over the second half, agreeing within the target. This is
   the one that actually separates *converged* from *precise*: a fit reaching
   past the free regime disagrees with itself across the window while each half
   stays tight.

Both are computed from data already taken. **Neither needs a longer run**, which
is the point — M2's third stage is not short of runs.

**Declared in the plan, evaluated by the operator, and chosen before the run.**
`CLAUDE.md` calls that the single hardest discipline on this side, and this is
the first time it is being exercised rather than described. A criterion picked
after seeing run 002's numbers would be fitted to them.

## D. Mechanics, and the corner nobody has been round

- **`v2_` prefix**, not `r2_` — rounds and revisions were one sentence until
  `a6ab72b` split them (§7.1 rule 3, P9).
- **Revision 1 stays on disk.** Revision 2 **may cite it as a record and may
  not take it as input** — feeding its numbers into a fresh calculation
  inherits the reason the re-run exists.
- `cards.refuse_overwrite` stops rather than replacing a card of another
  revision. Let it.
- **Re-pin `kb_version`** to the store as of this run. That is the whole point
  of revision 2 being the librarian run: it asks with the vocabulary that store
  actually has, and revision 1 keeps its own pin as the record of what was read
  the first time.
- **`plan_simulation_sim-20260917-001.md` must be regenerated** (P3). Check 9
  compares its numbers against the JSON and both the diameter and the target
  move under it. **`manager-bridge` never exercised this path** — their example
  plan had no markdown. If regeneration surprises you, that is the last
  unexamined corner of this migration and they asked to hear about it.

## When it lands

Tell this seat, and tell `manager-bridge` — they will re-run check 8 against
the new revision from their side. The rev-1 ledger then reads *"the source
moved on; the round is not comparable"*, which is the documented escape and is
why any of this works. **The delivered round in `microscope_agent/inbox/` then
describes a superseded plan.** That is `manager-bridge`'s to settle, they know,
and it does not gate your commit.
