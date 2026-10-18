# Librarian handoff list: dino-autofocus bench numbers and facts (question cards)

## 1. Purpose and basis

- Purpose: gather in one place every physical and bench number and fact the librarian must receive when dino-autofocus is merged into soft-matter-agents' `microscope_agent` (in about 3 weeks).
  Each line is one card that asks the user: **is it a value a person wrote or measured, and when and how.**
- soft-matter-agents rule (plan.md §10.3): numbers from another repository go only as entries through the librarian, at most E3. Safety limits do not cross as numbers
  (a person writes them directly into `envelope/safety.json`). A number a model produced is E6 and does not enter a card.
- Written: 2026-10-02; updated 2026-10-03 (workplan L-01: line numbers and KB column re-pinned, §2.9, §5). Read-only survey.
  Nothing in soft-matter-agents was changed.
- 2026-10-03 (D-02): the numbers of `focus/classical.py`, `focus/verdict.py`, `ops/focus_100x.py` and the map calibration values in the table below now
  live in one place, `src/dino_autofocus/bench_values.py`, and the flat files (`microscope_agent/src/*.py`) take those values **as arguments**.
  file:line was re-pinned in L-01 (2026-10-03) (base commit below). `tests/test_sma_shape.py` fails if such
  numbers come back into the flat files.
