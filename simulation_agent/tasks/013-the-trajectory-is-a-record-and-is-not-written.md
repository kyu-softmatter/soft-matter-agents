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

## Deleting one is settled, and it is not this card's work either

This card said deletion was a principle change and refused to card it. **That
was raised and answered the same day**, and the answer is worth knowing while
you write the writing half.

**No principle blocked it.** Architecture read P9 and found P12's cost column
had cited it for something it does not say: P9 governs the RECORD -- *a
correction is a new revision, never an overwrite* -- and says nothing about
the data a record points at. Dropping positions while the run log and
`trajectory_meta.json` stay is neither a correction nor an overwrite. P12's
column is corrected (`4ccaef9`), and the person approved the policy directly
in that session (`c438c30`).

**So a trajectory may be deleted, and the trigger has to be derivable.** The
contract for it is already in place and you do not have to design any of it:

```
run_log.schema.json   a `deletion` event carrying `what` and `triggered_by`
triggered_by.kind     criterion | falsifier -- nothing else
triggered_by.declared_in   the plan card AND its revision
triggered_by.recorded_in   required for a falsifier: where its firing is recorded
no free-text reason field, and additionalProperties refuses one
check 77              resolves all of it, and is NA until a deletion exists
```

**There is deliberately no prose reason.** The reason is the criterion's own
`statement` in the plan, by reference -- the same move `estimation` makes
against the vocabulary. A sentence there would make the trigger a verdict the
writer chooses, and deletion is the most expensive version of that: a wrong
claim leaves something to read, a deleted trajectory leaves nothing.

**None of this is your job in this card.** Write the trajectory. Deleting one
needs a criterion to have fired, and nothing has. What this section is for is
so you build the writing half knowing the shape that will later remove it --
in particular that `trajectory_meta.json` must keep meaning something after
the positions are gone, which is why it stays a summary and does not grow to
hold the deletion.
