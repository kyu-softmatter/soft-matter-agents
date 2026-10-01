# Round 1 — simulation to experiment

`thr-bleach-recovery-diffusivity-001` · wrapped by the bridge

The simulation side's result card for `sim-20260930-401`, the predicted
recovery of a bleached disc of fluorescent beads, is carried here unchanged.
The bridge wrote no number of its own: this envelope's `numbers[]` is empty,
which is why none of the payload's values appear below. Restating them would
put one quantity in two places.

Everything this round asserts is in three files and is not repeated here.
`r1_ask_experiment.json` holds the payload and the three gate verdicts.
`r1_hashes.json` holds the source card as it stood in the sender's directory —
its path, its id, its revision, the state it was read in and its hash.
`status.json` is the only place that says whose turn it is and what state the
thread is in, and it also gives the reason this is a new thread rather than a
round of the existing diffusivity thread.

## Who opened it

A person did. A result crosses only when a person hands it over, and the
person handed this one over directly. The hand-over covers this card at the
revision it names and nothing else.

## What the payload says about itself

The card states its own limits and how far it can be set beside a measurement.
Those statements are the simulation side's, they are in the payload, and they
are carried as written. The receiving side should read them there, not here.

## What the librarian would still have changed

The payload carries `degraded`, and the envelope carries the same list, so a
result made in reduced mode does not read as normal on this side. That list is
the simulation side's to empty.

Separately, this seat asked the store whether this observable has already
crossed and has an entry a round could be replaced with. What came back is
recorded in `status.json`.
