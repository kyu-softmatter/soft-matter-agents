# UI screens and behaviour specification (T-004)

Author: AF executor 5 (2026-10-01). The code it is based on is, at `main` 6ba1bc1, `scripts/launcher.py`,
`scripts/live_focus.py`, `scripts/edge_track.py`, `scripts/focus_servo.py`, `scripts/scan_4x.py`,
`scripts/mm_grab.py` (deleted in R-05; in the history). Operating rules are in `docs/runs/2026-09-30_substrate-scan.md` §2; design rules and
functional requirements are in `docs/PLAN.md` (§1–4 at v0.2, §3·5·6·7 at v0.9) §2·5·6·8. Per-operation details are in
`docs/operations-spec.md` (T-006, merged into main).

This document serves two purposes.

- The specification of the UI implementation after decision D1 (WP-D and the F1–F5 screens).
- An input to the design of `engine/events.py` in T-002 (executor 1). §4 is that input.

D1 was settled as a local web app (FastAPI server + React browser screens) (relayed by the manager, due in PLAN v0.3).
Screen layout is written independently of the toolkit, and the engine mapping table (§4) adds the transport (REST / WebSocket).
Screen area names are v0.3's `console`, `hardware`, `sample`, `map`, `objective`, `live` (1.0).
Details of plan / preflight / run / abort for each operation follow executor 4's `docs/operations-spec.md` (T-006),
and this document records only how a screen calls that operation and what it shows.

Notation:

- Code names and UI strings are quoted in English as they are. Example: `"Start live view"`.
- Coordinate `sum` = Ti2 XYStage/ZDrive + piezo, µm (`live_focus.py::sample_xyz`). The sign of the piezo axes
  has not been verified yet.
- **(proposed)** marks a command/event that is not in the T-002 task file's list and that this document proposes as new.

---

## 1. Screen list

### 1.0 Screen areas (v0.3) and how the current screens map onto them

Each area is implemented as `server/api/<area>.py` and `web/src/features/<area>/` (relayed by the manager).
Every screen carries a common status bar (lighting, running operation, connection state, whether remote).

| Area | What it holds | What comes from the current screens | New features |
|---|---|---|---|
| `live` | live image, ROI, focus verdict, metric traces, status bar, frame save | 1.2 (a) (b) (c) (f), 1.3 scan preview, 1.4 | — |
| `map` | XY map, boundary points and circle fit, edge tracking, 4x scan and its results | the map and hole lines of 1.2 (d) (e), the tracking settings of launcher Step 1, Step 2 | F4 mosaic, particle candidates, flags, click-to-move |
| `sample` | choosing a sample · creating a new one · its folder, sample record summary | launcher Sample, the sample line of 1.2 (e), `n` | F3 geometry, loading check |
| `hardware` | reading device state, turning lights on and off | launcher Step 0, `"Lights off"`, Step 1's light selection | F2 detection, configuration file, gates |
| `objective` | objective change and 100x focus | `change_objective.py`, `focus_100x.py` (not in the launcher, run by hand) | F5 7 steps, immersion liquid loading |
| `console` | agent questions and record browsing | none | F1 |

Remote rule (relayed by the manager): the server binds only to 127.0.0.1. Remote access is read-only, and commands that move anything or
write records are accepted only from the browser on the microscope PC. The items disabled when remote, per area, are listed in §7.
The server decides by the request's origin; the disabled look on screen is only extra guidance (the same principle as PLAN §6 item 2).

### 1.1–1.4 Current screens

The current screens are four tkinter windows: the launcher, the live view, the 4x scan preview, and the rarely used
ROI live window of `mm_grab.py`. The live view holds six areas in one window.
PLAN v0.2's new screens (F1–F5) are only listed in 1.5 and are specified in §7.

### 1.1 Launcher (`scripts/launcher.py` (deleted in R-05; in the history), window title `"DINO Autofocus"`)

A step-by-step window followed from top to bottom. It holds no hardware logic. Each operation runs in a new console window,
wrapped by `run_logged.py`, and its output is copied to a log file.

| Area | What it shows | Input | Update |
|---|---|---|---|
| Header | `"DINO Autofocus"`, `"Find the sample, then autofocus-scan it. Work top to bottom."` | — | fixed |
| Sample | Sample ID combobox. Names of the subfolders of `SAMPLES_ROOT` (`D:\AutoFocus\samples`), newest first | combo selection · typed entry, `"Open folder"`, `"New"` (empty value = the live view names it from the clock) | the list is re-read each time the combo is opened |
| Step 0 `"Check the microscope"` | `"Read only. The 4x scan needs the 4x objective in place."` | `"Show objective / Z / PFS"` | — |
| Step 1 `"Find the sample: live view + edge trace"` | light radio buttons, Aura line/percent, Exposure, Hole diameter, Trace speed, key hint text | radio `"Brightfield (DiaLamp): to find the hole edge"` / `"Aura line"`, line combo (`GREEN` only), `%` (default 1), Exposure (default 12 ms), Hole diameter (default 6 mm), Trace speed (default 100 µm/s), `"Start live view"` | changing the light switches the default exposure 12 ms ↔ 500 ms (`light_changed`) |
| Step 2 `"Autofocus scan at 4x (Aura GREEN 1 %)"` | Exposure (empty value = auto), hint text | Exposure, checkbox `"Dry run: only print the tile plan"`, `"Start 4x scan"`, `"Show scan result (mosaic + z map)"` | — |
| Other | — | `"Lights off (Aura + DiaLamp)"`, `"Try the demo (no hardware)"` | — |
| Status bar | `"Idle."`, `"Checking that the microscope is free ..."`, `"Started <label> (log: <file>)"`, `"Running: <labels>"`, `"Not started."` | — | 1 s polling (`poll`) |

Rules for running an operation (`Launcher.run`):

- A hardware operation is refused while another hardware operation launched by the launcher is still alive.
- Then `hardware_users()` reads process command lines through PowerShell to find microscope programs
  (`HW_MARKERS`: live_focus, scan_4x, Micro-Manager, NIS-Elements, etc.). If it finds one, it asks whether to continue.
- The log is written inside the sample folder if there is one, otherwise in `outputs/launcher_logs/`,
  as `launcher_<label>_<stamp>.log`.
- Stopping is Ctrl+C in each console. The script's own `finally` turns the lights off.

### 1.2 Live view (`scripts/live_focus.py` (deleted in R-05; in the history), window title `"Kinetix_red full sensor -- focus score"`)

One window made of three columns across and a status bar below.

```
+----------------------+------------------------------+----------------------+
| (a) image            | (b) gauge  | (c) 2 traces    | (d) XY map           |
|  full frame + ROI    |            |                 | (e) position, sample |
+----------------------+------------------------------+----------------------+
| (f) status bar                                                             |
+----------------------------------------------------------------------------+
```

| Area | What it shows | Update |
|---|---|---|
| (a) Image | The 2400 × 2400 full frame, mean-binned to at most `--display` (800 px) and stretched to 8-bit at the 0.5–99.8 percentiles (`bin_for_display`). The `--score-roi` (518 px) orange square in the middle = the ROI the metric is read from. With a head loaded, DINO tile (224 px) outlines: valid (`p_valid ≥ 0.5`) as solid blue with a dz number such as `+1.3`, invalid as dashed grey with `?` | on every kept frame (`--fps`, default 10 fps) |
| (b) Focus gauge (`Gauge`) | `"Focus score"`, `"depths of field"`. A −10..+10 DoF vertical scale, a ±1 DoF green band, a marker and sigma bar, a number (`+1.2`), a note (`"box: 3/4 tiles, sign unsure, offset +0.5"`, `"no head loaded (--head)"`, `"no readable sample in view"`, in the demo `"demo value, not a measurement"`). The value is the median of the last 5 readings | when a reading from the score thread arrives (asynchronous, tens of ms) |
| (c) Trace 1 (`Trace`) | `"Sharpness, centre 518 px"`: Brenner of the orange ROI. Auto-scaled, min/max/current value as text | on every kept frame. Length `--history` (30 s) × fps points |
| (c) Trace 2 | `"z_sum = ZDrive + piezo z (um)"` | same |
| (d) XY map (`XYMap`) | Title `"Sample map (stage um)    b: mark edge   u: undo"`. Visited-field squares (coloured by score: \|s\| ≤ 1 green, ≤ 3 blue, otherwise grey), boundary points (red dots), with 3 or more boundary points a circle fit (outlier removal at 8 or more, `robust_circle`) and its centre ×, with 2 a line, the current field of view (orange square + cross), scale `"<span> um across   +stage x ←  +y ↓"`. By default both x and y are drawn flipped (joystick direction) | 0.5 s |
| (e) Position·sample text | A table of x, y, z for Ti2 / piezo / sum. Sample ID and `"(n: new sample)"`, objective label, field of view in µm, number of map fields, boundary extent, hole centre · diameter · rms · point count, how many µm the current position is from the centre and how many µm inside the edge, `"(piezo not read)"`. Key hints and progress state: `"edge track: <status>"`, the tare offset if a head is loaded, `"piezo: <status>"` (servo), `"piezo focus: <status>"` (sweep), the read region | 0.5 s |
| (f) Status bar | `" shown 9.8 fps (camera 33.1)   mean 812  max 4095  sat 0.02%   x … y … z … um   REC"` | on every kept frame |
| Console (stdout) | key refusal reasons, start/stop, boundary point coordinates, tare results, tracker event JSON and more, from 25 `print` calls | when they happen |

Progress strings are each routine's `.status`. Examples: edge tracking `"calibrating"`, `"tracking 400 um/s  path 3.20 mm  …"`,
`"coasting on fitted circle (1/3)"`, `"stopped: <why>"`. Servo `"probing +0.5 um"`,
`"step 3: score +1.20 -> moving -0.240 um"`. Autofocus `"fine scan around 9.94 um"`,
`"peak beyond the scan: extending"`, `"Vollath flat: probing with DINO at -2 / +2 um"`.

Records the live view writes outside the screen (not screen items, but the basis for the events in §4):

| Record | Content | Interval |
|---|---|---|
| `track_<stamp>.jsonl` | A header (`header`, `sample`), then per frame the position, `sample_um`, score, score_raw, score_offset, sharpness, mean, max, sat_pct. Tracker, servo and sweep events go in the same file | every kept frame + events |
| `map.json` | `visits` (latest 20000), `boundary` | when boundary points change, and when `sample.json` is saved |
| `sample.json` | hole fit, boundary extent, number of visited fields, objectives used, stage-camera calibration, per-objective tare offset, config, camera | 10 s, and on tare and on window close |
| `--record` | `video_<stamp>_uint16_<h>x<w>.raw` (11.5 MB/frame) + `_meta.jsonl` | every kept frame |
| `autofocus_*.json`, `zsweep_*.json` | piezo autofocus and sweep results | when the routine ends |

### 1.3 4x scan preview (`scripts/scan_4x.py::Preview` (deleted in R-05; in the history), window title `"scan_4x preview"`)

