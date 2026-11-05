# Closed-loop test — readiness report (2026-11-05)

Branch `closed-loop-validation`, worktree `D:\closed-loop-validation`, on the
microscope computer (hostname `Takatori_lab`). The checklist is
`docs/drafts/closed_loop_test_checklist_20261105.md`. The five areas were
checked in parallel on 2026-11-05 between about 09:35 and 10:05 Pacific time.

**Nothing was opened on the bench.** No device was connected to, no stage
moved, no light switched, and nothing sent to the tweezers. The hardware part
reports only what Windows can see. The live connection test is still to do,
and needs the person to hand the bench to the session that runs it.

Nothing was written into either working copy apart from this report and the
checklist. Two side effects of running the checks: an ignored
`simulation_agent/src/__pycache__/`, and an ignored `.pixi/envs` link in this
worktree.

## Summary

| Area | Status | Blocking a live test? |
|---|---|---|
| Hardware: what Windows sees | **Partly working**: both Kinetix cameras missing, tweezers server not running | Yes |
| Simulation engine (WSL, HOOMD) | **Working** from the existing environment; **not** from this worktree's own path | Yes, for runs of this branch's code |
| Bridge | **Working** (read-only board, hand-written rounds) | No |
| Librarian (knowledge store server) | **Working**, and serving this branch's store | No |
| Repository checks | **Working**: 0 failed | No |
| Knowledge snapshots | Hashes check; **both 22 entries behind** the store | Only if a test uses those entries |
| Commit gate (git hooks) | **Not installed** in either copy | Not for testing; yes for trusting commits |
| Whole loop | Walked only as far as the microscope's goal, **never further** | This is what the test has to do |

## 1. Hardware

### What is there

| Component | Seen by Windows | Status |
|---|---|---|
| NI PCIe-6323 DAQ board (also drives the LUN-F lines) | yes | OK |
| Nikon Ti2 microscope body (USB) | yes | OK |
| Aresis Tweez 300 (USB, console on COM11) | yes | OK |
| IDS uEye UI-337x camera | yes | OK |
| Cypress FX3 device (probably the Mightex Polygon DMD; a guess) | yes | OK |
| Serial ports the approved Micro-Manager configuration needs: COM10 (spinning disk), COM3 (light engine), COM7 (Aura) | yes | OK |
| **Kinetix camera, blue arm** (PVCam, PCIe) | **no** | **Missing** |
| **Kinetix camera, red arm** (PVCam, PCIe) | **no** | **Missing** |
| Two unknown USB devices | yes | **Error**: "Port Reset Failed" |

### Software installed

NI-DAQmx 26.0.0, NIS-Elements 6.20.02, PVCam 3.10.2.7, Nikon Ti2 Control
2.90.108, IDS uEye 4.94, Tweez 300 SW 3.0.2. Micro-Manager is in two places:
`C:\Program Files\Micro-Manager-2.0` (adapters from 2023-12-23) and the
pymmcore-plus copy `Micro-Manager_2.0.3_20260806`. Python has pymmcore
12.5.0.75.0, which matches the version the focus gate expects, and
pymmcore-plus 0.18.1.

### Running right now

No NIS-Elements, Micro-Manager, ImageJ or Tweez 300 GUI. Nothing holds the
hardware. The PVCam and NI services are running, as usual.

**One unexpected process:** the operator console server (`sma_console`) is
running, with a placeholder backend and a mock store. This branch removed the
console, so the process comes from somewhere else, probably the main copy. It
touches no hardware.

### Problems

1. **Both Kinetix cameras are absent.** Windows lists their PCIe entries as
   not present. They are probably switched off, or their PCIe link is down.
   The approved configuration names both, so loading it would fail.
   *To do:* power them on, then confirm they appear in Device Manager.
2. **The tweezers server port (2070) is not listening**, because the Tweez 300
   GUI is not running. *To do:* start the GUI before the test.
