# 033 — one real acquisition today, with the person moving the microscope by hand

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-1`.** Take it before anything else queued
for you. Work sent down from the architecture seat at the person's request,
2026-09-24; the person's two decisions below are the person's, relayed, and
the card is what makes them an assignment.

**The goal is one real frame series on the particles today**, taken on this
computer, with the result card for the librarian. Not a finished pipeline:
the shortest path that is safe.

## What the person decided today

- **The person moves the microscope by hand**: objective turret, focus,
  stage, filters, light path. Software moves nothing.
- **The objective is the 20x dry lens.** Sample: the Abvigen particles, 5 µm,
  green excitation, red emission.

Both are **declarations**, recorded as the person's, and neither is evidence
of anything else (`preference_is_not_evidence`).

## Where things stand, so you do not redo them

| | state |
|---|---|
| 023 items 1, 2 (retract, clearance refusal) | landed, `5e6a8eb`. **They do not block today**, because today nothing moves under software (§1). **They still block the first software-driven motion**, and nothing in this card lifts that |
| 023 item 3 (router reaches `micromanager.py`) | landed, `48e40f5`. Needed today |
| 023 item 4 (honest verification) | `micromanager.apply()` already sets, waits, reads back and splits `verified` from `disagreed`. **Confirm the run log writes `readback` only for the `verified` half** and `none` for nothing on this path, because every device you command today reads back |
| acquisition | **does not exist in any backend.** No `snapImage`, no sequence, no `setExposure` anywhere in `src/`. You write it (§2) |
| driver | `pymmcore-plus` 0.18.1 imports; Micro-Manager 2.0 is at `C:\Program Files\Micro-Manager-2.0` |
| the validator | not a blocker. It judges records afterwards; run-time safety is `operator.py` and the orchestrator. Run it as `PYTHONUTF8=1 python contracts/validate.py` on this machine, since `python3` here is the Store placeholder |

## 1. No software motion, and code refuses it rather than a plan omitting it

**Write an allow-list, not a deny-list.** Today software may command exactly
two devices, plus the core settings that route them:

| allowed | what for |
|---|---|
| `LightEngine` | the excitation, by line, intensity and `State` |
| `Kinetix_red` | exposure, binning, acquisition |
| `Core` | `AutoShutter` (to 0, §2), and `Camera` / `Shutter` roles only if you must name them |

**Every other loaded device is refused, by name, before any command is
sent.** The request named ten: `ZDrive`, `Nosepiece`, `XYStage`, `PFS`,
`PFSOffset`, `IntermediateMagnification`, `FilterTurret1`, `FilterTurret2`,
`LightPath`, `CondenserTurret`. **The configuration you will load declares
more motorised or light-emitting hardware than that**, and a deny-list
written from the request would pass them:

- the spinning-disk unit: `CSUW1-Filter_Red`, `CSUW1-Filter_Blue`,
  `CSUW1-Dichroic`, `CSUW1-Port`, `CSUW1-Bright`, `CSUW1-Shutter`
- **`Aura`, a second light engine.** Commanding it puts light on the sample
  that the person was not told about
- `MightexPolygon1000` (the DMD), `DiaLamp`, `LappMainBranch1`,
  `Turret1Shutter`, `Turret2Shutter`, `Ti2-E__0`

That is P0's rule that ambiguity stops: a device nobody thought about is
refused, not permitted.

**Refuse the calls as well as the properties.** `setProperty` on a device
outside the list, and on any device: `setPosition`, `setRelativePosition`,
`setXYPosition`, `setRelativeXYPosition`, `setState`, `setStateLabel`,
`setConfig` (a group preset can move anything), `fullFocus`,
`incrementalFocus`, `enableContinuousFocus`. **Two places**: the
orchestrator refuses a plan that names any of these before the first command
goes out, so a bad plan fails whole and not halfway; and the backend refuses
at the call, as the backstop for a path that does not go through the plan.

**Reading is not motion and stays allowed.** `getProperty`, `getState`,
`getStateLabel` and `getPosition` on the stand are how you record what the
person set (§5).

**Watch it refuse before you trust it.** On mock: a plan with one `ZDrive`
command must refuse whole, and one with an `Aura` command must refuse too.
Report both refusals, word for word.

A person turning the turret at the stand gets the stand's own escape
(`nosepiece_write_runs_no_escape`, E3), which is why hand motion is safe
today and software motion is not.

## 2. Software drives only the excitation and the camera

**Name `LightEngine`, never `widefield_source_a`.** The Lapp branch is
unconfirmed (card 018 §5); the MM label is checked by `getLoadedDevices()`
and asserts nothing about the branch.

**Set `Core` `AutoShutter` to 0 immediately after loading, and read it
back.** This is a new P0 item and the most important line on this card. The
file sets `Property,Core,Shutter,LightEngine` and `Property,Core,AutoShutter,1`,
so **with it as loaded, every snap switches the light engine on by itself**.
That would light the sample without the person being told, and it would
spoil the dark-frame test in §4, because the snap would set `State=1` for the
very frame meant to prove `State=0` is dark. With `AutoShutter` at 0, light
comes on only when a command sets `State=1`, which is a command you log.

**Which line is green comes from the device, not from memory.** List
`getDevicePropertyNames("LightEngine")`, pick the green line by the name the
device reports, and record the name you picked. Get the particles' excitation
peak from the store (`tracer_excitation_peak`) through the librarian. If no
line name says a wavelength, stop and ask the person. Do not choose by
position.

**Write the acquisition code**, with the driver imported at the call and not
at module top (the module docstring says why):

- exposure through `setExposure`, then `getExposure` read back. It is a core
  call, not a property, so it publishes no allowed values (018 §4e)
- a single frame through `snapImage` / `getImage`
- a series through the sequence calls, keeping each frame's metadata,
  because `ImageNumber` is the only evidence of a dropped frame (018 §4b)
- the frame count derived from an integer, never accumulated (018 §4c)

**Shutdown order**, on finish and on abort: `LightEngine` `State=0` first,
read back, then anything else. Shutters before power (§2.1).

## 3. The configuration

**Load `C:\Users\Takatori lab\Desktop\bacteria4\Kyu_test\auto_chamber_setup\camera_red_only.cfg`
in place.** Do not copy it into the tree. Record the path and the file's
sha256 in the run log. When I read it, it began `4120281c36abb65c`. **If the
hash differs when you load, re-read the file before loading**, because
everything below describes that version.

What I read in that version, for you to confirm:

- **the `System` / `Startup` preset is empty**, so loading sets no positions
  by preset. Loading still initialises every declared device, including the
  Ti2 hub
- it declares `LightEngine` (Lumencor, COM3) and `Kinetix_red` as PVCAM
  `Camera-1`, and also `Aura`, the DMD and the spinning-disk unit (§1)
- **its own header explains the disagreement with the other file.** PVCAM
  `Camera-N` is an enumeration index, not an identity, so the one powered
  camera is always `Camera-1` and gets labelled `Kinetix_red` whichever body
  it is. `bacteria-dmd-main\micromanager\camera_red_only.cfg` (hash
  `963f44f6691fb36f`) maps it to `Camera-2` and loads no `LightEngine`; do not
  use that one. **Neither label settles which body is red.** Step 6 of §4 does

**Before loading**: the Micro-Manager GUI closed (PVCAM gives a camera to one
process), the tweezers GUI closed (`camera_red` `exclusive_with:
optical_tweezers_gui`), and the trapping laser off at its hand control.

**If the driver and the install disagree on device-interface version, stop
and report.** Do not work around it with another adapter directory.

**Fallback, on the person's word only: `C:\agentic_microscope`.** That is the
prior project, open under the ruling rule. Every item you take from it is
ruled **transfer, downgrade or drop** before use, never used for a safety
limit, and never loaded blind. **You cannot write `tasks/033-rulings.md`**
(your deny list covers `tasks/**`), so report each ruling up with the task
and I write the file.

## 4. Before any light, in card 018's order

1. **`getLoadedDevices()` against every name the plan calls.** A missing
   name is a gap, not a retry
2. **`AutoShutter` reads back 0** (§2)
3. **A dark frame is dark.** Take a baseline frame with the green line at 0
   and `State=0`. Then keep `State=0`, set the line to maximum, and take
   another. **They must match within read noise.** A run that cannot show the
   dark case cannot claim the bright one
   (`light_engine_master_state_gates_every_line`, E3)
4. **Intensity is per-mille, confirmed by reading back.** Read the line's
   upper limit (`getPropertyUpperLimit`). It should be 1000. Write the
   first-frame value and read it back. **The person's 10% is `100`; writing
   `10` gives one per cent** (`light_engine_line_intensity_is_per_mille`, E3)
5. **Set the line low *before* `State=1`, and tell the person before the
   light goes on.** Card 018 says "then `State = 1` and repeat". Repeating
   step 3 literally would switch full intensity onto the sample. Do not.
   **Nothing in `envelope/safety.json` caps excitation intensity** (it limits
   only laser power at the sample and objective clearance), so the low start
   is this card's instruction and not an enforced limit. Say that in the
   plan. Adding a limit is the person's decision
6. **Which physical camera sees the red light, settled by a frame, not by
   the label.** Read the camera's serial number and compare it with the store
   (`camera_bodies_are_told_apart_by_serial`), then confirm with a frame: the
   image changes when `State` goes 0 → 1. If the serial says the blue body,
   **that is a result**: record the mapping correction, do not relabel
7. **Bit depth measured from a saturated frame**, not read from `PixelType`,
   which reports 12-bit for 16-bit data (`pixeltype_misreports_bit_depth`,
   E3). **Do not saturate with the excitation on the particles, which
   bleaches the field.** Ask the person to raise the dia lamp at the stand by
   hand and lengthen the exposure. If that cannot be done today, record bit
   depth as unmeasured and report raw counts, not converted ones
8. **`ImageNumber` has no gaps**: a short dark sequence at `State=0`, every
   number present
9. **The planned exposure is the exposure taken**: set and read back at the
   value the plan uses (the pre-measurement asks 100 ms)

## 5. Then one short acquisition on the particles

The bare-particle pre-measurement shape is fine (card 016). It closes
`tracer_brightness` and `bleaching_rate`, the six abstentions standing on
them, and does not spend the one sample mount.

- **The objective is the person's declaration, recorded as such.** Also
  **read** `Nosepiece` `getStateLabel` (reading, not moving). The 20x is
  labelled `3-Plan Apo LmbdD0.8 20x` at state 2 in this file. **If the
  declaration and the read-back disagree, stop.** Record intermediate
  magnification the same way: declared, then read
- **Pixel size**: `pixel_size_20x_zoom_1x`, E2, through the librarian with an
  issued caller_id, at **1×1 binning** (its validity condition). Set binning
  and read it back
- **Bleaching spends a field.** Before each run the person moves to a fresh
  field by hand, and the run waits for the person to confirm it on the
  manual sheet (`manual.confirm`). Never on a timer
- the approval route is unchanged: **the person approves the plan** before it
  executes, as always. This card does not stand in for that

**At no cost, while the person is at the filters**: reading the designation
on the emission-wheel filter in the red position closes four open items at
once (card 018 §4f). Ask; it does not block.

## Constraints

- The trapping laser stays off; it has no software path. The tweezers GUI
  stays closed
- `envelope/safety.json` is the person's and is not edited
- Commits: hooks are not installed in this working copy, so no gate runs.
  Say so in the message. Take your email from `contracts/seats.json`

## Done when

- both refusals from §1 reported word for word
- every step of §4 logged with what was written and what was read back
- one series on the particles, the configuration's path and hash in its log,
  a result card for the librarian, and `ImageNumber` contiguous
- `PYTHONUTF8=1 python contracts/validate.py`, with the tree line read and
  quoted

**Re-read this card immediately before committing.**
