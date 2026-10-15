# What to check on the microscope PC (as of 2026-10-01)

> **Warning (2026-10-01): nothing moves on the real instrument yet.** The real-instrument backend (mm-real) is
> on main, but the things that check the clearance during a Z approach at the bench (the T-027 guard, the T-011 bench check) are not on main yet.
> Until both are merged, the microscope PC is used **read-only**. Status view, camera frames, and switching light sources on/off (D15)
> only; do not run any work that moves the stage, Z or the objectives. The new app's real-instrument backend is also locked in code
> (T-036, main 2c61b7b: `BENCH_MOTION = "LOCKED"`). **The old scripts that moved the instrument outside the lock
> (scan_4x, focus_100x, change_objective, etc.) were deleted in R-05 (they remain in history).** The instrument is moved through the app, or by hand.
> The lock is lifted once T-027, T-011b, T-015b (a safe default that treats the instrument backend as "bench" by default), T-027b (refuses approach above 2800 µm for an objective whose working distance is unknown), and the two follow-ups that make the guard and the executor use the same bench verdict (is_bench), T-036d (the startup preset check also looks at the device names the configuration file uses), T-015c (the bench verdict returns "bench" instead of an error), T-029c (records the Y escape before moving), and T-029d (refuses objective changes and the 100x approach on the real instrument until Q13 and Q20 are measured; partly lifted by the user on 2026-10-02: 40x WI, 60x and 100x only up to 2800 µm) are all merged and the manager and the lead have confirmed it, and at that point the lead session removes this warning.

Written by: the lead session. This gathers in one place the items that cannot be answered on the development desktop, and that get an
answer only by reading something on the microscope PC or running it there once. When an answer comes, write it in this file and tell the lead session. Until then the code runs on the
provisional values below, which are marked `unmeasured provisional` in the code and in the records.

## 1. What the user decides

