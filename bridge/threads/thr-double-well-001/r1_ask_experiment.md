# Round one — simulation to experiment

`thr-double-well-001` · wrapped by the bridge

The simulation side's result card for `sim-20260923-101`, the hold run
`run-20260924-101-v3-hold`, is carried here unchanged. The bridge wrote no
number of its own: this envelope's `numbers[]` is empty, which is why none of
the payload's values appear below. The trap targets, the bench ranges and the
predicted observables are in the payload's `numbers[]`, each with its own
source and grade, and the receiving side should read them there.

Everything this round asserts is in three files and is not repeated here.
`r1_ask_experiment.json` holds the payload and the three gate verdicts.
`r1_hashes.json` holds the source card as it stood in the sender's directory.
`status.json` is the only place that says whose turn it is and what state the
thread is in.

## The run started before this delivery, on the person's decision

The person handed this result over directly, and then decided to start the
bench without waiting for the round to be filed. The microscope side carded
its measurement citing the simulation's committed result by id. This round was
written afterwards, so that the thread exists and the microscope goal can link
to it. Nothing in it is backdated: the envelope's time is the time it was
written.

## A result, so a person opened it

A plan crosses when it is finished. A result crosses only when a person hands
it over, and that is what happened here.

## One observable gates the round

The payload predicts four double-well observables. The round is gated on well
occupancy alone, which the microscope side declares it can produce in all four
of its imaging configurations when combined with the traps. The other three
ride in the payload unchanged and are not gated, so a later round can still ask
any of them without repeating this one.

## Two things the bridge noticed and did not fix

Neither blocks this round, and both are written in the envelope's unit note.

- **Residence time is computed with a different estimator from the registered
  one.** The payload takes the mean of completed dwells; the registered
  definition divides total time in a well by the number of exits, because the
  mean of completed dwells reads low. Until both sides use one form, residence
  times cannot be put side by side.
- **The barrier height is labelled as dimensionless rather than in kT.** The
  value is in thermal-energy units in substance, but the label says otherwise,
  and a later round's unit check reads the label.

## What the store said

Before spending the round the bridge asked the librarian whether well
occupancy already has an entry that would answer this. It had none, so there
was nothing to point at instead of opening the round. The details are in
`status.json`.
