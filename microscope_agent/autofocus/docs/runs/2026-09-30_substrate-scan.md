# Run log — 2026-09-30, substrate scan (sample `20260930_1849_1`)

Machine-readable twin: [`2026-09-30_substrate-scan.yaml`](2026-09-30_substrate-scan.yaml)
(same facts, keyed for agents). Data: `D:\AutoFocus\samples\20260930_1849_1\`.

Operator: kyuchoi (Takatori lab). Agent: Claude Code in `D:\AutoFocus\dino-autofocus`.
Stand: Nikon Ti2-E, Kinetix_red camera, Aura light engine, NanoBench 6000 piezo (COM4, read
only all day). Session ran ~19:35–20:52 local.

---

## 1. Outcome in one table

| What | Value | Source file |
|---|---|---|
| Hole (chamber) centre, stage µm | **(8026.0, 571.6)** | `sample.json` → `hole` |
| Hole diameter | **6.144 mm** (fit rms 42.5 µm, 49 pts, 352° arc) | `sample.json` |
| 4x focus at hole centre (ZDrive) | **3048.7 µm** (plane fit, 73 blocks) | `scan4x_20260930-200241/scan.json` |
| 4x focus tilt | −1.66 µm/mm in x, −3.62 µm/mm in y; rms 7.6 µm | computed from `block_z_um` |
| 100x Oil focus, bottom particle layer | **2988.45 µm** at (8164.7, 523.4); **2989.42 µm** at (7811.0, 1529.0) | `focus100x_20260930-202507.json`, `-202813.json` |
| 100x focus − 4x focus (same area) | ≈ **−60 µm** | difference of the two rows above |
| Upper particle (operator-selected) | stage (8579.5, 68.3); operator focus **3012.94**; brightest at **3010.0** (≈ +21 µm above bottom layer); ~6.7 µm FWHM diameter | `particle_20260930-204954_*` |
| End state | Aura OFF, DiaLamp OFF (both read back); ZDrive 498.0 µm (retracted by operator), XY (6396.0, 177.5); 100x Oil in place | last command of the session |

---

## 2. The procedure, in order (repeatable)

**Standing rule from the operator:** brightfield first to find the edge, then switch to the
particle light (here Aura GREEN 1 %) and run the Z scan in that light. Never reuse an old hole
fit without re-tracing — this sample's hole moved **1.5 mm** between the 18:49 fit and the 19:57
rescan.

### Step 0 — State check (read only)
```
python scripts/change_objective.py --status
```
Found: Nosepiece 0 = `1-Plan Apo LmbdD20 4x` (already on 4x), ZDrive 62.9 µm, PFS off /
"Out of Range". No rotation needed.

### Step 1 — Brightfield edge trace (4x)
```
python scripts/live_focus.py --exposure 12 --sample 20260930_1849_1 --hole-diameter 6 \
    --set Aura State 0 --set DiaLamp State 1