| # | Question | Current state |
|---|---|---|
| U1 | Python environment (PLAN D2): whether to run the whole Windows side from this repository's single uv environment | Recommendation: unify on uv |
| U2 | Whether the WSL simulation writes its run records directly to `D:\AutoFocus\records\simulation\`, or leaves them where they are now and they are read there | **Decided at integration** (the user). No effect on mock |
| U3 | Whether abort alone is allowed from the remote access screen | **Decided: allowed** (PLAN D13) |
| U4 | Whether work a person does while watching (edge tracing, etc.) stops automatically if every browser on the microscope PC disconnects | **Decided: automatic stop after 10 s** (PLAN D14) |

## 2. What to read or measure on the microscope PC

### Simulation (WSL)

- Does a running simulation leave its progress (current step, total steps) in a file? If so, where?
- The actual paths of the trajectory (GSD) and log files. The server only reads them, through `\\wsl$\<distribution>\...`.

### Direction reference

Directions follow the 2026-09-30 run records (PLAN §5 Guards). The F5 Y escape was set to +Y first (to be checked under Q12).

### The operations spec's questions Q1–Q21

The questions in full and their reasons are in [operations-spec.md §10](operations-spec.md). Most are
answered by reading `C:\agentic_microscope\hardware\focus.py` (FocusAxis).

| Group | Questions | How to check |
|---|---|---|
| Z moves and sweeps | Q1 approach direction to the sweep start, Q2 readback tolerance, Q3 return value of `park_at`, Q4 the `best_z_um` rule, Q6 `dry_run` behaviour, Q7 Ctrl+C during a move, Q15 where the 100x ceiling is computed, Q21 whether a stepped-approach function exists | Read the FocusAxis code |
| Objectives and PFS | Q5 `require_pfs_quiet`, Q8 where the per-objective upper limits and working distances are kept, Q13 safe steps for raising the 100x from 0→2800 µm, Q14 what `waitForDevice("Nosepiece")` means | Read the code + one bench visit |
| Light sources and configuration | Q9 the visible change from the Startup preset, Q10 whether Aura State 0 turns off every line | By eye at the bench |
| XY and stage | Q11 XYStage readback error, Q12 F5 escape direction, distance, Y limit and the direction of the 24 mm side, Q20 the XY distance beyond which 100x oil needs a Z retract | Bench measurement |
| Sample map | Q16 Vollath focus on brightfield 4x tiles, Q17 the brightfield auto-exposure target, Q18 whether particles of about 6.7 µm show in the 4x mosaic, and the particle-candidate detection threshold (T-032, tuned only on synthetic tiles so far) | One bench visit. If one real mosaic is saved, the threshold can be re-tuned on the desktop |
| Piezo | Q19 what changes merely by opening `PiezoReader`, and what happens when its port overlaps with the NanoBench program | One bench visit |

### Provisional focus-verdict constants (`src/dino_autofocus/focus/verdict.py`)

| Constant | Provisional value | Meaning |
|---|---|---|
| `MIN_DYNAMIC_RANGE_ADU` | 20 | a brightness range smaller than this is taken to mean there is nothing to read |
| `MIN_CURVE_CONTRAST` | 0.05 | minimum contrast of the focus curve |
| `IN_FOCUS_DOF` | 1.0 | within this, `in_focus` |
| `MAX_SIGMA_DOF` | 3.0 | an uncertainty larger than this gives `unsure` |

### Provisional guard values set by the manager

| Value | Provisional | What to measure |
|---|---|---|
| Large-XY-move threshold | a per-objective table (in the guard). 4x allows tile moves, 100x Oil is min(field of view, 1 mm), an unknown objective gets the strictest | Q20, every value in the per-objective table |
| `z_safe` | 0 µm (fully retracted) | Q20 |
| Per-objective free working distance `FREE_WD_UM` (in the guard, T-027b) | Only 4x 20 mm and 100x Oil 130 µm are there. An objective without a value cannot approach above 2800 µm, and is also refused as the target of an objective change (F5). 10x, 20x, 40x WI and 60x are caught by this | The free working distances of 10x, 20x, 40x WI (at the 0.17 mm correction collar position) and 60x. Read them from the objective spec sheet or the marking on the objective barrel, and confirm once at the bench |
| `approach_step_um` (the step of the F5 stepped approach) | Kept in the per-objective table. 100x Oil 10 µm (about 1/13 of its 130 µm working distance), and 10 µm for the other objectives too for now. As in the existing procedure, the approach goes 0 → 2800 µm in one move and then steps up from 2800 | Q13. Confirm before M4's real bench use |
| F5 escape direction and distance | **+Y, 15 mm** (the user set +Y first; the distance is the shorter end of 15–20 mm). Refused if it would cross the stage's Y limit | Q12. Confirm before M4 |

### Device property names (T-015)

| Question | Current state | How to check |
|---|---|---|
| Kinetix_red's readout-mode property name and value list | Not in the camera write allowlist yet. The September 30 record has `ReadoutRate = 100MHz 12bit`, so the name looks like `ReadoutRate`, but it is not confirmed | Read Kinetix_red's property list and allowed values in Micro-Manager |
| The Aura's line names other than GREEN (VIOLET, CYAN, RED, etc.) and the `<LINE>_Intensity` properties | Only GREEN was used on September 30. The rest are `unmeasured provisional` | Read the Aura device property list |

### Real-instrument backend (T-033)

| Question | Current state | How to check |
|---|---|---|
| **Does loading the configuration file leave the moving devices alone?** (T-036b) | When a configuration is loaded, Micro-Manager itself applies the `Startup` preset of the `System` group and the `Property` lines after `Property,Core,Initialize,1`. If ZDrive, XYStage, Nosepiece or PFS values are in there, **merely opening it moves the instrument.** The September 30 record lists only `LappMainBranch1 State 1` (light path), and the rest has not been checked. Micro-Manager's default demo configuration rotates the objective at Startup and is caught by the new check. The new app checks before opening and refuses (the old `scripts/*` that opened the same file without a check were deleted in R-05; they remain in history) | The two commands below. If any name comes up -- not only ZDrive, XYStage, Nosepiece and PFS but the name of any device that handles Z, the stage, the objectives or PFS in this configuration (for example TIZDrive, or the name written in the `Property,Core,Focus,...` line) -- open nothing with that configuration and tell the lead session |
| **Does the configuration's shutdown preset leave the moving devices alone?** (T-036b) | Not confirmed whether Core applies the `System/Shutdown` preset when it unloads the devices. If it does, Z, stage or objective values in it move the instrument at shutdown. The new app refuses the Shutdown preset under the same rule | Look at the Shutdown line in the command below. Whether it is applied at shutdown: if the Shutdown preset holds a visible, harmless value (light path, etc.), see at the bench whether it changes when shutting down |
| Bench configuration file path and Micro-Manager install folder | The app's mm-real backend (`engine/backends/mm_real.py` `BENCH_CONFIG`) uses `C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg`. pymmcore-plus finds the install folder | Whether the file exists; `uv run python -c "from pymmcore_plus import find_micromanager; print(find_micromanager())"` |
| Is Core's AutoFocus device the PFS? | Not confirmed | After loading the configuration, read Core's AutoFocus role |
| Does it read as off after `enableContinuousFocus(False)`? | Not confirmed | Turn it off and read `isContinuousFocusEnabled()` |
| Is the 30 s XY move wait long enough for the longest move? | `DEFAULT_XY_TIMEOUT_S = 30`, provisional | Time a move between the two farthest points |
| Stage travel limits (X, Y) | The real-instrument backend currently returns "unknown". So **the F5 Y escape is refused on the real instrument** | Read or measure the stage limit values (together with Q12) |

Commands to check the configuration file (PowerShell on the microscope PC; both only read and do not open the instrument):

```powershell
Select-String -Path "C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg" -Pattern "^ConfigGroup,System,(Startup|Shutdown)"
```

This runs the same check the new app runs when it opens the instrument (T-036b, T-036d: it also refuses when the configuration file's role lines and the device names the app uses differ) (it does not load Micro-Manager). It shows everything that is set at load and prints `OK` at the end if nothing is wrong. If a moving device is there, it shows its name as `UnsafeConfig`:

```powershell
uv run python -c "from pathlib import Path; from dino_autofocus.engine.backends.mm_real import load_time_settings, check_load_settings, BENCH_DEVICES; p = Path(r'C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg'); s = load_time_settings(p.read_text(encoding='utf-8')); [print(x.text()) for x in s]; check_load_settings(s, p.name, BENCH_DEVICES); print('OK')"
```

### Installation state (T-020)

| Question | Why it is needed | Check command |
|---|---|---|
| Is git installed? | The DINO backbone checks the dinov2 clone's commit with `git rev-parse` and refuses to run without it. The record store (PLAN D10) is also local git | `git --version` |
| Where is the torch weights folder? | The weights files go in `checkpoints` under that folder (offline copy) | `uv run python -c "import torch; print(torch.hub.get_dir())"` |
| The Windows Firewall window when remote view is turned on (T-009) | Starting the server with `--remote-view` binds to every address (0.0.0.0), so the firewall asks once, the first time, whether to allow it. **Allow it only when remote view is needed, and only for "Private networks".** Do not allow public networks. If remote view is not used, this window does not appear | The first time the server is started with `--remote-view` |

### Other things to measure (from the September 30 record)

- The 4x→100x parfocal offset. On September 30 it was about −60 µm; measure it again on a reference sample.
- DINO latency on the A4000, and the measured performance of the fp16 head.
- The working distance of the 40x WI objective at the 0.17 mm correction collar position. Without this value the 40x WI path is blocked.

## 2026-10-02 microscope PC results

> The approach lock (`BENCH_APPROACH`) was **partly lifted** by the user on 2026-10-02 (before Q13 and Q20 are measured). On the real instrument, 4x, 10x and 20x
> go up to 3200 µm, and 40x WI, 60x and 100x up to 2800 µm. The motion lock (`BENCH_MOTION`) stays as it is.

> Of the code changes these results call for, the Aura line names, the camera's `Port` and `ReadoutRate`, and four objective working distances have been applied
> (user approval, 2026-10-02). The rest are in the "2026-10-02 bench results" item of the handoff section of the internal notes (outside the public repository, `dino-autofocus-internal/tasks/BACKLOG.md`).

Checked on the microscope PC. The repository was at `dbfd023`. The full device properties are in
[runs/2026-10-02_bench-properties.json](runs/2026-10-02_bench-properties.json), and a copy of the configuration file is at
`configs/micromanager/single_cam_red_noDMD_nocom10.cfg` (same SHA-256 as the original, `8184073E…3120`).

### Configuration file (T-036b)

- `check_load_settings` gives `OK`. The only things set at load are `Core.Camera=Kinetix_red`, `Core.Shutter=LightEngine`,
  `Core.AutoShutter=1` and `System/Startup: LappMainBranch1.State=1`.
- There is no `System/Shutdown` preset.
- `Core.Focus` is not set (`getFocusDevice()` returns empty). The new backend uses `ZDrive` by name, so this is fine, but
  code that uses the default focus device fails.

### Installation state (T-020)

- git `2.49.0.windows.1`
- torch hub: `%USERPROFILE%\.cache\torch\hub` (the weights go in `checkpoints` under it)
- Micro-Manager: `%USERPROFILE%\AppData\Local\pymmcore-plus\pymmcore-plus\mm\Micro-Manager_2.0.3_20260806`

### Device properties (T-015, T-033)

| Item | Result |
|---|---|
| Kinetix_red readout mode | The name is indeed `ReadoutRate`. But right now its only allowed value is `100MHz 16bit`, and with it `Port = Dynamic Range` (allowed `Port` values: `Dynamic Range`, `Sensitivity`, `Speed`, `Sub-Electron`). The September 30 `100MHz 12bit` seems to have come from a different Port (not confirmed). The allowlist has to hold `Port` and `ReadoutRate` together. `Gain` has one value, `1-Standard` |
| Aura lines | Aura III 5-NII-WA (COM7). The lines are **UV, CYAN, GREEN, RED, NIR**, each with on/off (0–1) and `<LINE>_Intensity` (0–1000). **The Aura has no VIOLET.** The code's `AURA_LINES = ("VIOLET", "CYAN", "GREEN", "RED")` (`engine/backend.py`) has to be fixed |
| LightEngine | A Spectra III 8-NII-XS (COM3), separate from the Aura. It is the Core shutter, and the configuration turns AutoShutter on. Its lines are VIOLET, BLUE, CYAN, TEAL, GREEN, YELLOW, RED, NIR |
| Core AutoFocus device | `PFS` |
| Reading after turning PFS off | It was off from the start (`Out of Range`), and still off after `enableContinuousFocus(False)`. Turning it off from the on state is not confirmed yet |
| Stage limits (X, Y) | Cannot be read from properties. XYStage and ZDrive have only Speed, Tolerance and Invert/Transpose. The librarian's store has no value either |

### Objective free working distances (T-027b)

Catalogue values (E3) from the librarian store's `kb/entries/objective_*.json`. The files were read directly, not through the service (`kb_query`)
(there was no issued `caller_id`), so this is not in the query log.

| Objective | Part number | Working distance |
|---|---|---|
| 4x | MRD70040 | 20 mm (same as the code value) |
| 10x | MRD70170 | 4 mm |
| 20x | MRD70270 | 0.8 mm |
| 40x WI | MRD77400 | 0.16–0.20 mm (the full correction collar range). The value at the 0.17 position is not in the catalogue and is an open gap in the store (`objective_40x_wd_at_170um`). The code value is **0.17 mm** (the user, 2026-10-02) |
| 60x Oil | MRD71670 | 0.15 mm |
| 100x Oil | MRD71970 | 0.13 mm (same as the code value) |

The store infers that these working distances are measured to the objective-side surface of the coverslip (E4, `working_distance_is_measured_to_the_coverslip`).

### One F5 Y escape (part of Q12)

Moved once at the user's request, for oil loading. The app's lock (`BENCH_MOTION`) was left in place, and a one-off script called core directly.
The order followed operations-spec F5: confirm 4x, PFS off and light sources off → Z 0 → read Z again → +Y 15 mm → readback.

| | X (µm) | Y (µm) | Z (µm) |
|---|---|---|---|
| Before (return position) | −5134.4 | 5498.9 | 483.62 |
| After | −5134.6 | 20498.8 | −0.08 |

- XY readback within 5 µm. The Y limit is at least 20498.8 µm.
- The move finished within 30 s (speed 25 mm/s).
- The user loaded the oil. The objective stayed at 4x; no objective rotation and no return were done.
- Between the first property read and the move, with no software command, Z changed from 485.16 → 483.62 µm and Y by about 0.7 µm. Whether it was touched by hand is not confirmed.

### 40x WI correction collar

- Confirmed by the user on 2026-10-02: the correction collar is still at 0.17 mm (coverslip thickness 170 µm). This agrees with the librarian's `objective_40x_collar_setting` (read 2026-09-22).
  The working distance value (`objective_40x_wd_at_170um`) is still open.

### Q10 Aura State 0

- The user's answer, 2026-10-02: at Aura `State 0`, every line is off.
- Agrees with the librarian: `aura_master_state_0_keeps_green_dark` (E1, 2026-09-24, the frame is dark at GREEN 1000),
  `light_engine_master_state_gates_every_line` (E3, both Lumencors).
- The librarian's `aura_reports_five_named_lines` (E1) also agrees with the five lines read today (UV, CYAN, GREEN, RED, NIR).

### Q9 Light path of the Startup preset

The user's note, 2026-10-02.

| Device and value | Meaning |
|---|---|
| `LappMainBranch1` State 1 | The Aura path is on. The 50/50 mirror goes in |
| `CSUW1-Port` State 0 | blue only (100/0 mirror) |
| `CSUW1-Port` State 1 | both blue and red. The 561 nm dichroic splits them by wavelength (not by intensity) |
| `CSUW1-Port` State 2 | red only (no mirror) |

- The librarian's `csuw1_port_slots` (E3, 2026-09-17) records three slots (empty, 561 nm dichroic, 100/0 mirror) and
  says "which slot is which State number is not known". This note gives those numbers. Tell the librarian session.
- Agrees with the librarian's `lapp_state_1_brings_the_aura_to_the_sample` (E3) and `single_cam_red_config_startup_puts_the_lapp_mirror_in` (E1).
  That it is a 50/50 mirror is new in this note.
- The Startup of `DMD_dualcam_LUNF.cfg` is `LappMainBranch1` 1 and `CSUW1-Port` 1 (both blue and red).
  A copy is at `configs/micromanager/DMD_dualcam_LUNF.cfg` (for reference). This installation cannot load it, because of `MightexPolygon1000` (device API v71).
  The `Label,CSUW1-Port` lines in that file, `2 red_only`, `1 blue_red`, `0 blue_only`, also agree with this note.
- `single_cam_red_noDMD_nocom10.cfg` has no CSU-W1 device, so only `LappMainBranch1` 1 is applied. The port keeps the previous session's value,
  so if it was left at State 0 (blue only), no light reaches Kinetix_red.
