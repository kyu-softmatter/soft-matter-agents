# Bench visit 1 (B-01) checklist — a day of measuring by hand only

> **Software moves nothing. Only hand actions (workplan 6.2 stop criterion 8).**
> Z, the stage, the objective turret, PFS and the laser are handled by the person, by hand only, at the Ti2 controller, joystick, Ti2 panel and vendor GUI.
> Do not use the dino app, `scripts/*`, SMA operator/orchestrator, or Micro-Manager's Multi-D Acquisition (Z stack) and stage-move buttons.
> In the Micro-Manager GUI, do **only reading (viewing properties) and camera Snap/Live**. Light is switched on and off by the person, by hand.

- Scope: B-01 in the workplan `docs/integration-sma-workplan.md` (the dino half). The SMA half (limits, refusal observation, first real abort,
  CSUW1 closed value, camera maximum count) is prepared separately by SMA's manager-microscope seat. The two halves avoid measuring the same value
  twice on the same day by the "box shared with SMA" marks in this document.
- Date: **2026-10-12 (Mon)**, half a day. Moved from the first date 2026-10-08 (Thu) (confirmed by the person with "yes" in the bench session window on 2026-10-09). Written 2026-10-05, against dino main `6802613`.
- Record: write values by hand in this checklist's boxes or photograph them, and after the visit pass them as they are to the bench session window.
  The bench session creates and fills `docs/runs/2026-10-12_bench-visit-1.md` and `.yaml` from the forms (`docs/runs/templates/`).
  Answers to the question cards go in `docs/librarian-handoff.md` §7.
- Every box gets **value / method / who / when**, or, if not measured, a mark at **"not measured"**. Do not fill an unmeasured value with a guess.
  "Who" is written as the person id (OD-6: the same handle as the approval name). Do not write emails or PC user names.

## 0. The locks stay as they are

- `mm_real.BENCH_MOTION = "LOCKED"` (`src/dino_autofocus/engine/backends/mm_real.py:89`, main 6802613).
- `guards.BENCH_APPROACH = "MEASURED"` (`src/dino_autofocus/engine/guards.py:95`; partly lifted 2026-10-02, 40x WI, 60x and 100x up to 2800 µm).
- Measuring Q13, Q20 and the stage range today does not lift the locks by itself. Only the person changes a lock, and not today.

## 0.1 Statements received in advance (2026-10-05; confirm on the visit day)

On 2026-10-05 the person said these in the merge-plan session window, and that session relayed them to this session. Until the person confirms them directly in this window they are
**relayed statements**, not measured values. Do not put them into code, guards or the envelope. On the visit day, confirm or correct them in the matching section.
On 2026-10-06 the person answered "yes" in the bench session window to S1–S6 and to the visit day 2026-10-08. That the statements are the person's is confirmed, but they are still **not measured values**, and the "Confirmation result" column below is filled from the visit-day measurements. The visit day was later changed to 2026-10-12 (the date line above).