3. **Two USB devices are in error** ("Port Reset Failed", vendor 0000,
   product 0001). Which instrument they belong to is unknown.
   *To do:* find which device is behind that hub, then replug or power-cycle it.
4. **Micro-Manager may load from the wrong folder (a risk, not tested).** The
   run engine does not say which Micro-Manager folder to use, and no
   `MICROMANAGER_PATH` is set. pymmcore-plus will then pick its own
   `2.0.3_20260806` folder, which has no driver for the Mightex Polygon DMD
   that the approved configuration loads. Only `C:\Program Files\Micro-Manager-2.0`
   has that driver. *To decide:* which folder the engine should load from.
5. **The approved configuration file exists only at one path.** The approved
   hash matches `microscope_agent/autofocus/configs/micromanager/DMD_dualcam_LUNF.cfg`.
   The copy on the Desktop (`Maintanance\micromanager\`) is a different file,
   and the run engine would refuse it. The old path
   `C:\agentic_microscope\config\...` does not exist.
6. **NIS-Elements conflicts with the LUN-F lasers (known).** NIS holds the NI
   board while it runs, so Micro-Manager's writes to the laser blanking lines
   are refused. Decide which program drives the lasers for the test.

### Working

- **Safety policy:** `microscope_runtime/envelope/safety.json` is present and
  reads cleanly: version 9, written by you on 2026-10-13, 33 limits.
  Reminder from the last bench visit: the focus upper limit of 3300 µm is the
  contact position with no margin.
- **Approvals:** the six plan approvals, the transmitted-lamp live-view
  approval and the Micro-Manager configuration approval all read cleanly.
- **Run lock:** free, and the last release was clean. It is an operating-system
  lock, so it cannot go stale.
- **Run-engine tests on the mock backend:** the 17 mock-only test files gave
  292 tests, all OK. About 36 other test files were **not** run, because they
  use a hardware backend with stand-in parts and could reach real
  Micro-Manager if a guard failed. `pytest` is not installed; the tests ran
  under `unittest`.
- The runtime's own instructions (`microscope_runtime/CLAUDE.md`) still say
  the code runs from `microscope_agent/src/` and that the policy sits there.
  That is out of date: both have moved into `microscope_runtime/`.

## 2. Simulation engine

### What is there

WSL2 `Ubuntu-24.04` with pixi 0.81.0. The `sim` environment has HOOMD 7.2.0
(CPU build, exactly as `pixi.lock` pins it), Python 3.12.14, gsd 5.0.1,
scipy 1.18.1 and numpy 2.5.3. Environments live on Ubuntu's own disk, one per
project folder.

### Working

- WSL starts. The first command after a cold start takes about 6 s.
- HOOMD imports with GPU off. The engine's own version check says the engine
  matches the pin.
- **Smoke run:** 64 free Brownian particles for 5000 steps on the CPU ran at
  about 15,800 steps/s. Mean squared displacement was 26.5 against 30.0
  expected, a ratio of 0.88 with a statistical error of about ±0.10. The script
  is
  `C:\Users\Takatori lab\AppData\Local\Temp\claude\671202903e92f9d6\80b25665-e18b-46f5-a270-33e9e8206923\scratchpad\sim\smoke_bd.py`.
- **The simulation agent's check scripts pass:** trajectory round-trip (8 of
  8), bleach backend (3 of 3), other-login refusal (8 of 8).

### Problems

1. **No environment exists for this worktree's path.** pixi keys each
   environment to the folder it serves, and only `D:\soft-matter-agents` has
   one. `pixi run -e sim` from `D:\closed-loop-validation` would build a new
   environment. The package cache may already hold every package; that is
   untested.
   *To do:* run once from this worktree:
   ```bash
   wsl.exe -d Ubuntu-24.04 --cd /mnt/d/closed-loop-validation -- /home/takalab/.pixi/bin/pixi install -e sim --frozen
   ```
2. **The workaround runs the wrong code.** Running the main copy's environment
   directly works, but `import contracts` then loads the **main** copy's
   `contracts/`, which differs from this branch's in 234 files. Six of the
   simulation's configuration modules import from it. Do not run this branch's
   simulations that way; build the environment first (item 1).
3. A Linux-side copy, `/home/takalab/exp-sim-closed-loop`, made on 2026-11-04,
   has its own environment. Its `plan.md` and `pixi.lock` differ from this
   branch's. This is noted only so the two are not mixed up.
4. A small trap: start the simulation's Python modules from
   `simulation_agent\` with `python -m src.<name>`. Started inside `src\`, the
   agent's own `operator.py` hides Python's standard `operator` module and the
   import crashes.

## 3. Bridge

### What is there

The bridge has no program of its own yet. Rounds are written by hand. A
read-only board (`python contracts/bridge_board.py`) shows the threads, and
the repository checks confirm each round carries its cards unchanged.

### Working

- **The board runs and lists three threads.** In all three it is the
  microscope's turn:
  - `thr-tracer-diffusivity-001`, round 3: a simulation plan, taken by the
    microscope's question `mic-20260919-001`
  - `thr-bleach-recovery-diffusivity-001`, round 1: a simulation result, taken
    by `mic-20260930-001`
  - `thr-double-well-001`, round 1: a simulation result, taken by
    `mic-20260925-001`
- None is undelivered, and none has a source revised after it crossed.
- The repository checks for rounds and envelopes all pass: 11 rounds carry
  their cards unchanged.
- **Waiting to cross**, none of it owed until you name what to hand over:
  - the microscope's finished plan `mic-20260920-001`
  - seven simulation results: `sim-20260923-003`, `-101`, `-102`, `-201`,
    `-042`, `-041` and `sim-20260917-001`
  - the simulation's finished plan `sim-20260923-001`

### Problems

1. **The simulation side has no inbox folder** (`simulation_agent/inbox/`).
   No round has gone from microscope to simulation yet, so nothing needs it
   so far. The first return round will have to create it.
2. **The bridge's settings may block delivery.** Its settings deny writes into
   both agents' folders, and on 2026-10-01 that rule stopped a delivery (the
   double-well thread's inbox holds the `.json` copy but not the `.md`). The
   rule is still there, so a bridge session could be blocked again when it
   delivers.
3. Some old wording in the bridge's files still refers to the old seat scheme.
   It has no effect on behaviour.

## 4. Librarian (knowledge store server)

### What is there

A read-only server with four tools (query, get, group, conflicts) over 352
entries, store version `kbv-d027f44dadc0`. Its launcher, `.mcp.json`, finds
`sh` and then the first Python that has `mcp`, `jsonschema` and `referencing`.

### Working

- **Launcher:** it finds `sh` in `C:\Program Files\Git\bin`, which is on the
  user PATH. It skips the `python3` Store alias and uses `python` (3.12.10,
  mcp 2.2.0).
- **Server:** its self-test passes, it builds and lists its four tools, and the
  query-log self-test passes.
- **Store:** the index is current (352 entries), the 10 safety guides and the
  90 wiki pages are current, and the exports are current.
- **One server is running**, started at 09:35 today from
  `D:\closed-loop-validation`, so it reads **this branch's** store, on the
  current server code. Today this branch's store is identical to main's.
- **Query log:** 1478 lines, all valid. Every call that was served carries an
  issued caller id; the 16 without one are refusals, which is what a refusal
  looks like. The last entry is from 2026-10-13, and nothing has been logged
  since.

### Notes

- The server reads the store once, when it starts. An entry edited later is
  seen only after the session restarts.
- The query log carries one known old inconsistency, from 2026-09-19: one
  question got two different answers under two server builds. The log is
  append-only, so it stays. Its verify step therefore exits 1, and that is
  expected.
- The planned store linter (`kb_lint.py`) does not exist yet.
- Cards from this branch whose answer came from the service need the query
  log committed on this branch too.

## 5. Repository and environment

### Working

- **Repository checks on this branch:** 225 passed, **0 failed**, 11 undecided,
  110 pending, 12 lost, 8 not applicable. The tree judged was this branch's
  last commit plus the checklist file.
  - The 11 undecided are tolerance thresholds nobody has chosen yet.
  - The 110 pending are artifacts a later step produces, such as run logs.
  - The strict run fails, as it must while anything is undecided or pending.
- **Rejected examples:** all 91 cards and all 92 groups are still rejected.
- **Checks that read git history:** 115 of 115 passed. They take about 15 min.
- **Python:** 3.12.10, with jsonschema, referencing, mcp and numpy. uv 0.12.19
  and the `py` launcher are present. `pytest` is **not** installed.
- **Clocks:** Windows syncs from time.windows.com and last synced today. WSL is
  synchronized too. The offset between them is about 0.03 s.
- **Disk:** C: has 146 GB free and WSL has 938 GB free. D: has 198 GB free but
  is **99% full**. That is enough for a test, but worth watching.
- **Git:** the branch matches its remote. The main copy is clean, on `main`,
  and untouched. The commit tool works from this worktree, and its lock
  resolves to the worktree's own lock.

### Problems

1. **Both knowledge snapshots are 22 entries behind the store.** The
   microscope and simulation copies are at the 2026-10-07 version with 330
   entries. The store has 352: the 2026-10-29 light-engine entries were never
   copied out. The hashes check, so nothing is corrupt.
   *To do:* the microscope and simulation agents each re-copy their snapshot
   before a test that relies on those entries.
2. **No commit gate is installed in either copy.** The hooks exist in
   `contracts/hooks/` but `core.hooksPath` is not set, so commits are not
   checked when they are made. The commit tool's own description assumes the
   gate runs.
   *To decide:* whether to install it, with this command:
   ```bash
   git config core.hooksPath contracts/hooks
   ```
3. **This branch's `CLAUDE.md` describes a commit tool with more options than
   this branch has.** Patch mode, holds, and the push list with other
   commits are gone. The tool's `--help` is what to follow.

## 6. The whole loop

Traced on the three existing threads:

| Step | Exists on disk? | Tool |
|---|---|---|
| Question | yes, on both sides | agent sessions |
| Simulation plan / result | yes | engine in WSL |
| Bridge round | yes, written by hand | read-only board and repository checks only |
| Microscope goal taking the round | yes, all three | exists |
| Microscope plan | **none for any thread** | `microscope_agent/src/plan_card.py` |
| Run (mock, then real) | **none for these threads** | `microscope_runtime/src/operator.py --backend mock`, needs an approval file |
| Microscope result card | **none anywhere** | **no result-card writer found** |
| Return round to simulation | **never done** | no simulation inbox yet |
| Store entry from a result | **none** | written by hand by the librarian, then indexed |

The loop has never gone past "the microscope's goal". The last four steps have
never been done for any thread. The missing result-card writer is the one gap
in the code itself; the others are steps that have simply never been done.

## Before the live test: what to do

**On the bench, yours:**
1. Power on both Kinetix cameras and confirm they appear in Device Manager.
2. Start the Tweez 300 GUI so port 2070 listens.
3. Find and fix the two USB devices that are in error.
4. Decide which program drives the LUN-F lasers (NIS-Elements or
   Micro-Manager).
5. Decide which Micro-Manager folder the engine loads from.
6. Hand the bench, in its own window, to the session that will run the live
   connection test.

**In the repository, the sessions':**
7. Build the simulation environment for this worktree (the `pixi install`
   command in section 2).
8. Have the microscope and simulation agents re-copy their knowledge snapshots.
9. Decide whether to install the commit gate.
10. Pick one thread, carry it through plan → mock run → result card → return
    round, and write the result-card step, which does not exist yet.
