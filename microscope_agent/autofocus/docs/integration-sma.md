# soft-matter-agents integration preparation (M6, draft 2026-10-02)

The starting point for PLAN.md §8 M6 "soft-matter-agents adapter design". It is based on a read-only reading of soft-matter-agents `baf6f1e`
(2026-09-29) and on this repository's main `d239448`. Paths on that side are relative to that repository.
This document is a design draft, and decisions go through the human decisions of §7.

## 1. Summary of the current state

| | dino-autofocus | soft-matter-agents |
|---|---|---|
| Focus | `focus/` classical metrics + verdict (`in_focus \| step_up \| step_down \| no_sample_here \| unsure`), DINO as an aid | No focus code. Task 026 (stage 2, first focus) **unassigned**. The verdict vocabulary is in `plan.md` §13.2 Trial 2 |
| Z motion | Only inside the engine guards; on the real instrument, a two-layer lock (`BENCH_MOTION`, `BENCH_APPROACH`) | ZDrive is refused in four places (not in `SOFTWARE_MAY_COMMAND`, `NAMED_REFUSALS`, `REFUSED_CALLS`, task 033) |
| Limits | The tables in `guards.py`, all `unmeasured provisional` (40x WI 0.17 mm is a user value) | `envelope/safety.json` (written only by a person). **No keys for ZDrive position, step or speed, XY travel range, or focus search range.** The schema is `additionalProperties:false` |
| Records | Experiment session folders, per-operation records, a grade on every number (`measured \| computed \| model`) | `runs/<run_id>/log.json` (run_log schema), grades E1–E6; model numbers are E6 and do not enter cards |
| Dependencies | core has torch, pymmcore-plus 0.18.1, sklearn, matplotlib and more | pixi `mic`: pymmcore-plus 0.18.1 / pymmcore 12.5.0.75.0 (the same pins). **No** torch, sklearn, skimage, pydantic, pyyaml |
| Visibility | Private (D5: made public at integration) | Public |

## 2. Basic direction of the integration (recommendation)

**The soft-matter-agents orchestrator stays the only path that moves the instrument.** This repository's engine and guards are not brought
over there as a second motion path. By the rules on that side, `devices/` is called only by the orchestrator, safety comparisons are
deterministic Python, and every move comes out of a plan field carrying `from`.

So what is handed over splits into three.

1. **Verdict provider**: a pure function that takes the deterministic metrics from frames and the encoder Z, and returns one verdict,
   the frame it points at, and the grounds. It does not return a Z and permits nothing (it can only refuse).
   `from_sweep` in `focus/verdict.py` already has this shape (numpy only; scipy is imported inside the function).
2. **Screen (UI)**: this repository's web app only reads files on that side (`agents/sma_files.py`). After integration too,
   the instrument side shows that side's runs and approvals, and actions are handed to that side's plan approval flow.
3. **Measured values and operating rules**: the bench results of September 30 and October 2, objective working distances and direction rules cross not as code but as
   librarian entries (at most E3) and the envelope a person writes. Numbers from this repository are not put directly into code on that side.

## 3. Contact points (locations fitted to that side's structure)