A window the scan loop updates directly. `--no-preview` turns it off. Closing the window removes only the preview;
the scan continues.

| Area | What it shows | Update |
|---|---|---|
| Image | the grabbed frame, binned to at most 700 px + percentile stretch | every snap |
| Curve | `"<tile>: Vollath F4 vs ZDrive (um)"`: scatter plot of the current tile's sharpness against ZDrive | every snap |
| Text line | `"<tile>  (k/n)   ZDrive 3048.70 um   Vollath 0.1234   max 2043/4095   exp 994 ms"` | every snap |

### 1.4 ROI live window (`scripts/mm_grab.py::live` (deleted in R-05; in the history), window title `"Kinetix_red centre ROI -- 's' saves a frame"`)

The 518 px centre ROI and one line of text. `s` saves the current frame as `.npy` and its position as `.json`.
It is not connected to the launcher. In the new UI it is absorbed into the live view's frame-save command (2.1, 4.2).

### 1.5 PLAN v0.2's new screens (no code yet)

Specified in §7. The UI shell (WP-D) puts these places in the navigation.

| Screen | Function | Work package |
|---|---|---|
| Agent console | question entry, past questions, simulation·experiment status/plans/results (F1) | WP-F |
| Hardware | detection results, `hardware_profile.json`, on/off per gate and the reason when off (F2) | WP-G |
| Sample loading | geometry entry, loading check (F3) | WP-H |
| Sample map | transmitted-light mosaic, particle candidates, flags, click-to-move (F4). An extension of 1.2 (d) | WP-I |
| Magnification change | XY escape, objective rotation, immersion liquid loading, return (F5) | WP-J |

### 1.6 Update interval summary

| Interval | What | Basis |
|---|---|---|
| 10 ms | emptying the camera buffer (`tick`) | `root.after(10, tick)` |
| 1 / `--fps` (100 ms) | frame keeping, image, traces, status bar, track record | based on the camera timestamp `ElapsedTime-ms`. If it falls more than one interval behind, it re-aligns rather than emitting the backlog |
| asynchronous | DINO reading and gauge | score thread. Hands over only the latest frame and does not queue |
| 0.5 s | position reading, re-reading the objective label and pixel size, redrawing the map and text | `pos_t`, `map_t` |
| 1 s | launcher status bar | `poll` |
| 10 s | saving `sample.json` | `save_t` |

The new UI carries these intervals over unchanged as engine event intervals (4.1). The screen only receives events and draws them.

---

## 2. Input list

### 2.1 Live view key bindings (`live_focus.py`)

Every key bound on the whole window (`root.bind`). Case-sensitive.

| Key | Action | Conditions and refusal text | Hardware | Engine command (4.2) |
|---|---|---|---|---|
| `b` | adds the current `sum` position as a boundary point and saves `map.json`. Console `"boundary point N: x … y … um"` | only when x, y are finite | none (read only) | `start("boundary_mark")` |
| `u` | deletes the last boundary point, saves | when there are boundary points | none | `start("boundary_undo")` |
| `n` | closes the current sample (saves `sample.json`) and makes a new sample ID from the clock | refused while tracking: `"stop edge tracking before starting a new sample"` | none | `start("sample_new")` |
| `t` | starts edge tracking. If it is running, stops it (`"stopped by key"`) | refused in the demo: `"edge tracking needs the real stage"` | **XY relative move** (`setRelativeXYPosition`) | `start("edge_trace", …)` / `abort` |
| `+`, `=`, numpad `+` | tracking speed × 2 (upper limit 1000 µm/s) | — | if running, from the next step | `update(op_id, {"speed_um_s": v})` (T-011) |
| `-`, numpad `-` | tracking speed × ½ (lower limit 10 µm/s) | — | same | same |
| `Esc` | stops edge tracking, servo and sweep, all of them (`"stopped by Esc"`) | — | sweep and autofocus return to the start z | `abort` (every running operation, 4.4 item 2) |
| `f` | starts/stops the piezo focus servo | needs the piezo and a head: `"focus servo needs the piezo (COM4) and a focus head (--head)"`. While tracking, `"stop edge tracking first"` | **piezo Z move** | `start("piezo_servo")` / `abort` |
| `w` | starts/stops piezo autofocus (Vollath peak, direction from DINO when far off) | needs the piezo and a head: `"piezo focus needs the piezo (COM4) and a focus head (--head)"`. While tracking or servoing, `"stop edge tracking / focus servo first"`. A creation failure gives `"<kind> not started: <exc>"` | **piezo Z move** | `start("piezo_autofocus")` / `abort` |
| `W` | diagnostic z sweep: 10 µm centred on the current position, at 0.25 µm spacing | same as `w` | **piezo Z move** | `start("piezo_zsweep")` / `abort` |
| `z` | tare: takes now as in focus and stores the median of the raw scores over the last 2 s as the current objective's offset | with fewer than 3 readings, `"tare: fewer than 3 readings in the last 2 s; nothing changed"` | none | `start("score_tare")` |
| `Z` | deletes the current objective's tare | — | none | `start("score_tare_clear")` |
| `o` | switches the DINO read region: orange box first ↔ full frame | — | none | `update(live_op_id, {"read_region": "box_first" or "frame"})` (T-011) |

While `w`, `W` run, the position is checked every frame. If ZDrive moves more than 0.3 µm or XY more than 2 µm, the run
stops with `"ZDrive moved by hand (+0.42 um) during the run"`. This check moves into an engine guard (4.3).

The live view has no frame-save key. Saving is only `--record` (continuous recording) and `mm_grab.py`'s `s`.
The new UI has `"Save frame"` as a live view command: `start("frame_save")` **(proposed)**.

Window close (`finally` order): stop edge tracking → stop servo and sweep → stop continuous acquisition → stop the score thread
→ Aura off if `--aura` was used and not `--leave-light-on` → close the sample → close the piezo → close the recording files.
**DiaLamp is not turned off** (operations record §4 item 4). In the web UI closing a tab does not stop the engine, so
turning the lights off falls to each operation's `finally` and to the server shutdown path (end of 4.2, §5).

### 2.2 Mouse

| Screen | Now | New UI |
|---|---|---|
| Launcher | buttons, comboboxes, radio buttons, entry fields, checkboxes (table in 1.1) | the same items as a form |
| Live view | **no mouse bindings** (there are no `<Button…>` bindings in the code). Everything is done with keys | a button next to each key in 2.1. The keys stay as shortcuts |
| 4x scan preview | window close = hides only the preview (`WM_DELETE_WINDOW`) | a panel inside the scan screen |
| XY map | no clicks | click-to-move (F4.3) and flags (F4.4) are new features (§7) |

### 2.3 Live view command-line arguments (`live_focus.py`)

`live.x` in the "In the new UI" column is a proposed argument name for `start("live", args)`. Screen-side display settings are written as "UI".

