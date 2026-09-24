# 033 — one real acquisition today, with the person moving the microscope by hand

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-1`.** Take it before anything else queued
for you. Work sent down from the architecture seat at the person's request,
2026-09-24; the person's two decisions below are the person's, relayed, and
the card is what makes them an assignment.

**The goal is one real frame series on the particles today**, taken on this
computer, with its run log. The result card waits (§6). Not a finished pipeline:
the shortest path that is safe.

## What the person decided today

- **The person moves the microscope by hand**: objective turret, focus,
  stage, filters, light path. Software moves nothing.
- **The objective is the 20x dry lens.** Sample: the Abvigen particles, 5 µm,
  green excitation, red emission.

Both are **declarations**, recorded as the person's, and neither is evidence
of anything else (`preference_is_not_evidence`).

- **The excitation is the Aura III, not the Spectra III** (MM labels `Aura`
  and `LightEngine`). The person said this to `microscope-20260924-1`
  directly on 2026-09-24: first *"those are connected but today you can use
  Aura3"*, then, asked whether to switch the card, *"Yes, switch to the
  Aura"*. **This card was written for `LightEngine` and has been amended
  throughout.** Where an older line and this one disagree, this one wins.
  Report any line still naming `LightEngine` as the light you drive

## Where things stand, so you do not redo them

| | state |
|---|---|
| 023 items 1, 2 (retract, clearance refusal) | landed, `5e6a8eb`. **They do not block today**, because today nothing moves under software (§1). **They still block the first software-driven motion**, and nothing in this card lifts that |
| 023 item 3 (router reaches `micromanager.py`) | landed, `48e40f5`. Needed today |
| 023 item 4 (honest verification) | `micromanager.apply()` already sets, waits, reads back and splits `verified` from `disagreed`. **Confirm the run log writes `readback` only for the `verified` half** and `none` for nothing on this path, because every device you command today reads back |
| acquisition | **does not exist in any backend.** No `snapImage`, no sequence, no `setExposure` anywhere in `src/`. You write it (§2) |
| driver | `pymmcore-plus` 0.18.1 imports, and finds its own Micro-Manager `2.0.3_20260806` (device interface 75) ahead of the lab's `C:\Program Files\Micro-Manager-2.0`. See §3 |
| the validator | not a blocker. It judges records afterwards; run-time safety is `operator.py` and the orchestrator. Run it as `PYTHONUTF8=1 python contracts/validate.py` on this machine, since `python3` here is the Store placeholder |

## 1. No software motion, and code refuses it rather than a plan omitting it

**Write an allow-list, not a deny-list.** Today software may command exactly
two devices, plus the core settings that route them:

| allowed | what for |
|---|---|
| `Aura` | the excitation, by line, intensity and `State` (the Aura III; the person's choice, above) |
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
- **`LightEngine`, the Spectra III, which is now the second light engine.**
  Commanding it puts light on the sample that the person was not told about.
  It was the allowed one until the person switched to the Aura; **it moves to
  the refused list, and nothing addresses it**
- `MightexPolygon1000` (the DMD), `DiaLamp`, `LappMainBranch1`,
  `Turret1Shutter`, `Turret2Shutter`, `Ti2-E__0`
- **`NIDAQHub` and `LUNF-Blanking`**, the laser combiner's blanking lines,
  which the file the person chose declares (§3)

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
command must refuse whole, and one with a `LightEngine` command must refuse too. **Re-run both after the swap**: the refusals you reported were for the old list.
Report both refusals, word for word.

A person turning the turret at the stand gets the stand's own escape
(`nosepiece_write_runs_no_escape`, E3), which is why hand motion is safe
today and software motion is not.

## 2. Software drives only the excitation and the camera

**Name `Aura`, never `widefield_source_a`.** The Lapp branch is
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
`getDevicePropertyNames("Aura")`, pick the green line by the name the
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

**Shutdown order**, on finish and on abort: `Aura` `State=0` first,
read back, then anything else. Shutters before power (§2.1).

## 3. The configuration — the person chose it, and loading it is not motion-free

**Revised the same day.** This section first sent you to a file on the
Desktop. **The person has since chosen the prior project's
`C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg`**
for today, and opened that repository for this work. Use that file, **loaded
in place**, never copied into the tree. Record its path and sha256 in the run
log. When I read it, the hash began `8184073e31e1a7a6`. **If it differs when
you load, re-read the file before loading**, because everything below
describes that version.

### Stop before loading: the startup preset moves a mirror

```
ConfigGroup,System,Startup,LappMainBranch1,State,1
```

`loadSystemConfiguration` applies the `System` / `Startup` preset, so
**loading this file commands the Lapp-branch mirror**. That is software
motion, and §1 says there is none today. It is not a collision device, but it
decides whether light from the side branch reaches the sample, and the
branch is the unconfirmed one (card 018 §5).

**ANSWERED by the person, 2026-09-24, in this seat's session: "accept it,
load the file as chosen."** So take the first route below, and load the file
unmodified. **Log the answer in the run log before the load**, as the
person's decision, relayed through this card. The second route is kept below
only as the record of what was offered.

The two routes, as they were put to the person:

- **accept it**: log it as a load-time command with `from` naming the
  file's Startup line, and read the state back after the load
- **or load a copy with that line removed**, kept outside the tree. It is
  then no longer the file the person chose, so the log must say so and give
  both hashes

**It also changes what the dark frame proves.** The file's own comment says
State 1 passes the Lapp-branch light and **State 0 blocks it as completely as
a dark frame**. So step 3 of §4 must run **with the mirror in the state the
run will use**. A dark frame with the mirror blocking proves nothing about
`Aura` `State=0`.

### What else the file does

| | what it means for you |
|---|---|
| `Core` `Shutter=LightEngine`, `AutoShutter=1` | **the same hazard as before**: every snap would switch the light on. **The Shutter role stays at `LightEngine`**, its loaded value, and is not repointed at the Aura: with `AutoShutter` at 0 nothing opens the shutter device, and repointing it would be a write that buys nothing. §2's first step, `AutoShutter` to 0 with read-back, stands |
| `Kinetix_red` is PVCAM **`Camera-2`** | the header records `Camera-2 = serial A24M723015` as the red body, measured 2026-09-03. **That is the prior project's reading, not ours.** Read the serial here and compare it with that and with the store (step 6 of §4) |
| `NIDAQHub`, `LUNF-Blanking`, and the `LaserLine` group | TTL blanking for the LUN-F laser combiner. Its power sits on a separate controller that is not in Micro-Manager. **Add both devices to the refused list in §1** (`setConfig` is already refused). **The combiner must be off at its own power**: a blanking line is not a safety control |
| `Aura` is declared, and the header says it fails to initialise when its chassis is off | error 573 means "no reply", not "no port". **It is today's excitation, so its chassis must be powered on before the load**, or the whole load fails. `LightEngine` stays declared too, and is **never commanded** (§1) |
| the header says the `Aura` lines are `UV CYAN GREEN RED NIR`, each `<NAME>` (0/1) plus `<NAME>_Intensity` 0–1000 per-mille | the prior project's reading. §2 still says read the names off the device. **If the Aura reports no green line, stop and ask the person** |
| a `PixelSize` block, 20x at `0.32373` µm | **cite the store's `pixel_size_20x_zoom_1x`, not `getPixelSizeUm()`**. The number agrees, but the store is where knowledge lives. And the same block calls this "a real 20.078x", which is the over-precise magnification this project already downgraded. Do not carry that phrase anywhere |
| `FocusDirection,ZDrive,1` and its long safety note | nothing today, since nothing moves under software. **Do not transfer it**: the retract direction is in the store already (`z_retract_direction_is_measured`, E3) |

**Which Micro-Manager: pymmcore-plus's own copy, by the person's decision
(2026-09-24).** Load against
`C:\Users\Takatori lab\AppData\Local\pymmcore-plus\pymmcore-plus\mm\Micro-Manager_2.0.3_20260806`,
which is what `find_micromanager()` returns first. **This reverses this
morning's "Program Files is authoritative"**, which the person decided before
anyone knew that install cannot load under this driver. The reason is
measured, not preferred: `C:\Program Files\Micro-Manager-2.0` is MMCore
11.1.1, device interface 71, and pymmcore 12.5.0.75 needs 75, so **every lab
adapter fails to load from there**. `microscope-20260924-1` hit it today. The
prior project hit the same wall on 2026-08-27, and the file the person chose
was written for this copy, without the devices it cannot load. **Nothing is
installed or downgraded.**

**Two consequences:**

- the run log records **which install was loaded**: path, and the device
  interface version the core reports
- **these adapters are newer than the ones the lab's own GUI uses**, so
  nothing the lab has seen them do counts as evidence here. The before-light
  checks in §4 are what establish that they behave: the dark frame, the
  per-mille read-back, the serial, the saturated frame. That is one more
  reason not to skip any of them

**Before loading**: the Micro-Manager GUI closed (PVCAM gives a camera to one
process), the tweezers GUI closed (`camera_red` `exclusive_with:
optical_tweezers_gui`), the trapping laser off at its hand control, the LUN-F
off at its power.

### Rulings, and who writes them

Every item above that you **use** is ruled transfer, downgrade or drop,
naming its A1–A7 slot and the §10.3 rule. No safety limit crosses. **Report
the rulings up with the task and I write `tasks/033-rulings.md`**, because
your deny list covers `tasks/**`. What I expect you will find, for you to
confirm or overturn:

```
downgrade | camera serial-to-index mapping (header, 2026-09-03) | E3 at best; re-read here | 10.3 rule 1
downgrade | LightEngine line names and 0-1000 scale (header)      | re-read off the device   | 10.3 rule 1
drop      | PixelSize block                                        | the store holds it at E2; P14
drop      | FocusDirection ZDrive note                             | safety content; 10.3 rule 4, and the store has it
```

**The Desktop file (`bacteria4\...\camera_red_only.cfg`, hash
`4120281c36abb65c`) is no longer the plan.** It maps the camera to
`Camera-1`, has an empty Startup preset, and loads the DMD and the
spinning-disk unit. Keep it as the fallback only if the person says so.

## 3b. Today runs through a session script, not the plan dispatcher

**OK'd for today by this seat**, at the request of `microscope-20260924-1`
(report on §1 at `9db8abf`, item 4), with architecture raising no objection.
**Why**: the device registry carries no Micro-Manager labels, so `Aura`
and `Kinetix_red` raise `GapError` at preflight. And `derive_commands` never
produces `params.settings`, so `apply()` would verify nothing. Going through
the dispatcher today would look like a checked run and not be one.

**Conditions, all of them, and the run log must show each:**

1. **Every command the script will issue passes
   `Orchestrator.check_software_motion` before the first one goes out.** That
   means the whole list, built first and checked as a list, not command by
   command as the script runs
2. **Only `GuardedCore` touches the instrument.** No call on the unwrapped
   core, with **one named exception**: `loadSystemConfiguration`, which the
   guard does not list and is right to refuse. It runs **once**, only after
   the person has answered the Lapp-mirror question above, and it is logged
   as the load-time command it is
3. **Everything goes to the run log as the orchestrator records it**: the
   same `record()` and the same event shapes, so the log reads like any
   other run's
4. **The run log says in words that this run did not come through the plan
   dispatcher, and why**: the two gaps above, named
5. **Added by this seat: the person approves the command list before the
   light goes on.** Skipping the dispatcher does not skip the approval. Show
   the checked list and the first-frame intensity, and wait for the person's
   answer. The approval is the person's to write, as always
6. **Added by this seat: the script is committed in `microscope_agent/`
   with the run**, so the record says exactly what ran. A script that exists
   only in a terminal is a run nobody can re-read

**Frames go outside the tree**: `D:\soft-matter-agents-frames\<run_id>\`,
with each file's path and sha256 in the run log (architecture accepts, no
`.gitignore` change). The run log itself stays in `runs/` in the tree.

**After today, not today**: Micro-Manager labels in the registry, and
`derive_commands` producing settings. Those two close the gap this section
works around. Until they land, **this route is for this card's run only.**
Using it again needs another card.

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
   plan. Adding a limit is the person's decision.
   **If the frame stays dark with the Aura on, stop. Do not turn it up.**
   Nobody knows which branch the Aura's light comes in on, and the Lapp
   mirror you set at load decides which branch reaches the sample. A dark
   frame at low intensity may be the light path, not the light, and
   raising intensity to chase a signal is how full power reaches a
   sample. A dark result here is a finding about the branch (card 018
   §5). Record it and ask the person
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
- **Every frame's metadata will carry a pixel size of 0.32373 µm, and that
  figure is not a source.** The file's `PixelSize` block puts it there:
  Micro-Manager stamps `getPixelSizeUm()` into each frame. **Nothing
  downstream may take a pixel size from frame metadata.** Any pixel size used
  comes from the store entry above. **The run log says so in words**: that
  frame metadata carries a figure from the loaded configuration, and that it
  is not a source. Added 2026-09-24 on architecture's ruling (`32e2263`):
  the file is ruled a transfer, and its figures are discarded as a source.
  **The two numbers are identical, and that is not corroboration.** The file
  says its table came from an April 2025 spreadsheet. The store's source
  says the day of measurement was never recorded, only the day it was
  reported. They are very likely one measurement, not two. So the E2 is the
  store's grade for that measurement, and the file adds nothing to it
- **Bleaching spends a field.** Before each run the person moves to a fresh
  field by hand, and the run waits for the person to confirm it on the
  manual sheet (`manual.confirm`). Never on a timer
- the approval route is unchanged: **the person approves** before it
  executes, as always. Today that is the checked command list (§3b
  condition 5). This card does not stand in for that approval

**At no cost, while the person is at the filters**: reading the designation
on the emission-wheel filter in the red position closes four open items at
once (card 018 §4f). Ask; it does not block.

## Constraints

- The trapping laser stays off; it has no software path. The tweezers GUI
  stays closed
- The LUN-F laser combiner stays off at its own power. Its blanking lines
  load with the configuration and are refused (§1, §3)
- **The Lapp-mirror question in §3 is answered: accept it.** The answer
  goes in the run log before the load
- `envelope/safety.json` is the person's and is not edited
- Commits: hooks are not installed in this working copy, so no gate runs.
  Say so in the message. Take your email from `contracts/seats.json`

## 6. The record today: a run log, no result card, and not yet in the tree

**Ruled 2026-09-24 on `microscope-20260924-1`'s question.** A result card
needs `plan_id`, `plan_revision` and `plan_hash`, and no plan fits this run.
`plan-mic-20260920-001` is written for the 100x oil lens with software
motion, and its axis ranges were computed for that configuration. **A new
revision citing 100x ranges for a 20x run would be laundering.** So:

- **today: the run, with a run log and no result card.** Nothing that
  matters is lost: the frames, their hashes and the log are the record
- **after today: a new question for the 20x bare-particle
  pre-measurement**, with its own goal, axes and plan. Its result card cites
  today's run as the acquisition. **That needs a card, and this is not it.**
  Write no goal or plan card on the strength of this paragraph

**But `run_log.schema.json` requires `plan_id` as a string** and says *"a run
exists because a plan did"* (§4.6). So a log with `plan_id: null` fails its
own contract, and that is a design question, not something to fix at the
bench. **Until it is answered:**

- write the log **in the run-log shape**, `plan_id: null`, with a
  `no_plan_because` field saying the above in words, and the §3b line that
  this run did not come through the dispatcher
- **put it beside the frames, `D:\soft-matter-agents-frames\<run_id>\log.json`**,
  with its sha256 in your report. **Not in `runs/`, and not left uncommitted
  in the tree**: the working copy is shared, and an uncommitted file there
  can be reverted by anyone. Outside the tree, git touches nothing
- **do not invent a `plan_id`** to make the schema pass. A made-up id is a
  record claiming a plan that did not exist

This seat has raised the schema question to architecture. When it is
answered, the log comes into `runs/` by whatever route that answer gives.

## Done when

- both refusals from §1 reported word for word
- every step of §4 logged with what was written and what was read back
- one series on the particles, the configuration's path and hash and the
  Micro-Manager install in its log, the frames and the log under
  `D:\soft-matter-agents-frames\<run_id>\` with their hashes, and
  `ImageNumber` contiguous (§6: no result card today)
- the script committed in `microscope_agent/` (§3b condition 6)
- `PYTHONUTF8=1 python contracts/validate.py`, with the tree line read and
  quoted

**Re-read this card immediately before committing.**
