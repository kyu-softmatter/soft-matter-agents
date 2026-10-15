# Round 1 — simulation to experiment

`thr-tracer-diffusivity-001` · wrapped by the bridge · **the microscope's turn**

The simulation side finished planning `sim-20260917-001`, and its plan card is
carried here unchanged. The bridge wrote no number of its own: this envelope's
`numbers[]` is empty, which is why none of the payload's values appear below.
Restating them would put one quantity in two places, and by next week it would
be two quantities (P3, check 9). The plan is in `r1_ask_experiment.json` under
`payload_card`, and its source is named in `r1_hashes.json`.

| gate | verdict |
|---|---|
| payload integrity | the carried card hashes to what `r1_hashes.json` recorded, and the source path recomputes |
| answerability | **yes** — four imaging configurations produce `tracer_diffusivity`, checked against `capabilities/microscope.json` |
| unit consistency | **no counterpart** — the opening round has nothing on the microscope side to compare against |

## Why this round could not be written yesterday

The ledger's source hash used to cover `status`. A plan moves `DRAFT →
VALIDATED → APPROVED` on the same file, so the approval this plan is due to
receive would have changed the digest of a card nobody touched, and check 8
would have reported a correctly transported round as tampering — with repair
forbidden. The hash now leaves `status` out and `source.status` pins the state
the card was read in instead. That ruling is `af5353b`; the round is written
against it.

## What is not settled

`plan_completion` is the trigger here: a validated plan is what opens a thread,
and a finished run is not. A result crossing back will carry `human`.

The payload's own revision is not frozen for good. The simulation seat says a
smoke run will replace an assumed cost model and a librarian pass will empty
`degraded`, and either changes the plan. When that happens the card gets a new
revision, this round stops being comparable, and a later round carries the new
one. That is the ledger working, not failing.

## What the librarian would have changed

`degraded: ["librarian_agent"]`. The store is serving now, but this session
started before the registration was fixed and cannot reach it, so the bridge
could not look for a knowledge entry that already answers this question. With
the store reachable, a repeat of this observable under the same conditions
comes back as a reference instead of a new round (plan.md 4.4 rule 5). Here a
repeat would reopen the round, and that is what this line costs.
