# 036 — the confocal laser

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-3`.** The person opened this seat on
2026-09-24 and chose the confocal laser as its first work, through
architecture. The laser first sat on card 035 with the piezo and the
tweezers. It was split off when the person opened two more seats. Card 035
is `microscope-20260924-2`'s piezo, and card 037 is `microscope-20260924-4`'s
tweezers. **Take nothing from either.**

**Goal**: the confocal laser is wrapped, understood and ready to check live,
and **checked live only with the bench handed to you by the person.**

## This is a hazard to people first

**No laser line is enabled from software, in either phase, until the person
has said which limit covers the confocal lines.** `optical_power_max` in
`envelope/safety.json` is the **trapping** laser's dial range, measured at
the sample plane, and says nothing about these lines. `illumination_power_max`
exists in the schema and is unwritten. Which one covers these lines, and at
what value, is the person's to decide and to write. Nothing from the prior
project or from a model enters that file.

**And no laser line is enabled while the light path can reach the
eyepieces.** No such rule exists in the safety rules yet. Architecture has
been told, and writes it. **Hold to it from this card in the meantime.**
Before any line is enabled, the light path's state is read back from the
stand, and a path that reaches the eyepieces refuses. A path that cannot be
read back refuses too. Ambiguity stops.

## One holder of the bench

`plan.md` 6.2.1, decided 2026-09-24: **a seat opens a device only after the
person has said, in that seat's own window, that the bench is its.** That
means a Micro-Manager load, a vendor program, a serial port, a DAQ task.
**A relayed hand-over is no hand-over**, from me or from any seat. When you
release the bench, **say so, and leave every device you opened in a stated
state.** Four microscope seats are running, and a laser lights frames
another seat was never meant to be in.

## Phase A — now. Nothing touches the hardware

**No device opened and no vendor process started.** No Micro-Manager load,
no NIS, no NIDAQ task, no SPI or serial port, no vendor GUI.

**New files only.** Do not edit anything another seat's run imports:
`src/devices/micromanager.py`, `src/orchestrator.py`, `src/operator.py`,
`src/session_033.py`, and whatever `microscope-20260924-2` and `-4` are
writing for their devices. Your module goes in `src/devices/` as a new file,
named the way the router resolves the registry's `driver` column. If it
cannot be reached without editing the router, **stop and report up**.

1. **Rule the prior project's material** under `plan.md` 10.2.1, open for the
   upgrade since `f0a475a`: `C:\agentic_microscope\config\lunf`
   (`probe_lunf.py`, `bisect_dac.py`, `handoff_from_nis.py`,
   `disk_survives_kill.py`) and its record. Each item is **transfer**,
   **downgrade** or **discard**, with **no fourth word** (`32e2263`). A
   transfer names its A1–A7 slot and the 10.3 rule it passed. **No safety
   limit crosses, including one written as a comment.** Write each ruling as
   one line in `microscope_agent/rulings.jsonl`, attributed to your seat
2. **Establish what `disk_survives_kill.py` shows.** Its name suggests the
   spinning disk keeps its state after the process controlling it dies. **A
   state that outlives its controller is exactly what a stated release has
   to cover.** If the disk keeps spinning, or the laser stays unblanked, when
   your process ends, then "leave every device in a stated state" has to
   include it. Read it, rule it, and say in the checklist what state each
   device is left in when your process is killed rather than closed
3. **Write the four functions against mock** (preflight, apply, read,
   abort), in the other backends' shape. The channel is `laser_combiner`:
   blanking and line select over the DAQ, per-line power over SPI, and
   **`read_back: false`**. So **every dispatch records `verification:
   none`, always.** A return code is not a read-back. The refusals, each
   with a test watched failing:
   - **no line enabled** while the person's limit for these lines is absent
   - **no line enabled** while the light path reads as reaching the
     eyepieces, or cannot be read
   - **abort blanks every line first**, and says it did, but records
     `none`, not `readback`, because nothing reads it back
4. **Write the live checklist**, card 018's style. Each line names what is
   tested, why, and the store entry it rests on:
   - `laser_shutter_on_the_combiner`
   - `csuw1_shutter_gates_confocal_excitation`
   - `csuw1_disk_speed_exposure_constraint`: an exposure through the
     spinning disk must be an integer multiple of the disk period, or stripes
     remain
   - `lunf_per_line_power_is_not_transmittable`

   A line with no entry says so and names the gap

## Phase B — later, and not by your own decision

**Only when the person has said, in your window, that the bench is yours,
and only after the person's limit for these lines is written.** Read-only
first. Then **one line, at the lowest setting**, with the person told before
it goes on, the path read back as not reaching the eyepieces, and a frame to
show it went where it was sent.

## What to bring back

- the rulings, in `rulings.jsonl`, with a count per word
- the module, and **each refusal test watched failing**: switch the refusal
  off, see the test fail, switch it back
- what `disk_survives_kill.py` establishes, and what that means for a
  release
- the live checklist
- **the questions only the person can answer**, in plain words: which limit
  covers the confocal lines, and its value

## Constraints

- **Nothing touches the hardware in phase A**
- `envelope/safety.json` is the person's alone
- Commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`,
  naming new files individually. Take your email from `contracts/seats.json`.
  Hooks are not installed; say so in the message. Run
  `PYTHONUTF8=1 python contracts/validate.py` and read the tree line

**Re-read this card immediately before committing.**