```
- Old boundary backed up, then cleared (only `boundary`; 95 field visits kept):
  `map_before_rescan_20260930-195719.json`, `sample_before_rescan_20260930-195719.json`.
- In the window: put the hole edge in view → press **`t`**. Tracker calibrates
  (+x, +y moves; phase correlation) then follows the edge; stops on a full loop.
  `+`/`-` double/halve speed, `Esc` stops. The operator sped it to 400 µm/s (step 200 µm).
- DiaLamp Intensity was 608 / 2100 (set at the stand). At 12-bit: 10 ms gave median 2766 ADU,
  ≥30 ms saturated. 12 ms used.
- Calibration result (4x): 1.6252 µm/px, 0.117°, `M_px_per_um = [[0.6160, 0.0024], [0.0013, -0.6146]]`.
- **The camera image is mirrored relative to the stage**: a feature moves *with* the stage
  (+x stage → +column). Sample point at pixel p sits at `stage + inv(M) @ (centre − p)`:
  columns run toward −x, rows toward +y.
- Note: `live_focus.py` turns the DiaLamp ON via `--set` but does **not** turn it off on close.

### Step 2 — 4x Z scan under the particle light
```
python scripts/scan_4x.py --sample 20260930_1849_1          # auto exposure
python scripts/scan_4x.py --sample 20260930_1849_1 --exposure 994
uv run python scripts/plot_scan.py D:/AutoFocus/samples/20260930_1849_1/scan4x_<stamp>
```
- Light: `aura_on` = DiaLamp State 0 → Aura GREEN_Intensity 10 (per-mille = 1 %) → GREEN 1 →
  State 1. Off in `finally`.
- Grid from `sample.json` hole + 0.5 mm margin, 15 % overlap → **2 × 2 tiles**, FOV 3901 µm,
  pitch 3315 µm, serpentine.
- Focus per tile with ZDrive through `agentic_microscope/hardware/focus.py::FocusAxis`
  (allow_motion, PFS off, every sweep ascends, readback-verified, ceiling 3200).
  First tile: coarse ±160 µm @10 µm around the current Z (3012) then fine ±12 @2 µm.
  Later tiles: ±50 @6 µm around the previous tile's focus, fine ±12 @2. Metric: Vollath F4.
  Each tile also gets a 6 × 6 block z map (`block_z_um`).
- Auto exposure: brightest 0.1 % → 50 % of the camera ceiling → **994 ms** (p99.9 2043 ADU).
- Results (ZDrive µm):

| tile | x | y | run 1 (`-200241`) | run 2 (`-200639`) |
|---|---|---|---|---|
| r0c0 | 6368.3 | −1086.0 | 3057.93 | 3054.52 |
| r0c1 | 9683.7 | −1086.0 | 3053.32 | 3052.94 |
| r1c1 | 9683.6 | 2229.2 | 3048.94 | 3053.99 → **3051.2** (light dropout removed) |
| r1c0 | 6368.3 | 2229.5 | 3042.95 | 3041.15 |

  Run-to-run 0.4–3.4 µm against a ~14 µm 4x depth of field.

### Step 3 — Objective change 4x → 100x Oil (software, SAFETY.md §2 sequence)
```
python scripts/change_objective.py --to 5 --park     # PFS off, Z→0, check PFS Out of Range, rotate, stay at 0
# operator oils the lens
python scripts/change_objective.py --return-only     # Z 0 → 2800
```
Operator explicitly authorised the software rotation. Rotation read back
`6-Plan Apo LmbdD0.13 100x Oil`. XY was first moved to the hole centre (8026, 572).

### Step 4 — 100x focus (sparse particles → peak-brightness metric)
```
python scripts/focus_100x.py --centre 2985 --half 30 --exposure 30
python scripts/focus_100x.py --centre 2988 --half 20 --exposure 20
```
- **Do not centre a 100x sweep on the 4x focus.** Lab history (objective-offsets.yaml) and
  today agree the 100x focus sits ~60–100 µm *below* the 4x focus. Ceiling per sweep is
  `centre + 0.4 × 130 µm WD`.
- Whole-frame sharpness (Vollath) fails at 100x: only a few particles per 156 µm field.
  Use `--metric peak` (default): brightest 4 × 4-binned spot minus median.
- Exposure at 100x, Aura GREEN 1 %: **20 ms** keeps the in-focus particle below the 4095
  ceiling (30–50 ms saturated). 30 ms Vollath run read only dark offset (~102 ADU) → no focus.
- Oil: the first good-looking curve had a spurious second rise near 3005 µm; after the operator
  **added more oil**, one clean symmetric peak. Check oil when a 100x curve looks doubled.
- The script refuses to climb when the peak sits at the top of the span; the operator approves
  any re-centre upward.

### Step 5 — Search for a particle 15–25 µm above the bottom layer
```
python scripts/find_particle_z.py --stack 2984 3042 --band 3004 3035   # NOT fit for use yet, see §4
```
Spiral of 100x fields (150 µm pitch) inside the hole; per field an ascending 1 µm stack;
a hit = spot peaking inside the band. 46 fields over four runs found **no** hit; two fields
(7239.9, 710.0) and (7239.9, 560.0) had bright in-band objects (~1900–2100 ADU) that failed the
spot test. The operator then found a particle by hand at (8579.5, 68.3), Z 3012.94.
Last run stopped on a FocusAxis guard: commanded 3037.0, read 3036.0 (stage was being moved by
hand at the time).

---

## 3. Settings reference

| Item | Value |
|---|---|
| MM config | `C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg` |
| Python | system Python 3.12 (pymmcore-plus 0.18.1, cv2) for hardware; `uv run` for plots (matplotlib) |
| Camera | Kinetix_red, 2400 × 2400, **12-bit** (`ReadoutRate = 100MHz 12bit`, ceiling 4095), AutoShutter off |
| Pixel size | 4x 1.625 µm (calibrated 1.6252); 100x 0.065 µm |
| ZDrive sign | increasing Z = toward the sample (measured 2026-09-05) |
| Z window | SAMPLE_Z_WINDOW_UM 2800–3200; 100x Oil free WD 130 µm; 4x free WD 20 mm |
| Brightfield | DiaLamp State 1, Intensity 608 (stand), CondenserTurret `3-`, LightPath `4-L100`, 4x 12 ms |
| Particle light | Aura GREEN 1 % (`GREEN_Intensity 10`, per-mille), DiaLamp 0; 4x 994 ms, 100x 20 ms |
| PFS | off throughout (never enabled by software) |
| Piezo | read only; z ≈ 9.94 µm all session |

---

## 4. Known issues / open items (for whoever picks this up)

1. **`find_particle_z.py` spot test is unresolved.** Real particles are ~6.7 µm (FWHM), not
   2.5 µm. With `--particle-um 7` it finds the operator's particle (3010.0) in the saved stack,
   but also passes 24 synthetic defocus-ring fragments. Needs an extra discriminator
   (e.g. a filled centre / radial profile) before it is trusted.
2. **Aura flicker**: one 4x tile had two frames at −23 % brightness. `scan_4x.py` now drops
   frames > 2 % off the sweep's median brightness and re-fits the fine peak (`dropout_z_um`).
3. **The operator moved the stage and focus during runs** (XY changes between records; Z read
   3059.06 µm at the start of `focus100x_20260930-202011`). Record start positions are in each
   file's `header.position`.
4. `live_focus.py` does not switch the DiaLamp off on close; switch it off explicitly.
5. 4x→100x parfocal offset today ≈ −60 µm (lab 2026-09-07 note suggested ~−100 µm via 60x).
   Worth a dedicated measurement on a fiducial.
6. The first 4x scan attempt (`scan4x_20260930-194928/`, empty) was stopped: auto exposure
   targeted a 16-bit ceiling on the 12-bit camera. Fixed (reads `getImageBitDepth`).

## 5. Files

- Scripts (this repo, `scripts/`): `change_objective.py`, `scan_4x.py`, `plot_scan.py`,
  `focus_100x.py`, `find_particle_z.py` (new today); `live_focus.py`, `edge_track.py`,
  `mm_grab.py` (existing).
- Data (`D:\AutoFocus\samples\20260930_1849_1\`): `sample.json`, `map.json` (+ `*_before_rescan_*`
  backups), `scan4x_20260930-200241/` and `scan4x_20260930-200639/` (scan.json, tile_*.npy,
  scan_overview.png), `focus100x_*.json`, `find_particle_*.json`, `particle_20260930-204954_frame.npy`
  / `_stack.npz`, `track_*.jsonl` (live-view event logs), `*.log` (stdout of each run).
