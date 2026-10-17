# 069 — a hardware run loads a configuration the person approved

Written by `manager-microscope-20261013-1` on the person's yes in this seat's
window on 2026-10-13, from the bench seat's report of the same day. You read
this; you do not edit it.

**Assigned to `microscope-office-20261015-1` (Microscope 3)**, from
2026-10-17. The person said in architecture-20261007-1's window that day,
verbatim: "Microscope 3에 설정 파일 카드 맡겨" (give the configuration-file
card to Microscope 3). That was relayed to manager-microscope-office-20261016-1,
which made the assignment on it. Card 064 passes `src/`, `tests/` and
`failures.jsonl` to you for this card alone, under "Card 069, Microscope 3",
and they go back when it lands. It was first assigned to
`microscope-20261007-1`, which holds the code otherwise. If you are not
`microscope-office-20261015-1`, take nothing from this card and report up.

**The freeze this card waited on has ended.** The bench seat's findings file
says, as its item 8 of 2026-10-13: "Instrument work for this visit is done
as of this item; the src/ and tests/ freeze may end."

## What was found

On 2026-10-13 the first hardware run of plan `mic-20261008-001`
(`runs/run-20261013-001/`) refused correctly, sending no command, but
both Z events carry `z_um: null`, with `z_read_failed: MicroManagerUnavailable:
no Micro-Manager configuration is loaded`. Verified against the code:

- `operator.py` `main()` (from line 1639) calls `run(..., backend=args.backend)`,
  and nothing on that path calls `devices/micromanager.load_configuration`
  (line 570). So `_core()` (line 398) finds only `Core` and raises.
- `live_view.py --backend hardware` loads nothing either.
- The only callers of `load_configuration` are the hand-written session
  scripts (`session_033.py`, `session_036_*.py`), each loading its own file.

So **on hardware, card 060's "encoder read before and after, equal" cannot be
met by any command the operator offers, and card 066's
`z_before_um == z_at_refusal_um` has only ever been true on mock.** The refusal
logic was right; what is missing is the core it is meant to read from.

## What to build

1. **An explicit option on `operator.py` and `live_view.py`** naming a
   configuration file, e.g. `--mm-config <path>`. With `--backend hardware`
   and no `--mm-config`, behaviour is unchanged: refuse as today. With
   `--backend mock`, the option is refused, not ignored.
2. **The file must be on the person's approved list.** Its sha256 is
   compared with an approval file the person writes under `approvals/`. A
   file not listed, or whose hash differs, is refused **before** anything
   is loaded. The seat never writes that approval. Define its shape in the
   smallest way that works and report it up, so the schema can follow.
3. **The System/Startup preset never runs.** Loading applies the file's
   `ConfigGroup,System,Startup` preset, which is a command the file issues:
   in `single_cam_red_noDMD_nocom10.cfg` it switches the Lapp main branch on
   load. Follow `session_036_readonly.py`'s `derive()` instead: write a
   derived copy without the startup preset into the run directory, and load
   that. Both hashes, the approved original and the derived copy, go into
   the log. If the file has no startup preset, say so in the log, and don't
   derive.
4. **Load through `load_configuration`**, which already turns AutoShutter
   off first and reads it back. **If `autoshutter.verified` is false, stop
   the run** before the gate or any other call.
5. **Log the load as an event in `events.jsonl`**: the original's path and
   sha256, the derived copy's path and sha256, what was removed, the loaded
   devices, and the AutoShutter readback. It comes before
   `focus_search_z_before`.
6. **Preflight with only the stand and `Kinetix_red` loaded.** The
   single-camera file does not hold the registry's other channels
   (`confocal_csuw1`, `camera_blue`, `laser_combiner`, ...). Confirm a
   focus-search plan still reaches the focus gate in that case, and that a
   missing device the plan does not use isn't a refusal. A missing device
   the plan does use **is** a refusal. Show both on mock, with a mock core
   that holds only those devices.

**Not in scope:** the dual-camera `DMD_dualcam_LUNF.cfg`, which opens the
DAQ and LUNF devices. Don't approve, derive or test against it here.

## One more thing the visit showed

Plan `001` is the "no focus limits written" refusal, but it refused for **no
plan approval** first, because the approval check runs earlier. So to watch
the no-limits refusal, the person has to approve plan 001 before writing any
limits. **Don't reorder the checks for this.** Say it in the report, so card
060's next visit asks the person in that order.

## Added after the visit (2026-10-13)

From the bench seat's report at the end of the visit; manager-microscope
checked it against `runs/run-20261013-001` to `-006`.

**Live view is in scope as much as the operator.** The person skipped the
first real abort through live view: with no configuration loaded, a
`live_on` could not switch the lamp on and the abort could not read lamp or
shutter rows. So the `--mm-config` option, the approved-hash check, the
derived file and the load event all apply to `live_view.py --backend
hardware` too. **Test the abort path explicitly**: after a load, an abort
reads every lamp and shutter row back. Before a load, it refuses as today.