| contact point | location on that side | what comes from this repository | rules on that side |
|---|---|---|---|
| A verdict provider | One flat file in `microscope_agent/src/` (e.g. `focus_verdict.py`). Called by the `observe` hook of `operator.run` (`operator.py:1186`) or by the Trial 2 search loop | The pure part of `focus/classical.py` + `verdict.py` | check 13 (flat src), check 16 (does not import devices), check 82 (external import declaration). Recorded as an event in `log.json` (`focus_verdict` or §13.1's `watcher_flag`) |
| B frame source | `snap` / `sequence` of `devices/micromanager.py` (already guarded) | Nothing. This repository's `Backend.snap` is not brought over | Frame Z is a device reading |
| C Z drive | An extension of `devices/micromanager.py`, or a new `devices/<driver>.py` | Operating rules only: upward sweep, readback check at every step, PFS off first, retract to 0 µm, retract before a large XY move | A **separate task card** that opens the allow list (an exception in the `_operation_gate` style), new Z limits in the envelope, a gap comparison at every step |
| D plan shape | A new section of `plan.schema` (focus search: step, range, cap on the number of moves, list of branches, success criterion), `operator.derive_*`, check 86 or a new check | The step definitions and caps of `focus_100x` | manager-microscope changes the schema and the checks |
| E working distance | `operator.RESOLVERS["working_distance"]` | 40x WI 0.17 mm (d239448) is **not put on that side as a number**. Measurement → librarian entry → resolves the gap `objective_40x_wd_at_170um` on that side | If a range, the near end (0.16 mm). The recommended first target is 100x Oil |
| F session ↔ run | `runs/<run_id>/` | The session id, user, backend and `bench` from `session.json` | The librarian skips `bench: false` sessions (T-106b, BACKLOG M6) |
| G tool exposure | Claude Code sessions on that side | The assistant's read tools over MCP (PLAN §5 X2) | Task 026 §9: calls to external services are "a person's decision, not approved" |

## 4. Preparation that can be done in this repository now (without touching that side)

| # | work | reason | owner |
|---|---|---|---|
| P1 (done, 802284e) | Split `pyproject.toml` into a light core (numpy, scipy) + the optional dependencies `ml` (torch, torchvision, sklearn, skimage), `hw` (pymmcore-plus), `server`, `plot` | Keep to a minimum what must be declared for check 82 and pixi `mic`. The same as the policy of PLAN §4 | pyproject permission order (BACKLOG) |
| P2 | Fix the public surface of the verdict provider: write the inputs and outputs of `focus.verdict` as a JSON contract, plus a contract test that it imports with numpy alone | Contact point A. That side copies it as one file or takes it as a dependency | WP-E |
| P3 | A converter from `FocusVerdict.as_record()` into the shape of a run_log event on that side, and a test that validates with that side's `contracts/schemas/run_log.schema.json` (read only) (skipped if that repository is absent) | Align the record format in advance. The `model` grade maps to E6 and does not go into cards | WP-E |
| P4 | A list of the source and grade of every number table in `guards.py` (FREE_WD_UM, BENCH_FREE_WD_UM, the large-XY threshold, the 15 mm Y move-away and so on) | The list to hand to the librarian and the envelope. On that side a person writes the values | guard owner |
| P5 | Pre-publication check: no real email in the records (a search of the full git history found 0, 2026-10-02), the operator name in the 9/30 record (decided to keep), `models/heads/*.joblib` (they are pickles, so the side that downloads and opens them from a public repository is at risk; consider a fixed format or a pinned hash), two security items (signup 409, attempt limiting) | D5 publication | lead |
| P6 | T-106b (backend kind and bench in `session.json`) | Contact point F | card exists |

P1–P3 are independent of each other, so they can be made into cards right away. P5 once more just before publication.

## 5. Dependency options (decision needed, §7 Q2)

| option | advantage | problem |
|---|---|---|
| a. Move only the verdict part into `src/` on that side as one file (copy) | Fits that side's detachable rule and check 13. The only external import is numpy | Two copies. This repository is the original, and the commit hash is written into the file on that side |
| b. The published dino-autofocus as a git dependency (pinned commit) | No copy | The architecture seat changes pixi. The core is heavy now, so P1 comes first |
| c. Path dependency | Easy | Breaks the rule of detaching `microscope_agent/` + `contracts/` to the microscope PC. Not recommended |

Decision (Q2): **a, folder by folder** (the source moves into the folder on that side). The first step is the classical verdict only, no DINO. This agrees with task 026 §9, under which the fallback path to the deterministic-metric maximum comes first.
DINO scores come after that, in shadow mode (§13.1), by way of b and the `ml` optional dependency.

## 6. Rules on that side that cannot be changed (what the design must keep)

- Model numbers are E6 and do not enter cards or KB entries. A verdict can only refuse, never permit.
- The Z found is an encoder reading. A Z handed over is a target, not a destination (no direct jump, a gap comparison at every step).
- Safety comparisons are deterministic Python. When it is ambiguous, stop. `unsure` is not a failure but an abstention.
- Every move is derived from a plan field and carries `from`. Above Tier 1, approval (`plan_approval`) comes first.
- Numbers from another repository go through the librarian, at most E3; safety limits do not cross (`rulings.jsonl`).
- Dependency files (`pyproject.toml`, `uv.lock`, `pixi.lock`) belong to the architecture seat only.
- This repository does not write to the repository on that side (PLAN §5).

## 7. Human decisions (the user, 2026-10-02)

| # | question | decision |
|---|---|---|
| Q1 | Who takes focus | **The hardware engine on that side takes it.** Part of the hardware orchestration (microscope_agent) |
| Q2 | Dependency approach | **Develop separately for now, and fix the folder structure in advance with the merge in mind.** When development is done, the source moves into the matching folder on that side. So b (dependency) of §5 is not used, and a (moving in) is done folder by folder. The mapping table and the stages are in §9 |
| Q3 | Whether to accept values from this repository as sources on that side | **Decided at the merge.** Whether a value was written or measured by a person, the user checks directly. This repository asks with one card per value (most will probably already be shared). Information for the librarian is gathered separately in `docs/librarian-handoff.md` |
| Q4 | Z limits | **Only the objectives that need immersion liquid (40x WI, 60x Oil, 100x Oil) get limits; the rest (dry) are lifted.** Follows the soft-matter-agents rule (the way `objective_clearance_min` is resolved from the working distance per objective position). Changes to this repository's guards go in a separate card |
| Q5 | Abstention threshold | **Proceed with the current temporary values** (`MAX_SIGMA_DOF = 3.0`, `MIN_CURVE_CONTRAST = 0.05`, `MIN_DYNAMIC_RANGE_ADU = 20`, all `unmeasured provisional`). Set them later from records that compare against focus set by a person at the bench |
| Q6 | Where the Claude integration sits | **This repository takes the interface (part of the frontend) and the autofocus (backend). The agents themselves all become backend.** The screen's Claude integration goes to the agents on that side after integration |
| Q7 | When to publish | **Within 3 weeks (by 2026-10-23).** P5 is finished before then |

Q5 explained: when its confidence is low, the verdict maker returns `unsure` (abstention) instead of `step_up` / `step_down`. "How low before it abstains" is
the abstention threshold. This repository's current values are `MAX_SIGMA_DOF = 3.0` in `focus/verdict.py` (abstain when the model uncertainty exceeds 3 times the depth
of field), `MIN_CURVE_CONTRAST = 0.05` and `MIN_DYNAMIC_RANGE_ADU = 20`, all temporary values. Task 026
§9 on that side leaves this threshold "undecided". Recommendation: start with the temporary values, and set them from records that compare against focus set by a person at the bench.

