# Round 2 — simulation to experiment

`thr-tracer-diffusivity-001` · wrapped by the bridge

Revision two of the simulation side's plan card for `sim-20260917-001` is
carried here unchanged. The bridge wrote no number of its own: this envelope's
`numbers[]` is empty, which is why none of the payload's values appear below.
Restating them would put one quantity in two places, and by next week it would
be two quantities (P3, check 9).

Everything this round asserts is in three files and is not repeated here.
`r2_ask_experiment.json` holds the payload, the three gate verdicts and what
this round supersedes. `r2_hashes.json` holds the source card as it stood in
the sender's directory — its path, its id, its revision, the state it was read
in and its hash. `status.json` is the only place that says whose turn it is and
what state the thread is in, because it is the only file here that changes.

## Why this is a supersession and not a repeat

Same observable, same direction, same thread as the opening round, which on
its own is a repeat and is refused: a repeat re-asks something that was
answered, and re-asking belongs in the ledger as a knowledge reference rather
than in a new round. This is legal for a different reason — the source moved.
The plan is a later revision of the same card, so nothing has been answered
and the question has not been asked twice.

The envelope names the round it replaces, and that name is not taken on trust:
check 8 recomputes the supersession from the two rounds' ledgers, which
already record what each was built on, and refuses a round that claims to
supersede one whose source did not move.

## What the supersession does to the parcel already delivered

The opening round's envelope sits in the receiving side's inbox, and nothing
is ever removed from an inbox — the delivery happened and the file is the
record of it. When that round was written the thread had no way to mark it
superseded, and this seat's ledger said so at the time. It has one now, and it
sits on the newer envelope rather than on the older one: a round says what it
replaces, and a parcel that has already been handed over is not edited
afterwards.

## What moved, without restating it

The substance is in the payload, named there with its own sources and grades.
The change has a single root: the tracer diameter stopped being this side's
assumption and became a measured entry from the store, and the fit window, the
record length, the saving interval and the expected diffusivity all follow
from that one substitution. The receiving side should design against the
payload's `numbers[]` rather than against the window it has been holding since
the opening round, which was set for the diameter that has been discarded.

## What the librarian would still have changed

The payload carries `degraded` and the envelope carries the same list, so a
plan built in reduced mode does not read as normal on this side. That list is
the simulation side's to empty and this seat does not touch it.

Separately, this seat did reach the store for this round and asked whether the
observable already has an entry a round could be substituted with, which is
what `plan.md` 4.4 rule 5 makes the duplicate gate for. What came back is
recorded in `status.json` and not here.
