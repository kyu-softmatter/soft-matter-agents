# 004 — A6, resolution and sampling

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**This card is `microscope-3`'s.** Commit as `microscope-3@seat.invalid`
(`8fa779e`). A4 is `microscope-1`'s under card 003 and is not yours; A2, A3
and A5 remain unassigned and are not yours either until a card says so. The
division lives here because nothing in the tooling refuses a collision — see
the last section.

## The task

**A6 for `mic-20260918-001`, configuration `widefield_inline`.** Pinned at
**`kbv-49feb73662b7`**. Do not re-pin: A1, A4 and A7 sit there, check 33 wants
siblings to agree, and the server serves the pinned version (`4033b4d`) with
`answered_from` proving it did.

A6 owns resolution and sampling. The expected shape, which 001 already named:
**the diffraction limit computes; Nyquist does not.** Six objectives carry the
inputs for the first; no pixel size exists for the second.

## The trap in this axis, and it is the whole reason for this card

**`kb_query(observable=numerical_aperture)` comes back `absent`, and that is
not a gap.** The store holds NA six times over. I checked the index rather
than repeating a report: `objective_mrd70040`, `_mrd70170`, `_mrd70270`,
`_mrd71670`, `_mrd71970`, `_mrd77400`, each of kind `claim`, each carrying

```
numbers[]: {"name": "na", "value": 0.20, "unit": "1", "source": "spec:MRD70040", "grade": "E3"}
           {"name": "working_distance", "value": 20, "unit": "mm", "grade": "E3"}
```

Nothing is indexed under the observable name `numerical_aperture`, so the
query misses. Reach them with `kb_get` on the entry ids.

**Generalise this before you record any gap.** The librarian seat classified
the whole query log on 2026-09-19: of ten `kb_query` calls, nine came back
empty, and **eight of those nine were the store failing to recognise its own
knowledge** — not absence. Exactly one, `pixel_size`, was an honest absent.

So: **an empty `kb_query` is not evidence of absence right now.** Before you
write `kind: absent`, look for the thing under another name — an entry id, a
`numbers[].name`, a table. If you find it, it is not a gap and the card must
not say it is. If you cannot find it, say `absent` and you will be right, as
`pixel_size` is.

This matters beyond tidiness. A4's card is on disk claiming five `absent`
gaps and at least three of them are not absent — the store has them in a
published table. That card will be revised. **Do not add a sixth wrong gap to
the same fan-out.**

## A third kind of answer you may meet

A query may return `in_published_table` rather than an entry or an absence —
"that is in your snapshot's `tables.devices`, sha256 `1a12298e…`". It is a
real answer and points you at your own envelope copy.

**Do not bake one into a card yet.** Those hashes currently point at
uncommitted bytes: `kb/exports/snapshot_microscope_agent.json` is modified in
the working copy and its `snapshot_hash` moved three times in ten minutes. A
card citing a hash with no commit behind it cannot be checked by anyone later,
which is the same reason `microscope-1` stopped before copying the snapshot
into `envelope/`. If A6 needs one, record the need and stop; the librarian
seat will announce publication.

## What holds

Every inequality the axis owns gets an entry: an interval, or an abstention
with `kind` and `reason`, and `missing` named when `kind` is `no_input`.
Silence is refused (§4.5.2.1); an interval with neither bound is that same
silence. **An abstention with a reason is a correct outcome** — A1 and A7 both
abstained and both were right to.

A computed value inherits the worst precision of its inputs (§5.8). NA is a
catalog designation at two figures and the entry says `0.20 is not 0.2
rounded`; do not improve on it.

An axis states a range and does not choose inside it. It does not read another
axis's output, and it does not read lessons (P16).

`degraded` must be empty only if that is true, and it is now checkable against
`librarian_agent/queries/log.jsonl`. A gap's `searched` names the call you
made, not a directory you read. A4 got both of these right and is worth
reading as the example.

## Surfaces you share, with nothing refusing a collision

There are no worktrees, so you and `microscope-1` write the same checkout:

- **`src/axis_common.py`** — do not edit it. Put helpers your axis needs in
  your own axis module. If you believe something genuinely belongs in the
  common module, say so and I will card it rather than have two seats edit it.
- **`questions/mic-20260918-001/failures.jsonl`** — append only, and a
  simultaneous append can lose a line. Write yours in one shot and re-read the
  file afterwards to confirm it is there.
- **`configs.json`** and **`goal.json`** are S3.0's and not yours.
- Commit with `git commit -- <paths>`, never `-A` (§6.2.1).

## Done when

The A6 card is committed and `VALIDATED`, `python3 contracts/validate.py` ends
`0 failed`, dead ends are appended to `failures.jsonl`, and `kb_refs`,
`kb_gaps` and `degraded` each say something true about how the answer was
actually obtained.

Then one sentence up: whether the diffraction limit produced an interval, and
what Nyquist abstained on.