| Argument | Default | What it does | In the new UI |
|---|---|---|---|
| `--exposure` | 30 ms | camera exposure | `live.exposure_ms` |
| `--fps` | 10 | display and record keeping interval | `live.fps` |
| `--display` | 800 px | display binning size | UI (fitted to the screen size) |
| `--score-roi` | 518 px | centre metric ROI and the orange box | `live.roi_px` |
| `--history` | 30 s | trace length | UI |
| `--record` | off | records the kept frames as raw + meta | `live.record` |
| `--out` | `D:\AutoFocus\frames` | recording folder | `live.record_dir` (default: under the sample folder) |
| `--demo` | off | Micro-Manager demo devices | engine backend selection (`mock` / `mm-demo` / `mm-real`). Not an operation argument |
| `--screenshot` | none | saves the window as PNG after 3 s and exits (for checking the layout) | UI test tool (`tests/ui/`) |
| `--config` | `single_cam_red_noDMD_nocom10.cfg` | Micro-Manager config | engine backend setting |
| `--set DEVICE PROPERTY VALUE` | none, repeatable | writes a property and confirms it by reading back, before the lights come on. The launcher uses it for the light selection | **Removed from the UI.** Lighting is the `light_set` semantic command (4.3). Arbitrary property writes are not exposed |
| `--aura LINE PERCENT` | none | turns an Aura line on (permille = percent × 10), turns it off on close | `start("light_set", {"mode": "aura", "line", "percent"})` |
| `--leave-light-on` | off | does not turn Aura off on close | **Removed.** Lights go off on every exit path (PLAN §6 item 5) |
| `--piezo` | `COM4` | piezo read address (`''` = do not open) | engine backend setting |
| `--sample` | new ID | the sample to continue in | `start("sample_open", {"sample_id"})` |
| `--samples-root` | `D:\AutoFocus\samples` | sample root | engine setting (`sample.py`'s root argument) |
| `--head` | none | DINO head path (torch, uv environment) | engine focus setting (WP-E). Without it the verdict panel shows `"no head loaded"` |
| `--tiles` | 4 | DINO tiles per frame | engine focus setting |
| `--score-offset` | none | a DoF offset that overrides the tare | **Removed.** Tare only through the `score_tare` command and the sample record |
| `--hole-diameter` | none | expected hole diameter in mm (stabilises the circle on a short arc) | `edge_trace.hole_diameter_mm` (operations-spec §8). The default comes from the sample geometry (F3) |
| `--track-speed` | 100 µm/s | tracking start speed (max 1000) | `edge_trace.speed_um_s` |

The launcher has only one argument, `--screenshot` (saves after 1.5 s and exits).

### 2.4 Commands the launcher buttons produce

| Button | Command it runs now | Validation | Engine command |
|---|---|---|---|
| `"Open folder"` | `explorer <sample folder or root>` | — | UI-local action (no engine) |
| `"New"` | clears the sample field | — | `start("sample_new")` |
| `"Show objective / Z / PFS"` | `change_objective.py --status` | hardware occupancy check | `start("status")` |
| `"Start live view"` (brightfield) | `live_focus.py --exposure E --hole-diameter D --track-speed S [--sample ID] --set Aura State 0 --set DiaLamp State 1` | number check | `start("light_set", {"mode": "brightfield"})` then `start("live", {"exposure_ms": E})` |
| `"Start live view"` (Aura) | the same front part + `--set DiaLamp State 0 --aura LINE PCT` | number check | `start("light_set", {"mode": "aura", "line": LINE, "percent": PCT})` then `start("live", …)` |
| `"Start 4x scan"` | `scan_4x.py --sample ID [--exposure E] [--dry-run]` | `sample.json` required, number check, a confirmation dialog unless it is a dry run | `start("scan_4x", {"sample_id", "exposure_ms": E or null, "dry_run"})` |
| `"Show scan result (mosaic + z map)"` | `plot_scan.py <latest scan4x_*>` in the uv environment | `sample.json` required, a finished scan required | not an engine command. The UI reads the record and draws it (4.1) |
| `"Lights off (Aura + DiaLamp)"` | `lights_off.py` | hardware occupancy check | the `lights_off` command (a command kind in events.py, not a `start`) |
| `"Try the demo (no hardware)"` | `live_focus.py --demo` | — | opens the engine with backend `mock` and runs `start("live")` |

The launcher's error and confirmation strings (gathered into dialog points in §3):

- `"Sample '<id>' has no sample.json yet.\nTrace the hole edge in brightfield live view first (Step 1)."`
- `"<name>: '<value>' is not a number."`
- `"<label> is still running; close it first."`
- `"Another program seems to be using the microscope: … Start anyway?"`
- `"Start 4x scan"` confirmation: whether the 4x objective is in place, and whether the hole was re-traced in brightfield this session
- `"No finished 4x scan in <id> yet."`

---

## 3. Confirmation dialog points

### 3.0 Principles

- **The engine decides when to ask.** Every confirmation that touches hardware starts as an engine `confirm_required` event,
  and the screen draws it and then sends `confirm(op_id, key, answer)`. The screen does not make up hardware
  confirmations of its own. Screen-only confirmations (3.2) are only the ones that touch no hardware.
- **A dialog is an extra confirmation.** Even after a "yes", the engine's guards and gates still run (PLAN §5).
  Conversely, there is no setting that skips a dialog.
- **There is no time limit** (T-011). While it waits, the dialog always holds an `"Abort"`.
- **It survives reconnection.** Pending confirmations are in `/api/state`, so opening a new tab or
  reconnecting brings the same dialog up again.
- **Remote screens and users without permission only watch.** Instead of a dialog they show a `"Waiting for the operator at the
  microscope PC: <prompt>"` band. There are no answer buttons.
- **The wording is the engine event's `prompt`, unchanged.** The strings below are copied from item 7 of `docs/operations-spec.md`,
  and the authoritative versions are that document and the engine. The screen adds the values in `context` (plan, current values) as a table.
- **Answers are recorded.** Who chose what, and when, is kept in the operation record and the audit log (PLAN §6 item 12).

### 3.1 Points where the engine asks

| # | Operation | When | Wording (operations-spec) | Options | Screen | Now |
|---|---|---|---|---|---|---|
| C1 | `scan_4x`, `sample_map` | before start | `"start scan_4x"` + plan | `"Start"` / `"Cancel"` | modal. Grid (n × m tiles), box, moving axes (XY, ZDrive), lights turned on, expected time | launcher `askokcancel` (2.4) |
| C2 | `scan_4x`, `sample_map` | the hole fit is not from this session | `"hole fit is from <time>; re-trace?"` | `"Re-trace now"` / `"Cancel"`. A third button only when the engine offers `"Use anyway"` as an option | modal. Fit time, previous centre and diameter. `"Re-trace now"` goes to edge tracking in the `map` area | only the question in the launcher's wording |
| C3 | `scan_4x`, `sample_map` | the first move comes in from outside the Z window | `"ZDrive <z> -> <z_guess>"` | `"Move"` / `"Cancel"` | modal. Current Z (encoder), target Z, difference in µm | none (on 9/30 it started at 62.9 µm) |
| C4 | `edge_trace` | a previous boundary exists | `"replace the hole fit from <fitted_at>? (backed up)"` | `"Replace"` / `"Cancel"` | modal. Backup file name | none (on 9/30 backed up by hand) |
| C5 | `edge_trace` | start | `"trace the edge: XY moves only, within 7 mm of here"` | `"Start"` / `"Cancel"` | modal. Start XY, speed, expected diameter | none (the `t` key starts at once) |
| C6 | `objective_change` | before start | `"rotate <label_now> -> <label_target>: retract Z, move Y <dy>, rotate"` + plan | `"Rotate"` / `"Cancel"` | modal. The 7-step plan (7.5) | on 9/30, explicit approval in chat |
| C7 | `objective_change` | step 5 | `manual_step: load_immersion` | `"Loading done"` | **Not a modal.** A large button on the step card in the `objective` area. The immersion type (oil / water) and who pressed it when are recorded. This answer is the approval for steps 6 and 7 | a person runs `--return-only` after the oil |
| C8 | `objective_change` | when changing to a dry objective (`escape=False`) | `"objective rotated; continue to approach Z?"` | `"Approach"` / `"Stop here"` | step card | none |
| C9 | `focus_100x` | the peak is at the top end of the sweep | `"peak at the top end of <lo>-<hi>; extend upward to <new_hi>?"` | `"Extend upward"` / `"Stop"` | modal. Sweep curve, new range, ceiling. The new range does not exceed the ceiling | the script stops and a person re-runs it (`no_climb_without_ok`) |
| C10 | `focus_100x` | no immersion loading recorded this session | `"no immersion loading recorded this session; oil applied?"` | `"Oil applied"` / `"Cancel"` | modal | none |
| C11 | `focus_100x` | the centre is above the 4x focus | `"centre <c> is above the 4x focus <z4>; 100x focus is usually 60-100 um below"` | `"Use this centre"` / `"Change centre"` | modal. 4x focus, the entered centre, the ceiling | warning in the script's header |
| C12 | `goto_xy` | a move that needs a Z retract | `"retract Z <z> -> <z_safe>, then move to (x, y)"` | `"Retract and move"` / `"Cancel"` | modal. Target shown on the map (7.4) | none (new feature) |
| C13 | engine start | another program seems to be using the microscope | (proposed) `"Another program seems to be using the microscope: <list>"` | `"Continue read-only"` / `"Retry"` | full-screen notice. This confirmation is per engine, not per operation (operations-spec 0.3) | launcher `askyesno` (`"Start anyway?"`) |

Why C2's default options do not include "use it as is": the operating rule is "an old hole fit is not reused without
re-tracing" (on 9/30 it moved 1.5 mm). If the engine decides to allow an exception, that option arrives in the event's
`options`.

### 3.2 Screen-only confirmations (no hardware)

| # | Point | Wording | Options | Notes |
|---|---|---|---|---|
| U1 | switching samples (`sample_open`, `sample_new`) | `"Close sample <id> and open <new_id>?"` | `"Switch"` / `"Cancel"` | The engine's refusal comes first. During edge tracking or `awaiting_return` it arrives as `preflight_failed`, and no dialog appears |
| U2 | undoing boundary points several times (`u`) | none | — | It removes one at a time, directly, without confirmation. `boundary_reset` (all of them) goes through C4 |
| U3 | deleting a flag | `"Retire flag <name>? It stays in the record."` | `"Retire"` / `"Cancel"` | Not deleted; `retired_at` is attached (operations-spec 6.2) |
| U4 | changing the geometry after the loading check | `"Geometry changed after loading was confirmed. Confirm loading again?"` | `"Change and re-check"` / `"Cancel"` | Coverslip thickness and orientation feed later safety limits (PLAN F3). The engine decides the re-confirmation state |
| U5 | leaving a screen with a form being filled in | `"Discard unsaved changes?"` | `"Discard"` / `"Stay"` | geometry, hardware human-confirmed items |
| U6 | sending a question (F1.1) | `"Send this question to <agent> (mock store)?"` | `"Send"` / `"Cancel"` | mock store only. The real store is read-only, so the button is off (7.1) |

Login, account approval, handing over control of the equipment, and confirming Claude proposal cards are outside this document's scope
(T-018, T-013, T-014). The screens in this document use their results (role, control) only as disabled reasons (7.0).

---

## 4. Engine mapping table

### 4.0 Conventions

The command/event list in the T-002 task file is used as it is, and only what the screen needs and the list lacks is added as **(proposed)**.
Every command and event is a JSON-serialisable dataclass (PLAN §6 item 7). The common fields
`kind`, `t`, `op_id` are omitted from the tables.

**Transport** (for the web app). The common paths are the names T-009 (server skeleton) set. The per-area `GET` paths are proposals.

| Kind | Transport | Path | Remote |
|---|---|---|---|
| Commands `start` / `abort` / `confirm` / `lights_off` / `update` | REST `POST`; the response is the acceptance result (`op_id` or a refusal reason). Results arrive as events | `POST /api/commands` (T-009) | **Refused** (403). Exception (D13): on this PC (loopback) `abort` and `lights_off` are accepted without login. From remote only a logged-in user's `abort` is accepted, and everything else, including a remote `lights_off`, is refused (PLAN §6 item 12) |
| Events (everything in the table below) | WebSocket, one JSON line each | `/ws/events` (T-009) | allowed (subscribe only) |
| Live video | WebSocket, binary JPEG (about 800 px, binned on the server, target 10 fps per camera) + that frame's `frame_id` and `camera`. With dual cameras both arrive on the same socket, and the screen shows them side by side, merged (blue as green, red as magenta), or one at a time | `/ws/frames` (T-009) | allowed |
| Reading the current state in one go (right after connecting, after reconnecting) | REST `GET`, engine `snapshot()` | `/api/state` (T-009) | allowed |
| Reading records (sample list, `sample.json`, scan results, one raw frame) | REST `GET` | `/api/<area>/...` (proposed, `server/api/<area>.py`) | allowed |

`/api/state` is where a screen that missed events re-syncs. It holds the position, objective, lighting, the running operation and its last
`progress`, the open sample, and any pending `confirm_required`.

**Commands**

Every command carries `origin` (`"human"` / `"assistant"`) (T-011 v0.4 adjustment). Every input in this document is
a human's input, so it is `origin="human"` and goes straight in as `confirmed`. Claude proposal cards (`proposed` →
human confirmation) are T-013 / T-014's screens.

| Command | Arguments | Use |
|---|---|---|
| `start` | `op` (operation name), `args` (dict) | starts every operation. Record operations that do not move hardware (boundary points, tare, opening a sample) go the same way too, so that they leave a record (PLAN §6 item 4). Turning the lights off is not a `start` but a separate command kind, `lights_off` (row below) |
| `abort` | `op_id` (if absent, everything running), `why` | `Esc`, stop button |
| `confirm` | `op_id`, `key`, `answer` (`"yes"` / `"no"` or a chosen value) | the user's answer to `confirm_required`. The kind `manual_step` (F5 `"Loading done"`) is kept as a manual step record (T-011) |
| `lights_off` | none | **Pre-emptive**: aborts the running operation and confirms by readback that every light is off (T-002 Appendix 3, `COMMAND_KINDS` in `engine/events.py`). On this PC it is accepted even without login. From remote it is refused (D13, PLAN §6 item 12) |
| `update` (T-011) | `op_id`, `args` (dict of the arguments to change) | changes a running operation's declared arguments. Used now for: tracking speed (`+`/`-`), live read region (`o`), live exposure. Anything outside the declaration gets a refusal event |

Why `update` is needed: the tracking speed is changed without stopping the operation. Imitating it with `abort` + `start`
would mean redoing the calibration (`cal_result`).

**Operation names** (`start.op`)

