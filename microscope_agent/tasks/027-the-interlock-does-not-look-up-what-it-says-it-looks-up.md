# 027 — the interlock does not look up what 035 thinks it looks up

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`** — you wrote `check_turret_rotation_allowed`,
and item 1 is a change to its refusal text.

**This card exists because I reported something wrong.** Librarian card 035
carries, as its reason for doing the row properly rather than fast:

> **They did not hardcode it.** The interlock looks the retract element up in
> the registry, so **the day this row exists the interlock passes with no code
> change.**

That sentence came from me. **It is false for most of the ids that row is
likely to carry**, and `librarian-2` is working 035 now against it.

## What the lookup actually is

`microscope_agent/src/orchestrator.py:443`:

```python
RETRACT_HINTS = ("focus", "z_drive", "z_axis", "objective_z", "z")

if e in self.RETRACT_HINTS or e.startswith("focus") or e.endswith("_focus")
```

I ran the predicate rather than reading it:

| matches | **does not match** |
|---|---|
| `z_drive` · `z` · `focus` | **`ZDrive`** · `zdrive` · `ZStage` |
| `focus_drive` · `objective_focus` | `z_motor` · `objective_focus_drive` |
| anything `focus…` or `…_focus` | `FocusDrive` · `TIZDrive` |

**`ZDrive` is the name 035 is most likely to come back with** — it is the
label I relayed out of the prior project's device list, and 035 quotes it.
It misses. So does the other Nikon-conventional form, `TIZDrive`. A correct
row, read off the right document, ruled transfer under §10.3, can land and
the interlock will not see it.

## Why this is worse than a plain miss

When `retract_elements()` is empty the refusal says:

> the objective is not retracted, AND NO PLAN CAN RETRACT IT. **No element in
> the device registry drives focus** … This is not a plan defect and it is not
> fixable in this agent — **the registry is the librarian's**

With a row present under an unmatched id, **every word of that is false and it
reads as true.** It names a cause that has been fixed and sends the reader
back to the seat that already did the work. 035's own warning is that a wrong
row passes the interlock naming the wrong thing; this is the inverse, and
neither of us wrote it down.

## 1. The refusal says what it searched for — do this first

No dependency, lands today. When `retract_elements()` is empty, the message
must carry the hints and the element ids it walked past, so that "the row is
missing" and "the row is there under a name I do not match" are
distinguishable **from the refusal alone**. Today they are not.

That is the whole of item 1. It does not make any plan pass; it makes the
next hour of somebody's day not be spent on the wrong seat.

## 2. The tuple must stop being the authority — and it needs 035 first

A tuple in `orchestrator.py` deciding which device performs a safety retract
is a rule stated in code **where the registry cannot see it** — the class this
repository keeps finding, and I am not quoting a count for it here because
every count written into prose in this repository has been wrong within a day.

The fix is a field on the element row — the registry says *this element drives
objective Z*, and the interlock reads that instead of guessing from spelling.
**That field is the librarian's to add and it is not in 035's three.** So:

- record it as a dependency, do not build it,
- and when it exists, `RETRACT_HINTS` is deleted, not widened.

## 3. Do NOT add `ZDrive` to the tuple

The shortcut is obvious and it is refused. `ZDrive` is **an unverified
quotation from a relay** — I flagged it as one when I sent it, and 035 repeats
that flag and tells its seat not to take the label from me. Adding it here
would put the same unverified string into the interlock **by the back door**,
where §10.2/§10.3 cannot rule it and no evidence grade attaches to it.

**P0 decides this.** A safety interlock is deterministic code; a guessed
spelling in its lookup table is a model-made value in a safety path, which is
the one thing P2 says enters nothing. Widening the tuple to catch a name
nobody has read is guessing the answer to 035 in code.

Wait for the row.

## REPORT

Item 1 landed, with the new refusal text quoted. For item 2: the field you
would want on the element row, stated precisely enough that a manager can
carry it to the librarian as a request — one sentence naming the field and
what it must distinguish. Do not ask for it yourself; `librarian_agent/` is
not yours and 035 is in flight.

And say whether anything else in `orchestrator.py` decides a device's ROLE by
spelling. `STABILISER = "pfs"` is the one I can see; I have not read for
others.
