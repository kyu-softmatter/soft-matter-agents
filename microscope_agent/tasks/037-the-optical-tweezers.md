# 037 — the optical tweezers

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-4`.** The person opened this seat on
2026-09-24, and through architecture gave it the optical tweezers. The
tweezers first sat on card 035 with the piezo and the confocal laser. They
were split off when the person opened two more seats. Card 035 is
`microscope-20260924-2`'s piezo, and card 036 is `microscope-20260924-3`'s
laser. **Take nothing from either.**

**Goal**: the tweezers are wrapped, understood and ready to check live, and
**checked live only with the bench handed to you by the person, and held
alone.**

## One holder of the bench, and this device holds it alone

`plan.md` 6.2.1, decided 2026-09-24: **a seat opens a device only after the
person has said, in that seat's own window, that the bench is its.** That
means a Micro-Manager load, a vendor program, a serial port, a DAQ task.
**A relayed hand-over is no hand-over**, from me or from any seat. When you
release the bench, **say so, and leave every device you opened in a stated
state.**

**Starting Tweez300 is opening a device.** So is its system manager. And
phase B holds the bench alone: the tweezers take a Kinetix and lock out every
other process both ways (`camera_red` `exclusive_with:
optical_tweezers_gui`), and they drive the most powerful light source on the
bench.

## Phase A — now. Nothing touches the hardware

**No Tweez300 process started at all**, not the GUI and not the system
manager, and no TCP connection to one. No Micro-Manager load, no camera, no
serial port, no DAQ task.

**New files only.** Do not edit anything another seat's run imports:
`src/devices/micromanager.py`, `src/orchestrator.py`, `src/operator.py`,
`src/session_033.py`, and whatever `microscope-20260924-2` and `-3` are
writing for their devices. Your module goes in `src/devices/` as a new file,
named the way the router resolves the registry's `driver` column
(`python_tcp`). If it cannot be reached without editing the router, **stop
and report up**.

1. **Rule the prior project's material** under `plan.md` 10.2.1, open for the
   upgrade since `f0a475a`: `C:\agentic_microscope\config\tweezers`
   (`active-microrheology-drive.yaml`, `run_pattern.py`,
   `trap_from_tracking.py`, `trap_sequence.py`) and its record. Each item is
   **transfer**, **downgrade** or **discard**, with **no fourth word**
   (`32e2263`). A transfer names its A1–A7 slot and the 10.3 rule it passed.
   **No safety limit crosses, including one written as a comment.** The
   prior project's command gap, retry count, backoff, reply timeout and
   readiness codes are **measured numbers from there**. They go to the
   librarian at E3, cited to that measurement, and **not into code as
   constants**. Write each ruling as one line in
   `microscope_agent/rulings.jsonl`, attributed to your seat
2. **Write the four functions against mock** (preflight, apply, read,
   abort), in the other backends' shape. The channel is `optical_tweezers`,
   **`read_back: false`**. The rules it must hold, each with a test watched
   failing:
   - **a return code is not a verification.** A zero means the GUI accepted
     the text. Six distinct ways a command can be ignored all return zero
     (`tweez300_reports_nothing_back`). **Every dispatch records
     `verification: none`, always**
   - **a missing reply is never retried.** Several commands are
     **relative**, so re-sending one that did land moves the trap twice.
     **An explicit rejection (the "busy" answer) may be retried**, because
     the GUI said it did not run the command. The two must be told apart in
     code, not by a timeout
   - **readiness is re-measured here.** The prior project treated three
     codes as up and five as up-but-unusable. One of the three came from
     measurement against the manual. Take that shape; the codes are theirs
     until measured on this bench
   - **an objective change invalidates both trap calibrations**
     (`objective_change_invalidates_trap_calibration`), and neither is
     readable over TCP. After any rotation, both are unknown until re-done
     by hand
3. **Write the live checklist**, card 018's style. Each line names what is
   tested, why, and the store entry it rests on. A line with no entry says
   so and names the gap

## Trap power is a hand control, and nothing here verifies it

`trap_laser_power_has_no_software_path`: the trapping laser's power is a
dial, with no software path at all. So `optical_power_max` in the safety
file is the only control there is, and **nothing here can verify compliance
with it. Do not write a test that implies otherwise.** A checklist line on
trap power says the person sets it by hand and says what they set it to.
Nothing is measured by this code.

**Trap motion is motion.** Check 85 refuses a run without a plan that
dispatches to `optical_tweezers`, so anything that moves a trap is a planned
operation.

## Phase B — later, and not by your own decision

**Only when the person has said, in your window, that the bench is yours,
and that no other seat needs a camera or the sample.** Read-only first: the
readiness codes, measured. Then one command at a time, with the person
watching the trap, and every reply logged as it came, including silence.

## What to bring back

- the rulings, in `rulings.jsonl`, with a count per word, and the prior
  project's constants sent to the librarian, not kept here
- the module, and **each rule's test watched failing**: switch the rule
  off, see the test fail, switch it back
- the live checklist
- **the questions only the person can answer**, in plain words: which
  camera body the tweezers GUI opens, and the trap power the person will set
  for the first live check

## Constraints

- **Nothing touches the hardware in phase A, and no Tweez300 process
  starts**
- `envelope/safety.json` is the person's alone
- Commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`,
  naming new files individually. Take your email from `contracts/seats.json`.
  Hooks are not installed; say so in the message. Run
  `PYTHONUTF8=1 python contracts/validate.py` and read the tree line

**Re-read this card immediately before committing.**
