# 035 — the piezo stage, then the confocal laser, then the optical tweezers

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-2`.** The person asked for this work
through architecture on 2026-09-24: *check the piezo stage, the optical
tweezers and the confocal laser*. The person then said **piezo first**. So
the order is **piezo, then confocal laser, then tweezers**, and within each,
phase A before phase B.

**Card 034 is also yours.** Carry on with 034 until your current axis work
is committed. Then take this card's phase A. Neither blocks the other.

**Goal**: each of the three is wrapped, understood and ready to check live,
and **checked live only after `microscope-20260924-1`'s run has released the
hardware, with the person at the bench, one device at a time.**

## Phase A — now. Nothing touches the hardware

**No device opened and no vendor process started.** No Micro-Manager load,
no Tweez300 GUI or system manager, no NIDAQ task, no serial port. The piezo
vendor DLL's **simulator link** (`sim:/NPC6330`) is allowed, because it
opens no port. Confirm that it opens none before relying on it.

**New files only.** Do not edit anything `microscope-20260924-1`'s run
imports, or anything `check_software_motion` or `GuardedCore` depends on:
`src/devices/micromanager.py`, `src/orchestrator.py`, `src/operator.py`,
`src/session_033.py`. That session loads them from this shared working copy,
and would run on a half-edited allow-list. Your device modules go in
`src/devices/` as new files, named by the registry's `driver` column the
way the router resolves them. If a module cannot be reached without editing
the router, **stop and report up**. That edit is a card of its own.

Per device:

1. **Rule the prior project's material** under `plan.md` 10.2.1, which is
   open for the upgrade since `f0a475a`: `C:\agentic_microscope\config\piezo`,
   `config\lunf` and `config\tweezers`. Each item is **transfer**,
   **downgrade** or **discard**, with **no fourth word** (`32e2263`). A
   transfer names its A1–A7 slot and the 10.3 rule it passed. **No safety
   limit crosses, including one written as a comment.** Write each ruling as
   one line in **`microscope_agent/rulings.jsonl`**, in that ledger's shape
   and attributed to your seat. That file is yours to write, unlike
   `tasks/`
2. **Write the device's four functions against mock** (preflight, apply,
   read, abort), in the shape the other backends have. For the piezo,
   against the DLL simulator too
3. **Write the live checklist**, card 018's style: each line names what is
   tested, why, and the store entry it rests on. A line with no entry says
   so, and names the gap

## Phase B — later, and not by your own decision

**Only after `microscope-20260924-1` reports its run finished and the
hardware released, with the person at the bench, one device at a time.**
That seat reported run `-002` complete. Wait for the person to say the bench
is yours. A report between sessions is not that.

## 1. The piezo stage — first

**What the person stated (2026-09-24, to architecture):** three axes, **X, Y
and Z on controller channels 1, 2 and 3**. Each axis's device range is
**−100 to 600 µm**, and the person prefers to operate in **0 to 600 µm**.
**These are the person's statement, not a reading.** Record them as such.

**The limit the person must write before any live command.**
`envelope/safety.json` has no piezo limit today. The schema for one landed
at `37c6d69`: `piezo_{x,y,z}_position_{min,max}`, in µm, each end requiring
the other, each with `bounds`. **Only the person writes that file.**
Architecture will hand the person a paste-ready block. Nothing from the
prior project or from a model enters it.

**The wrapper, in phase A, refuses in these cases, each with a test watched
failing:**

- **an axis whose limits are absent**: every command on it is refused. A
  missing limit is a refusal, never a default to the device range
- **a start outside the limit**: the wrapper reads each axis's position
  **before** any command and refuses if it is out of range. **It never
  "corrects" by moving into range.** That would be an unplanned move
- **a target outside the limit**, and a floor above its ceiling (the
  schema cannot compare the pair, so the wrapper does)
- **the waveform generator, entirely.** On 2026-08-27 in the prior project,
  a ±5 µm sine uploaded to the controller's waveform generator in picometres
  swung the axis **314 µm**. The unit the generator reads was never settled
  there. **Refused until that unit is measured here.** It is a failure-list
  item: write it to the failure record under 8.2's fields
- **any exit path that leaves the controller unlocked.** Commands exist only
  after an unlock to user or super-user. The prior scripts had a
  `--leave-unlocked` flag. **Yours returns the controller to its base
  security level on every exit path, including abort and an exception**

**Z is a collision axis, and a travel limit is not a clearance limit.**
Which piezo-Z direction approaches the objective is **unmeasured**, the same
shape as `pfs_offset_sign_unmeasured`. **No piezo-Z motion beyond a small
direction-finding step**, with the person watching and the step size the
person's, until that direction is measured and recorded.
`objective_clearance_min` binds piezo Z as it binds `ZDrive`.

**A second master.** The prior project never settled whether the controller
also follows the analogue line `Dev1/ao2` that NIS drives. Two masters on one
actuator means either can move the sample. **Settle it before any live
command**: read the controller's analogue/digital path setting, and ask the
person whether NIS is running. `microscope-20260924-1`'s run loaded no NIDAQ
analogue output (`dad0f5e`).

**Phase B, in this order:**

1. **read-only first**: the command set, position per channel, the
   security level, the analogue/digital path setting. With the person present
2. **motion only after the person's limit is written, and only as a planned
   operation.** A preparatory run cannot include it: check 85 refuses a
   plan-less run that dispatches to `piezo_stage`
3. **the first motion verifies the channel-to-axis mapping**: a small step
   on each channel, watching which way the image moves, the way the camera
   was verified by a frame. Then the facts leave as a result card for the
   librarian, graded by how they were established

## 2. The confocal laser — second

`laser_combiner`: the registry says blanking and line select over the DAQ,
per-line power over SPI, and **`read_back: false`**, so every dispatch
records **`verification: none`**. A return code is not a read-back
(`lunf_per_line_power_is_not_transmittable`, `laser_shutter_on_the_combiner`).

**This is a hazard to people first.** `optical_power_max` in the safety file
is the **trapping** laser's dial range, measured at the sample plane.
**Whether any limit covers the confocal lines is the person's to say.
Until the person has said it, no line is enabled from software**, in phase A
or B.

In phase A: rule `config\lunf`, wrap against mock, and write the checklist.
**Every live line waits on the person's limit.**

## 3. The optical tweezers — third

- **The Tweez300 takes a Kinetix and locks others out both ways**
  (`camera_red` `exclusive_with: optical_tweezers_gui`). So it cannot run
  while anything else needs a camera, and phase B for it is a bench session
  of its own
- **Trap power is a hand control** (`trap_laser_power_has_no_software_path`):
  nothing here verifies `optical_power_max`, and no test may imply otherwise
- **It reports nothing back** (`tweez300_reports_nothing_back`). A return
  code is not a verification. **A missing reply is never retried**, because
  several commands are relative. **An explicit rejection may be.** Its
  readiness codes are re-measured here, not taken from the prior project
- **An objective change invalidates both trap calibrations**
  (`objective_change_invalidates_trap_calibration`), and neither is readable
- trap motion is motion: check 85 refuses a plan-less run that dispatches to
  `optical_tweezers`

## What to bring back

- the rulings, in `rulings.jsonl`, with a count per word
- each module, and **each refusal test watched failing**: switch the refusal
  off, see the test fail, switch it back
- each device's checklist
- **the questions only the person can answer**, in plain words: the piezo
  limit and whether the waveform generator may ever be used; whether NIS
  drives `Dev1/ao2`; whether a limit covers the confocal lines, and what it
  is

## Constraints

- **Nothing touches the hardware in phase A**
- `envelope/safety.json` is the person's alone
- `microscope-2` is a retired name and stays unused
- Commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`,
  naming new files individually. Hooks are not installed; say so in the
  message. Run `PYTHONUTF8=1 python contracts/validate.py` and read the tree
  line

**Re-read this card immediately before committing.**
