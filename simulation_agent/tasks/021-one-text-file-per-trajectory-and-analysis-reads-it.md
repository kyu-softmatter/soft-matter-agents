# 021 — one text file per trajectory, and analysis reads it instead of re-running

**For:** one simulation execution seat — handed to window 4 (`simulation-10`),
whose active runs produced ten of the eleven trajectories now on disk.
**Supersedes the format of:** `013`, which made trajectories get written at all,
as GSD. The person has since asked for text.

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

## What the person asked

A run keeps its trajectory as **one text file**, so that analysis reads the file
instead of running the simulation again, and the person deletes the file by hand
when they need the space. Architecture recorded the rule in plan.md §4.6
(`4fb0b98`); the contract side is in place (`ca56709`): a schema for
`trajectory_meta.json`, and check 83, which reports a written trajectory that has
since gone.

## The writer — `src/trajectory.py`

**One file, `runs/<run_id>/trajectory.txt`. Not beside a GSD.** Two copies of one
trajectory are one fact in two places, and this repository has spent a day on
what that costs. If there is a reason a GSD must also survive — a HOOMD restart
input, say — do not write both: report the reason, and architecture will rule
whether it is a record or a cache.

**Header**, as comment lines at the top of the file:

- `run_id`, the plan hash, the engine and its version, the seed
- the box, the save interval **in steps**, the number of particles and of frames
- for every column, its meaning and its unit — and where the engine works in
  reduced units, the length and time scales that convert them
- the dtype the values had before they were written

**Columns:** the integer step index, the particle id, the **unwrapped**
position components, and the orientation where the model has one. Unwrapped,
because the mean-squared-displacement estimator requires it, and because the
periodic-image flags that would otherwise have to travel with the file are the
thing a flat box got wrong today (`hoomd_backend._snapshot_positions`, fixed by
window 3).

**Time is the step index**, never an accumulated floating-point time.

**Digits follow the source**: 9 significant figures for float32, 17 for
float64 — each round-trips exactly — and the header says which. Writing more
than the source carries prints precision that does not exist, and the schema
refuses any other count.

## `trajectory_meta.json`

Stamp it `"artifact": "trajectory_meta"`, `"schema_version": 1`, and make it
validate against `contracts/schemas/trajectory_meta.schema.json`. That
discriminator is what brings the file under the schema — the 44 metas already
on disk do not carry it and are not judged. Under `trajectory`, a written text
file needs:

- `sha256` — of the **file's bytes**. Integrity for reuse.
- `coords_sha256` — over the **coordinate array in its source dtype**, not the
  text. The text hash moves with formatting (digits, separators, line endings)
  and so cannot say whether two runs produced the same positions; the array hash
  can, and it is what shows which engine ran.
- `dtype`, `sig_figs`, `time_base: "step_index"`, `save_interval_steps`,
  `frames`, `particles`, `engine`, `engine_version`, `seed`, `plan_hash`,
  `box`, `units`, and `columns` (name, unit, meaning for each).

A run that writes no trajectory says so: `written: false` with a `reason`.

## The reuse path

Analysis that needs the positions **reads the file**. When the file is absent,
or its bytes no longer match `sha256`, the reader **says so and stops** — it
does not quietly re-run the simulation, and it does not read some other file in
its place. Re-running is the person's decision once they have been told the
file is gone; check 83 is what tells them, naming the rerun (engine, version,
seed, configuration) and the hash that will verify it.

## Done when

- a run on an engine backend leaves exactly one `trajectory.txt` and no GSD;
- its `trajectory_meta.json` validates against the schema;
- recomputing `sha256` over the file and `coords_sha256` over the re-read
  array both match what the meta recorded;
- the reuse path, pointed at a run whose file was deleted, refuses with the
  reason rather than re-running — watch it refuse;
- `python3 contracts/validate.py` ends `0 failed` and check 83's denominator
  counts the new run as present.

Report the check-83 line you get, with its denominator.

## Closed at ab334c9, and what happens to the GSD files already on disk

Done by window 4 and measured on `run-20260923-042-small-s2`: one
`trajectory.txt` (31 MB, 17 digits because the frames are float64) and no GSD
beside it; the meta validates; both hashes recompute and match after a re-read;
the reuse path refused a deleted file with the rerun recipe. Check 83 counted
19 runs with a trajectory, 19 present.

**The person decided (2026-09-23): the twelve GSD trajectories already on disk
stay as they are, and only new runs write text.** Converting them was weighed and
declined. It adds no information -- the positions are already in those files --
and it would either keep the same data twice or delete originals that cannot be
recovered. The size cost is not uniform: measured on two of them, a one-particle
run SHRINKS as text (GSD's per-frame header outweighs one particle's coordinates)
while a thirteen-particle run grows 1.7x, and the two 1000-particle runs that hold
most of the 1.4 GB would grow severalfold against a 10 GB storage ceiling.

**So a GSD trajectory is not a defect to fix.** The schema accepts it as the legacy
form and check 83 counts it. Convert one only when an analysis actually needs it,
and then mark the result as converted from GSD, not written by the run.

**Not adopted: having the operator re-read every file it writes.** Whether text
round-trips is a property of the writer's format -- 9 digits for float32 and 17
for float64 return the same array by construction -- proven once on the run above
and unable to change between runs unless the writer does. Re-parsing 30 MB to 2 GB
on every run would pay repeatedly for that. The guard belongs to a test that runs
when `src/trajectory.py` changes.
