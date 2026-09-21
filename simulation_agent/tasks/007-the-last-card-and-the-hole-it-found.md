# 007 — the result-card writer, and the hole writing one finds

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**This is the last thing between this repository and an end-to-end pass.**
Every stage before it exists on disk: goal, six axes, synthesis, a plan card,
two runs with `observables.json`. `criteria_evaluation` appears nowhere in
`src/`, so by this agent's own contract the smoke runs are **recorded and not
done**, and will stay that way until something writes a result card.

## Three contracts were in the way and are not any more

Measured, not read. Before `1949c0e` a result card for either run on disk was
**impossible to write**, not merely unwritten:

| what | where | state |
|---|---|---|
| `approval_id` was a non-nullable string while `operator.py` legitimately writes `approval: {id: null, kind: null}` for Tier 0-1 | `result.schema.json` | fixed — null accepted, key still required, so "needed none" stays distinct from "failed to record one" |
| `simulated:` was in §5.3 and in no source pattern, so check 1 refused it outright | `common.schema.json` | fixed |
| `simulated:` was in no `SOURCE_GRADE`, so check 21 called it an unknown kind | `contracts/validate.py` | fixed — it grades as `computed:` does, `max(E4, worst input)` |

Check 15 also stopped being PENDING (`a3808d7`): both runs pass it, because
`plan-sim-20260917-001` declares tier 1 and tier 0 and the null approval is
therefore the honest state rather than an omission.

## One copy of the table is still yours

`src/cards.py` holds its **own** `SOURCE_GRADE` and it does not have
`simulated`, so `grade_for("simulated:run-...")` raises `ValueError` today.
That is the §11-11 shape — one fact in two places — and the copy in your tree
is yours to move. Mirror §5.3: fixed `None`, then `max(E4, worst input)` the
way `computed` already does there.

## And then you will hit this, so hit it knowing

**For `bd_overdamped` the run may not cite itself.** §5.3 is explicit: the
tracer diffusivity is fixed analytically by the input, so `2.128e-13` against
the analytic `2.146e-13` confirms the integrator and the estimator and
**says nothing independent about any diffusivity**. The capability table now
declares that (`output_independent_of_input: {independent: false}`) and
check 21 enforces it, so a number sourced `simulated:run-20260920-002` on a
card standing on this plan **fails**.

Now try to write the card anyway and watch where it jams:

- `values[].number` names an entry in `numbers[]`, which needs a source.
- `criteria_evaluation[].observed_number` names one too.
- `deviations[].actual_number` names one too.

**What this run observed has no legal source kind.** It is not `measured:` —
a simulation is not a measurement, §5.3 settled that on 2026-09-20. It is not
`computed:` — nothing derived it by formula, an integrator emitted it. And
`simulated:` is exactly what the table just refused for this configuration.

**Do not invent one and do not route around it.** Writing it as `computed:`
would be self-reporting a grade through a kind that owes a recomputation
(check 17) it cannot produce, and that is worse than the gap. This is §5.3
and §5.3 is architecture's, so it is raised, not decided here.

**What you can build while it is open**, because none of it depends on the
answer: everything the card needs that is not the observed value itself.
`time_base` from the run log's `t0_wall`/`t0_mono` and its alignment,
`estimation` by reference rather than by copying the vocabulary's text
(the schema says so, and `001` says why), `outcome`, `deviations`' planned
side from the plan, `criteria_evaluation`'s `id`/`kind` for every stop and
success criterion the plan declares — `minItems: 1` and **every** one, not
the ones that are easy. Leave `met` and `observed_number` for last; they are
the two that wait.

Build it so the blocked part is one function returning the observed number's
source, and the rest does not know. When §5.3 answers, that is the only edit.
