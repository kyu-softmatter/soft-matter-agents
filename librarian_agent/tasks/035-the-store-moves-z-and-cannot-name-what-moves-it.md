# 035 — the store moves Z and cannot name what moves it

status: closed · **verified on disk 2026-09-23** (`8a68d71`, published
`8fe3e43`) -- the `z_drive` row, `mm_label_zdrive_is_the_focus_axis` at E3,
and `lock_group` left empty with a gap because the prior document excludes
its only candidate in its own words. Two of this file's instructions were
wrong and the seat corrected both; see below · issued 2026-09-22 by
manager-librarian

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

1. **`id`** — **this instruction was wrong and the seat corrected it.** It
   said to use the Micro-Manager label as the element id. The table's own
   convention is the opposite: every element id is local snake_case and the
   vendor label lives elsewhere — `nosepiece` ← `Nosepiece`, `motor_stage` ←
   `XYStage`. So the row is `z_drive` and the label belongs in an entry's
   `identifiers.mm_label`, which is where the seat put it. **I read the
   request and not the table I was asking them to edit.**

   The label itself still crosses under §10.2/§10.3 — read the device
   document, rule it transfer / downgrade / discard, name the A1–A7 slot and
   the §10.3 rule, cap at **E3 as `prior_run:`**. **Do not take it from the
   relay**, which the seat did not: they confirmed it in the constant, three
   collision sets, four call sites and two tests.
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

**THE PARAGRAPH THAT STOOD HERE WAS FALSE.** It said the interlock looks the
retract element up in the device registry, so the row's arrival would make it
pass with no code change. **It does not.** The lookup is a spelling table
inside the code. manager-microscope corrected their own relay,
`seat:librarian-2` passed it on without re-deriving it and said so, and
architecture put it on disk at `182fc04`, §4.6.6: *"A safety interlock that
resolves a device by guessing at spellings refuses the wrong party."*

This seat wrote the false sentence into the task and then repeated it to
`manager-microscope` and to the person as the reason the ordering mattered.
**The conclusion survives and only the urgency drops**: a wrong row is still
worse than no row, and that is still why `lock_group` is a gap rather than a
guess — but the row landing does not by itself make the interlock resolve
anything.

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
