# 2026-10-15 (Thu) bench to-do — 5 µm sample, a day of measuring by hand only

> **Software moves nothing. Only hand actions.**
> Z, the stage, the objective turret, PFS, light and the laser are handled by the person, by hand only, at the Ti2 panel, focus knob, joystick and vendor GUI.
> In the Micro-Manager GUI, do **only property reading (Device Property Browser) and camera Snap/Live**.
> Do not use MM's Multi-D Acquisition (Z stack) or stage-move buttons, the dino app, `scripts/*`, or SMA operator / orchestrator / live_view.

- Written so that this document alone can be taken to the bench. The detailed original checklist is dino-autofocus `docs/runbooks/bench-visit-1.md` (main 4d38e72); its section numbers are in brackets.
- Every box gets **value / method / who / when**, or, if not measured, a mark at **not measured □**. Do not fill in a guess.
  "Who" is the person id. Do not write emails or PC user names.
- Under "Method", write the source: measured by hand / read from the device / catalogue / decided by the person.

## 0. What was and was not done on the last visit (2026-10-13)

Taken from the SMA record `microscope_agent/findings/microscope-20261013-1-20261013.json` (SMA 1104cc6).

| Done | Details |
|---|---|
| PFS three states read | Off / on and locked read (the searching state was too quick to catch) |
| Camera maximum | 65535 ADU, Port `Dynamic Range`, ReadoutRate `100MHz 16bit`, read from the histogram. **Exposure and which camera were not written down** |
| CSUW1 shutter | Only `Open` read. **The closed name was not read** |
| SMA limits | The person wrote `focus_z_<lens>_min` 0 µm and `_max` 3300 µm for all six objectives in `envelope/safety.json`. **3300 is exactly the position where the objective touches, with no margin** |
| 6 SMA runs | All refused, 0 commands to the instrument. Z was never read |

| Not done (to do today) |
|---|
| All of dino's hand measurements: sample focus curve, focus difference per objective, PFS offset direction, first-focus miss after an objective change, 40x water objective working distance |
| SMA card 060 step 6, the CSUW1 closed name, the blanks in the camera maximum |

**Still not done today**: Z readings before and after a refusal, a refusal test with PFS on, a real abort through live view, a focus search.
These are done on the next visit, after SMA card 069 (the hardware run loading the approved configuration file) has been built.
The locks `BENCH_MOTION = "LOCKED"`, `BENCH_APPROACH = "MEASURED"` stay as they are.

## 1. How to stop (at any time)

| What | Where |
|---|---|
| Hardware stop | Ti2 controller / joystick at the stand |
| Let go | A hand-driven move stops when you let go |
| Light off | Light-source panel / Ti2 panel shutter |
| Laser off | Tweez300 vendor GUI / laser key (the person only) |

An odd sound, the oil or water film breaking, a feeling that the objective touches the coverslip → stop on the spot and lower Z by hand.

## 2. Before starting (nothing moves)

| # | Check | Result |
|---|---|---|
| 2.1 | SMA operator / orchestrator / live_view is not running (Task Manager, SMA terminals) | yes / no (→ stop) |
| 2.2 | Only one MM GUI. dino app server, Jupyter and scripts are off (two cores on one MM is a known failure) | yes / no (→ stop) |
| 2.3 | **Read which objective is in place now.** At the end of 10-13 it was **changed by hand from 60x Oil → 20x** (nobody has checked since) | Nosepiece State ___ Label ___ |
| 2.4 | 5 µm sample: slide type, particle type (fluorescent or not, colour), coverslip thickness, whether the particles are stuck to the glass or floating | |

## 3. Reading the starting state (read only) (§3)

| Item | Value |
|---|---|
| Objective (Nosepiece State, Label) | |
| ZDrive µm | |
| XY µm | |
| PFS (FocusMaintenance, PFS Status, PFS in Range) | |
| Light sources (Aura, LightEngine, DiaLamp) | |
| Piezo z µm (NanoBench display) | |
| Time | |

These values are the starting point of the 4.4 drift. At the end, read them once more in §12.

---

## Today's tasks (in the recommended order)

### ① The direction in which the ZDrive value increases (§4.1) — 5 minutes

