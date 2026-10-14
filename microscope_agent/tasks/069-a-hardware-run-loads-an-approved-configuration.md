# 069 — a hardware run loads a configuration the person approved

Written by `manager-microscope-20261013-1` on the person's yes in this seat's
window on 2026-10-13, from the bench seat's report of the same day. You read
this; you do not edit it.

**Assigned to `microscope-20261007-1`**, which holds `src/` and `tests/`
under card 064. **Do not start until card 064's freeze ends**: the bench seat
says in its findings file that the visit's instrument work is done. Before
then, design and test only in a scratch copy.

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

## Tests

On mock, under `tests/`:

- no `--mm-config` on hardware → refused, unchanged;
- a file whose hash is not approved → refused, nothing loaded;
- an approved file with a startup preset → the derived copy is loaded and the
  preset's lines are absent from it;
- AutoShutter not verified → stop before the gate;
- the load event is in `events.jsonl` before `focus_search_z_before`, and Z
  is read on both sides of a refusal.

Watch each new test fail before the code that passes it exists.

## What comes back

To manager-microscope:

- the commits;
- the approval file's shape;
- the validator's last line;
- every place the change needed a file outside `src/` and `tests/`.

**No hardware run is part of this card.** The first load on the instrument
is the person's, on a later visit, from a file they approved.
