# Round 1 — experiment to simulation

`thr-diffusivity-crosscheck` · wrapped by the bridge · **the human's turn**

The microscope side finished `mic-20260917-001`, and its result card is carried
here unchanged. The bridge wrote no number of its own: this envelope's
`numbers[]` is empty, which is why none of the payload's values are restated
below. Restating them would put one quantity in two places, and by next week it
would be two quantities (P3, check 9).

| gate | verdict |
|---|---|
| payload integrity | the canonical hash of the carried card matches `r1_hashes.json` |
| answerability | **yes** — `bd_overdamped` produces it, checked against `capabilities/simulation.json` |
| unit consistency | **no counterpart** — the opening round has nothing to compare against |

## Why the round is held rather than refused

`capabilities/simulation.json` declares no configuration, and
`contracts/observables.json` defines no entry, so the engine side has not said
whether it can produce `tracer_diffusivity`. Not declared is not impossible.
Refusing here would record an impossibility nobody established, and answering
yes would claim a capability nobody declared. So the round is held, the turn goes
to a person, and `status.json` names the open question.

## What the librarian would have changed

`degraded: ["librarian_agent"]`. With the knowledge store reachable, a repeat of
this observable under the same conditions would come back as a reference instead
of a new round (plan.md 4.4 rule 5). With no store to point at there is nothing
to substitute, so a repeat would reopen the round. That is what this line costs.