| Operation | Hardware | Source | Details |
|---|---|---|---|
| `status` | read | `change_objective.py --status` | operations-spec |
| `live` | continuous camera acquisition, position reading | the acquisition loop of `live_focus.py` | this document 4.1, 4.4 |
| `light_set` **(proposed)** | lighting (semantic units: brightfield / Aura line / off) | the launcher's `--set`, `--aura` | 4.3 |
| (`lights_off`) | lights off + readback | `lights_off.py` | operations-spec. Not an operation name but a command kind (command table above) |
| `edge_trace` | XY relative move | `edge_track.py::EdgeTracker` | operations-spec |
| `scan_4x` | XY, Z, lighting | `scan_4x.py` | operations-spec |
| `objective_change` | Z retract, objective rotation, (F5) XY escape/return | `change_objective.py` | operations-spec, §7 F5 |
| `focus_100x` | Z sweep, lighting | `focus_100x.py` | operations-spec |
| `piezo_servo`, `piezo_autofocus`, `piezo_zsweep` **(proposed)** | piezo Z | `focus_servo.py` (`f`, `w`, `W`) | the `focus_servo` judgement in operations-spec (may be outside the M1–M3 scope) |
| `sample_open`, `sample_new` **(proposed)** | none | `--sample`, `n`, launcher Sample | 4.2 |
| `boundary_mark`, `boundary_undo`, `boundary_reset` **(proposed)** | none (position read) | `b`, `u`, the boundary backup before re-tracing | 4.2, §5 |
| `score_tare`, `score_tare_clear` **(proposed)** | none | `z`, `Z` | 4.2 |
| `frame_save` **(proposed)** | none (latest frame) | `s` of `mm_grab.py` | 4.2 |

**Events** (T-002 list + proposals). The fields are the minimum set, by what the screen uses.

| Event | Fields | Where the screen uses it |
|---|---|---|
| `planned` | `op`, `plan` (dict: tile grid, sweep range, ceiling, etc.), `dry_run` | plan preview on the scan and focus screens, dry-run results |
| `preflight_ok` / `preflight_failed` | `op`, `checks`: `[{name, ok, want, read, why}]` | the check list next to the start button. Failed items and their reasons shown as they are |
| `started` | `op`, `args`, `start_state` (position, objective, lighting readback) | status bar `"Running: …"`, progress panel |
| `progress` | `op`, `status` (string for people), `step`, `n_steps` (optional), `data` (per-operation dict) | progress string (the `.status` of 1.2), scan tile k/n, tracking path length |
| `frame_ready` | `frame_id`, `shape`, `t_camera_ms`, `t_host`, `exposure_ms`, `pos` (x/y/z, piezo), `stats` (`mean`, `max`, `sat_pct`, `bit_depth`), `source_op` | image (a), status bar (f), scan preview. **Pixels are not put in the event** (4.4 item 1) |
| `reading` | `source` (`"classical"` / `"model"`), `metric`, `value`, `grade` (`"model"` if from the model), `verdict` (5-word vocabulary), `region` (`"box"` / `"frame"` / `"frame (box empty)"`), `frame_id`, `z_encoder_um`, `tiles` (`[{y0, x0, size, valid, verdict}]`) | gauge (b), trace (c), tile outlines (a). Display rules in §5 |
| `position` (engine periodic event, no record folder, T-002 Appendix 3) | `x_um`, `y_um`, `z_um`, `piezo_x_um`, `piezo_y_um`, `piezo_z_um`, `sum_um` ([x, y, z]), read-failure fields (`xy_error`, `z_error`, `piezo_error`) | position table (e), current field of view on the map (d), status bar (f), z trace |
| `light_changed` | `dialamp` (`"on"` / `"off"` / `"unknown"`), `aura` (`state`, `line`, `intensity_permille`), `verified`, `records` (list of readback records) | the lighting indicator on the status bar (§5), the current value of the launcher's light selection |
| `property_set` | `device`, `property`, `wanted`, `read`, `verified` | log panel. `verified=false` is a warning banner |
| `confirm_required` | `key`, `prompt` (English text), `options`, `context` (dict) | dialog (§3) |
| `finished` | `op`, `summary` (dict), `end_state` (lighting readback required), `record_dir` | result display, status bar `"Idle."` |
| `aborted` | `op`, `why`, `end_state` (`awaiting_return` if F5 stops after the escape and rotation, T-011) | progress panel `"stopped: <why>"`. If `awaiting_return`, a waiting-for-return warning on the common status bar (§7 F5) |
| `error` | `op`, `message`, `where` | error banner, log |
| `log` | `level`, `text` | log panel (today the 25 console `print` calls) |
| `objective` **(proposed)** | `label`, `nosepiece_state`, `pixel_um`, `fov_um` | position text (e), map field-of-view size. So that an objective changed by hand shows within 0.5 s |
| `sample_opened` **(proposed)** | `sample_id`, `dir`, `created`, `hole` (including `fitted_at`, T-002 Appendix 3), `calibration`, `objectives_used`, `score_offset` (grade `"model"`) | Sample field, the sample line of the position text, the age of the hole fit (§5) |
| `map_changed` **(proposed)** | `boundary` (list of points), `circle` (`cx`, `cy`, `r`, `rms`, `n`, `arc_deg`) or null, `limits`, `visits_added` (the new visited fields), `n_visits` | map (d), the hole line of the position text |
| `calibration` **(proposed)** | `um_per_px`, `angle_deg`, `M_px_per_um`, `objective` | position text, sample record. Today the tracker's `cal_result` event |
| `live_stats` **(proposed)** | `shown_fps`, `camera_fps`, `kept`, `seen`, `recording` | status bar (f). May also go into `progress(live).data` |

### 4.1 Screen item → event

| Screen item | Event received | Interval (1.6) | Notes |
|---|---|---|---|
| (a) image | `frame_ready` + preview channel (4.4 item 1) | fps | binning and stretching are done by the engine-side preview generator (JPEG for the web) |
| (a) orange ROI | `started(live).args.roi_px` | at start | — |
| (a) tile outlines | `reading(source="model").tiles` | asynchronous | a verdict mark instead of a number (§5) |
| (b) gauge | `reading` | asynchronous | the median of 5 is computed by the engine (WP-E) and emitted as one `reading`. The UI does not average |
| (c) sharpness trace | `reading(source="classical", metric="brenner")` | fps | today the UI computes Brenner. Moved into the engine |
| (c) z trace | `position.sum_um[2]` | 0.5 s (today the same value is re-plotted every frame) | encoder value |
| (d) map | `map_changed`, `position`, `objective` | on change, 0.5 s | visited fields are added by the engine every 0.5 s (`XYMap.add` rule: same objective and within ¼ of the field of view means update) |
| (e) position table | `position` | 0.5 s | — |
| (e) sample·objective·hole lines | `sample_opened`, `objective`, `map_changed` | on change | "how many µm from the centre" and "how many µm inside the edge" may be computed by the UI from `position` and `circle` (a display calculation, not a safety judgement) |
| (e) progress line | `progress(op).status` | on change | one line per operation |
| (f) status bar | `frame_ready.stats`, `live_stats`, `position`, `light_changed` | fps | adds the lighting state (§5) |
| scan preview | `frame_ready(source_op="scan_4x")`, `progress(scan_4x).data` (`tile`, `k`, `n`, `z_um`, `vollath`) | every snap | the curve points come from `progress.data` |
| scan result (mosaic + z map) | `finished(scan_4x).record_dir` → the UI reads `scan.json` and the tile `.npy` files | at the end | replaces `plot_scan.py`. Read-only |
| launcher status bar | `started`, `finished`, `aborted`, `error` | on change | the 1 s polling is no longer needed |
| log panel (new) | `log`, `property_set`, `error` | when they happen | today's console windows |

### 4.2 Input → command

Every row is REST `POST /api/commands` and is refused from remote (the transport table in 4.0).
Results arrive on `/ws/events`.

| Input | Area | Command | Arguments | Expected events |
|---|---|---|---|---|
| launcher sample selection / `--sample` | `sample` | `start("sample_open")` | `sample_id` | `sample_opened`, `map_changed` |
| `"New"` / `n` | `sample` | `start("sample_new")` | — | `finished` for the current sample, a new `sample_opened`. While tracking, `preflight_failed` (`"stop edge tracking before starting a new sample"`) |
| `b` | `map` | `start("boundary_mark")` | none (the engine reads the current position) | `map_changed`. `preflight_failed` if the position is not finite |
| `u` | `map` | `start("boundary_undo")` | — | `map_changed` |
| re-trace (new, §5) | `map` | `start("boundary_reset")` | — | backs up `map.json`·`sample.json` (`*_before_rescan_<stamp>.json`), then clears only the boundary, `map_changed` |
| `"Start live view"` | `hardware` → `live` | `start("light_set")` → `start("live")` | 4.0, 2.3 | `light_changed`, `started`, `frame_ready` … |
| `t` | `map` | `start("edge_trace")` / `abort` | `speed_um_s`, `hole_diameter_mm` (2.3) | `started`, `calibration`, `progress`, `map_changed` (per edge point), `finished` / `aborted` |
| `+` / `-` | `map` | `update(edge_trace, {"speed_um_s": v})` | the engine clamps to 10..1000. A step is speed × 0.5 s, 20..200 µm | `progress` (speed and step shown) |
| `Esc` | any area | `abort` | no `op_id` = everything running (except live acquisition: 4.4 item 2) | `aborted` events |
| `f` / `w` / `W` | `live` | `start("piezo_servo" / "piezo_autofocus" / "piezo_zsweep")` / `abort` | 4.0 | `progress`, `reading`, `finished` / `aborted` |
| `z` / `Z` | `live` | `start("score_tare")` / `start("score_tare_clear")` | the engine uses the model readings of the last 2 s | an updated `sample_opened` and a `log`. `preflight_failed` if there are fewer than 3 |
| `o` | `live` | `update(live, {"read_region": …})` | `"box_first"` / `"frame"` | `reading.region` changes from then on |
| `"Save frame"` (new) | `live` | `start("frame_save")` | — | `finished.summary.path` |
| `"Show objective / Z / PFS"` | `hardware` | `start("status")` | — | `finished.summary` (objective, Z, PFS) |
| `"Start 4x scan"` | `map` | `start("scan_4x")` | 2.4 | `planned`, `preflight_*`, `confirm_required` (§3), `progress`, `frame_ready`, `finished` |
| `"Lights off"` | `hardware` (also on the common status bar) | the `lights_off` command (a command kind in events.py, not a `start`) | — | `light_changed`, `finished.end_state` |
| closing the browser tab / server shutdown | — | Closing a tab sends no command. Server shutdown does `abort` (everything) → `lights_off` → close the backend | — | `aborted` …, `light_changed`, the close result (§5) |

On the web, "closing the window" is not engine shutdown. The server's operations continue after a tab is closed. So turning the lights off is not hooked
to closing a tab but to the server shutdown path and each operation's `finally` (§5). What happens when a moving operation runs while the microscope PC's last local tab
is disconnected is 4.4 item 6.

