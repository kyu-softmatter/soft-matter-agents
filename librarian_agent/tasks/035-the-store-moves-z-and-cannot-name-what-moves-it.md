# 035 — the store moves Z and cannot name what moves it

status: open · issued 2026-09-22 by manager-librarian · **requested by
manager-microscope; an interlock is waiting on the row** · found by
`microscope-1` writing the interlock

## Verified here, not relayed

Every claim below I read off `kb/staging/devices.v0.json` and the entries,
because the request came through a manager and the row is in this seat's
tree:

```
stand_ti2e  role:      "... output port, intermediate magnification, FOCUS,
                        transmitted lamp"
            elements:  nosepiece · filter_turret_1 · filter_turret_2
                       light_path_port · intermediate_magnification · pfs
                       dia_lamp · lapp_branch · motor_stage        (9)
            read_back: true
```

**The channel's role says focus and no element is one.** And the two nearest
are not it:

- `pfs` — its own note says *"focus **stabilisation**; disabled across turret
  and path changes"*. Stabilisation, not drive.
- `motor_stage` — `lock_group: stage`, note *"coarse **xy**"*.

**Nothing in the store names a Z drive.** Searched `kb/` for `ZDrive`,
`z_drive`, `focus_drive`, `focusdrive`: **0 files.**

## And the store already asserts Z moves

`z_retract_direction_is_measured`, E3:

> **Smaller Z is retracted on this stand — measured, not inferred.**
> Micro-Manager now carries the same convention in its configurations, so the
> instrument can answer which way retract is rather than requiring somebody
> to read a note.

**So the direction is known at E3 and the thing that moves in that direction
has no address.** The store asserts the motion and cannot name the mover.

## TASK — one element row on `stand_ti2e`

Three fields, and **each has a different failure mode if guessed**:

1. **`id`** — the Micro-Manager label. manager-microscope reports reading
   `ZDrive` in the prior project's 28-device list and **explicitly flagged it
   as a quotation they did not verify.** Treat it that way: this crosses
   under §10.2/§10.3 like the other control-path facts — read the device
   document, rule it transfer / downgrade / discard, name the A1–A7 slot and
   the §10.3 rule, cap at **E3 as `prior_run:`**. **Do not take the label
   from the relay.**
2. **`lock_group`** — manager-microscope reasoned it should serialise with
   rotation, because `nosepiece_write_runs_no_escape` says Z does not move on
   a software turret write. **They flagged that as their inference and it is
   not a registry value.** If the source document does not say which group it
   is in, **record the gap and leave the field out.** A guessed lock group
   schedules real motion.
3. **`read_back`** — this is the one the interlock turns on, and
   manager-microscope drew the right distinction: the **channel** is
   `read_back: true` and whether the **element** is may be a different
   question. Answer the element's, and if the document only speaks for the
   channel, say so rather than inheriting.

## Why it is worth doing properly rather than fast

`microscope-1`'s `check_turret_rotation_allowed` requires a PFS release and a
retract that was **read back** — `verification == readback`, because a
retract issued and not read is an assumption. **The retract action has
nothing to name**, and inventing a name is refused by check 38 anyway.

**They did not hardcode it.** The interlock looks the retract element up in
the registry, so **the day this row exists the interlock passes with no code
change.** That is why a wrong row is worse than no row: it would pass the
interlock while naming the wrong thing.

## A gap is an acceptable answer

manager-microscope said it and it is right: *"nobody asked"* and *"we looked
and it is not there"* are different, **and this is now the second.** If the
prior document does not carry the label, or carries it without a lock group
or a read-back, **a gap with `searched` filled is the deliverable** — and
then it is a bench question, not a store question.

## REPORT

The row, or the gap. For each of the three fields: what the source actually
said, and what you refused to fill. And say whether anything else in the
store was addressing Z without a name for it — `z_retract_direction_is_measured`
names O1 preflight and the orchestrator as movers, so there may be more than
one consumer waiting on this row.
