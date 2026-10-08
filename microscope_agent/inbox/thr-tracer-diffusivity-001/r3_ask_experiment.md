# Round 3 — simulation to experiment

`thr-tracer-diffusivity-001` · wrapped by the bridge

Revision three of the simulation side's plan card for `sim-20260917-001` is
carried here unchanged. The bridge wrote no number of its own: this envelope's
`numbers[]` is empty, which is why none of the payload's values appear below.

Everything this round asserts is in three files and is not repeated here.
`r3_ask_experiment.json` holds the payload, the three gate verdicts and the
round it supersedes. `r3_hashes.json` holds the source card as it stood in the
sender's directory. `status.json` is the only place that says whose turn it is
and what state the thread is in.

## Why this is a supersession and not a repeat

Same observable, same direction, same question as the round before it, and the
plan is a later revision of the same card: the source moved under the earlier
round, so nothing has been answered twice. The round it replaces is named in
the envelope, and the validator recomputes that claim from the two rounds'
ledgers rather than taking it.

The earlier envelopes stay in the receiving side's inbox. Nothing is removed
from an inbox; this envelope, delivered beside them, is how the receiving side
learns the source moved.

## What moved, without restating it

The diameter, the temperature, the viscosity and the expected diffusivity did
not move. What moved is how long the run is and how fine its step is: both are
now set from the tracer's diffusive time instead of being the engine's
operating point, and both carry a better grade for it: computed, where they
were assumed. The ratio of the fit window to the record follows
from the longer record. The receiving side should design against this
payload's `numbers[]` rather than against round two's.

## What the librarian would still have changed

The payload carries `degraded`, and so does the envelope. This seat could not
reach the store for this round, so the check for an existing entry the round
could be replaced with was not made; the round is spent rather than
referenced, and that cost is what the envelope's `degraded` records.