### 4.3 Direct hardware calls inside the UI → into the engine

Every hardware call the current UI process makes directly. The new UI makes none of them directly
(PLAN §6 item 1).

| Now (file: location) | What it does | Where it moves |
|---|---|---|
| `live_focus.py`: `open_core(...)` (`mm_grab.open_core`) | config load, AutoShutter off, exposure, ROI | engine open (backend `open`). Exposure is `live.exposure_ms` |
| `live_focus.py`: `set_and_read` × `--set` (the launcher puts in `Aura State 0`, `DiaLamp State 1/0`) | switches lighting by writing properties | `start("light_set", {"mode": "brightfield" / "aura" / "off", …})`. Uses the backend's semantic methods (`lamp_on/off`, `aura_line_on`, `aura_off`, T-002 Appendix 2), with the readback in `light_changed.records`. Arbitrary `--set` is removed from the UI |
| `live_focus.py`: `aura_on(core, line, pct)`, on exit `aura_off(core)` | Aura on/off | `light_set` / `lights_off`. Lights-off on exit is the engine guard's `finally` (T-002 guards) |
| `live_focus.py`: `setCircularBufferMemoryFootprint`, `startContinuousSequenceAcquisition`, `getRemainingImageCount`, `popNextImageAndMD`, `stopSequenceAcquisition` | continuous acquisition and popping frames, fps thinning | the `live` operation. The thinning rule (by camera timestamp, re-align when behind) moves into the engine too |
| `live_focus.py`: `positions(core, piezo)` 0.5 s | XY, Z, piezo read | the engine emits it as the `position` event |
| `live_focus.py`: `getProperty("Nosepiece", "Label")`, `getPixelSizeUm()` 0.5 s | objective and field-of-view size | the `objective` event **(proposed)** |
| `live_focus.py`: `getImageBitDepth()` | saturation ceiling (12-bit = 4095) | `frame_ready.stats.bit_depth`. `sat_pct` is computed by the engine |
| `live_focus.py`: `PiezoReader(...)` open, read, close | piezo read | backend |
| `edge_track.py`: `EdgeTracker`'s `setRelativeXYPosition`, `getXYPosition`, `waitForDevice` (`t` key) | calibration moves (200 µm per axis) and tracking moves (step ≤ 200 µm) | the `edge_trace` operation. `feed(frame)` receives `live` frames inside the engine. `on_point` → `map_changed`, `cal_result` → `calibration`, `set_speed` → `update`. The stop conditions (edge lost for 3 frames, 7 mm from the start point, one full lap, path 25 mm, 360 s) stay inside the operation as they are |
| `focus_servo.py`: `piezo.move_z(target, window)` of `FocusServo` / `AutoFocusZ` / `ZSweep` (`f`, `w`, `W`) | piezo Z move (start point ±5 µm, 0..600 µm) | the `piezo_*` operations. The window limit becomes a guard. The check for movement by hand (ZDrive 0.3 µm, XY 2 µm) becomes a guard too |
| `live_focus.py`: the `FocusScorer` thread (`dino_autofocus.live`) | DINO reading | the engine focus layer (WP-E `focus/dino.py`) emits `reading(source="model")`. torch only at the point of use |
| `live_focus.py`: `brenner(box)`, `vollath4(box)` | classical metrics | the engine focus layer (WP-E `focus/classical.py`) emits `reading(source="classical")` |
| `live_focus.py`: `raw.write`, `meta.write` (`--record`) | recording | the `live.record` argument. An engine record |
| `live_focus.py`: `Sample`, `XYMap.add/mark_boundary/save`, `track.write` | sample, map and track records | the engine's `sample.py` (T-002) and the record operations above. Only drawing (`XYMap.draw`) stays in the UI |
| `launcher.py`: `hardware_users()` (PowerShell process check) | detecting microscope use by other programs | engine preflight (single core-owner guard + external program check). The result is `preflight_failed` or `confirm_required` (§3) |
| `launcher.py`: `subprocess.Popen(CREATE_NEW_CONSOLE)` + Ctrl+C | a separate process per operation, stopping | engine operations run in the same process (D3). Stopping is `abort`. Log files are engine records |
| `scan_4x.py`: `axis.position_um()`, `core.getExposure()` in `Preview` | preview text | `progress.data`, `frame_ready` |

### 4.4 Questions passed to T-002 / T-011 and how they were resolved

Resolved by the manager (2026-10-01, the T-011 task file at main 2742069):

| # | Question | Resolution |
|---|---|---|
| 1 | the path for frame pixels | T-009's `/ws/frames` handles it (server-binned JPEG, latest only) |
| 2 | live and the "one operation" rule | **Adopted**: continuous acquisition is an engine-owned acquisition stream and does not count toward single ownership. `scan_4x`, `focus_100x` stop the stream when they start and restore it when they finish |
| 3 | record operations | **Adopted**: record operations that do not move hardware (`b`, `u`, `z`, opening a sample) are excluded from single ownership |
| 4 | changing arguments while running | T-011's `update` command |
| 5 | remote `abort` | **Decided (D13)**: remote can send only `abort`. Every other remote command is refused |
| 6 | operations running with every local tab disconnected | **Decided (D14)**: when every connection drops, automatic stop after 10 s (PLAN §7) |

Below is the original text of the questions as written in the draft.

1. **The path for frame pixels.** 2400 × 2400 uint16 is 11.5 MB. The `frame_ready` event carries only metadata and
   the pixels go on a separate channel. The engine holds only the latest frame, and the server's `/ws/frames` bins and stretches it
   (the same way as `bin_for_display`) and sends it as JPEG. Only the latest is kept and nothing is queued (today's score
   thread approach). A slow browser skips frames. If the raw frame is needed, one is fetched with `GET`.
   The engine-side contract needs only `latest_frame() -> (frame_id, ndarray)`.
2. **Conflict between `live` and the "one operation at a time" rule (T-011).** T-011 refuses a new operation command while one is running.
   But today's live view accepts edge tracking (`t`), servo (`f`), sweep (`w`/`W`),
   boundary points (`b`) and tare (`z`) with continuous acquisition on. Tracking and servo run on live frames. Carried over as is,
   `t` would be refused while the live view is on. Recommendation: make continuous acquisition not an operation but an engine-owned **acquisition
   stream**. The stream does not count toward the single-ownership rule, and operations subscribe to the stream's frames.
   Operations that take their own snaps, like `scan_4x`, `focus_100x`, stop the stream when they start and restore it when they finish.
   `Esc` and `abort(no op_id)` do not stop the stream. The alternative is to keep `live` as a background operation
   and have the engine hold a table of operations that may run alongside it. Either way, it has to be decided in T-011.
3. **Whether record operations also go through `start`.** This document proposed sending boundary points, tare and opening a sample through `start`, to leave
   a record. But under the rule in point 2, `b` and `z` would be refused during tracking. For record operations that do not move hardware,
   the recommendation is to exclude them from the single-ownership rule or to bundle them into one separate `sample` command.
4. **Argument declarations for `update`.** Tracking speed (`speed_um_s`), live read region (`read_region`) and live
   exposure (`exposure_ms`) are the names this document uses. Match the names to T-006's `edge_trace`.
5. **`abort` from remote.** Remote is read-only. But it has to be decided whether to allow `abort` alone, so that someone who sees a problem on a remote screen
   can stop it. Stopping is in the direction of less motion, so allowing it is recommended, but it is the user's decision.
6. **Operations running with the local screen gone.** Operations continue after a tab is closed. An operation that needs confirmation
   (waiting on `confirm_required`) can simply stay stopped until an answer comes. For operations a person uses while watching, like edge tracking,
   decide whether they `abort` themselves some time after every local WebSocket drops. The recommendation is "abort 10 s after
   the disconnect", with the time an engine setting.

---

## 5. Enforcing the operating rules on screen

Keeping the rules is the engine's job. The screen (1) shows what a rule blocked, with the reason, (2) makes the required order
visible, and (3) never sends rule-breaking input in the first place. What the screen blocks is guidance; if the same request
comes directly through the API, the engine must block it.

### 5.1 Operating rules of 2026-09-30

| Rule | Basis | Where the engine blocks | What the screen does |
|---|---|---|---|
| **Trace the edge in brightfield, then particle light** | head of §2 of the operations record (`brightfield_edge_then_particle_light`) | `edge_trace` turns Aura off and DiaLamp on at run step 1. `scan_4x` turns on its own light (Aura GREEN 1 %) and turns it off at the end | The `map` area shows the order as steps: `"1  Trace the hole edge (brightfield)"` → `"2  Scan (particle light)"`. The step 2 button is enabled only when there is a hole fit from this session. When it is disabled, `"Trace the hole edge in brightfield first"`. If `t` is pressed while the live view is on with Aura, the C5 dialog states that tracking will switch the light to brightfield |
| **Re-trace every session; no reuse of an old hole fit** | on 9/30 the hole moved 1.5 mm between 18:49 → 19:57 | the `scan_4x`, `sample_map` preflight looks at `hole.fitted_at` (T-002 Appendix 3). C2 if it is from before this session | The hole summary always carries the fit time and state: `"Hole fit 19:57 (this session)"` (normal) or `"Hole fit 18:49, previous session: re-trace before scanning"` (warning colour). "This session" is measured from the start time of the open experiment session (F7, T-019), or the engine start time if there is no session **(proposed: align with T-019)**. The re-trace button shows C4's backup notice first |
| **Do not centre the 100x sweep on the 4x focus** | operations record Step 4. The 100x focus is about 60–100 µm below the 4x focus | `focus_100x` preflight: C11 if the centre is above the 4x focus. Ceiling `min(3200, centre + 0.4 × 130)` | The 100x focus form in the `objective` area fills the centre field **with a computed value, not left empty**: the 4x focal-plane value at the same XY − 60 µm (with `"lab offset, to be re-measured"` beside the value). The 4x focus and the ceiling are shown side by side in the same table. The ceiling line is drawn on the sweep plan plot |
| **Extending upward at 100x needs human approval** | `no_climb_without_ok` | if the peak is at the top end, the operation stops with C9 | The button that extends upward exists only inside the C9 dialog. Raising the range directly in the form is a new run, and it too passes the ceiling and C11 |
| **Wait for immersion liquid loading after objective rotation** | `confirm_oil` | step 5 of `objective_change` stops as a `manual_step` and sends no Z, XY or Nosepiece commands | the C7 step card. While waiting, the common status bar shows `"Waiting: load immersion oil"` so that it is visible from other areas too |
| **Lights off at exit, and show that state** | 9/30 known issue 4 (DiaLamp not turned off) | every operation's exit context does `all_off()` + readback. `lights_off` is pre-emptive | 5.2 |
| **Model verdicts only in the 5-word vocabulary, Z only as encoder values** | PLAN §6 item 3 | Model values do not enter safety judgements. Exception: Live's Z score gauge shows the DoF number (user decision 2026-10-02, display only) | 5.3 |