When the focus knob is turned a little **in the direction in which the objective approaches the coverslip**, does the ZDrive value increase or decrease.
(Because SMA's `_max` means "the closest Z", if this sign is reversed the person re-examines what 3300 means.)

| increases / decreases | Objective | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|
| | | | | | |

### ② Glass-interface Z per objective and the focus difference between objectives (§5.4) — find the interface with the 5 µm particles

At the same XY, the ZDrive value at which each objective focuses on the particles (= the coverslip interface). Difference = each objective's Z − the 4x Z.
**Before rotating an objective, always lower Z and switch PFS off.** For immersion objectives, oil/water on the person's judgement.
These values become the grounds for the margin on `focus_z_<lens>_max` (⑩). The interface Z must be below 3300 — stop if it comes close to 3300.

| Objective | Interface Z µm | Difference vs 4x µm | Light | XY | How far the first focus missed after the objective change µm | Who | When | Not measured □ |
|---|---|---|---|---|---|---|---|---|
| 4x | | 0 | | | | | | |
| 10x | | | | | | | | |
| 20x | | | | | | | | |
| 40x WI | | | | | | | | |
| 60x Oil | | | | | | | | |
| 100x Oil | | | | | | | | |

For reference: on 2026-09-30, 4x→100x was about −60 µm (once); the lab note says about −100 µm. Do not try to match them.

### ③ 40x water objective working distance, correction collar 0.17 (§5.3)

First check that the correction collar reads 0.17. The person's statement is 170 µm (10-05). Inside dino both 160 and 170 exist — **write the measured value as it is, and do not choose.**
Example methods: (a) the value on the objective barrel or spec sheet (a catalogue value); (b) interface focus Z_f → only if the person judges it safe, very slowly to just before the objective front face touches (where the shape of the water film changes), Z_c. **Do not let it touch. If unsure, do not do (b).**

| Correction collar | Z_f µm | Z_c µm | Working distance µm | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

### ④ Q13 — 100x Oil approach step (§5.1) — no answer yet

Z 0 → 100x Oil by hand → oil → knob up to near the interface → above that, little by little with the fine knob.
Do not call the current code's provisional value of 10 µm right; write what was seen today and the step the person will allow.

| Item | Value | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|
| One knob click µm (fine / coarse) | | | | | |
| Step µm used near the interface | | | | | |
| Wait between steps s | | | | | |
| Maximum step the person will allow the software µm | | | | | |
| Z µm at which the oil joined (if seen) | | | | | |

### ⑤ Focus curve per mode (§5.5) — the "sample focus curve" in the 10-13 record

Near the particles, move Z one step at a time **with the knob** and save one MM GUI Snap at a time. One row per mode (brightfield / fluorescence / reflection).
The curve is computed on the desktop after the visit. If the frames can be shared with ⑥, write so.

| Objective | Mode, light | Z range µm | Step µm | Frames | Exposure ms | Readout mode (Port + ReadoutRate) | Save folder | Not measured □ |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

### ⑥ Shadow-mode evaluation frames (§5.7, `docs/sma-shadow-mode.md` §7)

Frames for a first record of how well the classical metrics and DINO agree with the person's hand focus. **Scores are not computed at the bench.**
Illumination is fluorescence (the person's answer, 10-07). Objectives, number of fields, plane spacing and count, and tolerance are **decided by the person today after seeing the actual fields** (no proposed values).

Order: (1) choose objective and illumination → (2) in one field, focus by hand and read z0 (ZDrive) and XY → (3) with the knob, pass through the planes around z0, reading ZDrive and taking one Snap at each plane → (4) repeat in another field → (5) (optional) one field with no particles.

| Tolerance (DoF) µm | Objective | Reason for the choice | Who | When | Undecided □ |
|---|---|---|---|---|---|
| | | | | | |

| Objective | Illumination (light source, line, intensity) | Exposure ms | Readout mode | Number of fields | Plane spacing and count | Not measured □ |
|---|---|---|---|---|---|---|
| | | | | | | |

| Objective | Field # | Hand focus z0 µm | XY µm | Particles present / absent | Who | When |
|---|---|---|---|---|---|---|
| | | | | | | |

| Objective | Field # | Plane # | ZDrive µm | Frame file name |
|---|---|---|---|---|
| | | | | |

### ⑦ PFS offset direction (§7) — switching on and off by hand only, at the Ti2 panel

The three states were read on 10-13. Today, only the **direction**.
Focus on the interface → switch PFS on at the panel → confirm locked → turn PFSOffset a little with the panel knob → which way did the focal plane go, did the PFSOffset value increase or decrease → switch off at the panel → turn Z a little by hand and see that PFS does not follow.

| Item | Value | Method | Who | Not measured □ |
|---|---|---|---|---|
| Focal-plane direction as PFSOffset increases (toward the sample / away) | | | | |
| Difference between the focus Z with PFS on and the Z after switching off µm | | | | |
| After switching off, turning Z by hand is not followed | yes / no | | | |
| One property to trust as saying the servo has stopped (if any) | | | | |

### ⑧ The blanks in the camera maximum (§6) — the same value as SMA's

Fill in what is missing from the 10-13 value of 65535 ADU (`Dynamic Range` / `100MHz 16bit`). Do not write theoretical values (4095, 2^16−1). **Only the maximum seen.**
Switch the brightfield DiaLamp on by hand and raise the exposure to saturation → save a Snap → read **the Max in the image information** (not the histogram).

| Item | Kinetix_red | Kinetix_blue |
|---|---|---|
| Saturated-frame maximum ADU (image information Max) | | |
| Port / ReadoutRate (always together) | | |
| BitDepth / PixelType / Gain | | |
| Exposure ms, light | | |
| Saved file path | | |
| (Optional) mean ADU of a frame with the light off | | |
| (Optional) maximum on another Port | | |

### ⑨ CSUW1 shutter closed name (§8) — read only, do not select

Selecting a value in the dropdown moves the shutter. **Do not select.** Instead:
- open the Micro-Manager configuration file (.cfg) in Notepad and read the line of allowed `State` values for `CSUW1-Shutter`, or
- have the person close the shutter by hand on the CSU-W1 panel, then read `State` in the Device Property Browser.

| Closed name | Open name | Where read (cfg line / closed at the panel and read) | Who | Not measured □ |
|---|---|---|---|---|
| | `Open` (10-13) | | | |

### ⑩ Grounds for the margin on `focus_z_<lens>_max` (§10) — not written today

The current `_max` of 3300 µm is exactly the touching position. How much margin to leave, and changing safety.json, are **the person's to do**. This table only collects the grounds.

| Objective | ② interface Z µm | 3300 − interface Z µm | Margin the person wants µm (if decided) | Reason | Who |
|---|---|---|---|---|---|
| 4x | | | | | |
| 10x | | | | | |
| 20x | | | | | |
| 40x WI | | | | | |
| 60x Oil | | | | | |
| 100x Oil | | | | | |

### ⑪ (Optional) Checking the pixel size from the apparent size of the 5 µm particles (§5.6)

For each objective, measure the diameter of a few particles in pixels. Also write the particle diameter tolerance (manufacturer's label). A ruler slide is the right tool for an exact calibration — this is a rough check.

| Objective | Particle diameter px (several) | Manufacturer diameter and tolerance | µm/px (computed later) | Not measured □ |
|---|---|---|---|---|
| | | | | |

### ⑫ (If there is time) the short items left

| Item | Original section | Value | Not measured □ |
|---|---|---|---|
| Change in ZDrive and XY over 10 untouched minutes (start and end times and values) | §4.4 | | |
| The Z retract height the person wants for each objective, and why | §4.5 | | |
| Q20 — the distance at which the oil/water film starts to drag when XY is moved at focus height (100x / 60x / 40x WI) | §5.2 | | |
| Stage end values X+ / X− / Y+ / Y− (to check the person's statement of ±2 cm) | §4.3 | | |
| Focal-plane direction as piezo z increases (NanoBench, by hand) | §4.2 | | |

---

## 12. End

- Switch all light off by hand (Aura, LightEngine, DiaLamp, laser).
- Retract Z by hand (near 0). Wipe the oil objective. PFS off. **Write down which objective was left in place.**
- Read the §3 table once more and write it down as the end state (the end of the ⑫ drift).

| End state | Value |
|---|---|
| Objective | |
| ZDrive µm | |
| XY µm | |
| PFS | |
| Time | |

- Write down the items done / not done, odd readings, stops used, and saved file paths.
- Bring this filled-in file (or photos) to the Office computer. The record carries over only the values and files the person gave directly.
