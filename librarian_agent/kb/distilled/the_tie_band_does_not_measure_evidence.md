# A tie in value is not a tie in evidence, and P15 only measures the first

Written down because it existed only in messages. It came out of a manager
exchange about the bridge thread on 2026-09-19 and belongs to §5.8 and P15,
which are the architecture seat's — that session was not reachable, so the
manager is holding it to raise. A thing being held in a session's context is
the failure the seat beside this one recorded an hour earlier: a deferral that
lived in a report and in nobody's file, and survived only because a compaction
summary happened to carry it. This is the same shape, so it goes on disk now
and the raise can cite it.

Read by: seat librarian-3, 2026-09-19. Store at `kbv-7c77fa74ee5a`.

## The situation, off disk

| | value | source | grade |
|---|---|---|---|
| the simulation, in six cards | `bead_diameter` 2 µm | `assumed:a_sample` | E5 |
| the store, since 19:41 | `tracer_diameter` 5 µm | `calibration:tracer_diameter_20260919` | E2 |

The six are `goal.json`, `plan_simulation_sim-20260917-001.json`,
`synthesis.json` and axes `a1`, `a3`, `a4` under
`simulation_agent/questions/sim-20260917-001/`.

Stokes–Einstein gives `D = kT/(3πηd)`, so `D ∝ 1/d` and the two diameters put
the diffusivities a factor of **2.5** apart. P15 says differences under 10x are
ties in explore mode. So the comparison the bridge thread
`thr-tracer-diffusivity-001` exists to make comes out **a tie**, and would come
out a tie whether or not anybody ever measured anything.

## The claim

**P15's 10x band is a rule for comparing two values. It is not a rule for
comparing two bodies of evidence, and nothing else in the contract is.**

This morning 2 µm and 5 µm were both E5 — an `assumed:` against an
`operator_recall:` — and the tie was honest in both senses: the values were
close and neither claim outranked the other. Now one of them is a measurement
on this bottle. The values are exactly as close as they were. Everything about
what may be concluded has changed, and the band cannot see any of it.

**An assumption tying with a measurement is not a tie.** §5.8 says a computed
value takes the worst grade and precision in its chain, so a comparison that
holds an assumption against a measurement does not split the difference — it
settles onto the assumption. The tie band says *these two numbers are not far
apart*; §5.8 says *this result is worth what its weakest input is worth*. Only
the second one is about whether the conclusion stands.

## Why it matters rather than being a definition

**The band is currently doing the opposite of what it is for.** P15 exists so
nobody chases a 1.4x difference in a system nobody understands yet. Here it
licenses keeping 2 µm: the difference is inside the band, so the bridge reports
no disagreement, so no card has to re-justify anything. The real disagreement
is not in the values at all — it is that one side has evidence and the other
has a placeholder, and the axis the band measures is the one axis on which the
two sides genuinely agree.

A report of "no difference" that is produced this way is not wrong about the
numbers and is badly misleading about the state of knowledge.

## What this does not say

It does not say 2 µm is wrong, and it does not say the simulation must re-run.
5 µm is E2 about **this bottle**; the simulation is modelling a system, and a
model may legitimately be run at a diameter the bench does not have, so long as
the choice is recorded as a choice. What changed is that `assumed:a_sample` was
a reasonable placeholder while nothing better existed and is now a decision
taken against an available measurement. That decision is fine and it has to be
made rather than inherited.

Nor does it say the band should be narrowed. Narrowing it would break P15 for
every comparison where both sides are equally weak, which is most of them
today. The thing missing is not a smaller number; it is a second question
asked alongside the first — **are these values close, and is the evidence on
the two sides comparable** — with only the first currently having a rule.

## The same shape, one section over

§4.3.1 and task 011 recorded that one entry can mean two different things to
the two sides of a comparison: `declared_versus_inferred_temperature` is the
reason a number was chosen on the simulation side and a claim about the sample
on the experiment side, and the uncertainty therefore sits entirely on one
side. That is this argument for a different quantity — a comparison whose two
halves are not the same kind of statement, where the machinery compares the
halves as if they were.

Two instances is a pattern worth one rule rather than two fixes.