### 5.2 Lighting state display

- **Always visible on the common status bar.** `"DiaLamp OFF · Aura OFF"` and the time of the last readback. The values
  come only from `light_changed` events. The screen does not guess the lighting state.
- There are three states: off (readback confirmed), on (line and percent, e.g. `"Aura GREEN 1 %"`), unknown
  (`"unknown"` or `verified=false`). Unknown is in a warning colour and shows the raw readback text, as in
  `"Lights not confirmed: DiaLamp read 1, wanted 0"`.
- **The `"Lights off"` button is on every screen's status bar.** `lights_off` is pre-emptive, so it can be pressed even while an operation
  is running. One line beside the button says that pressing it stops that operation (`"stops <op>"`). Locally anyone logged in, including a viewer, can press it,
  and from remote it is disabled (D13: remote can only stop, 7.0).
- **Each time an operation ends**, the result panel adds one line with the lighting readback from `end_state`.
- **Server shutdown.** Closing a web tab is not shutdown (end of 4.2). When the desktop launcher (T-016) stops the server, it leaves the last
  lights-off readback in the launcher window and the app log. The next time the server starts, the first screen shows `"Last shutdown: lights off
  confirmed at <t>"` or the confirmation failure **(proposed)**.

### 5.3 How model output and Z are shown

| Now (live_focus.py) | New screen |
|---|---|
| DoF number on the gauge (`+1.2`), sigma bar, −10..+10 scale | **By the user's decision (2026-10-02) the 9/30 gauge stays as it is**: `"Z score"` in the Live area's Focus panel (`web/src/app/live/FocusGauge.tsx`). A −10..+10 DoF vertical bar, 0 = in focus, +10 above (`above`), −10 below (`below`), ±1 DoF green band, marker, sigma bar, number (`+1.2`), note. A source label is always attached: `"mock truth"` (the true z of the mock world, not a measurement) or `"model"` (the DINO head read with `--head`, median of the last 5). Without a head, `"No DINO head loaded (--head)"`. It is a screen display only and enters no judgement. The verdict badges (`in_focus` … `unsure`) are used unchanged in operation results and on the map |
| note `"box: 3/4 tiles, sign unsure, offset +0.5"` | The gauge note uses the 9/30 format (`"box: 3/4 tiles, sign unsure"`). The tare offset is not applied to the gauge yet. It is kept in the record as `grade: "model"` |
| `+1.3` on the tile outlines | a small mark of the verdict badge on each tile (icon or abbreviation). Unreadable tiles stay dashed grey |
| tare result `"offset +0.52 DoF"` | `"Tared at this focus (objective <label>)"`. The number goes only into the record |
| colours of the visited fields on the map (\|s\| ≤ 1 green, ≤ 3 blue) | colour by verdict: `in_focus` green, everything else one neutral colour. "How far off" is not shown by colour |
| z trace `z_sum` | unchanged. The encoder value from `position` |
| x axis of the sweep curve | each point's `z_readback_um` (not the commanded value). The chosen focus is the encoder z of the nearest actual frame (T-003) |

- **Nowhere on screen is a "predicted Z" or "target Z" shown as a model value.** Z numbers are only the encoder readback,
  values a person entered, and the plan (sweep range, ceiling), and each one is labelled (`"read"`, `"entered"`, `"plan"`).
- Classical metric values (Vollath, Brenner, peak) are measurements, so they may be shown as numbers. The traces and sweep curves are such.
- Numbers Claude gives in an answer are marked `"model"` (PLAN §5 Claude integration). That belongs to the prompt pane (T-014).
- Numbers on agent cards carry the grade the card holds (E1–E5) as a badge, unchanged (7.1). E6 cannot enter a card.

### 5.4 Other on-screen indications that came from 30 September

| Case | Screen |
|---|---|
| Aura flicker (−23 % frames) | the scan progress and results state the number of dropped frames and their z (`dropout_z_um`) |
| A person moved the stage (readback 3037 / 3036) | a guard stop as an `error` banner, stating the cause as it is: `"ZDrive read 3036.0, commanded 3037.0: stopped"`. No guess such as `"moved by hand?"` is added |
| Double peak (not enough oil) | a `"check immersion oil"` warning in the `focus_100x` result (classical verdict). A button to the reload variant (operations-spec 4.2) |
| Saturation | `sat %` on the status bar in a warning colour when it is above 0. `"reduce exposure"` in the sweep result |
| Only the dark level read at 30 ms | `"signal at dark level"` (classical) together with the verdict `no_sample_here` |

---

## 6. Milestone display

Milestone definitions follow PLAN §8 (not restated here). M1 is every feature on mock, so every item in this document
runs end to end at M1 on the mock backend and the mock store. The table's "Real" column records where the same item first runs for real: on real data (M2), microscope PC read-only
(M3), motion (M4), or focus verdict (M5).

| Area | Item | M1 | Real | Notes |
|---|---|---|---|---|
| Common | navigation, common status bar, disabled reasons (7.0) | M1 | M3 | the position and lighting on the status bar are real readback at M3 |
| Common | `"Lights off"` (pre-emptive) | M1 | M3 **(proposed)** | Lighting is not motion. Seeing live video at M3 means turning lights on and off, so it goes in M3 together with `light_set`. Needs the lead session's confirmation |
| Common | confirmation dialog frame (3.0) | M1 | with each operation | |
| `console` | reading questions, cards, versions, number grades, runs, inbox | M1 | M2 | reading soft-matter-agents files |
| `console` | submitting questions | M1 (mock store) | undecided | the real path belongs to the integration stage (PLAN §10) |
| `console` | link from run details to F6 | M1 | M2 | F6 itself is T-012 |
| `hardware` | detection, configuration file, gate table | M1 | M3 | |
| `hardware` | entering human-confirmed items | M1 | M3 | |
| `hardware` | state (Step 0, `status`) | M1 | M3 | |
| `hardware` | turning lights on (`light_set`) | M1 | M3 **(proposed)** | the same reason as `"Lights off"` above |
| `sample` | sample list, opening, creating new | M1 | M2 | reading the real sample folders (the user agreed to provide a copy, T-005) |
| `sample` | geometry form | M1 | M3 | the field list needs the user's confirmation (PLAN §10) |
| `sample` | loading check (person + image) | M1 | M3 | the image check uses only the lighting and the camera |
| `map` | drawing the map, visited fields, boundary, hole summary | M1 | M2 | reading the real `map.json`, `sample.json` |
| `map` | boundary points `b` / `u` | M1 | M3 | position read only |
| `map` | edge tracking | M1 | M4 | XY motion |
| `map` | 4x scan, sample map (mosaic, candidates) | M1 | M4 | viewing scan results is M2 (saved `scan4x_*`) |
| `map` | flags, candidate confirmation | M1 | M2 | record operations. On a real sample |
| `map` | click-to-move | M1 | M4 | |
| `objective` | 7-step objective change, `"Loading done"`, return, reload | M1 | M4 | the escape distance and sign are undecided (PLAN §5 direction convention, §10), so until then only `escape=False` |
| `objective` | 100x focus (classical verdict) | M1 | M4 | |
| `live` | live video, status bar, traces | M1 | M3 | the real camera is M3 (read-only + lighting) |
| `live` | classical verdict badge | M1 | M3 | |
| `live` | DINO verdict badge, tare | M1 (fake verdicts) | M5 | a head trained on the microscope PC |
| `live` | piezo `f` / `w` / `W` | kept off | after M5 | operations-spec 9.2: needs to be redesigned |
| `live` | `"Save frame"`, recording | M1 | M3 | |
| `live` | viewing saved stacks with the replay backend | M1 (`data/smoke`) | M2 | T-005 |

Of PLAN §8's M1 check method, the "end to end" for the F1–F5 part this document covers is the order below. Login, logs, F6 and F7 belong
to their own tasks (T-018, T-012, T-019), and this order starts after logging in and opening an experiment session:
in console, put one question into the mock store → in hardware, check mock detection and the gates → in sample, a new sample with
its geometry and loading check → in map, brightfield tracing, scan, flag, click-to-move → in objective, the 4x → 100x change (including Loading done)
and the 100x focus → in live, check the verdict badges → `"Lights off"` and a check of the lighting readback.

---

## 7. F1–F5 screens

Scope adjustment: the "v0.2 adjustment" section of the internal note `tasks/T-004-ui-spec.md`. F6 (simulation status details) is specified by T-012,
F7 (experiment sessions) by T-019, login by T-018, and the prompt pane by T-014. Here only the places that use their results
are recorded. For the detailed order of each operation see `docs/operations-spec.md`; it is not copied here.

### 7.0 Common to all areas

**Layout**

```
+--------------------------------------------------------------------------------+
| Navigation: console  hardware  sample  map  objective  live  (simulation, sessions) |
+--------------------------------------------------------------------------------+
| Area screen                                                  | Prompt pane (X1)  |
|                                                              | T-014             |
+--------------------------------------------------------------------------------+
| Common status bar: user · experiment session · lighting · running operation · pending confirmation · position · [Abort] [Lights off] |
+--------------------------------------------------------------------------------+
```

- The common status bar's values come from `position`, `light_changed`, `started` / `progress` / `finished` and
  `confirm_required` on `/ws/events`, and from `/api/state` (T-010).
- The prompt pane sends each area's own context along with it (PLAN "Common requirements"). The "Prompt context" of each area's section is that content.
  Per D7, images and frames are not put into the context.

**Disabled reasons** (F2.2 "does not hide a disabled function; it shows it inactive, together with the reason it is off"). Buttons and forms are not hidden but disabled, with the reason shown right beside them
on one line. The server and the engine decide; the screen draws the result. When several reasons apply at once, the first one from the top is shown.

| Reason | Wording | Decided by | Affects |
|---|---|---|---|
| Remote access | `"Read-only: remote view"` | server (request origin, command 403) | every command except `abort` (D13) |
| Role | `"Needs the operator role"` | server (T-018) | for a viewer, every command except `abort`, `lights_off`. Equipment commands only for admin/operator |
| Device control | `"<name> has control of the microscope"` | server (PLAN "Device control") | equipment commands, while someone else has control |
| Experiment session | `"Open an experiment session first"` | engine (PLAN §6 item 12) | commands that move equipment |
| Gate | `"<feature> is off: <reason>"` (e.g. `"no XYStage readback"`) | engine gate (F2.2) | the whole feature |
| Running operation | `"<op> is running"` | engine (single ownership) | other motion operations. Record operations and `lights_off` are excepted (4.4) |
| Waiting for return | `"Return to the sample position first"` | engine (`awaiting_return`) | every motion operation except the return |
| preflight | the `why` text of `preflight_failed`, as it is | engine | that operation |

**Stopping**: the `"Abort"` on the common status bar is enabled even in the locked state, for a viewer, and for a user without control (PLAN "anyone can press stop (abort)").
It is enabled from remote too (D13). The lights-off button can be pressed by anyone locally and is disabled from remote.