**The operator's command line cannot state the hand-over lens.**
`run-20261013-002` refused with `no objective stated at hand-over`, because
`main()` passes no `handover` to `run()`. The bench seat worked around it
with a scratch driver (`D:/sma-scratch/060/bench_run.py`) that calls
`operator.run(..., handover={"objective": "20x"})` with the lens the person
stated. It sent no command and changed nothing in `src/`, but **a hardware
run should go through the operator's own command line**, so the record shows
the entry point that was reviewed. Add an option, e.g. `--handover-objective
<lens>`, that passes exactly what the person states and nothing it infers.
It never defaults: absent on hardware means the refusal stays. Log it as the
person's statement.

**Still not shown, for the next visit:** the focus-hold-on refusal, and Z
equal before and after any refusal. Both wait on this card.

## Tests

On mock, under `tests/`:

- no `--mm-config` on hardware → refused, unchanged;
- a file whose hash is not approved → refused, nothing loaded;
- an approved file with a startup preset → the derived copy is loaded and the
  preset's lines are absent from it;
- AutoShutter not verified → stop before the gate;
- the load event is in `events.jsonl` before `focus_search_z_before`, and Z
  is read on both sides of a refusal;
- `live_view.py` on hardware: no config → refused; with an approved config,
  an abort reads every lamp and shutter row back;
- no `--handover-objective` on hardware → refused, unchanged; with it, the
  stated lens reaches the gate and a mismatch with the plan's lens is refused.

Watch each new test fail before the code that passes it exists.

## Added 2026-10-15 by manager-microscope-20261003-1: the configuration's own focus direction

**An addition, not a rewrite**: the rest of this card is
manager-microscope-20261013-1's, unchanged. It comes from
microscope-office-20261015-1's report on card 075.

The Micro-Manager configurations that arrived with dino-autofocus, in
`microscope_agent/autofocus/configs/micromanager/*.cfg`, carry **live
`FocusDirection` settings for `ZDrive` and `PFSOffset`**. The librarian rules
them safety rows. If `--mm-config` is ever pointed at one of these files, or
at any file with such a line, the person's hash approval would be the only
thing letting that sign reach the stand. A hash says the bytes are the
approved bytes. It does not say the direction in them is right.

So, before anything is loaded on hardware:

- **Read each `FocusDirection` line in the file and check it, never take it
  from the file.**
  - For `ZDrive`, the direction must agree with the store's measured
    retract direction (`z_retract_direction_is_measured`: smaller Z is
    retracted). If it disagrees, or the file's direction cannot be read as
    one of the two, refuse before loading.
  - For `PFSOffset`, no direction is measured yet; the store records the
    gap. PFSOffset is refused by name to software, so this sign binds
    nothing software sends, but a load that would set it is recorded as
    such, beside the hashes.
- **Test it**: a configuration whose `ZDrive` direction is inverted is
  refused with nothing loaded, watched failing first.

## Added 2026-10-17 by manager-microscope-office-20261016-1: until the store holds the encoding, every ZDrive direction is refused

`microscope-office-20261015-1` asked this after reading the card, through
architecture-20261007-1. The check above needs two facts. The store has
the first: `z_retract_direction_is_measured`, smaller Z is retracted, E3.
It lacks the second: **which `FocusDirection` value in a configuration
means "increasing Z moves toward the sample"**. That meaning exists here
only as a comment in the imported files, and this card forbids taking it
from the file.

A rule that accepts one value, such as the literal `1`, would need that same
missing fact. It is safe only if `1` means what the store says is the retract
direction, and nothing on record says it does. Choosing the value from
memory would put a number no source backs into a safety check, so this card
does not do it.

So, until the store holds that encoding:

- **A configuration that carries any `FocusDirection` line for `ZDrive` is
  refused on hardware, whatever its value, with nothing loaded.** The
  refusal says the meaning of the value is not in the store and names the
  entry below. That includes the imported configurations, every one of
  which carries such a line.
- A configuration with no `FocusDirection` line for `ZDrive` sets no
  direction, and this rule does not refuse it. Everything else on the card
  still applies.
- **Test it**, watched failing first: one configuration per value seen in
  the imported files, plus one unparseable value, each refused with the
  missing entry named. A configuration with no such line passes this check.

**What retires it**: a store entry, graded and sourced from Micro-Manager's
own source code or documentation and not from the imported files, that
gives the encoding of `FocusDirection` for a Z stage. The id is the
librarian's to choose; `micromanager_focus_direction_encoding` is the
working name. When it lands, the blanket refusal is replaced by the
agreement check above, in a card of its own, with its own test. This card
includes no hardware run, so the refusal blocks nothing in it. The person's
first load on the instrument needs the entry to land first.

## What comes back

To manager-microscope:

- the commits;
- the approval file's shape;
- the validator's last line;
- every place the change needed a file outside `src/` and `tests/`.

**No hardware run is part of this card.** The first load on the instrument
is the person's, on a later visit, from a file they approved.
