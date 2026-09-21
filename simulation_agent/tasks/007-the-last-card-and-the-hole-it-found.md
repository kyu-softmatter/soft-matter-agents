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

## The thing that was blocked is answered, and it is one line

**This section said a verification run had no legal way to state what it saw.
Architecture ruled it the same day (`a8c6470`) and the gate now carries the
ruling (`88c496a`), so build straight through it.**

`simulated:<run_id>` is **one kind with two roles, and the field already says
which.** The independence declaration governs only whether the number may
*also* stand as a claim about the world:

| field | role | `bd_overdamped` |
|---|---|---|
| `values[].number`, `values[].uncertainty` | the card **asserts** something about the system | **refused** — the evidence is the input, and citing the run launders the input's grade |
| `criteria_evaluation[].observed_number` | what the run **read** | allowed |
| `deviations[].actual_number`, `.planned_number` | what the run **read** | allowed |
| named by no field at all | nothing says which | **refused** — undeclared is not a permission |

So the function this card told you to isolate returns `simulated:<run_id>`
unchanged. Do not branch it on role: the writer choosing a kind is exactly
what the ruling avoided.

**The grade is unchanged, `max(E4, worst input)`.** It says how far the
reading could be trusted as a claim; the field restriction says it is not
being offered as one. Neither was weakened for the other, so an E5 on an
`observed_number` is not a defect to tidy — a reader meeting it learns the
true thing, that this reading is no stronger than what went into it.

**And what it may never feed.** A `simulated:` number under
`independent: false` may be named from those comparison fields **and nowhere
else**: never from `values[]`, never carried into another card, never into a
KB entry. All three are enforced now, so you will be refused rather than
trusted — `ORIGIN_RE` does not accept `result_*.json` as an origin at all, and
check 43 resolves the run to its plan to its configuration before letting an
entry in.

**Where the diffusivity does belong, then.** `values[]` still has to say
something, and for this configuration the answer the card asserts is the
**predicted** number — `computed:stokes_einstein`, the one the plan already
carries. The run's reading sits beside it as the comparison term. That is the
honest shape of a verification run: the claim is the model's, the reading is
the run's, and the card shows them meeting.

**Do not read a grade off this card. Carry the plan's.** An earlier draft here
wrote "E4" beside that source, and a grade stated in a task card is a
self-reported grade, which is the one thing P2 exists to stop. The rule is
`max(E4, worst input)` and it resolves differently per revision, because the
input moved:

| the plan you stand on | `bead_diameter` | so `diffusivity` |
|---|---|---|
| revision 1 | `assumed:a_sample` E5 | **E5** |
| revision 2 | `kb:tracer_diameter_measured` E2 | **E4** |

`run-20260920-002` carries `plan-sim-20260917-001` at **revision 1**, so a
result card for that run carries **E5** — the measurement that improved it
landed in revision 2 and that run predates it. Take the number from the plan
card the run names; do not recompute the grade and do not match it to a
sentence written here. `simulation-5` asked this before writing anything, and
asking was right: the moment a seat adjusts a grade to fit prose, the grade is
self-reported whatever the prose said.

## What to build

Everything the card needs, with nothing now waiting on anyone:

- `time_base` from the run log's `t0_wall`/`t0_mono` and its alignment
- `estimation` **by reference**, not by copying the vocabulary's text — the
  schema says so and `001` says why
- `outcome`, one of `DONE` / `FAILED` / `NOT_CONVERGED`
- `deviations`, planned from the plan and actual from the run. An empty list
  is a claim, not a default — the schema says that in as many words
- `criteria_evaluation` for **every** stop and success criterion the plan
  declares, not the ones that are easy. `minItems: 1` is a floor, not a target
- `values[]` asserting the predicted number, with the reading beside it

`approval_id` is `null` for both runs and that is correct, not a placeholder:
check 15 verifies it against `plan-sim-20260917-001`'s tier 1 and tier 0.