### 7.1 Decision bundle A (the user, 2026-10-05)

On 2026-10-05 the user gave bundle A of §5 of the workplan (`integration-sma-workplan.md`) "모두 승인" (approve all). So the
**recommendation for each question is recorded as the decision, unchanged**. Where the soft-matter-agents side decided first on 2026-10-03~04 (key names, stop channel, 10.2 extension),
that side's commit is recorded with it. Bundle B (OD-9, 11, 14, 17, 21, 22) is asked after the bench visit (B-01).

| # | question | decision |
|---|---|---|
| OD-1 | The name and number of the SMA autofocus seat | The form `microscope-<YYYYMMDD>-<n>`, the existing `microscope-20261001-1` row copied as code, ownership `['microscope_agent']`; cards call it "the autofocus seat". Which session is that seat, the user says in that session's window |
| OD-2 | Is dino-autofocus opened as a source in SMA plan.md 10.2? | Yes, under the 2026-09-17 conditions as they stand. **Already recorded**: SMA 96db738 (10.2 extension; the user stated it directly to the architecture seat = OD-31) |
| OD-3 | After the copy, which side is the original? | (i) after the copy **SMA is the original**, (ii) dino keeps a **read-only mirror pinned by hash**, and `tests/test_sma_shape.py` catches drift, (iii) updates only by a dated SMA card (D-06) |
| OD-5 | Where console plan drafts live, and who brings them in | The console config folder `<config_dir>/plans/drafts/<draft_id>.json`; the autofocus seat copies them under its own name into SMA `questions/<qid>/`; no new folder in SMA; the draft's `author` is `human` |
| OD-6 | Person ids in drafts and public records | The same handle as the approval name, otherwise a random `p-xxxxxx`; drafts and exports carry only the id, never an email; the audit record is local; a handle appearing in `runs/` is allowed |
| OD-7 | The local record git and SMA `runs/` | The `D:\AutoFocus\records` git is the private full original (not pushed); SMA `runs/` gets the de-identified `console.*` that the seat puts there; manual export from the session screen after the session is closed (R-03's bench-only rule) |
| OD-8 | Bounding Z of the immersion objectives in SMA | Both the envelope's **explicit per-objective keys** (written by a person) and a clearance check at run time. The key names are SMA's `focus_z_<objective>_{min,max}` (e079983; the plan row's `z_drive_position_*` proposal is not used); the upper bound is written by a person and not derived (250a138); "lifting" for dry objectives is a wide value written by a person |
| OD-10 | Patterns at the bench | Only the expressible subset (piezo single-axis segment, single-axis sine; traps as `.tpf` or a small enumeration of steps, and on hold); the circle and spiral schema (P-04) only when needed, after the first focus; repetition and periodic Z motion always refused |
| OD-12 | Keep `trap_move/trap_set/pattern_run` as mock demos? | Keep them, marked "mock demo" in operations-spec |
| OD-13 | The console's direct hardware and bench frames after S5 | Until the console uses the G-14 frame tap (SMA 0c6452d), only mm_real's cfg load, reads and illumination (no motion); no bench live view before that (two cores on one Micro-Manager is a known failure); the console's mm_real is not opened at the same time as the SMA operator |
| OD-15 | May the console validate drafts? | Only a jsonschema check inside the console (a read-only copy of SMA `plan.schema.json`, pinned by a provenance header, labelled "schema-valid (console check)"); SMA `validate.py` runs on that side after the draft is brought in |
| OD-16 | `scripts/focus_servo.py` | Deleted in R-05 (stays in history); a bounded direction finding is the job of SMA G-12 |
| OD-18 | MCP exposure of the console tools | Excluded from this plan; looked at again later as a read-only server that SMA architecture registers (C-14) |
| OD-19 | The independent dino engine behind `/api/commands` | Kept (`LocalEnginePort` for mock/replay/mm-demo); bench motion removed in D-05 |
| OD-20 | XY moves in this merge | All on hold, and recorded now (G-17); scan_4x/sample_map/edge_trace/the step-aside stay mock/replay until the XY card after B-03 |
| OD-23 | Abort/confirm in SMA mode before the stop path exists | Disabled with an honest reason ("at the instrument or at the operator terminal"); since SMA's stop channel (f6c0996, 11-25 b) now exists, re-enabled in C-08; the "Abort is always on" promise becomes "for the local engine only" |
| OD-25 | Backup of `D:\AutoFocus\data`, `samples`, the hardware profiles and the record git | Raw frames are kept locally (copying to SMA `runs/<run_id>/raw/` is the seat's decision per run); export of the sample folder and the hardware profiles on hold; the record git is backed up to a second disk or an encrypted copy (the user does it) |
| OD-26 | The simulation screen and PLAN §10 F6/F7 | The screen stays in the console, and `SmaFilesPort` reads SMA `simulation_agent/questions` and `runs/` (C-03) |
| OD-27 | The console title and the lab name in documents | The console title is changed to a neutral one ("Autofocus Console"); the lab name in documents is kept, per decision P3 |
| OD-28 | Language of the public tree | Design documents stay in Korean; one English paragraph in the README, with a note that "design documents are in Korean"; the English summary for SMA readers at the head of this document |
| OD-29 | Put `map_*.py` in the first copy? | Left out and on hold (SMA 10.2 rules the same way: there is no slot for a sample map); the first copy is `focus_classical`, `focus_verdict`, `focus_search` and their tests (SMA card 059, dino b802837) |
| OD-30 | D14 (automatic stop when the viewer disconnects) for plans SMA runs too? | **Not applied** for now (the same as SMA's temporary default: the run continues when the viewer disconnects, f297a28); decided again once hw_port uses the stop channel |

## 8. What needs measuring first (microscope PC)

Task 018 §6 and the bench items of this repository's BACKLOG overlap. One bench visit fills both:
pixel size, through-focus curves per method, interface offset, PFS offset sign, parfocal residual (4x→100x about −60 µm, needs re-measuring),
working distance at the 40x WI 0.17 mm collar, Q13 (approach step), Q20 (XY move that needs a Z retract), stage limits, uncommanded Z drift
(485.16 → 483.62 µm). The results go into this repository's `docs/runs/` and into the librarian on that side, each.

## 9. Folder structure (Q2, draft 2026-10-02)

Further decisions (the user, 2026-10-02, after seeing the draft of this section):
- **Actions only through plans.** After the merge the screen makes plan drafts, and when a person approves, the operator/orchestrator on that side runs them.
  The screen does not move the instrument directly. S5's `hw_port` aims at this shape (submit a plan, read runs).
- **The screen (server, web, launcher) stays in this repository.** What moves to that side is only the `microscope_agent/` part (the focus and map core).
  `console/` below is a location inside this repository; no new top-level folder is made on that side (no ALLOWED_PATHS approval needed).
- **All records go to `runs/` on that side.** `runs/` on that side is public, so personal information such as emails and names must be removed before handing over
  (this needs a design that replaces user ids with opaque values; a new task). The admin email stays outside git, as now.
- **scipy is replaced with numpy** (`separated_peaks`). The focus core uses numpy only.


Constraints that come from the rules on that side (soft-matter-agents `baf6f1e`, `contracts/validate.py`):
- check 13: an agent's `src/` holds only flat files or `src/devices/<file>`. `tests/` holds only flat `*.py` (no fixture folders).
- Modules on that side load sibling files **by path, not by package import** (`spec_from_file_location`, e.g. `axis_a1_snr.py:44`).
  Tests are `unittest`, no conftest.
- check 82: looks even at imports inside functions. `scipy` is only in the `sim` feature, so the check passes, but it is absent from the `mic` environment on the microscope PC.
  `separated_peaks` in `focus/classical.py` (`scipy.signal.find_peaks`) fails at run time in that environment.
- That side has no UI or server folder. A new top-level folder first needs approval from architecture (ALLOWED_PATHS, pixi) and the manager (AGENT_OF_PATH).

Mapping table (summary):

| this repository | location on that side | handling |
|---|---|---|
| `focus/classical.py`, `verdict.py`, `sma_event.py` | `microscope_agent/src/focus_classical.py`, `focus_verdict.py` | moved (path loader, scipy removed) |
| `focus/dino.py`, `live.py`, `backbone.py` | later `focus_dino.py` (shadow mode, torch in `mic`) | stage 2 |
| The Z rules of `guards.py` (upward sweep, readback check, PFS off first, retract to 0, retract before a large XY move) | `focus_step_rules.py` (pure functions, limits as arguments from the envelope) | pure part only |
| Step generation in `focus_100x.py` | `focus_search.py` (`from` on every step) | split |
| `mosaic.py`, the pure parts of `sample.py`, `scan_4x.py` and `sample_map.py`, the detection part of `edge_trace.py` | `map_mosaic.py`, `map_geometry.py`, `map_tiles.py`, `map_edge.py` | split |
| `runner`, `backend`, `events`, `records`, `gates`, the remaining guards and number tables, `objective_change`, `z_retract`, `light_set` | orchestrator, operator, envelope, `runs/<run_id>/` | stays only in this repository (for standalone running) |
| `mm_real.py`, `mm_demo*.py` | absorbed into `devices/micromanager.py` | dropped at the merge |
| `server/`, `auth/`, `assistant/`, `agents/`, `web/`, `tools/launcher/` | a new top-level `console/` (`sma_console` package, `console/web`, `console/launcher`) | moved |
| `synth/`, training and evaluation scripts, `models/`, `configs/ti2_*.yaml` | not moved (stays in this repository for building models) | stays |

Intermediate layout inside this repository (mirroring that side as it is):

```
microscope_agent/src/        focus_*.py map_*.py   (flat, no __init__.py, stdlib + numpy only)
microscope_agent/src/devices/
microscope_agent/tests/      test_focus_*.py ...   (flat, unittest, path loader)
console/sma_console/         app ws static hw_port api/ schemas/ auth/ assistant/ store/
console/web/  console/launcher/  console/tests/
src/dino_autofocus/          the rest, for standalone running (engine, backends, operations, records, synth, live, backbone)
```

Distribution stays single (`uv sync`, editable install, pytest unchanged). `dino_autofocus.focus` stays as a thin shell that re-exports the flat files,
keeping existing imports alive. `tests/test_sma_shape.py` applies checks 13, 16 and 82 in advance to the two folders that will move.

Stages (tests pass at the end of each stage):
- S0 (P1 done) split the dependencies. S3 (P3 done) verdict → run_log event.
- S1 (done) the focus core into `microscope_agent/src/` (`focus_classical`, `focus_verdict`, `focus_run_log`), scipy removed,
  `tests/test_sma_shape.py`. The old names `dino_autofocus.focus.{classical,verdict,sma_event}` remain as the same module objects.
- S2 the pure core files one at a time (`focus_step_rules`, `focus_search`, `map_*`). The old modules re-export the same objects.
  - `map_geometry` (done): pixel ↔ stage (`stage + inv(M) @ (centre - p)`), `calibration_of`, the geometry fields, validation and view of `sample.py`, `hole_loop`.
  - `map_mosaic` (done): all of `mosaic.py` (scipy filters → numpy, bit-for-bit identical to scipy). `mosaic_from_scan` stays in the old module because it uses guards' `registry_key`.
  - `map_tiles` (done): snake tile order, the scan rectangle, `fit_plane` / `plane_z`, camera calibration defaults (`scan_4x.py`, `sample_map.py`). The allowed XY box belongs to guards (`XYBox.around`), so it stays.
  - `map_edge` (done): the detection part of `edge_trace.py` (`find_edge`, circle fit, `hole_fit`); the scipy label in `remove_small_regions` → numpy run grouping (the same regions).
  - `focus_search` (done): the parameters of `focus_100x.py`, the centre, the coarse, fine and upward-extension spans, the peak position, the warning rules, `sweep_z` (limits as arguments, the same Z as guards' `FocusAxis.plan`). The actual planning and checks stay in guards.
  - `focus_step_rules` (done 2026-10-03, pure file only; workplan D-01): rule functions that take the Z window, retract, return, readback tolerance, per-objective working distance, long-move
    threshold and approach step all **as arguments** (upward sweep, readback check, rise check, approach step enumeration, sweep and approach caps,
    PFS off and out of range, turret rotation condition, retract before a long XY move — including Q4's lifting for dry objectives, rejection of the model grade), and flat unittests.
    **D-01b (done 2026-10-03)**: `guards.py` calls 16 of the 20 rules at the moment of comparison (limits, backend calls, records and the bench
    locks stay in guards). The four not delegated — `approach_steps` (the next approach target comes from the readback),
    `needs_retract_before_xy` (needs D-04's objective kind; for now every objective is bundled as a row of the table), `pfs_quiet` and
    `pfs_out_of_range` (used inside `nosepiece_turn_allowed`). One thing got stricter: if the PFS state cannot be read, turret rotation is
    refused (before, only the on state was refused). `tests/engine/test_guards_delegation.py` pins that the refusal sentences are the same as
    the flat rules' sentences.
  - D-02 (done 2026-10-03, workplan `integration-sma-workplan.md`): the bench and tuning numbers of the flat files (sweep centre 2930, parfocal
    −60, dark 102, signal floor 50, exposure 20, spans 40/2/3/0.2, verdict thresholds 20/0.05/3/1.0/3.0, saturation 0.001, dropout 0.02,
    double peak 0.2, 4x calibration 1.625 and the matrix) moved to `src/dino_autofocus/bench_values.py` and are taken as function arguments;
    `tests/test_sma_shape.py` rejects any number outside the per-file allow list of number literals.
  - D-03 (done 2026-10-03): a three-line provenance header on every flat src and test file — `# origin: dino-autofocus, public since
    2026-10-03:`, the public URL `https://github.com/kyu-softmatter/dino-autofocus/blob/<commit>/<path>`,
    `# body-sha256: <hash of the body below the header, line endings normalised to LF>`. `<commit>` is the commit in which that body first entered, so
    changing the body needs two commits (the body, and the header that names that commit), and in between `tests/test_sma_shape.py` fails
    (`python -m dino_autofocus.flat_origin --check` / `--commit <sha>`). The tokens `dino_autofocus`,
    `scripts/` and `docs/` are banned inside flat files (they mean something else after the copy), the SMA commit the mirror follows is pinned (`SMA_SHAPE_COMMIT`), and when a
    soft-matter-agents checkout sits beside it, a drift check by reading only (whether the pinned commit is in history, whether checks 13, 16 and 82 still
    exist, whether the body of each file present on both sides is the same). After the copy the header is turned round to point at soft-matter-agents (D-06).
- **Mirror rule (OD-3, the user 2026-10-05; workplan G-06, D-06)**: by card 059, soft-matter-agents copied
  `focus_classical`, `focus_verdict`, `focus_search` and their three tests (`test_focus_core`, `test_focus_contract`,
  `test_focus_search`) byte for byte from dino 5cc5057 (SMA f2c56dc). **For these six files SMA is now the
  original, and dino's `microscope_agent/` copy is a pinned read-only mirror.** The header records
  `# origin: soft-matter-agents, ...` and the public URL of the SMA commit (`flat_origin.MIRRORED`,
  `SMA_MIRROR_COMMIT`). Any change to these files is made in SMA first (by a card); dino takes the body of that commit and
  re-points the header with `python -m dino_autofocus.flat_origin --mirror <sha>`. `tests/test_sma_shape.py` checks
  against the SMA checkout that they match the body of that commit. For the remaining flat files (`focus_step_rules`, `focus_run_log`,
  `focus_verdict_model`, `map_*`), dino stays the original.
- **XY on hold (OD-20, the user 2026-10-05; first half of workplan G-17)**: nothing XY crosses in this merge.
  `scan_4x`, the `goto_xy` of `sample_map`, `edge_trace`, and the +Y step-aside of `objective_change` stay dino's
  mock/replay only, even after the merge. No XY plan shape, exception or envelope key is requested from soft-matter-agents. The table of retracts before a long XY
  move for immersion objectives (`guards.OBJECTIVE_LIMITS.long_xy_um`, Q4) stays in dino, and question cards L-019 and L-020 ask a person for those values.
  The XY design (second half of workplan G-17: the `motor_stage` step, `motor_stage_{x,y}_position_min/max`,
  a retract verification interlock) is SMA's work after B-03.
- S4 move the server, web and launcher to `console/` (about 100 imports, gen:api, launcher paths).
- S5 `hw_port.py`: the screen does not call the engine directly but goes through one port (after that, console does not import `dino_autofocus`).
- S6 the merge week: copy after the approval order on that side is finished (person: seat → architecture: seats.json, pixi, ALLOWED_PATHS spec → manager: validate.py →
  manager-microscope: task card, plan.schema, envelope schema). The approval chain is long, so **start in week 2**.
