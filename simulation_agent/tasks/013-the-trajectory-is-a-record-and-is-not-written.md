# 013 — the trajectory is a record, and nothing writes it

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
The person asked for trajectories to be kept. Half of that is already the
design and is simply not implemented; the other half is a principle change and
is **not in this card** — see the last section.

## Measured

```
runs/*/            config.json · log.json · observables.json · trajectory_meta.json
files that are not json                     0
mock_backend.py  writes positions           0 times
hoomd_backend.py writes positions           0 times
```

The trajectory is computed frame by frame, consumed by the estimator and
**discarded**. `trajectory_meta.json` is 314 bytes of summary — frames, steps,
max single-step displacement, how it stopped. There is no trajectory on disk
and there never has been.

## Where it goes is already decided, and it is not the KB

§4.3.2's table, the **Record** row:

> what happened — questions, plans, run logs, **raw data**, the query log →
> each agent's `questions/` and `runs/` → **that agent, append-only**

So raw data is this agent's record, in `runs/<id>/`, beside the four files
already there. Nothing to design.

**And it is not a KB entry, for a reason the store demonstrated today.**
`kb_entry` requires `grade`; a grade attaches to **a claim about the world**
(§5.3.1). A trajectory is not a claim, it is data. On 2026-09-22 the librarian
retracted `pixel_size_calibration_is_not_repeated` on exactly this wall — a
decision is not a claim, so it cannot carry a grade, and the schema forced the
retraction rather than anyone choosing it. **A trajectory hits the same wall.**
P14 says the same thing from the other side: the librarian owns knowledge,
execution agents keep records.

## What to build

**Write the positions beside `trajectory_meta.json`.** The meta file stays
what it is — a summary that can outlive the data.

**Both backends must produce the same readable thing.** HOOMD writes GSD
natively and the mock does not, and if each writes its own format then a
mock-versus-engine comparison reads two formats and the first thing to diverge
is how a frame is indexed. That is `010`'s estimator argument one level down,
and `cc3adaa` already chose the right answer once by extracting
`src/estimator.py` rather than copying it. **Do the same here or say why not.**

**The cost number moves, and that is a revision.** Measured for revision 3:

```
10001 frames x 1000 particles x 3 coords x 8 bytes  =  0.24 GB per run
six revision-3 runs                                 =  1.4 GB
envelope storage_max                                =  10 GB      affordable
the plan's storage_estimate                         =  0.02 GB    becomes wrong
```

So storing trajectories makes `storage_estimate` false by an order of
magnitude — the same shape as the wall-clock estimate that came in 125× low
today. **Do not quietly leave it.** `a_cost_reference`'s falsifier has already
fired once on the wall clock; this is the storage half of the same assumption,
and replacing it is revision 4's work, not this card's.

**And say what a frame is.** A reader who opens the positions file a month
later needs the units, the ordering and what index 0 means without reading the
backend. Two lines in `trajectory_meta.json` cost nothing and are the only
thing that will still be there.

## Deleting a bad trajectory is NOT in this card

The person also asked that a trajectory found bad later be deleted with the
reason recorded. **That is a principle change and this seat cannot card it.**

```
P12's cost column   "Outputs accumulate without limit and are not deleted (P9)."
P9                  "Logs are append-only. A correction is a new revision, never an overwrite."
§4.3.2 Record row   "that agent, append-only"
```

Three places say outputs are not deleted, and one of them lists it as a cost
the design **accepted on purpose**. Root `CLAUDE.md`: if work would violate a
principle, the work is wrong, not the principle — and changing one means
editing `plan.md` first, in the same commit, with the reason. `plan.md` is
architecture's.

**It is raised, not dropped**, and with the part this seat can contribute:
a deletion trigger has to be **derivable**, not a verdict someone chooses.
That is the whole of today — check 6 recomputes `met`, check 72 recomputes
`within_tolerance`, and `simulation-2` caught a false backend label because
the numbers disagreed with it. A seat that may delete a trajectory by
declaring it bad is an unchecked verdict destroying evidence. If the principle
moves, the trigger should key on what is already declared: the result card's
criteria, or a named `falsifier` firing. An opinion formed later has to
**become** a declared criterion before it can delete anything.

**Do not implement deletion on the strength of this card.** Write the
trajectory; the rest waits on architecture.
