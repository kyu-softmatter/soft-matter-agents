# Record form — bench visit 1 (B-01), by hand only

> **This is a form, not a record.** When values arrive, the bench session copies it to `docs/runs/<visit date>_bench-visit-1.md` and fills it in.
> If a file of the same name already exists, do not overwrite it; stop (6.2 #5).
> Machine twin: `<visit date>_bench-visit-1.yaml` (form `bench-visit-1.template.yaml`, the same facts). Checklist: `docs/runbooks/bench-visit-1.md`.

- Date and time: ____ (planned 2026-10-12; moved from the first date 2026-10-08)
- Operator: `<person-id>` (OD-6 handle). Do not write emails or PC user names.
- Recorder: Claude Code bench session (records only; no hardware command). dino main: `____`
- Software motion: **none**. Every motion was done by hand (workplan 6.2 stop criterion 8).
- Locks (confirmed on the day with `git show origin/main:`): `BENCH_MOTION = "LOCKED"`, `BENCH_APPROACH = "MEASURED"`.
- A value has only two possible sources: words the person wrote directly in the bench session window (`user statement in the bench window, <date>`),
  or a file whose path the person gave in that window (`file <path> sha256 <hex>`).
- Conflicting values (40x WI working distance 160/170, Kinetix 12/16-bit) are written as read. Do not merge them or choose between them (6.2 #7).

Status labels: `unmeasured` / `measured` (measured by hand) / `read_from_device` / `catalog` / `person_decision` / `person_statement`.

## 1. One-table summary

| Checklist section | Item | Value | Status | Method | Who | When | Source | Card |
|---|---|---|---|---|---|---|---|---|
| 2 | Configuration-file checks | | | | | | | L-075 |
| 4.1 | ZDrive encoder sign | | | | | | | L-013 |
| 4.2 | Piezo Z direction | | | | | | | L-073 |
| 4.3 | Stage X+ / X− / Y+ / Y− | | | | | | | L-023, L-024 |
| 4.4 | Z and XY drift without commands | | | | | | | L-067 |
| 4.5 | Wanted Z retract height | | | | | | | L-015 |
| 5.1 | Q13 100x approach step | | | | | | | L-018 |
| 5.2 | Q20 XY distance that needs a retract (100x / 60x / 40x WI) | | | | | | | L-019 |
| 5.3 | 40x WI working distance (collar 0.17) | | | | | | | L-005 |
| 5.4 | Glass-interface Z per objective, parfocal residual | | | | | | | L-033 |
| 5.5 | Through-focus curve (folder) | | | | | | | — |
| 5.6 | 1x1 pixel size | | | | | | | L-031 |
| 5.7 | Shadow-mode evaluation frames (objectives, fields, planes, folder) | | | | | | | — (S-01) |
| 6 | Kinetix_red saturated-frame maximum, properties | | | | | | | L-055, L-056 |
| 7 | PFS release path, PFSOffset sign | | | | | | | L-062–L-065 |
| 8 | Core.Focus, CSUW1-Port, CSUW1 closed, Lapp 50/50, Aura flicker, readout delay | | | | | | | L-029, L-043, L-044, L-051 |
| 9 | Tweez300 camera body, trap x and y sign, trap Z | | | | | | | L-090, L-091 |
| 11 | G-05b SMA copy | | | | | | | — |

## 2. Confirming the statements received in advance (relayed 2026-10-05)

| # | Statement | Visit-day result (same / different: value / not confirmed) | Source |
|---|---|---|---|
| S1 | 40x WI WD at collar 0.17 = 170 µm | | |
| S2 | Lower Z by 100 µm before a long XY move (Q20); Q13 not answered | | |
| S3 | Piezo 0–6000 µm, stage ±2 cm (piezo needs confirming) | | |
| S4 | Kinetix saturation "2^16" (as worded; write as the value only the maximum seen in a saturated frame, do not assume 2^16 − 1) | | |
| S5 | PFS is controlled through MM; the property that switches it off is open | | |
| S6 | Tweez300 releases the camera; as y decreases, the trap moves down in the image | | |

## 3. Details by section

Copy the checklist's tables as they are (4.1 … 11). Add the source in the last column of each table.

## 4. U-03 grounds (not envelope values)

Write only the grounds for the 12 keys `focus_z_<lens>_{min,max}`. The values are written by the person into SMA `safety.json` at U-03.

| Key | Grounds | kind (physical / carried_over) | how | by | on |
|---|---|---|---|---|---|
| focus_z_4x_min … focus_z_100x_max (12 rows) | | | | | |

## 5. End of the visit

- Items done / not done:
- Odd readings:
- Stops used:
- Saved files (path, sha256):
- End state (objective, Z, XY, PFS, light):

## 6. Handover

- SMA `findings/<seat>-<date>.json` is written by an SMA seat (prerequisites G-01 + G-05). The bench session passes on only the paths and sha256 of this file and the yaml.
- This record does not go into SMA `runs/` (OD-7).