| # | Statement (translated) | Card | Section to confirm on the visit day | Confirmation result |
|---|---|---|---|---|
| S1 | 40x WI working distance, correction collar 0.17: 170 µm | L-005 | 5.3 | |
| S2 | Retract before a long XY move: lower Z by 100 µm (Q20). The Q13 approach step was not answered separately | L-019 / L-018 | 5.2 / 5.1 | |
| S3 | Travel range: piezo 0–6000 µm, motorised stage ±2 cm. **The piezo needs confirming**: dino's provisional `PIEZO_RANGE_UM` is ±100 µm, and the KB's controller is NPC-6330, so 0–6000 may be a different unit or axis | L-023 / L-024 / L-094 | 4.3 / 4.2 | |
| S4 | Kinetix saturation: "2^16 이 포화 값" (2^16 is the saturation value) (16-bit readout; the person's exact words). On 9/30 it read as 12-bit. **Draw no number from this statement**: write only the maximum actually seen in a saturated frame, and do not assume 2^16 − 1 (the camera can saturate lower than that) | L-055 / L-056 | 6 | |
| S5 | PFS is controlled through Micro-Manager. Which property switches it off is still open. **On the visit day, still switch it on and off by hand at the Ti2 panel, and only read through the MM GUI** (B-01 is hand actions only) | L-062 / L-063 / OD-9 | 7 | |
| S6 | Tweez300 releases the camera (same as KB `tweez300_camera_is_released_so_it_shows_no_image` E5). As trap y decreases, the trap moves down in the camera image | L-090 / L-091 | 9 | |

## 1. How to stop (at any time)

| What | Where | Effect |
|---|---|---|
| Hardware stop | Ti2 controller / joystick at the stand | Always available. Use this if the screen does not respond |
| Let go | Joystick, focus knob | A hand-driven move stops when you let go |
| Light off | Light-source panel / shutter on the Ti2 panel | Turns off the light only |
| Laser off | Tweez300 vendor GUI / laser key | Handled by the person only |

If there is an odd sound, the oil or water film breaking, or a feeling that the objective touches the coverslip, stop on the spot and lower Z by hand (toward 0).

## 2. Checks before starting (nothing moves)

| # | Check | Result box |
|---|---|---|
| 2.1 | SMA operator / orchestrator is not running on the microscope PC (check Task Manager for `python` windows, and SMA terminals) | yes / no (→ stop) |
| 2.2 | No second Micro-Manager core: only one MM GUI; dino app server, Jupyter and scripts are off (two cores on one MM is a known failure, OD-13) | yes / no (→ stop) |
| 2.3 | The two configuration-file read checks (the `Select-String` line and the `check_load_settings` line in `docs/microscope-pc-checklist.md` "Real-instrument backend (T-033)"). Both only read the file | `OK` / `UnsafeConfig: ____` |
| 2.4 | (Optional) One open-and-close from runbook `first-bench-motion.md` Step 1. With the lock on, it cannot move anything. The resulting `notes["bench_motion"]` | `LOCKED` / other ____ |
| 2.5 | Does the configuration file's sha256 match `8184073e…3120` | same / different ____ |

**If `UnsafeConfig` appears, stop.** Do not open the MM GUI with that configuration; report the result to the bench session (the bench session passes it to the lead session).
Do not edit the check code to get past it.

## 3. Reading the starting state (Device Property Browser in the MM GUI, read only)

| Item | Value | Where read |
|---|---|---|
| Objective (Nosepiece State, label) | | Nosepiece `State`, `Label` |
| ZDrive position µm | | ZDrive `Position` or Ti2 panel |
| XY µm | | XYStage |
| PFS (on/off, `Out of Range`/`Within Range`/`Locked`) | | PFS properties |
| Light-source state (Aura State, LightEngine State, DiaLamp) | | each device |
| Piezo z µm (NanoBench, read only) | | vendor display |
| Time | | clock |

This reading is also the starting point of **3.Z drift**. At the end, read it once more in §9.

## 4. Z and the stage

### 4.1 ZDrive encoder sign (needed for check 86's z_drive ascending rule)

- What: when the focus knob is turned **toward the sample (the direction in which the objective approaches the coverslip)**, does the ZDrive value increase or decrease.
- Order: on 4x, with no sample or with Z low. Turn the knob a little toward the sample and watch the ZDrive value on the Ti2 panel / MM GUI.
- Related: L-013 (2026-09-05 prior measurement "larger is toward the sample"), a KB entry of the same shape as SMA's `PIEZO_Z_DIRECTION_ENTRY`.

| Value | increases / decreases | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|

### 4.2 Piezo Z direction

- What: as the piezo z value increases, does the focal plane move toward the sample. The person changes it a little with the NanoBench vendor program / knob and watches which way the image blurs.
  dino/SMA software does not command the piezo.
- Related: L-073, L-094.

| Value (z+ = toward the sample / away) | Amount changed µm | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|

### 4.3 Stage travel range (T-029d, Q12, L-023, L-024)

- First: **lower Z by hand to near 0, and put the 4x in place by hand** (runbook 2b). If an oil objective is up, wipe it.
- Order: with the joystick, slowly to the +X end, the −X end, the +Y end, the −Y end. Slow down before reaching an end. Read the XYStage value at each end.
  If going all the way to an end feels unsafe, write only an "at least this far" value (like Y ≥ 20498.8 on 2026-10-02).
- Whether the F5 step-out (+Y 15 mm) is within range is checked later by the person against these values. Today the app's F5 is not used.

| Axis and end | Read µm | Reached the end / at least | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|---|
| X + | | | | | | |
| X − | | | | | | |
| Y + | | | | | | |
| Y − | | | | | | |
| Time taken between the two farthest points s (optional, to check the 30 s wait value) | | | | | | |

### 4.4 Z drift without commands (L-067)

- What: how much ZDrive and XY change when nobody touches anything. Between the §3 reading and the §9 reading, leave out the time when things were touched.
  If possible, set aside one 10-minute stretch with nothing touched (start and end values).

| Stretch start time, Z, XY | End time, Z, XY | Touched in between? | Who | Not measured □ |
|---|---|---|---|---|

### 4.5 The Z retract height the person wants (L-015, `z_safe`)

- What: how far down the person wants Z before rotating an objective or making a long XY move. Per objective, if it differs by objective.
  This is not a measured value but a value the person decides. Write one line on why.

| Objective | Retract Z µm | Reason | Who | Undecided □ |
|---|---|---|---|---|

## 5. Approach per objective (by hand; oil and water objectives only on the person's judgement)

### 5.1 Q13 — 100x Oil approach step

- What: on 100x Oil, raise Z from 0 → 2800 µm in one go; above that, in steps of how many µm is it safe to go up? How long to wait between steps?
- Order: at 4x, Z 0 → rotate to 100x Oil by hand → oil → knob up to 2800 → above that, little by little with the fine knob, until focus (the glass interface) is seen.
  Also write how many µm one knob click is (the coarse/fine setting on the Ti2 panel).
- The current code's provisional value is 10 µm (`approach_step_um`, L-018). Do not call that value right; write what was seen today and the step the person will allow.

| Item | Value | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|
| One knob click µm (fine / coarse) | | | | | |
| Step µm used above 2800 | | | | | |
| Wait between steps s | | | | | |
| Maximum step the person will allow the software µm (OD-14, decided at U-02) | | | | | |
| Z µm at which the oil joined the objective and the coverslip (if seen) | | | | | |

### 5.2 Q20 — how far Z must be lowered before an XY move (immersion objectives)

- What: on 100x Oil (and 60x Oil, 40x WI if they can be used), moving XY with the joystick at focus height, from how many µm
  does the oil/water film drag, break, or form bubbles. For moves longer than that distance, Z must be lowered first.
- Order: at focus height, with the joystick, +X by 100 µm, 300 µm, 1 mm … increasing little by little. If a problem appears, stop and lower Z.
  If there is no problem, write "no problem up to at least ___ µm".
- The current code's provisional values: 100x 156, 60x 260, 40x WI 390 µm (L-019). Do not try to match them.

| Objective | Distance where a problem appeared µm / no problem up to at least µm | What was seen | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|---|
| 100x Oil | | | | | | |
| 60x Oil | | | | | | |
| 40x WI | | | | | | |

### 5.3 40x WI working distance, correction collar 0.17 (D-08, L-005, OD-21)

- What: the working distance of the 40x WI with the correction collar at 0.17 mm (objective front face to the objective-side face of the coverslip).
  Inside dino both 160 (`configs/ti2_40x.yaml:23`, `mock_world:133`) and 170 (guards) exist. **Write today's measured value as it is, and do not choose.**
- First, check again that the correction collar reads 0.17.
- The person chooses the method. Write the chosen method as it is. Examples:
  - (a) read the value on the objective barrel or spec sheet (a catalogue value, not a measured one; the catalogue gives only the range 0.16–0.20);
  - (b) put water on and focus on the sample-side face of the coverslip (the glass interface) → read Z_f; then, only if the person judges it safe, very slowly
    bring the objective front face to just before it touches the coverslip (where the shape of the water film changes) → read Z_c. Write the difference and what it means.
    Touching is not recommended. If unsure, do not do (b).
- Without this value the 40x WI stays not issuable, as OD-21 says. Not measured is also an answer.

| Correction collar reading | Z_f µm | Z_c µm (if done) | Working distance µm | Method (a/b/other) | Who | When | Not measured □ |
|---|---|---|---|---|---|---|---|

### 5.4 Glass-interface Z per objective and parfocal residual (L-033, input to 026 stage 1)

- What: on the same sample at the same XY, the ZDrive value at which each objective focuses on the coverslip glass interface. 4x in brightfield.
  Parfocal residual = each objective's interface Z − the 4x interface Z.
- Order: interface at 4x brightfield (DiaLamp by hand) → read Z. Lower Z, rotate the objective by hand (oil/water for immersion objectives), raise again to the interface → read Z.
  Before rotating an objective, always retract Z and switch PFS off (L-066).
- On 2026-09-30, 4x→100x was about −60 µm (once); the lab note says about −100 µm.

| Objective | Interface Z µm | Residual vs 4x µm | Light | XY | Who | When | Not measured □ |
|---|---|---|---|---|---|---|---|
| 4x | | 0 | brightfield | | | | |
| 10x | | | | | | | |
| 20x | | | | | | | |
| 40x WI | | | | | | | |
| 60x Oil | | | | | | | |
| 100x Oil | | | | | | | |

### 5.5 Through-focus curve per mode (input to OD-14)

- What: near the interface, move Z one step at a time **with the knob** and save one frame at a time with Snap in the MM GUI. One row per mode (brightfield / fluorescence / reflection etc.).
  MM's Z stack (Multi-D) is a software Z move, so do not use it.
- Write the save folder and the number of frames, the step µm, and the Z range. The curve is computed on the desktop after the visit.

| Objective | Mode, light | Z range µm | Step µm | Frames | Exposure ms | Save folder | Not measured □ |
|---|---|---|---|---|---|---|---|

### 5.6 1x1 pixel size (optional; only if L-031 was not closed by the 12 E2 items)

| Objective | µm/px | Method (ruler slide / compare stage move with image move) | Who | When | Not measured □ |
|---|---|---|---|---|---|

### 5.7 Shadow-mode evaluation — frames for comparing scores with hand focus (S-01, `docs/sma-shadow-mode.md` §7)

- What: frames for a first record of how well the classical metrics and DINO agree with the person's hand focus. **Scores are not computed at the bench.**
  They are computed on the desktop after the visit, from the saved frames.
- Only the person handles the equipment. Light is switched on by hand, Z moves only with the focus knob, and frames are saved one at a time with Snap in the MM GUI.
  MM's Z stack (Multi-D) is not used. If the frames can be shared with 5.5, write so.
- **Boxes the person decides (no proposed values):** the list of objectives, the number of fields, and the spacing and number of planes around z0 are decided by the person on **10-12 (Mon)**
  (the person's words on 2026-10-07, relayed by the merge-plan session). Whether to do this evaluation on that visit is also the person's call. This checklist sets no numbers.
- **Tolerance (depth of field, DoF):** **decided by the person at the bench** after seeing the actual fields (the person's words on 2026-10-07, relayed by the merge-plan session).

| Tolerance (DoF) µm — decided by the person at the bench | Objective | Reason for the choice | Who | When | Undecided □ |
|---|---|---|---|---|---|
- Order: (1) choose the objective and illumination → (2) in one field, focus by hand and read that ZDrive (z0) and XY →
  (3) with the knob, pass through the planes around z0 in turn, reading ZDrive and saving one Snap at each plane → (4) repeat (2)–(3) in another field →
  (5) (optional) one field with no sample.

Per objective:

| Objective | Illumination setting (light source, line, intensity) | Exposure ms | Readout mode (Port + ReadoutRate) | Number of fields (decided by the person) | Plane spacing and count (decided by the person) | Not measured □ |
|---|---|---|---|---|---|---|

Per field:

| Objective | Field # | Hand focus z0 (ZDrive µm) | XY µm | Sample present / absent | Who | When |
|---|---|---|---|---|---|---|

Per plane:

| Objective | Field # | Plane # | ZDrive µm | Frame file name |
|---|---|---|---|---|

## 6. Camera — Kinetix_red bit depth (D-08, L-055, L-056, L-052 conflict card §4 item 2)

- What: the maximum value of one saturated frame. 12-bit (`engine/backend.py` comment, 9/30) and 16-bit (10/02 property read) conflict. The only value recorded is **the maximum actually seen**. Do not assume or write theoretical values such as 4095 or 2^16 − 1.
- Order: Live/Snap Kinetix_red in the MM GUI. Switch the light on by hand (brightfield DiaLamp is easiest) and raise the exposure until the histogram sits against the right-hand end.
  Save one Snap, and read that frame's **maximum** and the camera properties `Port`, `ReadoutRate`, `BitDepth`, `PixelType`, `Gain`, and the exposure.
  If possible, change `Port` (Dynamic Range / Sensitivity / Speed / Sub-Electron) and read the allowed `ReadoutRate` values for each (which Port gives 9/30's `100MHz 12bit`).
- **Box shared with SMA**: SMA's "camera full-scale count" is this maximum. Measure once and use the same value on both sides.
- Also (optional): the mean of a dark frame (light off) — dark offset L-057 (9/30 about 102 ADU, property `Offset = 100`).

| Item | Value | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|
| Saturated-frame maximum ADU | | | | | |
| **That frame's readout mode (Port + ReadoutRate)** — always write it together with the maximum (SMA's blanks are separate per readout mode) | | | | | |
| Port / ReadoutRate / BitDepth / PixelType / Gain | | | | | |
| (Optional) if also saturated on another Port, the maximum per Port | | | | | |
| Exposure ms, light | | | | | |
| Allowed ReadoutRate values per Port | | | | | |
| Saved file path | | | | | |
| Dark-frame mean ADU (optional) | | | | | |

## 7. PFS release path (OD-9, L-062, L-063, L-064, L-065)

- What: when an engaged PFS is switched off, which property tells you the servo has stopped. **Switching it on and off is by hand only, at the Ti2 panel (or the PFS button).**
  Software (`enableContinuousFocus`) neither switches it on nor off. The person only reads the properties and status text before and after.
- Order:
  1. With it off, read all PFS properties ("before" below).
  2. Focus on the interface → switch PFS on at the Ti2 panel → confirm it is locked (Locked/Within Range) → read all properties ("on").
  3. Turn PFSOffset a little with the panel knob, and note whether the focal plane moved toward the sample or away, and whether the PFSOffset value increased or decreased ("sign").
  4. Switch PFS off at the Ti2 panel → read all properties ("after"). Turn Z a little by hand and see that PFS does not follow.
- Properties to read: `the whole PFS device in the MM GUI` — in particular the status text (`Out of Range` etc.), `FocusMaintenance`, `DichroicMirrorInserted`, `LEDIntensity`,
  `PFSOffset`, and Core's `isContinuousFocusEnabled` / `isContinuousFocusLocked` indicators (the Autofocus window in the MM GUI).

| Point | Status text | FocusMaintenance | ContinuousFocus enabled / locked | PFSOffset | Other | Time |
|---|---|---|---|---|---|---|
| before | | | | | | |
| on | | | | | | |
| after | | | | | | |

| Item | Value | Method | Who | Not measured □ |
|---|---|---|---|---|
| One property to trust as saying the servo has stopped (if any) | | | | |
| Focal-plane direction for PFSOffset + | | | | |
| After switching off, turning Z by hand is not followed | yes / no | | | |

## 8. Light path and light-source follow-ups (the three follow-ups from 2026-10-02)

| Item | What to look at | Value | Not measured □ |
|---|---|---|---|
| `Core.Focus` is empty (L-029) | MM GUI Configuration → whether Core `Focus` is an empty value | | |
| CSUW1-Port state number (L-044) | Set it to 0 / 1 / 2 on the CSU-W1 panel and see whether light reaches the blue/red camera in each: does it match the note 0 blue_only, 1 blue_red, 2 red_only | | |
| CSUW1 shutter closed value (**box shared with SMA**) | The value the device shows when the CSU-W1 shutter is closed | | |
| LappMainBranch1 State 1 = 50/50 mirror (L-043) | Panel / device display | | |
| Aura flicker (L-051, −23% frames) | Switch one Aura line on by hand, save about 20 Snaps from Live, and give the fraction of frames with low mean brightness | | |
| Readout delay per step (T-029d) | Time (roughly) after a hand turn until the ZDrive value on the panel and in the MM GUI stops. If a software move would be needed, not measured | | |

## 9. Tweez300 — camera body and trap y sign (OD-11, L-090, L-091, L-095, L-096)

- **The laser and its power are handled by the person only. This checklist does not set a power value.** dino/SMA software does not switch the laser on.
- Order:
  1. When the Tweez300 GUI is opened, which camera becomes unusable in MM, and the serial number shown in the GUI's camera settings
     (A24M723015 = Kinetix_red, A23H723003 = Kinetix_blue). The MM label of the camera imaging the trap plane.
  2. At a power the person chose, move one trap in the vendor GUI (0,0) → +x → +y and see where the trap goes on both camera screens.
  3. Does the GUI have trap Z control (if so, the name only; it need not be moved).

| Item | Value | Method | Who | When | Not measured □ |
|---|---|---|---|---|---|
| Camera serial number / MM label held by Tweez300 | | | | | |
| MM label of the camera imaging the trap plane | | | | | |
| Is (0,0) the centre of the screen | | | | | |
| Is +x to the right of the screen (red / blue camera each) | | | | | |
| **Is +y up or down on the screen** (red / blue each) | | | | | |
| Trap Z control present / absent, name | | | | | |
| Objective used | | | | | |

## 10. U-03 preparation — the 12 SMA envelope keys `focus_z_<lens>_{min,max}` (not written today)

- These 12 are written later by the person directly (U-03, week 2) into SMA `microscope_agent/envelope/safety.json`. Today this table is the place to collect the grounds for writing them then.
  The bench session proposes no values, and does not carry dino's 2800–3200 / 0 / 10 / 0.25 into these boxes.
- Meaning (SMA `contracts/schemas/envelope_safety.schema.json:370-415`): `_min` is the lowest encoder Z the focus search may go to;
  `_max` is **the encoder Z at which that objective may come closest to the coverslip**. Both are fixed numbers the person writes, not computed from a measured value + working distance.
  Without a key, every search on that objective is refused. To free a dry objective, **write a wide value** (not a missing key).
- Each limit needs its own confirmation record `{kind, by, on, how}`: `kind` is `physical` (confirmed by hand, as today) or `carried_over` (carried over from another document).
  `how` is what was actually done (10 characters or more), not "confirmed".
- If the encoder sign from 4.1 comes out reversed, the person re-examines the relation between `_max` and "closest".

| Key | Today's grounds (5.4 interface Z, 5.3 working distance, 4.5 retract, etc.) | kind | how (what was done) | by | on |
|---|---|---|---|---|---|
| focus_z_4x_min | | | | | |
| focus_z_4x_max | | | | | |
| focus_z_10x_min | | | | | |
| focus_z_10x_max | | | | | |
| focus_z_20x_min | | | | | |
| focus_z_20x_max | | | | | |
| focus_z_40x_min | | | | | |
| focus_z_40x_max | | | | | |
| focus_z_60x_min | | | | | |
| focus_z_60x_max | | | | | |
| focus_z_100x_min | | | | | |
| focus_z_100x_max | | | | | |

## 11. G-05b — the SMA copy on the microscope PC, `D:\soft-matter-agents` (read only)

The person (or the manager seat on that PC) reads these in PowerShell. **Today nobody commits or pushes from this copy (6.2 #3).**

| Command | Result |
|---|---|
| `git -C D:\soft-matter-agents rev-parse HEAD` | |
| `git -C D:\soft-matter-agents status -sb` (behind/ahead) | |
| `git -C D:\soft-matter-agents fetch --dry-run` (optional) | |
| `git -C D:\soft-matter-agents config core.hooksPath` | If empty → record that SMA commits from that copy are forbidden |
| `Get-Command sh` (sh on PATH) | |
| `python --version` / `Get-Command python` | |
| (Optional) `git -C D:\soft-matter-agents var GIT_COMMITTER_IDENT` — the name part only; do not write the email | If it is not a seat → record that commits are forbidden |

Write the push method down as text only: `git -c credential.helper=manager push`. Do not run it today.

## 12. End of the visit

- Light: switch everything off by hand. Aura State 0, LightEngine off, DiaLamp off, laser off.
- Retract Z by hand (near 0). Wipe the oil objective. PFS off.
- Read the §3 table once more and write it down as the end state (the end of the 4.4 drift).
- To write down (runbook "After the session"): items done and not done, odd readings, stops used, saved file paths.
- Pass the values to the bench session window: a photo path of these tables, or text. The bench session records **only values and files the person gave directly in this window**.

## 13. Link to decision bundle B (U-02, about 45 minutes after the visit)

| OD | Section of this checklist |
|---|---|
| OD-9 PFS release path | 7 |
| OD-11 trap Z, camera body | 9 |
| OD-14 threshold and sweep range, step cap | 5.1, 5.5, 5.7 |
| OD-17 source instead of grade | "Method" in every box (measured by hand / read from the device / catalogue / decided by the person) |
| OD-21 first focus objective and per-objective Z limits | 5.3, 5.4, 4.5, 10 |
| OD-22 20 items before copying + four conflicts | 5.3 (L-005), 5.6 (L-031), 6 (L-056), 8 (L-052 replaced by checking the filter name) — answer rows in `docs/librarian-handoff.md` §7 |
