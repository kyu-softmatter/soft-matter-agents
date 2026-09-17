# staging — extracted, not yet in final form

## What this is

Two tables pulled out of the prior microscope project at M1, under the rules in
`plan.md` §10.2 and §10.3:

- `devices.v0.json` — one row per control channel: how it is driven, whether it
  can be automated, whether its state can be read back.
- `optical_paths.v0.json` — which configurations deliver light to a detector,
  what must be set for each, and which cannot run together.

## The storage form is provisional, and that is deliberate

**These are flat tables. They are not the final shape of this knowledge.**

The design says one atomic claim per entry (`plan.md` §4.3), and neither of these
files obeys that. The reason for waiting: the right decomposition depends on how
the knowledge will be queried, and the querying side — the librarian agent, its
`kb_query` arguments, its condition-range matching — does not exist until M3.
Splitting these into forty small entries now would fix a shape around a guess.

So they sit here, in `staging/`, read directly by the microscope agent at M1
(`plan.md` §4.3.0 allows direct reads while there is no service), and they get
decomposed when there is something to decompose them *for*.

`kb_index.py` does not index this folder. Nothing cites these files with a
`kb:` source yet, because a `kb:` citation has to resolve to an entry with a
grade, and that is exactly what M3 will create.

## What was dropped, and why

The source dossier is far larger than what is here, and most of it was left
behind on purpose. Dropped: part numbers, serial numbers, firmware versions,
spectral band tables, per-fact verification dates, and the running narrative of
how each fact was corrected, retracted and re-confirmed.

None of it has a consumer. The test applied to every field was **"which of
S3.0, axis A4, the orchestrator's locks, or O1 preflight reads this?"** — and a
field with no reader is a field that will be out of date without anyone
noticing, which is worse than not having it.

The narrative is not worthless; it is just not this file's job. It belongs in
`kb/distilled/` if and when someone needs to know why a value changed.

## Everything here is capped at E3

`plan.md` §10.3 rule 1: a measurement taken in another project is not a
measurement taken here, because there is no run id and the calibration state of
that day cannot be reproduced. Confirming any of these on the instrument
promotes it to E1 and supersedes the extracted row.

Two things were **not** extracted at all:

- **Safety limits.** Policy, not knowledge (§4.3.2), and §10.3 rule 4 says a
  person writes them after confirming them physically. They go to
  `microscope_agent/envelope/safety.json`.
- **The specific port position that carries the detection path.** The prior
  project recorded it, and it is one integer that would be wrong silently after
  any re-cabling. It is listed as a gap instead.

## Gaps are part of the content

Both files end in a `gaps` list, and both now also carry `resolved_gaps`. The
three the operator originally named — a motorised xy stage, the spinning disk's
speed and in/out position, and whether a separate laser shutter exists — were
recorded as gaps rather than guessed, and all three were answered on 2026-09-17.
That is the rule working: an unknown that is written down can be filled, and one
that is inferred cannot be found again.

## What the verification pass of 2026-09-17 did to these files

The operator read every row at the instrument. The confirmed claims are now
atomic entries in `kb/entries/`, cited from these tables as `entry_ref`, and the
tables kept the structure the entry schema has no slot for: part numbers, slot
positions, per-element ids. `kb/distilled/operator_verification_20260917.md` is
the record of what changed and why.

Two rows left `channels[]`. `camera_splitter` was never a device — it is the
confocal unit's port, and it was absent from the device list under that name
because it was already there under another. `temperature_stage` has never been
connected, so nothing actuates the sample temperature and it is not a control
channel. Neither fact was deleted: both are in `retired_rows`, with what the row
had claimed and why it was wrong, because a row that vanishes silently is
indistinguishable from one that was never there.
