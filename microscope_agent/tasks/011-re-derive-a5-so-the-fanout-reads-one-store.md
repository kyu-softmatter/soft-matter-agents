# 011 — re-derive A5, so the fan-out reads one store

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Small, and it is holding a check out of the tree.** Whichever seat holds
`mic-20260918-001` — 008's seat, not `microscope-4`.

## What is wrong

Six axes read one store and A5 reads another:

```
kbv-7c77fa74ee5a   a1  a2  a3  a4  a6  a7
kbv-49feb73662b7   a5                        <- revision 1, never re-derived
```

Six commits and fifty-eight entries apart. **Check 33 passes on this**, and
that is not a bug in check 33: it groups by `(scope, qid, revision)` because a
revision is a re-run and `caller_id` carries no revision component, so
grouping without it would fire "caller_id reused" on a card and the card that
replaced it. Correct for that question — and it partitions the fan-out, so the
`kb_version` agreement holds trivially inside each partition and nothing looks
across them.

**A revision counts re-runs of one axis, not of the fan-out.** Six axes at
revision 2 and one at revision 1 are one fan-out, and S4 will intersect all
seven.

## Why it matters even though nothing is wrong yet

I checked all six of A5's missing inputs — `drift_rate`, `focus_tolerance`,
`pfs_behaviour`, `settling_time`, `session_time_budget`,
`instrument_availability_window` — against the current store. **All six are
still absent.** So A5's card is not currently saying anything false.

**That is the reason to fix it now, not the reason to leave it.** The hazard
is the shape, not today's values: an axis at an older pin reports `absent` for
something the newer store holds, and downstream **that is indistinguishable
from a real absence**. S4 would take it at face value. Closing it before it
costs something is cheaper than after.

## The task

**Re-derive A5 at `kbv-7c77fa74ee5a`** — or at whatever the other six sit on
when you start; read it off a card rather than off this line.

**Re-derive, not re-pin.** Ask every one of A5's bounds again at the new
version. A gap that stays `absent` only because nobody re-asked is the false
absence check 49 exists to catch, and it is the same failure this card is
about, one level down.

Expect the six to stay absent. **Say so explicitly if they do** — that is a
result, and it is what makes the re-derivation checkable rather than assumed.

## What is waiting on this

**Check 58 is implemented and cannot land while this is true**, because it
fails on exactly this fan-out and the commit gate refuses a failing tree.
Weakening it to make it landable is the failure architecture named today:
*deleting the right thing to satisfy the gate leaves a green tree, which is
worse than a bypass because a bypass leaves a trace.* So the check waits for
the defect, which is the correct order.

Tell me when this lands and I will put it in the same hour.

## What holds

`degraded` stays `[]` and stays honest.

Cite the store as `kb:<entry_id>`; do not repeat the entry's own source
prefix. Both spellings give the same grade so nothing catches the wrong one,
and the wrong one adds nothing to `kb_refs`.

`git diff -- <paths>` before committing. Naming a path is not naming a change.

## Done when

All seven axis cards under `mic-20260918-001` name one `kb_version`, A5's
bounds have each been asked again at it, `python3 contracts/validate.py` ends
`0 failed`, and one commit.

Then one sentence up: whether any of the six stopped being absent.
