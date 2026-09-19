# 005 — carry the fan-out's caller_ids to the versioned form

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**This card is `microscope-1`'s**, because every file it touches is one this
seat wrote. Do it before A3.

## Where this picks up

`71da178` moved `caller_id` into `common.schema.json` as
`<qid>:v<N>:<config>:<axis>`, and says the form without `v<N>` is accepted
only while cards predating `a6dca6a` migrate, then refused. Every caller_id in
this fan-out is the old form. It passes today and all of it breaks when the
window closes.

## Scope — counted, not listed from a report

I counted rather than taking the four files that were reported, and there are
five, with one of them excluded for a reason that matters:

| file | v-less ids | |
|---|---|---|
| `axis_widefield_inline_a1.json` | 5 | migrate |
| `axis_widefield_inline_a2.json` | 9 | migrate |
| `axis_widefield_inline_a7.json` | 4 | migrate |
| `configs.json` | 7 | migrate |
| `failures.jsonl` | 3 | **leave alone** |

Twenty-five ids move; three stay. There is no A4 card — it was never
committed and is not on disk, so it is not in scope.

**`failures.jsonl` does not migrate.** Its three are inside historical
records: two deviations at 07:26:33Z and 07:42:51Z, and the abandoned A4
attempt at 07:35:00Z. Each describes something that happened when the
caller_id genuinely was the old form. Rewriting them would make the record
say a call was made that was not — the same argument that keeps the old
`kb_version` strings in `goal.json`'s provenance note. **A record of the past
is not stale merely because the present moved.**

## Substitution is not migration

**Do not edit the ids in place.** A card's `caller_id` is a claim that *that*
caller made *those* calls, and the calls are in `queries/log.jsonl` under the
old id. Rewrite the card alone and the correspondence §0.3-4 exists to check
is broken — the card points at a caller with no queries, and the queries point
at a caller with no card. That is worse than the thing being fixed, because it
is invisible.

**So re-query under `:v1:`.** Revision 1 writes `v1` rather than omitting it —
the schema says so. The answers do not change: same pin `kbv-49feb73662b7`,
same `answered_from`, same entries, same grades. The cost is the call count
and nothing else. If an answer *does* come back different, stop and report it
— that is a finding about the store, not about this task.

## One commit

All four files in one commit. Check 33 compares siblings under a directory and
a qid, so a1 migrated while a7 is not is a mid-state that fails it, and a seat
that hits that failure will be tempted to fix it by re-pinning. Do not split
the work, and do not let the gate see a partial tree.

`configs.json` is S3.0's card and is the exception to the usual rule that you
do not touch it: it carries the fan-out's seven issued ids, so the issuer has
to move with the issued. Move all seven, including `a3`, `a5` and `a6`, which
name axes not yet written — an id the executor issued is the executor's to
keep consistent whether or not an axis has used it yet.

## What holds

The pin does not move. `kbv-49feb73662b7`, as everywhere in this fan-out.

`degraded` must still be empty and still be true — you will be making real
calls, so it should stay empty honestly. A2 is the standard here: it is the
first card in this repository that committed with `degraded: []` (`3774c49`).

## Done when

Twenty-five ids read `mic-20260918-001:v1:widefield_inline:a<N>`, the three in
`failures.jsonl` are untouched, `python3 contracts/validate.py` ends
`0 failed` with check 33 passing, and one commit as `seat:microscope-1`.

Then one sentence up: whether any re-query answered differently.

## Who holds which axis

On disk so that two seats in one checkout do not collide:

| axis | seat | |
|---|---|---|
| A1, A2, A7 | `microscope-1` | done |
| A4 | `microscope-1` | blocked on the discrete-constraint slot |
| A6 | `microscope-3` | card 004 |
| **A3** | `microscope-1` | after this card |
| **A5** | `microscope-3` | after A6 |

## Not this task

**A4.** Its guard is the missing discrete-constraint slot and `71da178` did
not touch that. When the slot lands, re-running produces the card — the rule
is read from the schema.

**The envelope snapshot**, which waits on the librarian publishing the export.