**Remote screen summary** (per-area details in each section)

| Area | Works from remote | Disabled from remote |
|---|---|---|
| `console` | reading questions, cards and run records, comparing versions | sending questions |
| `hardware` | reading detection results, the configuration file, gate state | running detection, saving human-confirmed items, turning lights on/off |
| `sample` | reading the sample list and records, the geometry | opening or creating a sample, saving the geometry, loading check, `"Open folder"` |
| `map` | viewing the map, mosaic, flags, candidates, progress | tracking, scanning, writing flags, confirming candidates, click-to-move, boundary points |
| `objective` | viewing the current objective and the progress step | objective change, `"Loading done"`, 100x focus |
| `live` | viewing video, verdicts, traces, position | live start/stop, exposure, every key command, frame save |

### 7.1 `console` — agent console (F1)

The data goes through AgentStore (T-008): `list_questions(agent)`, `get_question(qid)`, `list_runs(agent)`,
`get_run(agent, run_id)`, `list_inbox()`, `submit_question(...)`. The real soft-matter-agents store is read-only.
The UI does not edit cards (PLAN §6 item 9). The field names below were confirmed by reading the files at soft-matter-agents `baf6f1e`.

**Screen**

| Panel | What it shows | Source |
|---|---|---|
| Question list | questions of both agents. Columns: `qid`, agent, `status` (`DRAFT`, `VALIDATED`, `REFUSED`, etc.), `purpose`, `intent`, `observable.name`, `created_at`, latest version (no prefix = version 1, then `v2_`, `v3_`, … as many as exist). Filters: agent, status, date | `goal.json` in `*/questions/<qid>/` (latest version) |
| Question details | card tabs: `goal`, `axis` (one per axis, e.g. `a1`…`a7` of `bd_pairwise`, `verdict`), `synthesis` (`chosen_config`, `operating_point`, `rejected`), `plan` (`sweep`, `conditions`, `envelope_check`, `cost`, `stop_criteria`, `success_criteria`, `open_risks`), `refusal` (`stage`, `reason_code`, `alternatives`), and other cards such as `analysis_method_declared` on the microscope side | the `*.json` in the same folder. The JSON is authoritative (soft-matter-agents P3). `.md` only as an aid, marked "generated" |
| Version | a version picker. The list is not fixed; it collects every `vN_` prefix in the folder (as of baf6f1e they go up to `v6_`). The default is the largest N. A view of the field differences between two versions | file prefix (T-008's version rule) |
| Number table | the card's `numbers`: `name`, `value`, `unit`, `source`, **grade badge** (`E1`–`E5`), `precision`. The grade is the card's value, used as it is; the screen does not re-grade | `numbers[]` |
| Assumptions and gaps | `assumptions` (`statement`, `authorised_by`), `kb_refs`, `kb_gaps`, `degraded`. A warning band if `degraded` is not empty | same card |
| Run list | per agent: `run_id`, `qid`, `plan_id`, `backend`, start (`t0_wall`), end (`finished_at`), approval (`approval.kind`) | `*/runs/<run_id>/log.json`, `config.json` |
| Run details: simulation | `parameters_si`, `envelope_check`, `seed` from `config.json`. The events from `log.json` (`preflight`, `dispatch`, `progress`, `complete`). From `observables.json`, `fit` (e.g. `diffusivity`, `standard_error`), `uncertainty`, and a `msd_curve` plot. Progress, trajectories and downloads are a link through to the F6 (T-012) screen | `simulation_agent/runs/<run_id>/` |
| Run details: microscope | the events of `log.json` in time order (`gate_open`, `apply`, `failed`, `shutdown_failed`, etc.), `approved_commands`, and explanation fields such as `no_plan_because`, `not_dispatched`. `commands.json` | `microscope_agent/runs/<run_id>/` |
| Inbox | thread list (`thr-…`), rounds (`r1_`, `r2_`), `direction`, `trigger`, `answerability`, `unit_consistency.verdict`, `value_comparison.verdict`, `supersedes` | `microscope_agent/inbox/<thread>/` |
| Experiments in this repository | sample records and the list of experiment sessions. Choosing a sample goes to the `sample` area | `D:\AutoFocus\samples`, the F7 record store |
| Submit a question (F1.1) | body, target agent (`microscope` / `simulation`), send | `submit_question`. Writes only to the mock store (`"origin": "dino-autofocus mock"`). For the real store the button is disabled with `"Submitting to soft-matter-agents is not connected yet (read-only)"` |

**Transport and updates**

| Request | Transport | Update |
|---|---|---|
| lists, details, runs, inbox | REST `GET /api/console/...` (proposed: `questions?agent=`, `questions/{qid}?version=`, `runs?agent=`, `runs/{agent}/{run_id}`, `inbox`) | when the area is opened, and on the `"Refresh"` button. No file watching **(proposed: 30 s if periodic polling turns out to be needed)** |
| submitting a question | REST `POST /api/console/questions` (mock only) | re-read the list after the response |

**Remote and roles**: reading works from remote and for a viewer. Submitting a question is local operator/admin only **(proposed: since it is not hardware, decide in T-018 whether to open it
to a viewer too)**.

**Prompt context**: the chosen `qid`, version, chosen card kind, chosen `run_id`.

### 7.2 `hardware` — hardware discovery and state (F2, launcher Step 0)

Operations: `hardware_scan` (operations-spec §5), `status`, `light_set`, `lights_off`.

**Screen**

| Panel | What it shows | Source / event |
|---|---|---|
| Detection summary | time of the last detection, backend (`mock` / `mm-demo` / `mm-real`), config path, configuration file name and hash, differences from the previous configuration file | `hardware_profile.json` (`GET`) |
| Device table | per device: name, type, loaded, property read, readback verifiable, note. Rows with problems go to the top | same |
| Objective table | Nosepiece position and label, NA, magnification, immersion, working distance (`"not set"` if absent), pixel size | same + objective table |
| Camera · piezo | bit depth (Kinetix 12-bit, ceiling 4095), sensor size, whether the piezo is connected | same |
| Human-confirmed items | entered, not detected: DiaLamp intensity (the value read at the stand, 608/2100 on 9/30), CondenserTurret, the 40x WI correction collar, etc. Who entered each and when | `human_confirmed{}` (operations-spec §5) |
| Gate table | per feature: on/off, the list of reasons it is off (missing device, readback impossible, no human confirmation, value not measured, e.g. `"escape distance not set"`), required devices | the engine's gate decision (`GET`) |
| Current state (Step 0) | objective, Z, PFS (`enabled`, `locked`, `in_range`). The result of running `status` with `"Show objective / Z / PFS"`, and the periodic `position` | `finished(status).summary`, `position` |
| Lighting | brightfield on, Aura on by line and percent, off. Current state as in 5.2 | `light_changed` |

**Input**

| Input | Command | Notes |
|---|---|---|
| `"Scan hardware"` | `start("hardware_scan")` | read only |
| saving human-confirmed items | `start("hardware_confirm", {...})` **(proposed, WP-G)** | recorded in the configuration file. The gates are decided again |
| `"Show objective / Z / PFS"` | `start("status")` | |
| `"Brightfield on"` / `"Aura <line> <pct> % on"` | `start("light_set", {...})` | 4.0 |
| `"Lights off"` | the `lights_off` command (a command kind in events.py, not a `start`) | pre-emptive |

**Remote and roles**: remote and viewer read only. Turning lights on is an equipment command, so it needs the operator role and control. Lights-off (`lights_off`) alone can be sent locally by anyone logged in.

**Prompt context**: the chosen device name, the chosen gate name and its list of reasons.

### 7.3 `sample` — sample and loading check (F3, launcher Sample)

Operations: `sample_open`, `sample_new` (4.0), geometry save and loading check (WP-H, names proposed).

**Screen**

| Panel | What it shows | Source |
|---|---|---|
| Sample list | sample ID (`YYYYMMDD_HHMM_n`), creation time, hole fit time (`fitted_at`), objectives used, last experiment session, an `awaiting_return` mark | `GET /api/sample/list` (proposed). Sample root |
| Open sample | ID, folder, hole summary, calibration (`um_per_px`, objective), number of scans, maps and flags | `sample_opened`, `map_changed` |
| Geometry form (F3.1) | sample size (default 24 × 50 mm), chamber shape and hole diameter (the 9/30 sample about 6 mm), coverslip thickness (default 170 µm), sample thickness, orientation (normal / flipped). For each field, the source of its value (`"entered by <user> <t>"`, `"default"`, `"not set"`). **Fields that feed safety limits** (coverslip thickness, sample thickness, orientation) carry a mark | sample record (`GET`) |
| Loading check | 3 steps: (1) geometry entered (2) a person confirms `"Sample is on the stage"` (3) image check: judging from one 4x brightfield image whether the hole edge is visible (grade `"computed"`: computed from measurements, not a model). When all three are done, `"Loading confirmed (person + image)"`. PLAN F3: reading a selector value is not a state check | engine record (proposed) |

**Input**

| Input | Command | Notes |
|---|---|---|
| choosing from the list | `start("sample_open", {"sample_id"})` | U1 |
| `"New sample"` | `start("sample_new")` | U1. The geometry form opens |
| `"Open folder"` | opens Explorer on the server PC | on the local screen only. From remote there is no button, and only the path is shown |
| saving the geometry | `start("sample_geometry_set", {...})` **(proposed, WP-H)** | U4. A record operation, so it is excluded from single ownership |
| `"Sample is on the stage"` | `start("loading_confirm_person")` **(proposed)** | manual step record |
| `"Check with an image"` | `start("loading_check_image")` **(proposed)** | turns brightfield on, takes one image and turns it off. It is an equipment command (gates: camera, DiaLamp, 4x). The result's grade is `"computed"` (T-027) |

**Remote and roles**: remote and viewer read only. The image check is an equipment command, so it needs the operator role, control and an experiment session.

**Prompt context**: sample ID, the geometry values and their sources, the loading check state.

### 7.4 `map` — sample map (F4, the live view's map, launcher Step 1·2)

Operations: `edge_trace`, `scan_4x`, `sample_map`, `map_flag`, `goto_xy` (operations-spec §3·6·8), `boundary_mark`,
`boundary_undo`, `boundary_reset` (4.0). Particle candidate confirmation has no name, so one is proposed.

**Map layers** (bottom to top; each layer can be turned on and off)

| Layer | What it draws | Source |
|---|---|---|
| Mosaic | transmitted-light 4x mosaic (brightfield recommended). A picker if there are several scans | the server turns `sample_map_<stamp>/mosaic.npy` + `mosaic.json` (`x0, x1, y0, y1, um_per_px, bin`) into an image (`GET`, proposed). The left-right flip is set by the server from the sign of the calibration `M` (operations-spec 6.1). The image is a mirror image of the stage, and the stage coordinate of pixel p is `stage + inv(M) @ (centre − p)` (PLAN §5 direction convention, v1.2) |
| Scan box | the box of the last `scan_4x` / `sample_map` plus a 1 mm margin (the allowed range for click-to-move) | scan record |
| Visited fields | as in 1.2 (d). Coloured by verdict (5.3) | `map_changed` |
| Boundary and hole | boundary points, circle fit, centre. Fit time and session state (5.1) | `map_changed`, `sample_opened` |
| Particle candidates | **the two kinds are told apart by shape**: classical-processing candidates (`source: "classical_candidate"`) as hollow circles, ones a person confirmed (`source: "person_confirmed"`) as filled circles. Rejected candidates are hidden by default and, when turned on, are a grey × | `features.json` or `map.json` (operations-spec 6.1) |
| Flags | a flag with its name. Retired flags are hidden by default | `flags.json` |
| Current field of view | orange square and cross (1.2 (d)) | `position`, `objective` |
| Click target | the stage coordinate under the mouse, the distance from the current position, inside/outside the allowed range | a screen calculation (display only). From mosaic pixel to stage coordinate, the formula of PLAN §5's direction convention is used, and the screen does not pick a sign of its own. The server sends the formula and `M` down together with `mosaic.json` **(proposed)** |

The axes are drawn flipped to the stand's joystick direction, as in 1.2 (d), and the scale text states the direction.

**Side panels**

| Panel | What it shows / input |
|---|---|
| Order | the two steps of 5.1 (brightfield tracing → particle-light scan) and the state of each step |
| Hole summary | centre, diameter, rms, point count, arc angle, `fitted_at`. A warning if it differs from the expected diameter by more than 20 % (operations-spec §8) |
| Edge tracking | speed (default 100 µm/s, 10..1000), expected diameter (default: the sample geometry), `"Start tracing"` / `"Stop"`, `+` / `-`. Progress: status string, path length, point count |
| Scan | kind (`"4x scan, particle light"` = `scan_4x`, `"Sample map, brightfield"` = `sample_map`), exposure (empty = auto), dry run, focus mode (`per_tile` / `plane`). Progress: tile k/n, the current tile's curve (1.3), dropped frames |
| Results | list of `scan4x_*`, `sample_map_*`. Choosing one shows the mosaic layer and the z map (per-tile focus, z in 6 × 6 blocks) |
| Flags | list: name, note, time, objective, x, y, z (encoder). Add; note edits as a new entry; retire (U3) |
| Candidates | choose from the list or on the map: `"Confirm"` / `"Reject"`. Confirmations and rejections do not overwrite; they add a new entry |

**Click-to-move (F4.3)** — the order as seen on screen

| Step | Screen | Engine |
|---|---|---|
| 1 hover | the target coordinate and distance, and `"outside the scanned area"` beside the cursor if outside the allowed range | none (display calculation) |
| 2 click | a pin at the target. `start("goto_xy", {"x_um", "y_um", "sample_id"})` | `planned` (distance, whether it is a large move, whether a retract is needed, `z_safe`) |
| 3a out of range | the pin turns into a red × with the reason from `preflight_failed`: `"outside the scan box + 1 mm"`. No movement | preflight refusal |
| 3b refused for another reason | the reason in the same place (`"<op> is running"`, `"Return to the sample position first"`) | preflight refusal |
| 3c retract needed | the C12 dialog: `"retract Z <z> -> <z_safe>, then move to (x, y)"` | `confirm_required` |
| 4 retract | progress line `"Retracting Z 3048.7 -> <z_safe>"`. The Z in the position table is seen going down as an encoder value | `progress`, `position` |
| 5 XY move | `"Moving to (x, y)"`. The current field-of-view square moves | `progress`, `position` |
| 6 end | a `"Arrived (x, y read back). Z left retracted at <z>: refocus with a scan tile or focus_100x"` band | `finished` (landing readback) |

Z is not raised again (operations-spec 6.3, point 4). The screen only shows a button to the next focus operation.

**Input → command**

| Input | Command |
|---|---|
| `"Start tracing"` / `t` | `start("edge_trace", {"speed_um_s", "hole_diameter_mm"})` (C4, C5) |
| `+` / `-` | `update(op_id, {"speed_um_s": v})` |
| `b` / `u` | `start("boundary_mark")` / `start("boundary_undo")` |
| `"Re-trace"` | C4 of `start("edge_trace")` (back up, then clear). The separate clear button is `start("boundary_reset")` |
| `"Start scan"` | `start("scan_4x", …)` or `start("sample_map", …)` (C1–C3) |
| adding a flag | `start("map_flag", {"sample_id", "x_um", "y_um", "name", "note"})` |
| retiring a flag | `start("map_flag_retire", {"flag_id"})` **(proposed)** (U3) |
| confirming / rejecting a candidate | `start("candidate_confirm" / "candidate_reject", {"candidate_id"})` **(proposed)** |
| clicking the map | `start("goto_xy", …)` (C12) |

**Remote and roles**: remote and viewer only view the map and progress. Flags and candidate confirmation are not hardware, but they write the sample record, so
local operator only **(proposed)**.

**Prompt context**: sample ID, the clicked coordinate or the chosen region, the chosen flags and candidates, the hole summary. The mosaic image is not included (D7).

### 7.5 `objective` — magnification change, immersion liquid loading, 100x focus (F5)

Operations: `objective_change` (operations-spec 4.2), `focus_100x` (§7).

**Objective change screen**

| Panel | What it shows / input |
|---|---|
| Current | objective label, pixel size, Z (encoder), PFS |
| Choose | the objectives in the objective table. The same objective, an objective not in the table, and an objective with no working distance (40x WI) are disabled, with reasons (`"already on that objective"`, `"no working distance value"`) |
| Options | Y escape (`escape`) on/off and its distance. **Both the distance and the sign (+Y / −Y)** of the escape are not yet confirmed by the user (PLAN §5 direction convention v1.2, §10). Until they are decided, on is disabled, and the reason is the engine's wording as it is, `"escape distance not set"` (operations-spec 4.2, the principle in 3.0). The wording mentions only the distance, but the sign is undecided too, and the screen does not pick a sign as a default. Between dry objectives, off is the default |
| Plan | the 7 steps and the target values of each step (`planned`) |
| Start | `"Rotate"` → C6 |

**7-step progress display** — one line per step: state (waiting, in progress, done, failed), the value read, the time.

| Step | What the line holds | Event |
|---|---|---|
| 1 record | start XY, Z, objective (`return_xy`, `z_before`, `objective_before`) | `started.start_state` |
| (1b) lights off | lighting readback | `light_changed` |
| 2 Z retract | `"PFS off · Z 3048.7 -> 0.0 (read 0.0) · PFS Out of Range"` | `progress(step=2)`, `position` |
| 3 Y escape | `"Y 571.6 -> <y + dy> (read …)"`. A mark that the Z retract check was read again just before the move | `progress(step=3)` |
| 4 rotate | `"Nosepiece <now> -> <target> (read <label>)"` | `progress(step=4)`, `objective` |
| 5 loading | **Large card**: `"Load <oil / water> on <label>, then press Loading done"`. Button `"Loading done"` (C7). Who pressed it and when | `confirm_required(kind="manual_step")` |
| 6 return | `"XY -> (x, y) (read …)"`. Z is still retracted | `progress(step=6)` |
| 7 Z approach | progress bar: current Z (encoder), target (`approach_target_um`, default 2800), number of steps, the objective's upper limit. It does not jump to the target; it moves one notch per step | `progress(step=7, data={z_um, target_um, step, n_steps})` |
| end | new objective, pixel size, Z, lights off | `finished` |

- The state left behind depends on where it stops (the table in operations-spec 4.2 item 5). Stopping in steps 3–6 leaves `awaiting_return`, and the common status bar
  shows `"Objective change interrupted: return to the sample position"` and a `"Return to sample position"` button in every area.
  This button is a return operation that runs only steps 6 and 7 **(name proposed: `start("objective_change", {"resume": true})`, align with T-011)**.
- The reload variant (only steps 2·3·5·6·7 on the same objective, the operations-spec 4.2 item 8 proposal) is a `"Re-load immersion"` button.
  The double-peak warning of `focus_100x` leads straight to this button.

**100x focus screen**

| Panel | What it shows / input |
|---|---|
| Form | centre (filled with the computed value, 5.1), half width (default 40), step (2), fine half width (3), fine step (0.2), exposure (the 9/30 value of 20 ms as a candidate), metric (`peak` by default, `vollath`) |
| Reference values | the 4x focal-plane value at the same XY, the ceiling `min(3200, centre + 0.4 × 130)`, whether there is an immersion loading record this session (C10 if not) |
| Curve | metric against Z. x is `z_readback_um`. The ceiling line, the peak mark, saturated points marked |
| Result | verdict badge (classical), the encoder Z of the chosen frame, warnings (`"check immersion oil"`, `"reduce exposure"`, `"signal at dark level"`) |

**Input → command**

| Input | Command |
|---|---|
| `"Rotate"` | `start("objective_change", {"target_state", "escape", "escape_dy_um", "approach_target_um", "approach_step_um"})` (C6) |
| `"Loading done"` | `confirm(op_id, "load_immersion", "done")` (C7) |
| `"Return to sample position"` | the return operation above (proposed) |
| `"Re-load immersion"` | `start("objective_change", {"target_state": <current>, …})` (the variant operations-spec proposes) |
| `"Find 100x focus"` | `start("focus_100x", {"centre_um", "half_um", "step_um", "fine_half_um", "fine_step_um", "exposure_ms", "metric"})` (C9–C11) |

**Remote and roles**: remote and viewer only view progress. `"Loading done"` is pressed by the person at the microscope, so from remote it is
always disabled, whatever the settings.

**Prompt context**: the current objective, the target objective, the progress step, the verdict and encoder Z of the last 100x result.

### 7.6 `live` — live view

It is the live view of §1·2 as it is, and the display rules follow 5.3. Only what changes:

- The gauge keeps its 9/30 shape (5.3, user decision 2026-10-02). The two traces stay as they are.
- The key bindings (2.1) stay as shortcuts, with buttons for the same actions. The keys unrelated to the verdict (`b`, `u`, `t`, `+`, `-`) are the same commands as in the `map` area.
- The piezo keys (`f`, `w`, `W`) are **kept off** until M5 per operations-spec 9.2, showing the reason `"piezo focus is out of scope until M5"`.
- `"Save frame"` (new).
- Remote: the video, verdicts, traces and position are visible, and every key and button is disabled.
- **Prompt context**: the running operation, the latest verdict (vocabulary), position (encoder), objective, lighting. Frames are not included (D7).
- **A fixed caption when there are two cameras** (P-01): the side-by-side and merged views pair frames by host arrival time;
  they are not simultaneous captures (`WsFrame.time_base: "software"`). Display only; not used for timing, correlation or co-occurrence
  analysis. Simultaneous capture is the job of a soft-matter-agents plan with a hardware trigger (plan.md 4.6.9 on that side).