- Base commits (2026-10-03, re-pinned in L-01; the 2026-10-02 edition was based on dino `025080f` and SMA `baf6f1e`):
  - dino-autofocus `2e8109f` (tip of branch `merge-plan/D-03-provenance-headers`; includes D-02, D-01, D-07, D-03; working tree clean).
    **Every file:line below is against this commit** (`git show 2e8109f:<path>`). Numbers that left the flat files in D-02 point at lines of `bench_values`,
    and structural constants left in the flat files point at lines of `flat/<file>` (the first three lines of a flat file are the D-03 provenance header, so line numbers are shifted by 3).
    Of the 244 line numbers in the 2026-10-02 edition, 64 shifted and 18 were re-pointed by hand because the file moved; the line numbers of `BL` are from the internal
    repository and are left as they are.
  - soft-matter-agents `b346c02d5de14e23a3036b92e0245b8b68c0fd6d` (origin/main HEAD, working tree clean; the quoted lines of `safety`, `rulings`,
    `plan.md` and `devices.v0` are at the same place in this commit too). The librarian store holds `librarian_agent/kb/entries/*.json`
    **309 (kbv-70754d3df50b)**. microscope_agent's copy `envelope/snapshot.json` holds **297 entries (kbv-a0f093a66393,
    built_from_commit `21ca509`, commit 1a9d05e 2026-10-01)**, 12 entries behind the KB — `librarian_agent/kb/exports/
    snapshot_microscope_agent.json` is already kbv-70754d3df50b (309, built_from `1c66f91`) but has not been copied
    into `envelope/`. The 12 behind: 8 `bangs_*` (particle specs), `csuw1_disk_speed_is_not_exposed_here`,
    `lunf_blanking_lines_reservable_right_after_nis_kill`, `mm_config_load_did_not_return_after_nis_force_kill`,
    `optical_tweezers_work_with_40x_60x_100x_person_statement` (L-095). In the "in soft-matter-agents?" column below, `(S)` means also in the envelope snapshot
    (kbv-a0f093a66393), `(KB)` means only in the store (kbv-70754d3df50b). Entries that were `(KB)` in the 2026-10-02 edition are all
    in the snapshot now and were changed to `(S)`; none of the cited entries' grades changed, and the five cited gaps
    (`objective_40x_wd_at_170um`, `kinetix_red_bit_depth`, `pfs_offset_sign_unmeasured`, `camera_exposure_grid`,
    `lapp_branch_assignment`) are all still open (unchanged in `devices.v0` and in the export's tables).
- "Already there?" column: `present` same value, `partial` only part of it present, `conflict` value or source differs, `absent`. Entry ids and grades are given.
- `[envelope]` mark: safety limits and guard values. Not sent to the librarian as numbers (§3). The card is kept to ask "who set it".
- Source abbreviations: `guards` = src/dino_autofocus/engine/guards.py, `backend` = engine/backend.py, `mm_real`/`mm_demo`/`mm_demo_core`/`mock`/`mock_world` = engine/backends/*.py,
  `ops/*` = engine/operations/*.py, `bench_values` = src/dino_autofocus/bench_values.py (where the numbers gathered after D-02),
  `flat/<file>` = microscope_agent/src/<file> (flat files), `patterns` = engine/patterns.py, `tweez300` = engine/backends/tweez300.py,
  `scr/tweezers`·`scr/patterns` = console/docs/screens/{tweezers,patterns}.md, `web/tweezers.test` = console/web/src/features/tweezers/tweezers.test.tsx,
  `chk` = docs/microscope-pc-checklist.md, `run930y` = docs/runs/2026-09-30_substrate-scan.yaml,
  `run930m` = docs/runs/2026-09-30_substrate-scan.md, `bp1002` = docs/runs/2026-10-02_bench-properties.json,
  `cfg1` = configs/micromanager/single_cam_red_noDMD_nocom10.cfg, `cfg2` = configs/micromanager/DMD_dualcam_LUNF.cfg,
  `BL` = BACKLOG.md (from 2026-10-02 the internal note `dino-autofocus-internal/tasks/BACKLOG.md`). SMA side: `safety` = microscope_agent/envelope/safety.json, `devices.v0` = librarian_agent/kb/staging/devices.v0.json,
  `rulings` = microscope_agent/rulings.jsonl.

## 2. Question cards

### 2.1 Objectives and working distance

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-001 | Nosepiece State → Label (6 read at the bench) | 0 `1-Plan Apo LmbdD20 4x`, 1 `2-Plan Apo LmbdD4 10x`, 2 `3-Plan Apo LmbdD0.8 20x`, 3 `4-Apo LmbdS 40x WI`, 4 `5-Plan Apo LmbdD0.15 60x Oil`, 5 `6-Plan Apo LmbdD0.13 100x Oil` | bp1002:179; cfg1:178-183 | device read 2026-10-02 (the label strings are set by the cfg) | partial: `nosepiece_objective_assignment` E3 (S, by part number), `stand_state_read_20260924_20x_in_place` E1 (KB, label of position 2 only) | Did a person look at the objectives and confirm that the six labels match the actual objective at each position? (Is it the same as the 9/17 part-number check?) |
| L-002 | 4x free working distance | 20000 um | guards:68; mm_real:104; configs/ti2_4x.yaml:23; run930y:22 | catalogue (guards:64 says "2026-09-30 run") | present: `objective_mrd70040` E3 (S), 20 mm | Is the 20 mm in the 9/30 record copied from the catalogue, or measured at the bench? |
| L-003 | 10x free working distance | 4000 um | guards:68; mm_real:104; ti2_10x.yaml:23; chk:158 | catalogue; the librarian's E3 read directly from its files on 2026-10-02 (chk:152-153) | present: `objective_mrd70170` E3 (S) | If it was never measured at the bench, there is nothing new to hand over. Right? |
| L-004 | 20x free working distance | 800 um | guards:68; mm_real:104; ti2_20x.yaml:23; chk:159 | catalogue (same as above) | present: `objective_mrd70270` E3 (S) | Same as above |
| L-005 | 40x WI free working distance | 170 um (0.17 mm) | guards:65-68; mm_real:103-104; mm_demo:81; chk:160; commit d239448 "(user)" | user value 2026-10-02. Grounds written down: "collar at 0.17; catalog range 0.16-0.20 mm, value at that collar not in the catalog" | **conflict**: `objective_mrd77400` E3 (S) gives a range of 0.16–0.2 mm, `devices.v0` wd_mm is null, gap `objective_40x_wd_at_170um` open. `safety:49-65` `objective_clearance_min` uses the near end, 0.16 mm, when a range is given | Is 0.17 mm a measured working distance, or the collar mark 0.17 mm (coverslip thickness 170 um) carried over as a working distance? If measured, the date and method |
| L-006 | 60x Oil free working distance | 150 um | guards:68; mm_real:104; ti2_60x.yaml:23; chk:161 | catalogue | present: `objective_mrd71670` E3 (S) | Is it right that there is no bench measurement? |
| L-007 | 100x Oil free working distance | 130 um | guards:68; mm_real:104; ti2_100x.yaml:23; run930y:22; run930m:134 | catalogue (also as a setting in the 9/30 record) | present: `objective_mrd71970` E3 (S). The same number is `safety:66-77` `objective_clearance_absolute_min` 130 um, confirmation physical "Approach test on the stage" (2026-09-20) | Is the 130 um in the 9/30 record the catalogue value? Is it the same measurement as the approach test in safety.json? |
| L-008 | NA, magnification and immersion per objective | 4x 0.2 air, 10x 0.45 air, 20x 0.8 air, 40x 1.25 water, 60x 1.42 oil, 100x 1.45 oil | configs/ti2_*.yaml:1,19-21 | catalogue (the yaml header cites librarian entries as the source) | present: `objective_mrd70040`, `_mrd70170`, `_mrd70270`, `_mrd77400`, `_mrd71670`, `_mrd71970` E3 (S) | Nothing new to hand over. Confirm only |
| L-009 | coverslip thickness | 170 um (#1.5) | ti2_*.yaml:3,45; mock_world:239 | lab practice | present: `coverslip_thickness_in_use` E3 (S) | Same value. Confirm only |
| L-010 | 40x WI correction collar re-check | still at 0.17 mm | chk:181-184 | user check 2026-10-02 | present: `objective_40x_collar_setting` E3 (S, read 2026-09-22) | Should the 2026-10-02 re-check go to the librarian as a new observation (same person, another day)? Was it seen by eye? |
| L-011 | refractive index of the immersion media | oil 1.518, water 1.333, glass 1.515, sample 1.33 | ti2_*.yaml:21,40-44 | design value (not measured) | partial: `water_refractive_index_*` E3 (S). No oil entry | Does the oil refractive index come from the label on the oil bottle? (If you give the bottle/lot, it is a candidate spec entry) |
| L-012 | Nosepiece position → objective key | 0 4x, 1 10x, 2 20x, 3 40x-WI, 4 60x-Oil, 5 100x-Oil (from 0) | ops/objective_change.py:74-76 | from the configs header | present: `nosepiece_position_indexing`, `nosepiece_objective_assignment` E3 (S) | Confirm only |

### 2.2 Stage, Z and XY limits and directions

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-013 | ZDrive direction | larger is toward the sample, 0 = fully retracted | backend:6; run930y:3; run930m:133 ("measured 2026-09-05") | measured 2026-09-05 (prior project) | present: `z_retract_direction_is_measured` E3 (S). plan.md:1506 notes that these are two records of the same 2026-09-05 measurement, so the grade was not raised | Has this direction been measured again since 2026-09-05? (If so, an E1 candidate) |
| L-014 | [envelope] sample Z window | 2800–3200 um | guards:61; run930y:21; run930m:134 | the code comment says "measured window of the 2026-09-30 bench", but it is really the script constant `SAMPLE_Z_WINDOW_UM` | absent (safety.json has no ZDrive position key, docs/integration-sma.md:13) | Who set this window? Was it measured on some sample, or is it policy? (a value a person writes into the envelope) |
| L-015 | [envelope] retract height / return height | z_safe 0 um / return 2800 um | guards:62,72-73; run930y:109 | unmeasured provisional (chk:63, Q20) | absent | Are the retract to 0 um and the single 0→2800 move a procedure a person set? |
| L-016 | [envelope] upper bound for judging "Z retracted" | 1 um (z_safe + 1) | guards:74 | provisional | absent | Can you set it as an envelope value? |
| L-017 | [envelope] sweep ceiling ratio | centre + 0.4 × free working distance, at most 3200 | guards:10-11,63; run930m:101-102 | prior project script rule | absent (`rulings:23` drops the prior's free_working_distance_um) | Who set the 0.4 ratio? |
| L-018 | [envelope] stepped-approach step | 10 um for every objective (about 1/13 of WD for 100x Oil) | guards:138-147; chk:65 | provisional, Q13 unmeasured | absent | Was Q13 measured? Or is it a value to write directly into the envelope? |
| L-019 | [envelope] XY move length that requires a Z retract | 4x 10000, 10x 1000, 20x 777, 40x-WI 390, 60x-Oil 260, 100x-Oil 156 um; unknown objective 0 | guards:133-149 | provisional, computed from the field of view (2400 px × pixel), Q20 unmeasured | absent | Was Q20 (the oil film) measured? Is this table a value a person writes into the envelope? |
| L-020 | [envelope] XY box margin | 1000 um | guards:70 | the manager's temporary value | absent | Keep it as a policy value? |
| L-021 | [envelope] readback tolerance | Z 0.25 um, XY 5.0 um. Device settings: ZDrive Tolerance `0.000um`, XYStage Tolerance `0.000um` | guards:121-122; bp1002:59,128 | temporary value (Q2). Device values read 2026-10-02 | absent | Who set 0.25 / 5 um? Should the device Tolerance reading go to the librarian as a fact entry? |
| L-022 | [envelope] F5 Y move-away | +Y, 15000 um | guards:75-76; docs/PLAN.md:22,304-305; docs/operations-spec.md:412 | user (PLAN v1.3, the shorter end of 15–20 mm), provisional | absent | Is +Y 15 mm an envelope policy value? Should the single run on 2026-10-02 (L-026) go over as a measurement record? |
| L-023 | lower bound of the stage Y travel range | ≥ 20498.8 um | chk:176; BL:56-57 | measured 2026-10-02 (read after a +Y 15 mm move) | absent (chk:148 "the librarian store has no value either") | Hand this reading over as an observation that "Y goes at least this far"? Not used as a limit (`rulings:71`: a travel range used as a limit is a safety limit) |
| L-024 | Can the stage X/Y limits be read as properties? | not readable (XYStage and ZDrive have only Speed, Tolerance, Invert/Transpose) | chk:148; BL:57; mm_real:117,375 | device read 2026-10-02 | absent | Hand it over as a fact entry? Do the real limits have to be measured with Ti2 Control or by hand? |
| L-025 | move speed setting | XYStage 25.00 mm/sec (allowed 0.25–51.00), ZDrive 2.50 mm/sec (allowed 0.50–2.50) | bp1002:41,110; chk:177 | device read 2026-10-02 | absent | Who set these speeds (Ti2 Control, default)? |
| L-026 | result of one F5 move-away | before X −5134.4 Y 5498.9 Z 483.62 → after X −5134.6 Y 20498.8 Z −0.08 um; XY readback within 5 um; within 30 s (25 mm/s) | chk:166-178 | measured 2026-10-02, a one-off script calling core directly | absent | Did you actually watch this move? Hand it to the librarian as observation entries (XY readback error, Z 0 command → −0.08)? |
| L-027 | [envelope] XY move wait time | 30 s | mm_real:105 | provisional | absent | Was the time of the longest move measured? |
| L-028 | orientation of the image relative to the stage | the image is flipped relative to the stage: +x stage → +column, columns −x, rows toward +y. XYStage Invert-X/Y `No`, TransposeMirrorX/Y `0`; camera Transpose all `0` | run930m:54-56; mock_world:14-16; flat/map_geometry.py:6-11; flat/map_mosaic.py:11-15; bp1002:88,147,1629 | measured 2026-09-30 (edge tracker calibration) + device read 2026-10-02 | absent | Candidate librarian fact entry. Is it right that the basis is a single 9/30 calibration? |
| L-029 | Core role devices | Core.Focus empty (`getFocusDevice()` = ""), Core.AutoFocus `PFS`, Core.XYStage `XYStage` | bp1002:2371-2373; chk:130-131,146; BL:58-59 | device read 2026-10-02 | partial: `mm_label_zdrive_is_the_focus_axis` E3 (S, ZDrive is the focus axis in the prior project cfg) | Core.Focus being empty is a new fact. Hand it over? |
| L-030 | sample size and the 24 mm side | usually 24 mm × 50 mm; orientation of the 24 mm side unmeasured | docs/PLAN.md:83,121; mock_world:236 | written as needing user confirmation | absent | Is 24 × 50 mm a value the user stated? What is the sample type (slide part number)? |

### 2.3 Calibration (pixel size, 4x M, parfocal offset)

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-031 | pixel size per objective (1x intermediate magnification, 1x1 binning) | 4x 1.625, 10x 0.65, 20x 0.32373, 40x 0.1625, 60x 0.10833, 100x 0.065 um/px | cfg1:274-308; ti2_*.yaml:7; mm_real:102 (0 and 5 only) | cfg1:294-296 comment: "Only 20x is a measurement. The other five are exactly 6.5/M" | **value present, source conflict**: `pixel_size_*_zoom_1x` E2 (S) has all six as "measured by the operator" (calibration `cal-pixel-size-20260919`). `*_computed` E4 (S) also present | In the 2026-09-19 calibration, were all six objectives measured, or only 20x? (the cfg comment and the librarian differ) |
| L-032 | 4x stage–camera calibration | 1.62524 um/px, 0.117 deg, `M_px_per_um = [[0.61602, 0.00236], [0.00126, -0.61456]]` | run930y:51-55; run930m:53; bench_values:70-74; bench_values:70-72; ops/edge_trace.py:113-118; mock_world:163-165 | measured 2026-09-30 (edge tracker, +x/+y moves and phase correlation) | absent (the librarian has only 1.625 E2; difference 0.015 %) | Did you run this calibration yourself on 9/30? Hand it to the librarian as a measurement separate from the E2? |
| L-033 | parfocal offset 4x → 100x Oil | ≈ −60 um (2026-09-30, one sample). A lab note of 2026-09-07 says about −100 um | bench_values:56; run930y:123,155; run930m:21,154; docs/operations-spec.md:790; chk:109 | measured once, provisional | absent (0 hits for `parfocal`) | Is −60 um the difference between the two focus z values of 9/30 (3048.7 vs 2989.4)? Who wrote the 2026-09-07 note? |
| L-034 | intermediate magnification | `1.0x` (read-only property, allowed 1.0x/1.5x). The pixel presets assume 1x | bp1002:487; cfg1:281-285 | device read 2026-10-02 | present: `intermediate_magnification_is_not_a_state_device` E1 (S); devices.v0 values 1x/1.5x | Confirm only |
| L-035 | camera pixel pitch and sensor | 6.5 um, 2400 × 2400 | mock_world:63; ti2_*.yaml:26; bp1002:1699 | datasheet + device read | present: `camera_sensor_geometry` E3 (S) | Confirm only |
| L-036 | 20x actual magnification | 20.0785 (= 6.5 / 0.32373) | ti2_20x.yaml:20; mock_world:132 | computed (back-derived from the pixel size) | absent, and devices.v0 deliberately has no numeric magnification field ("prior project's 20.078x") | Recommend not sending it (§3). Do you agree? |
| L-037 | 4x focus repeatability | 0.4–3.4 um between two scans, against a 4x depth of focus of about 14 um | run930y:101; run930m:84 | measured 2026-09-30 | absent | Hand it to the librarian as an observation entry? |

### 2.4 Light sources and light path (Aura lines, LApp Branch1, CSUW1-Port)

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-038 | Aura device and lines | `Aura III 5-NII-WA`, COM7, s/n 30859, fw 3.14.7; lines UV, CYAN, GREEN, RED, NIR (on/off 0–1, `<LINE>_Intensity` 0–1000). No VIOLET | bp1002:1718-1873; backend:307-310; cfg1:34-36; chk:144 | device read 2026-10-02 (cfg header 2026-09-03) | present: `aura_reports_five_named_lines` E1 (S), `mm_label_aura_is_the_aura_iii` E3 (S), `aura_green_intensity_runs_to_1000` E1 (S) | Same value. Confirm only |
| L-039 | intensity unit | per-mille: 1 % → `GREEN_Intensity 10` | backend:11-12; run930y:45-47; mm_real:580 | 9/30 setting | present: `light_engine_line_intensity_is_per_mille` E3 (S) | Confirm only |
| L-040 | lines used at the bench | GREEN only (9/30: GREEN 1 %, DiaLamp 0 → GREEN_Intensity 10 → GREEN 1 → State 1) | mm_real:100; mm_demo:77; mock:61; backend:307-309; run930y:44-49 | used 9/30 | partial: `particles_show_on_the_green_605_path` E2 (S) | Have you ever switched on the other lines (UV, CYAN, RED, NIR)? |
| L-041 | with Aura State 0 every line is off (Q10) | yes | chk:186-191 | user answer 2026-10-02 | present: `aura_master_state_0_keeps_green_dark` E1 (S), `light_engine_master_state_gates_every_line` E3 (S) | Was it seen by eye or in frames? Did you check lines other than GREEN? |
| L-042 | LightEngine (the other Lumencor) | `Spectra III 8-NII-XS`, COM3, s/n 28145, fw 3.5.4; lines VIOLET BLUE CYAN TEAL GREEN YELLOW RED NIR. The cfg sets Core.Shutter = LightEngine, AutoShutter 1 | bp1002:565-742; cfg1:32-33,170-172; chk:127,145 | device read 2026-10-02 | present: `mm_label_lightengine_is_the_spectra_iii` E3 (S), `single_cam_red_config_arms_autoshutter_on_the_lightengine` E1 (S). gap `light_engine_channel_sets` open (this read gives the list of line names; not the wavelengths) | Hand over the 8 names read from the device as a partial answer to gap `light_engine_channel_sets`? |
| L-043 | LappMainBranch1 | State 1 = `mirror_in` = Aura path on, **50/50 mirror**; State 0 = `mirror_out`. The cfg Startup sets State 1 | chk:197-199,206-207; cfg1:212-213,261; bp1002:501-508 | user note 2026-10-02 (50/50 is a new fact) | partial: `lapp_state_1_brings_the_aura_to_the_sample` E3 (S), `single_cam_red_config_startup_puts_the_lapp_mirror_in` E1 (S). gap `lapp_branch_assignment` open | Was the 50/50 mirror confirmed by looking at it or from documents, or is it memory? |
| L-044 | CSUW1-Port state numbers | 0 `blue_only` (100/0 mirror), 1 `blue_red` (561 nm dichroic, split by wavelength), 2 `red_only` (no mirror) | chk:200-205,210; BL:60-63; cfg2:204-207,257,263 | user note 2026-10-02 + cfg2 Label lines (cfg2:257 calls State 1 "operator-stated 2026-09-05") | **partial (fills a gap)**: `csuw1_port_slots` E3 (S) gives only the contents of the three slots, "which physical slot is at which position number is not known". devices.v0 gap "csuw1_port slot order" open, "One acquisition settles it" | Were these numbers confirmed by an acquisition (light on, and which camera gets a signal in each of the three states), or only by the note and the cfg labels? |
| L-045 | the single-camera cfg has no CSU-W1 device | the port stays at the previous session's value; at State 0 no light reaches Kinetix_red (no error) | chk:211-212; BL:60-61 | inference from reading the cfg | absent | Hand it over as a fact entry (hazard notice)? |
| L-046 | DMD_dualcam_LUNF.cfg | Startup: LappMainBranch1 1, CSUW1-Port 1. Cannot be loaded in this install because of `MightexPolygon1000` (device API v71) | chk:208-210; cfg2:8,255,263; cfg1:6-15 | cfg copy + attempt 2026-10-02 | partial: devices.v0 dmd row `automatable_condition: core_requirement` | Confirm only |
| L-047 | DiaLamp intensity | 608 / 2100 (set at the stand) | bp1002:533-540; run930y:40; run930m:51; mock_world:204; mock:60 | used 9/30, same value read 2026-10-02 | absent | Who set 608, and when? |
| L-048 | brightfield light path | 9/30: CondenserTurret `3-`, LightPath `4-L100`. Read 2026-10-02: Condenser `1-ND` (State 0), LightPath `4-L100` (State 3) | run930y:41-42; run930m:135; bp1002:212-219,376-383 | 9/30 record + device read | partial: `stand_state_read_20260924_20x_in_place` E1 (KB, LightPath 4-L100, Condenser 1-ND), `ti2e_optical_path_addresses` E3 (S) | Is using condenser `3-` for brightfield a user rule? |
| L-049 | brightfield 4x exposure | 10 ms → median 2766 ADU (DiaLamp 608), saturates at ≥ 30 ms, 12 ms used | run930y:43; run930m:51-52; ops/sample_map.py:60; mock_world:223-225 | measured 2026-09-30 (12-bit readout) | absent | Hand it over? (it depends on the readout mode, L-056) |
| L-050 | exposure for particle light (Aura GREEN 1 %) | 4x 994 ms (auto, p99.9 2043 ADU); 100x 20 ms (max 3435 ADU, no saturation); 100x 30–50 ms saturates | run930y:48,87,119-121; run930m:74,105-106; bench_values:59; mock_world:104-110 | measured 2026-09-30 | absent | Hand it over? |
| L-051 | Aura flicker | two frames at −23 % within one 4x tile | run930y:152; run930m:148-149; bench_values:24-27; mock_world:188-194 | observed 2026-09-30, once | absent | Hand it over as an observation entry? |
| L-052 | fluorescence emission "605 nm" | emission centre 0.605 um, band 0.040 um in the configs | ti2_*.yaml:3,51-52; mock_world:62 | value taken from the path name | **possible conflict**: `red_path_605_is_the_ff01_595_31_filter` E5 (S): 605 is this bench's path name and the filter is FF01-595/31 | Is it right that dino's 0.605 um comes from the path name and not from the filter centre? (Then it is not handed over) |
| L-053 | FilterTurret1 | `1-MXR00724 -Empty` (State 0); FilterTurret2 `1-Empty` | bp1002:254-261,315-322 | device read 2026-10-02 | present: `filter_cube_mxr00724_is_five_band` E3 (S), `stand_state_read_20260924_20x_in_place` E1 (S) | Confirm only |

### 2.5 Cameras

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-054 | Kinetix_red identity | s/n A24M723015, chip TMP-Kinetix, fw 30.48, PVCAM 3.10.2, adapter 1.4.5. Kinetix_blue = A23H723003 (not loaded in this cfg) | bp1002:830-1534; cfg1:24-28,42-49 | device read (cfg header 2026-09-03) | present: `kinetix_red_label_opens_serial_a24m723015` E1 (S), `camera_bodies_are_told_apart_by_serial` E3 (S) | Confirm only |
| L-055 | readout mode on 2026-10-02 | Port `Dynamic Range` (allowed Dynamic Range, Sensitivity, Speed, Sub-Electron); ReadoutRate `100MHz 16bit` only; BitDepth 16; PixelType 16bit; Gain `1-Standard` | bp1002:863,1104,1392,1400,1432; backend:323-328; chk:143; BL:49-51 | device read 2026-10-02 | present: `kinetix_red_adapter_properties_as_reported_20260924` E1 (KB, the same 16bit). gap `kinetix_red_bit_depth` open ("closes with a frame that saturates") | Confirm only |
| L-056 | readout mode on 2026-09-30 | ReadoutRate `100MHz 12bit`, bit depth 12, ceiling 4095. Grounds: auto-exposure aiming at the 16-bit ceiling failed, saturation at 4095 at 100x 30–50 ms | run930y:18-19; run930m:131,156-157; backend:116; flat/focus_classical.py:42-43; mock_world:152-155; mm_real:115 | 9/30 record. Which Port it was is unconfirmed (chk:143) | **conflict**: L-055 and the KB E1 are 16bit. `pixeltype_misreports_bit_depth` E3 (S) is the opposite direction ("PixelType reports 12bit while the data delivered is 16-bit") | Did you change the Port on 9/30? Hand the 9/30 frame that saturated at 4095 (`focus100x_20260930-202226.json`) over as evidence for gap `kinetix_red_bit_depth`? |
| L-057 | dark offset | about 102 ADU observed 9/30; property `Offset = 100` on 2026-10-02; the configs have a 100 ADU placeholder | bench_values:57; mock_world:156; run930y:19; bp1002:1152; ti2_*.yaml:34 | observed 9/30 + device read | absent | Was 102 ADU measured with a dark frame, or seen in a frame with no signal? |
| L-058 | Full well | configs 80000 e- (datasheet, 16-bit DR); device property `FullWellCapacity = 15000` (read-only) | ti2_*.yaml:10,31; configs/kinetix_100x_oil.yaml:26; bp1002:1096 | datasheet vs device read 2026-10-02 | absent (`cameras_both_kinetix22` E3 only says they are the same model) | The two values differ. Which one goes to the librarian? Or both as facts (with separate sources)? |
| L-059 | read noise | 1.6 e- rms (DR mode, datasheet) | ti2_*.yaml:8,29; mock_world:158 | datasheet | present: `camera_read_noise_dynamicrange` E3 (S) | Confirm only |
| L-060 | quantum efficiency | 0.96 (600 nm, read off the graph); configs/kinetix_100x_oil.yaml has 0.80 (near 690 nm) | ti2_*.yaml:9,28; configs/kinetix_100x_oil.yaml:23 | datasheet graph | present: `camera_qe_at_600nm_from_the_kinetix_graph` E3 (S) 0.96. 0.80 absent | Where does 0.80 come from? (If unknown, it is not handed over) |
| L-061 | readout time | `Timing-ReadoutTimeNs` 9000000 (9 ms, at a 10 ms exposure), `ScanLineTime` 3750 | bp1002:1503,1610 | device read 2026-10-02 | absent (related to gap `camera_exposure_grid`) | Hand it over as a fact entry? |

### 2.6 PFS

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-062 | PFS state reading | off throughout 9/30, `Out of Range`. Off from the start on 2026-10-02 (`enabled false, locked false, Out of Range`), still off after `enableContinuousFocus(False)`. Switching off from an on state is unconfirmed | run930y:24,60; bp1002:2374-2387; chk:147; BL:66 | device read | absent (procedure rule only: `rulings:24` "PFS must not be servoing during a Z sweep" transfer) | Hand it over? When can the test of switching off a PFS that is on be done? |
| L-063 | PFS properties | DichroicMirrorInserted `Yes`, FocusMaintenance `Off`, LEDIntensity 27 (0–4095) | bp1002:412-460 | device read 2026-10-02 | absent | Hand it over as a fact entry? |
| L-064 | Core AutoFocus device | `PFS` | bp1002:2371; chk:146; mm_real:110 | device read 2026-10-02 | absent (the objectives' `*_selector_properties` E3 says only "Ti2-E PFS compatible") | Hand it over? |
| L-065 | PFSOffset sign | no value (unmeasured on both sides) | docs/integration-sma.md:100 | unmeasured | gap `pfs_offset_sign_unmeasured` open | Has it ever been measured? |
| L-066 | objective rotation condition | only after Z retract, PFS off, and `Out of Range` confirmed | guards:31,517-538; run930y:109 | 9/30 procedure (prior project SAFETY.md §2) | partial: `nosepiece_write_runs_no_escape` E3 (S), `rulings:24` | Not a number. Hand it over as a procedure only? |

### 2.7 Drift and bench observations

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-067 | uncommanded Z and Y drift | Z 485.16 → 483.62 um, Y about 0.7 um (between the first property read and the move-away) | chk:179; BL:64-65; bp1002:2362-2370; docs/integration-sma.md:101-102 | measured 2026-10-02. Whether anything was touched by hand is unconfirmed | absent | Did you touch the stand or the focus knob in between? |
| L-068 | 9/30 readback mismatch | commanded 3037.0, read 3036.0 um → stopped (the stage was moved by hand at that time) | run930y:132; run930m:120-121; guards:15 | observed 2026-09-30 | absent | Is it right that it was moved by hand? Hand it over as an observation entry? |
| L-069 | 9/30 sample hole | centre (8026.0, 571.6) um, diameter 6.1438 mm, fit rms 42.5 um, 49 points, 352 deg; moved 1.5 mm from the previous fit | run930y:62-75; run930m:16-17,29-32; mock_world:237-238 | measured 2026-09-30 (sample `20260930_1849_1`) | absent | This is a value for one sample. Put it in the librarian as a sample observation, or keep it here? |
| L-070 | 9/30 4x focal plane | hole centre z 3048.7 um, tilt x −1.66, y −3.62 um/mm, rms 7.6 um (73 blocks) | run930y:96-100; run930m:18-19; mock_world:242-243 | measured 2026-09-30 | absent | Same as above |
| L-071 | 9/30 100x focus and particles | bottom layer 2988.45 um (8164.7, 523.4), 2989.42 um (7811.0, 1529.0); particle the user found (8579.5, 68.3) z 3012.94, brightest 3010.0, 20.6 um above the bottom, FWHM about 6.7 um | run930y:113-139; run930m:20-22; mock_world:244 | measured 2026-09-30 | partial/caution: `tracer_diameter_measured` E2 (S) is a diameter of 5 um. 6.7 um is an image FWHM, so not the same quantity | Do you agree not to use the 6.7 um FWHM as the particle diameter? Are they particles from the same bottle? |
| L-072 | oil double peak | the first curve rose a second time near 3005 um; a single peak after adding more oil | run930m:107-108; run930y:119-120 | observed 2026-09-30 | absent | Hand it over as an observation entry? |
| L-073 | piezo reading | 9/30 "NanoBench 6000", COM4, read only, z ≈ 9.94 um all day | run930y:23; run930m:138; mock:64-65; ops/hardware_scan.py:56 | read 2026-09-30 | partial: `piezo_controller_identity` E1 (KB, COM4, NPC-6330), `piezo_rest_position_as_found_20260924` E1 (KB, ch3 −0.0017 um, another day) | Is "NanoBench 6000" a program name? Hand the 9/30 z 9.94 um over as an observation? |
| L-074 | 9/30 start and end state | start: 4x, Z 62.9 um, PFS off. End: 100x Oil, Z 498.0 um (retracted by the user), XY (6396.0, 177.5), Aura and DiaLamp off, confirmed by readback | run930y:58-60,141-147; run930m:23 | record 2026-09-30 | absent | Is there any need to hand it over? (recommendation: only as a run record) |
| L-075 | bench cfg load check | sha256 `8184073e31e1a7a63731932a20a622131d4dba04cf839bc9e651bf9abcd53120`; set on load: Core.Camera=Kinetix_red, Core.Shutter=LightEngine, Core.AutoShutter=1, System/Startup LappMainBranch1.State=1; no System/Shutdown | bp1002:1-21; chk:121-129 | read 2026-10-02 | partial: `single_cam_red_config_startup_puts_the_lapp_mirror_in` E1, `single_cam_red_config_arms_autoshutter_on_the_lightengine` E1 (S). "No Shutdown" is a new fact | Hand over "no Shutdown preset"? |
| L-076 | install state | Micro-Manager_2.0.3_20260806 (pymmcore-plus copy), git 2.49.0.windows.1, torch hub path | chk:133-137 | read 2026-10-02 | present: `pymmcore_plus_micromanager_copy_loads_single_cam_red_config` E1 (S) | Not a physical value. Is it fine not to hand it over? |

### 2.8 Focus-verdict thresholds and operation parameters (all tuning values, not physical values)

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-077 | `MIN_DYNAMIC_RANGE_ADU` (tuning) | 20 ADU | bench_values:34-36; chk:53 | provisional; from the 9/30 case where a 100x 30 ms Vollath read only the dark offset | absent | Do you agree not to hand it over until it is re-tuned with dark frames? |
| L-078 | `MIN_CURVE_CONTRAST` (tuning) | 0.05 | bench_values:37-38; chk:54 | temporary | absent | Same as above |
| L-079 | `MIN_SWEEP_FRAMES` (tuning) | 3 | bench_values:39-40 | temporary | absent | Same as above |
| L-080 | `IN_FOCUS_DOF` (tuning) | 1.0 DoF | bench_values:41-42; chk:55 | temporary | absent | Same as above |
| L-081 | `MAX_SIGMA_DOF` (tuning, used on model readings) | 3.0 DoF | bench_values:43-44; chk:56 | provisional | absent | Classified under §3 because it is a threshold on model sigma. Do you agree? |
| L-082 | `MAX_SATURATED_FRACTION` (tuning) | 0.001 | bench_values:21-23; ops/sample_ops.py:66 | temporary | absent | Recommend not handing it over |
| L-083 | `DROPOUT_TOLERANCE` (tuning) | 0.02 | bench_values:24-27 | rule set from the 9/30 −23 % flicker (scripts/scan_4x.py (deleted in R-05; in history)) | absent | Recommend not handing it over (the underlying observation is L-051) |
| L-084 | `PEAK_BIN` (tuning) | 4 (4 × 4 binning) | flat/focus_classical.py:47 | scripts/focus_100x.py (deleted in R-05; in history) | absent | Recommend not handing it over |
| L-085 | loading check thresholds (tuning) | `MIN_RANGE_ADU` 20, `MIN_STRUCTURE_RATIO` 3.0 | ops/sample_ops.py:67-68 | temporary | absent | Recommend not handing it over |
| L-086 | `focus_100x` parameters (tuning) | centre 2930 um, ±40 @ 2 um, fine ±3 @ 0.2 um, exposure 20 ms, GREEN 1 %, `SIGNAL_MIN_ADU` 50, settle 0.1/0.15 s, 3 extensions | bench_values:54-67; ops/focus_100x.py:126; flat/focus_search.py:55 | provisional (9/30, once) | absent (task 026 unassigned, docs/integration-sma.md:11) | Do you agree to hand it over only as a procedure definition and to set the numbers again in a plan on that side? |
| L-087 | `scan_4x` parameters (tuning) | z estimate 2960 um; first tile ±160 @ 10, next ±50 @ 6, fine ±12 @ 2 um; auto-exposure target 0.5 of the ceiling, 6 tries, start 30 ms, 1–2000 ms; margin 500 um, overlap 0.15; settle 0.1/0.2/0.2 s | ops/scan_4x.py:121-142; run930y:82-86 | 9/30 script values | absent | Same as above |
| L-088 | `edge_trace` parameters (tuning; the speed cap is [envelope]) | default 100 um/s (on 9/30 the user used 400 um/s, step 200 um), speed 10–1000 um/s, step 20–200 um, `MIN_BLOB_UM` 500, `CAL_MIN_PEAK` 8.0, `CAL_SCALE_RANGE` 0.7–1.4, angle difference 10 deg, diameter warning 0.2, cal 200 um, point spacing 250 um, radius 1000–7000 um, path 25000 um, 360 s | ops/edge_trace.py:104-118,122-134; run930y:67 | temporary / used 9/30 | absent | Who set the 1000 um/s speed cap? (envelope candidate) |
| L-089 | mosaic and candidate detection (tuning) | `BIN` 8, candidate detection thresholds (tuned on synthetic tiles only) | flat/map_mosaic.py:22-26,72,325-333; chk:46 | tuned on synthetic data | absent | Recommend not handing them over until re-tuned on a real mosaic |

### 2.9 Patterns and optical tweezers (Tweez300, piezo stage) — added 2026-10-03 (L-01)

Cards for the assumptions that dino's pattern and optical-tweezers screens and guards make. Tweez300 is not connected yet (`tweez300` refuses every call),
and every number is provisional, so **there are no numbers to hand over**; only facts and signs to confirm are asked.

| id | item | value + unit | dino-autofocus location | recorded source | in soft-matter-agents? | question for the user |
|---|---|---|---|---|---|---|
| L-090 | camera body held by Tweez300, and its MM label | dino: the single-camera cfg header "the Tweez 300 GUI can hold Kinetix_blue at the same time"; dino has no MM label for the camera that images the trap plane | tweez300:18; cfg1:27,43; scr/tweezers:33-38 | cfg header 2026-09-03 (inference, not measured) | **possible conflict**: `tweez300_software_opens_the_red_arm_camera` E5 (S), `tweez300_camera_is_released_so_it_shows_no_image` E5 (S) — the user's recollection of 2026-09-24: Tweez300 opens the **red arm** camera | Which serial number is the body Tweez300 opens (A24M723015 red / A23H723003 blue)? What is the MM label of the camera that images the trap plane? (§4 item 7) |
| L-091 | trap coordinate origin and x/y signs | dino: trap position in um from the centre of the field (`TRAP_RANGE_UM` ±60); the screen overlay draws the row direction of frame pixels (down) as +y | patterns:32-33; tweez300:9-10; scr/patterns:44-46 | dino's assumption (not measured) | partial: `tweez300_position_origin_is_image_centre` E3 (S), `tweez300_positive_x_is_right_on_screen` E3 (S). **No y-sign entry** | Is Tweez300's +y up or down on screen? If confirmed, a librarian fact entry (not a number) |
| L-092 | Tweez300 position unit | dino: "own units" (pixels or um undecided); the unit → camera pixel → um conversion is planned as a per-objective calibration | tweez300:9-10,17 | 2026-09 mock agent data | absent (`tweez300_host_streamed_positions_move_smoothly` E3 (S) does not state the unit) | Is the unit pixels, um, or a normalised value? **Confirmation only** — nothing to hand over from dino as a number |
| L-093 | source of the pixel size for the pattern and trap overlay | frame `meta.pixel_um` × binning; if absent, **assume 0.1 um/px**, marked "assumed"; bench table `BENCH_PIXEL_UM {0 (4x): 1.625, 5 (100x): 0.065}` (two states only) | scr/patterns:46; web/tweezers.test:102; mm_real:102; mm_demo:79 | 4x and 100x are the cfg presets of L-031; 0.1 is the screen default | present (numbers): `pixel_size_4x_zoom_1x` E2 1.625, `pixel_size_100x_zoom_1x` E2 0.065 (S); `objective_change_selects_a_pixel_size_row` E5 (S, assumption ruling). The source conflict is L-031 | Do you agree that 0.1 um/px is not handed over (screen only)? The two `BENCH_PIXEL_UM` values go under the one card L-031 |
| L-094 | [envelope] piezo travel range, trap reach range, trap readback tolerance | `PIEZO_RANGE_UM` x/y ±100, z ±50 um; `TRAP_RANGE_UM` x/y ±60, z ±10 um; `TRAP_TOL_UM` 0.05 um | patterns:30-33; guards:643 | PROVISIONAL, unmeasured | absent (`piezo_controller_axis_labels` E1 (S) has only the axis labels; no trap range entry) | Are these values a person writes into the envelope, or are they to be measured first? (workplan P-02: the console receives limits derived from the envelope) |
| L-095 | objectives used with the optical tweezers | not in dino (the pattern and trap guards have no objective condition) | — | — | present (KB only): `optical_tweezers_work_with_40x_60x_100x_person_statement` E5 (KB; one of the 12 the snapshot lags) | A fact in the reverse direction (SMA → dino). Add "no trap at 4x/10x/20x" to dino's guards? (workplan C-08) |
| L-096 | laser power and position readback | dino: "laser power set by hand; no position feedback" — yet `guards.TrapAxis` reads back on every trap move (possible only in the mock) | tweez300:17-18; guards:643,646; scr/tweezers:33-38 | 2026-09 mock agent data | present: `trap_laser_power_has_no_software_path` E3 (S), `tweez300_reports_nothing_back` E3 (S) — the same fact | Confirm only. The stand has no readback, so TrapAxis's readback check is mock only (workplan P-01, §4 item 8) |

## 3. What must not go to the librarian as numbers

| what | location | reason |
|---|---|---|
| All DINO synthetic results (signed MAE, sign acc, \|dz\| MAE, 17-plane error, predictions of `models/heads/*`) | docs/synthetic-results.md:16-49 | Model output, E6. Synthetic data, so not bench facts either. Synthetic results of the classical metrics are not bench values either |
| `MAX_SIGMA_DOF` 3.0 and the verdict that thresholds on model sigma | bench_values:43-44; flat/focus_verdict.py:220 | A threshold on a model number. Model numbers do not enter cards |
| GTX 1650 SUPER latency | docs/synthetic-results.md:51-63 | Measured on the development desktop. Not a value for the microscope PC (A4000) |
| mock_world estimates: power-law interpolation of fluorescence intensity, parfocal log M interpolation (10x–60x), weight 0.25 for lines other than GREEN, DiaLamp factor 0.9, chamber 120 um, particle density 200 /mm², upper-layer fraction and height | mock_world:104-123,215-225,241,245-247 | "estimate" / "not measured" in the code. Not measurements |
| mock_world stage limits ±57000, ±37500, Z 0–9000 um, speed 5000 / 1000 um/s, settle 0.05 s | mock_world:172-181 | "Not measured: placeholders". And they are limits, so safety values |
| mock_world objective labels at positions 1–4 (`2-Plan Apo LmbdD 10x`, `4-Apo LmbdS 40xC WI` and so on) | mock_world:126-137 | Differ from the labels read at the bench (L-001). Made-up labels |
| the 40x WI working distance of 160 um in mock_world and configs/ti2_40x.yaml | mock_world:133; configs/ti2_40x.yaml:23 | The value from before guards changed to 170 um (L-005) is still there. They disagree even inside the repository |
| placeholders in the configs: gain 1.25 e-/ADU, offset 100, dark_current 0.5, prnu 0.005, hot_pixel_rate 2e-5, photons_per_emitter 8000, background 40, bandwidth 0.040 | configs/ti2_*.yaml:11-12,30-36,52-56; mock_world:157 | The files themselves say "placeholder" / unmeasured |
| qe 0.80, wavelength 0.690 "assumed", t_immersion 100 in configs/kinetix_100x_oil.yaml | configs/kinetix_100x_oil.yaml:23,43,47 | Unknown source or assumed. Also differs from the other configs |
| 20x magnification 20.0785 | configs/ti2_20x.yaml:20; mock_world:132 | Back-derived from the pixel size. devices.v0 deliberately has no numeric magnification field (a back-derived value attached to a nominal name) |
| demo values in mm_demo_core: Z offset 3000, demo Z −300..300, demo LED wavelengths `385nm/470nm/550nm/635nm` | mm_demo_core:69-78 | Micro-Manager demo device values. Not the real wavelengths of the Aura lines |
| the mock's piezo `PIEZO_UM (0.0, 0.0, 9.94)` | mock:64-65 | A mock constant, provisional. If handed over at all, only as the original 9/30 reading (L-073) |
| All guard limits and locks: Z window 2800–3200, retract 0 / return 2800, retract judgement 1 um, ceiling 0.4 × WD, approach step 10 um, large-XY-move threshold table, XY box 1000 um, tolerance 0.25 / 5 um, Y move-away +15000 um, XY wait 30 s, edge_trace speed cap, Aura percent (0, 100], `BENCH_APPROACH`, `BENCH_MOTION` | guards:61-149,836-837; mm_real:87-105; ops/edge_trace.py:104-105; ops/light_set.py:40 | Safety limits. §10.3 rule 4: they do not cross as numbers. A person writes them directly into `envelope/safety.json` (the schema keys belong to the manager on that side) |
| the `FREE_WD_UM` / `BENCH_FREE_WD_UM` tables in guards themselves | guards:64-69; mm_real:103-104; mm_demo:80-81 | Guard input tables. The working-distance facts already exist as objective catalogue entries (`objective_mrd*`), and moving these tables would make a second record of the same fact (`rulings:23` also drops the prior's same table). 40x WI 170 um only as a gap answer, once a measurement is confirmed |
| the tuning thresholds and operation parameters of §2.8 (L-077–L-089) | see each row | Not physical values but verdict and procedure tuning. Even if handed over, they are not bench fact entries. Most are provisional or tuned on synthetic data |

## 4. Conflicts between the two repositories and inconsistencies inside a repository

Between the two repositories (the value or the source differs):

1. **40x WI working distance**: dino 170 um (user, 2026-10-02; guards:68, mm_real:104) vs librarian `objective_mrd77400` E3 0.16–0.2 mm, wd null, gap `objective_40x_wd_at_170um` open; `safety:49-65` uses 0.16 mm. 0.17 is the same number as the collar mark (coverslip thickness), so first confirm whether it is a measurement or a copied value.
2. **Kinetix_red bit depth**: dino 9/30 12-bit, `100MHz 12bit`, ceiling 4095 (run930y:18-19) vs librarian `kinetix_red_adapter_properties_as_reported_20260924` E1 16bit, and dino's 2026-10-02 read is 16bit too (bp1002:1432). The librarian's `pixeltype_misreports_bit_depth` E3 is the opposite direction (property 12bit, data 16-bit). Gap `kinetix_red_bit_depth` is written as closing with one saturated frame, and 9/30 has a frame saturated at 4095.
3. **4x pixel size**: dino 9/30 calibration 1.62524 um/px (run930y:52) vs librarian `pixel_size_4x_zoom_1x` E2 1.625. And the source: dino cfg1:294-296 says "only 20x measured, the other five are 6.5/M", while the librarian has all six as "measured by the operator" (E2).
4. **Emission 605 nm**: dino configs emission centre 0.605 um (ti2_*.yaml:51) vs librarian `red_path_605_is_the_ff01_595_31_filter` E5: 605 is a path name and the filter is 595/31.
5. **Particle size**: dino 9/30 particle FWHM about 6.7 um (run930y:138), mock 5.0–6.7 um vs librarian `tracer_diameter_measured` E2 5 um. Not the same quantity, but easy to mix up.
6. Piezo: dino 9/30 z 9.94 um, "NanoBench 6000" vs librarian 9/24 ch3 −0.0017 um, `NPC-6330`. The dates differ, so it is not a conflict; the names differ.
7. **Camera held by Tweez300** (added 2026-10-03): dino cfg1:43 "the Tweez 300 GUI can hold Kinetix_blue at the same time" (2026-09-03 header, inference) vs
   librarian `tweez300_software_opens_the_red_arm_camera` E5 (2026-09-24 recollection: red arm). Must be confirmed by body and serial number (L-090).
8. **Trap position readback** (added 2026-10-03): dino `guards.TrapAxis` requires a readback on every move (the mock returns one) vs librarian
   `tweez300_reports_nothing_back` E3. A conflict of design assumption, not of value: the stand has no readback (L-096; workplan P-01 wrote it into the `tweez300.py` docstring).

Inconsistencies inside dino-autofocus (to clean up before integration; not fixed in this survey):

- 40x WI working distance: guards / mm_real / mm_demo have 170, configs/ti2_40x.yaml:23 and mock_world:133 have 160.
- Full well: configs 80000 e- vs device `FullWellCapacity` 15000 (bp1002:1096).
- Quantum efficiency: ti2_*.yaml 0.96 vs configs/kinetix_100x_oil.yaml:23 0.80.
- Objective labels: mock_world:131-134 vs the bench (bp1002:179, cfg1:178-183).
- backend:116 comment "4095 for the Kinetix 100 MHz 12-bit readout" vs the 16bit of 2026-10-02 (backend:324-326).

Values that agree (confirm only): 4x / 10x / 20x / 60x / 100x working distances, NA per objective, pixel size numbers, coverslip 170 um, 40x collar 0.17 mm, Z direction, the five Aura lines and per-mille, Aura State 0, Spectra III identity, read noise 1.6 e-, QE 0.96, sensor 2400 × 2400 / 6.5 um, Kinetix_red serial number.

## 5. The 20 cards to answer before the copy (workplan OD-22; the 15-card cap is dropped)

OD-22 of the workplan `docs/integration-sma-workplan.md`: the 16 cards for numbers that left the flat files (D-02) and the 4 cards for conflicts between the two repositories need the user's answer before
the copy (G-06). The rest (about 70 cards + the 7 of §2.9) are asked in bundles of 20 in L-03.

- The 16 cards whose numbers left the flat files: L-032 (4x M calibration), L-033 (parfocal −60 um), L-057 (dark offset 102 ADU),
  L-077 ~ L-089 (13 cards of verdict thresholds and operation parameters; all of them are in `bench_values`).
- The 4 cards for conflicts between the two repositories: L-005 (40x WI working distance 170 um), L-031 (source of the pixel size), L-052 (605 nm is a path name), L-056 (9/30 12-bit readout).
- Shape of the answer: one line per card — **send** (as a librarian entry; source, date, grade) / **don't send** (kept only in dino; reason) / **measure first** (when, how).
  "Send" goes to SMA `findings/<seat>-<date>.json`, and envelope values are written by a person directly into `safety.json` (§3).

## 6. Definitions that enter the KB before the copy (L-05; no numbers)

soft-matter-agents plan.md 10.2 (96db738, 2026-10-03): until the place for focus search (11-24) is designed, no code crosses, and **only definitions of the method** may enter as librarian entries — what each metric is, what each verdict means, and that `unsure` is an abstention. The shape set by the session leading on the SMA side (architecture-20261003-1, 2026-10-03): `contracts/schemas/kb_entry.schema.json`, kind is always **`claim`** (SMA has no document_fact kind); of the required fields entry_id, schema_version, kind, claim, validity_conditions, grade, source_ref, date, curated_by, **entry_id, grade and curated_by are not pre-filled** (the grade comes from the source, curated_by is the librarian); whether to bundle entries into one or split them into several is the librarian seat's decision. What the dino side provides: **one claim per sentence, no numbers, source = the public blob URL (pinned to a commit) of the file that holds the docstring + body sha256, validity conditions stated.** There is no librarian seat yet (a person seats it).

Sources (the values of the D-03 provenance headers; body sha256 with line endings normalised to LF):

- `classical` = https://github.com/kyu-softmatter/dino-autofocus/blob/fa9790378ea3f06e94b933a2fb65219322f6702a/microscope_agent/src/focus_classical.py — body-sha256 `2fa776faeb2b366f5dd1892345715d087e63a702cc168e179e81cb0bfd3f2af3`
- `verdict` = https://github.com/kyu-softmatter/dino-autofocus/blob/fa9790378ea3f06e94b933a2fb65219322f6702a/microscope_agent/src/focus_verdict.py — body-sha256 `07bc1342a4c868e5856b549bc8bc6a8c3a5af8fd8bd6dd83cc6c6970d01be099`
- `search` = https://github.com/kyu-softmatter/dino-autofocus/blob/fa9790378ea3f06e94b933a2fb65219322f6702a/microscope_agent/src/focus_search.py — body-sha256 `7ffaf28f014ffdd87587f803f2481e3d9eff47219fde15432d97932483655bc6`
- `run_log` = https://github.com/kyu-softmatter/dino-autofocus/blob/fa9790378ea3f06e94b933a2fb65219322f6702a/microscope_agent/src/focus_run_log.py — body-sha256 `cb47d6d43e1d4695be71480afb945ff114a2cda103728c783631098d736a06c6`

| # | source | claim (one sentence) | validity_conditions |
|---|---|---|---|
| L05-01 | `classical` | `vollath4` is the scale-invariant Vollath F-four sharpness: the frame is median-subtracted and divided by its mean absolute deviation, then the first-lag autocorrelation minus the second-lag autocorrelation is summed over both image axes, so that a brighter exposure does not read as sharper and uncorrelated noise cancels. | classical sharpness metric on one monochrome widefield frame as read, clipped pixels not masked; says nothing about which plane holds the sample |
| L05-02 | `classical` | `brenner` is the scale-invariant Brenner sharpness: after the same normalisation as `vollath4`, the squared second-lag differences are averaged over both axes; it rises on dim, noisy frames. | classical sharpness metric on one monochrome widefield frame as read, clipped pixels not masked; says nothing about which plane holds the sample |
| L05-03 | `classical` | `peak_brightness` is the brightest binned spot minus the binned median of the frame, meant for sparse particle fields at high magnification where a whole-frame sharpness barely moves. | classical sharpness metric on one monochrome widefield frame as read, clipped pixels not masked; says nothing about which plane holds the sample |
| L05-04 | `classical` | `tenengrad` is the Sobel gradient energy over the valid interior of the frame, with the same normalisation as `vollath4` and `brenner`. | classical sharpness metric on one monochrome widefield frame as read, clipped pixels not masked; says nothing about which plane holds the sample |
| L05-05 | `classical` | every classical metric here peaks at best focus, and `vollath4` sums both axes whereas the synthetic-training variant uses one axis, so the two peak at the same plane with different values. | classical sharpness metric on one monochrome widefield frame as read, clipped pixels not masked; says nothing about which plane holds the sample |
| L05-06 | `classical` | a frame whose clipped-pixel fraction exceeds the caller's limit is not readable for focus, because a clipped core flattens the gradient at the top of a particle and the frame under-reads its own sharpness; the clipped fraction is kept beside every score. | classical sharpness metric on one monochrome widefield frame as read, clipped pixels not masked; says nothing about which plane holds the sample |
| L05-07 | `classical` | a sweep frame whose mean departs from the sweep's median mean by more than the caller's tolerance is a light dropout, not a focus change, and cannot be chosen as the peak. | classical sharpness metric on one monochrome widefield frame as read, clipped pixels not masked; says nothing about which plane holds the sample |
| L05-08 | `verdict` | the focus verdict vocabulary is exactly `in_focus`, `step_up`, `step_down`, `no_sample_here` and `unsure`. | a verdict is for display and for the record only; it never sets a limit, opens a gate or takes part in a safety decision |
| L05-09 | `verdict` | `step_up` means best focus lies above the current stage z (the focus drive would move toward larger z) and `step_down` the opposite; at the oil immersion objective a step up is the operator's call and the verdict only reports it. | a verdict is for display and for the record only; it never sets a limit, opens a gate or takes part in a safety decision |
| L05-10 | `verdict` | the z of a verdict is the encoder readback of a real frame that was taken, never a model output and never an interpolated z; computed numbers and model numbers are kept only as evidence with their grade. | a verdict is for display and for the record only; it never sets a limit, opens a gate or takes part in a safety decision |
| L05-11 | `verdict` | a verdict returns a branch and the frame it chose, never a Z to move to; it can refuse and cannot permit, carrying no limit, no target and no command. | a verdict is for display and for the record only; it never sets a limit, opens a gate or takes part in a safety decision |
| L05-12 | `verdict` | `unsure` is an abstention: too few readable frames, a flat curve, a model reading whose spread exceeds the caller's bound, or a sign that cannot be told. | a verdict is for display and for the record only; it never sets a limit, opens a gate or takes part in a safety decision |
| L05-13 | `verdict` | from a classical sweep: no frame with more than dark-level dynamic range gives `no_sample_here`; too few readable frames or a flat curve gives `unsure`; a peak at the top of the span gives `step_up` and at the bottom `step_down`; a peak inside gives `in_focus` at the real frame nearest the parabola vertex. | a verdict is for display and for the record only; it never sets a limit, opens a gate or takes part in a safety decision |
| L05-14 | `verdict` | from one signed model reading in depth-of-field units: no tile with sample signal gives `no_sample_here`; tiles but none readable, or a spread above the caller's bound, gives `unsure`; a displacement inside the caller's in-focus band gives `in_focus`; a known sign gives `step_down` for a stage above focus and `step_up` below; otherwise `unsure`. | a verdict is for display and for the record only; it never sets a limit, opens a gate or takes part in a safety decision |
| L05-15 | `verdict` | every threshold the verdict uses is a keyword argument the caller must supply; the file holds no default and no bench number. | a verdict is for display and for the record only; it never sets a limit, opens a gate or takes part in a safety decision |
| L05-16 | `search` | the focus search is a coarse sweep around a centre, then, if the coarse peak lies inside the span, a fine sweep around that peak. | describes the order of spans only; every limit is an argument supplied by the caller, and nothing in the file moves anything |
| L05-17 | `search` | a peak on the top end of a span is not climbed: z returns to the low end and the operator is asked whether to extend one span higher from the old top, a bounded number of times and never past the ceiling; a peak on the low end is reported as re-centre lower. | describes the order of spans only; every limit is an argument supplied by the caller, and nothing in the file moves anything |
| L05-18 | `search` | the search yields spans and z points only; the floor and ceiling are the caller's, every move is checked and read back by the caller, and no model value takes part. | describes the order of spans only; every limit is an argument supplied by the caller, and nothing in the file moves anything |
| L05-19 | `run_log` | a focus verdict is logged as one run-log event that is not a command: it carries no params and no channel, the chosen frame's z is the encoder readback, values read in the run and deterministic computations on them carry their grades, and model numbers appear only as signals without a grade. | shape of the run-log event; the grade mapping is provisional until the person rules on it |

Check: the claim and validity cells of this section contain no number literals (checked with `grep`; the hashes and commits in the source lines excluded). Bench and tuning numbers are handled separately by the cards of §2.8 (L-077~L-089) and the 20 cards of §5; this section is definitions only.

## 7. Answer rows (bench visit B-01 and the 20 cards before the copy) — added 2026-10-05, blank

- Blank answer rows made by the bench session (B-01 preparation). §1–6 were not changed. Checklist `docs/runbooks/bench-visit-1.md`, record form `docs/runs/templates/bench-visit-1.template.{md,yaml}`.
- The answer shape is the same as in §5: **send** (as a librarian entry; source, date) / **don't send** (reason) / **measure first** (when, how). No grade is written (OD-17: source only; SMA derives the grade).
- Columns: answer / value (if any) / source (`user statement in the bench window, <date>` or `file <path> sha256`) / confirmation `{kind, by, on, how}` / bench confirmation (visit date, 2026-10-12).
- Person statements S1–S6 (2026-10-05): the person said them in the merge-plan session window and that session relayed them. `how` = "stated in the merge-plan session window; not yet confirmed at the bench". On 2026-10-06 the person confirmed with "yes" in the bench session window that S1–S6 are their own statements (user statement in the bench window, 2026-10-06). They are not measured values, and the bench confirmation column stays open.
- Envelope values (`focus_z_*`, retract, step) are not set here. A person writes them into SMA `safety.json` at U-03.

### 7.1 Cards answered at bench visit 1

| id | checklist section | answer | value | source | confirmation {kind, by, on, how} | bench confirmation |
|---|---|---|---|---|---|---|
| L-005 | 5.3 | | 170 um (S1, person statement) | relayed by the merge-plan session 2026-10-05 | {person_statement, person, 2026-10-05, "stated in the merge-plan session window; not yet confirmed at the bench"} | |
| L-013 | 4.1 | | | | | |
| L-015 | 4.5 | | | | | |
| L-018 | 5.1 | | (S2: not answered separately) | | | |
| L-019 | 5.2 | | lower Z by 100 um (S2, person statement) | relayed by the merge-plan session 2026-10-05 | {person_statement, person, 2026-10-05, "stated in the merge-plan session window; not yet confirmed at the bench"} | |
| L-023 | 4.3 | | stage ±2 cm (S3, person statement) | relayed by the merge-plan session 2026-10-05 | {person_statement, person, 2026-10-05, "stated in the merge-plan session window; not yet confirmed at the bench"} | |
| L-024 | 4.3 | | | | | |
| L-029 | 8 | | | | | |
| L-033 | 5.4 | | | | | |
| L-043 | 8 | | | | | |
| L-044 | 8 | | | | | |
| L-051 | 8 | | | | | |
| L-055 | 6 | | "2^16 이 포화 값" (2^16 is the saturation value), 16-bit (S4, the person's statement word for word; not a numeric value — only the maximum seen in a saturated frame becomes the answer; do not assume 2^16 − 1) | relayed by the merge-plan session 2026-10-05 | {person_statement, person, 2026-10-05, "stated in the merge-plan session window; not yet confirmed at the bench"} | |
| L-062 | 7 | | controlled through MM (S5, person statement); the property that switches it off is still open | relayed by the merge-plan session 2026-10-05 | {person_statement, person, 2026-10-05, "stated in the merge-plan session window; not yet confirmed at the bench"} | |
| L-063 | 7 | | (same as S5) | | | |
| L-064 | 7 | | | | | |
| L-065 | 7 | | | | | |
| L-067 | 4.4 | | | | | |
| L-073 | 4.2 | | | | | |
| L-090 | 9 | | releases the camera (S6, person statement) | relayed by the merge-plan session 2026-10-05 | {person_statement, person, 2026-10-05, "stated in the merge-plan session window; not yet confirmed at the bench"} | |
| L-091 | 9 | | when y decreases, it moves down in the image (S6, person statement) | relayed by the merge-plan session 2026-10-05 | {person_statement, person, 2026-10-05, "stated in the merge-plan session window; not yet confirmed at the bench"} | |
| L-094 | 4.2 | | piezo 0–6000 um (S3, person statement; **needs confirmation**: dino `PIEZO_RANGE_UM` ±100 um, KB controller NPC-6330) | relayed by the merge-plan session 2026-10-05 | {person_statement, person, 2026-10-05, "stated in the merge-plan session window; not yet confirmed at the bench"} | |
| L-095 | 9 | | | | | |
| L-096 | 9 | | | | | |

### 7.2 The 20 cards to answer before the copy (§5, OD-22)

| id | answer | value | source | confirmation {kind, by, on, how} | if measure first, when and how |
|---|---|---|---|---|---|
| L-032 | | | | | |
| L-033 | | | | | |
| L-057 | | | | | |
| L-077 | | | | | |
| L-078 | | | | | |
| L-079 | | | | | |
| L-080 | | | | | |
| L-081 | | | | | |
| L-082 | | | | | |
| L-083 | | | | | |
| L-084 | | | | | |
| L-085 | | | | | |
| L-086 | | | | | |
| L-087 | | | | | |
| L-088 | | | | | |
| L-089 | | | | | |
| L-005 (conflict) | | (see 7.1) | | | |
| L-031 (conflict) | | | | | |
| L-052 (conflict) | | | | | |
| L-056 (conflict) | | (see L-055 in 7.1) | | | |
