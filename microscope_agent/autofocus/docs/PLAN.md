# dino-autofocus development plan (draft v0.2, 2026-10-01)

Author: the lead session (direction set in conversation with the user). Only the lead session edits this file.
Code, comments, logs and UI text are written in English; plan documents are written in Korean.

Change history
- v0.1: goals, structure, design rules, decisions D1–D5, work packages WP-A–E.
- v0.2: user requirements F1–F5 added (2026-10-01). **Every feature is built in mock first**.
  Python environment policy added. Work packages WP-F–J added. D1 recommendation updated. D5 decided (public at integration).
- v0.3: **D1 decided: local web app (FastAPI + React)**. D3 confirmed. Server/web structure, API rules, work package WP-D split. Node is the uv group `web`.
- v0.4: F6 simulation status in detail, common requirements X1 (a prompt box on every screen), X2 (Claude integration).
  Claude integration design (§5), decisions D6–D8, work packages WP-K, WP-L.
- v0.5: decided to implement the F6.3 trajectory viewer in both 2D and 3D.
- v0.6: D7 (only text to Claude, no images) and D8 (no cost limit for now) decided. D6 goes ahead as the recommendation.
- v0.7: X3 login, X4 logs, F7 experiment sessions (a folder + branch/worktree per session, the librarian merges periodically).
  Design (§5), rule 12, decisions D9–D11, work packages WP-M, WP-N.
- v0.8: D9 decided (email login, the administrator email only in local settings), D10 decided (local git on the microscope PC).
- v0.9: D11 record structure changed (each party's own folder instead of per-session branches, the librarian reflects them), D12 account creation (name, email, password, administrator approval).
- v1.0: D13 remote stop allowed, D14 automatic stop 10 s after every connection drops.
- v1.1: D15 light sources allowed in M3, D16 view-only users cannot ask questions or flag.
- v1.2: direction basis fixed to the 2026-09-30 run record (Z sign, upward sweep, image mirrored against the stage, serpentine).
- v1.3: F5 Y step-out provisionally set to +Y, 15 mm (the user).
- v1.4: §3 current state updated (2026-10-02). New task assignment stopped; only work in progress is finished. Development then moves to a way of working that uses fewer tokens.

## 1. Purpose and scope

- **Final goal**: attach this repository's measurement functions to soft-matter-agents' hardware engine
  (`microscope_agent/src/orchestrator.py` + `devices/*`) to automate experimental measurement.
  The repository is named autofocus, but its scope is not limited to focus.
- **Goal of the current stage**: build a **user interface** for people. It has two parts.
  - Agent console: enter questions, and see the status/plans/results of earlier questions and of simulations and experiments.
  - Microscope operation: understanding the hardware, sample loading check, sample map, objective change and immersion liquid loading.
- **mock first**: every feature is first built end to end with mock hardware and a mock agent store.
  The real hardware is connected on the microscope PC after the behaviour is confirmed in mock.
- Integration itself is not done in this stage, but designs that would block integration are avoided now (§6).

## 2. Functional requirements (the user, 2026-10-01)

The numbers are not priorities; they are the order things came to mind. Empty items are filled in later.

### F1. User interface

Technology: **local web app, FastAPI backend + React front end** (D1, the user's decision 2026-10-01). Structure in §5.

| | Function | Data source |
|---|---|---|
| F1.1 | A place to ask questions | Puts the question into the agent store. In mock, a local store |
| F1.2 | View earlier questions | goal, axis and plan cards in `*/questions/<qid>/` |
| F1.3 | Simulation status / plans / results | `simulation_agent/questions/`, `simulation_agent/runs/` |
| F1.4 | Experiment status / plans / results | `microscope_agent/questions/`, `microscope_agent/runs/`, this repository's sample records |

- The agent store is opened **read-only**. By soft-matter-agents' principles the files are the truth, and
  cards are written only by the designated sessions and gates. The UI never edits a card directly.
- What submitting a question (F1.1) actually writes, and where, is within soft-matter-agents' design scope.
  For now it is implemented behind an adapter interface with a mock store, and the real path is settled at the integration stage
  with the architecture session there (§10, open).
- Simulations run in WSL. The UI does not import simulation code; it only reads files.

### F2. Detecting connected hardware and its state

| | Function |
|---|---|
| F2.1 | Detect the connected hardware and write a **hardware profile file** |
| F2.2 | The profile file determines **which gates are enabled** |

- Detection: the devices loaded in Micro-Manager, each device's properties, whether it can be read back, the objective list,
  camera bit depth, whether the piezo is connected. In mock, the same format is built from the mock device list.
- Profile file: `hardware_profile.json` (working name). It holds the detection time, each device's state and the items a person confirmed.
- Gates: each function declares the devices and conditions it needs. For example the F4 sample map is enabled only when XYStage, ZDrive,
  DiaLamp, a 4x objective and a camera are present and can be read back.
  The UI does not hide a disabled function; it shows it inactive, together with **the reason it is off**.
- Gates are decided by code. Neither a model nor a UI dialog opens a gate.

### F3. Sample loading check

| | Function |
|---|---|
| F3.1 | Sample geometry selection window: sample thickness, coverslip thickness, sample form (flipped or not, etc.) |
| F3.2 | (to be written) |

- The geometry feeds the safety limits of later stages. Coverslip thickness changes the objective's working distance and
  correction collar condition; flipping changes the focus search range.
- Candidate fields (to be confirmed by the user): sample size (usually 24 mm × 50 mm), chamber shape and hole diameter
  (about 6 mm for the 30 September sample), coverslip thickness (default 170 µm), sample thickness, orientation (upright / flipped).
- The loading check uses a person's confirmation and an image check together. Reading a selected value is not a state check.

### F4. Sample mapping (transmitted light recommended)

| | Function |
|---|---|
| F4.1 | Record roughly where particles were |
| F4.2 | Use it to find a particle in use when it is lost, and to recommend good sample regions |
| F4.3 | Click a region on the map to move there |
| F4.4 | Flag important regions |

- A mosaic is built from a transmitted-light (DiaLamp) 4x tile scan. The 30 September edge tracing and 4x scan are reused.
- Particle positions are recorded as **candidates** found by classical image processing, kept apart from those a person confirmed.
- Click-to-move goes through the motion gate. Outside the scan box it is refused; if Z is not at a safe height it retracts first.
- A flag records name, note, time, objective and coordinates in the sample record.

### F5. Objective change and immersion liquid (oil/water) loading

| | Function |
|---|---|
| F5.1 | Because of how the stage is built, loading liquid at an objective change is hard once the sample is on |
| F5.2 | With the objective change, move about 15–20 mm away in y so the liquid is easy to load. Direction to be decided later |
| F5.3 | After loading, the user clicks and the stage returns to the original position |

Sequence (the existing `change_objective.py` procedure plus the XY step-out and return):

```
1. Record the current XY, Z and objective
2. PFS off -> Z retract (0 µm) -> confirm PFS Out of Range
3. Move Y to the step-out position (allowed only while Z is retracted)
4. Rotate the objective, read it back
5. User: load oil/water -> click "Loading done"      <- manual step, recorded
6. Return XY to the position from 1 (Z still retracted)
7. Z does not jump to the target value; it approaches step by step from the retract position
```

- The step-out direction and distance are set after measuring the stage limits and which way the 24 mm side faces (§10).
- The guard allows the XY moves of steps 3 and 6 only when the Z retract is confirmed.
- Step 7 is the same as soft-matter-agents task 026's rule "the handed-over Z is a target, not a destination".

### F6. Simulation status in detail (extends F1.3)

| | Function |
|---|---|
| F6.1 | Progress of a running simulation (current step / total steps, elapsed time, expected end) |
| F6.2 | A button to download the data easily (bundled per run folder) |
| F6.3 | Simulation visualisation: particle trajectory playback. **Implement both a 2D (Canvas) and a 3D (Three.js) viewer** (the user, 2026-10-01) |
| F6.4 | View key results as graphs: log values (energy, temperature, pressure, etc.) and observables |

- Reference: [kyu-softmatter/HOOMD_GUI](https://github.com/kyu-softmatter/HOOMD_GUI). The same structure is used:
  a FastAPI local runner, loopback binding only, a Host header allow list, web and API served from the same origin.
  Both viewers are built together. 2D is a slice or projection on Canvas; 3D is Three.js GPU instancing.
  The two viewers share one trajectory frame format and the playback controls (play, stop, frame step, speed),
  and the screen switches between 2D and 3D. The server reads frames from GSD and sends only the fields needed.
  Progress comes over WebSocket or server-sent events. Trajectories are GSD, logs HDF5/CSV.
- Data source: in soft-matter-agents `simulation_agent/runs/<run_id>/`, the files `config.json`,
  `log.json`, `observables.json` and `trajectory_meta.json`. The trajectory files themselves are not in the repository; they are on the WSL side.
  The server only reads them through a `\\wsl$\<distribution>\...` path. The real path is checked on the microscope PC.
- Progress source: a running simulation has to leave its progress in a file. Whether it does so now needs
  checking (§10). In mock, a fake run that advances over time is used.
- Download: the server zips the run folder and streams it. Large trajectories are included by choice.
- Numbers in the graphs are drawn exactly as read from the record files. The screen does not recompute them.

### Common requirements

| | Function |
|---|---|
| X1 | **A box on every screen where a request can be made by prompt** |
| X2 | **Every prompt and function is integrated with Claude** (design in §5 "Claude integration") |
| X3 | **When the executable starts, decide who the user is and log in** |
| X4 | **Keep a log file**: who did what, and when |

- The prompt box is one shared component, and each screen sends it with its own context attached.
  E.g. the sample map screen sends the selected sample id and the clicked region; the simulation screen, the selected run id.
- Answers and proposals are shown inside that screen, and the same conversation history can be followed from every screen.

### F7. Experiment session management

| | Function |
|---|---|
| F7.1 | One experiment is opened as an **experiment session**. It carries the logged-in user, the sample and the start time |
| F7.2 | Each experiment session is kept in a **separate folder**. The party that made the data writes only to its own folder (v0.9, instead of branches) |
| F7.3 | Finished sessions are **read periodically by the librarian agent and reflected into the knowledge store** |
| F7.4 | Open an earlier session to view it, and start a new session continuing with the same sample |

- An "experiment session" means one microscope measurement. It is not the same thing as a Claude development session.

## 3. Current state (2026-10-02, main 3cbe466)

### How work proceeds

- **Freeze lifted** (the user, 2026-10-02, after the microscope PC results were taken in). New work can be assigned again.
- (Before it was lifted) **New task assignment stopped** (the user, 2026-10-02). Only work already committed or under review is taken through review, merge and push
  to completion. Newly found work is only written down as an item in the internal notes (outside the public repository, `dino-autofocus-internal/tasks/BACKLOG.md`).
- Further development **moves to a way of working (a platform) that uses fewer tokens** (the user). The list to hand over is the handover section of BACKLOG,
  what to check is [microscope-pc-checklist.md](microscope-pc-checklist.md), and the session rules are `sessions.md` in the internal notes.
- Task cards (`T-NNN`), BACKLOG and the session rules were moved on 2026-10-02 out of the public tree into the private repository `dino-autofocus-internal`
  (the user, pre-publication check D1). `T-NNN` in this document and in the code points at those cards.
- The execution sessions, the review assistants and the work-assignment assistant have all been archived. The sessions left are the lead, the manager and review.

### Milestone progress

| | Status |
|---|---|
| M1 all features in mock | Nearly done. Once "under review" below is merged, the user checks everything from login through F1–F7 on the development desktop |
| M2 real data reading | soft-matter-agents file reading and replay are on main. The format is checked once a simulation `trajectory.txt` sample and the WSL path come from the user |
| M3 microscope PC read-only | The real-instrument backend (mm-real) and the configuration file check are on main. Waiting for the microscope PC check (steps 1–3 of the checklist) |
| M4 motion | Locked twice in code (below). The first-motion procedure is [first-bench-motion.md](runbooks/first-bench-motion.md) |
| M5 focus verdict | Classical metrics, the DINO wrapper and the training procedure are on main. Training and latency measurement happen on the microscope PC |
| M6 integration preparation | Not started. Rules such as the librarian skipping mock sessions are in the BACKLOG M6 items |

### What is on main

- **Engine**: backend contract, events, records, guards, gates, runner. Backends are mock, replay, mm-demo, mm-real.
  Operations are status, light_set, hardware_scan, scan_4x, focus_100x, edge_trace, objective_change, sample_ops, z_retract.
- **Server**: FastAPI, WebSocket events and frames, login cookie and lock, a check that accepts only requests from its own address (T-009c),
  closing open sessions as "interrupted" on restart (T-009e), clean shutdown (T-026).
- **Screens**: console (F1), hardware (F2), sample (F3), sample map (F4), objective change (F5), simulation and the 2D/3D trajectory viewer (F6),
  live view, the prompt box on every screen. The Claude integration router (T-013b, tested with a fake provider).
- **Records**: session folders, path-scoped auto-commit, manifest, fake librarian.
- **Launcher**: build script for the new exe (`tools/launcher/build.ps1`). The exe on the desktop is still the old tkinter version.

### Work that was in progress

All work in progress at the freeze has been merged and pushed (3cbe466). Last full test run: pytest 1488 passed, 11 skipped;
vitest 322 passed; web build passed. No branch is left unmerged. In came the login screen (T-105), the sessions screen (T-106), sample map stage 2 and
goto_xy (T-032), and the server starting with the real runner and the mock backend (T-009i, mock records outside the real records folder).
Cards that exist but were never started are in the HANDOVER section of BACKLOG.

### Real-instrument locks

| Lock | Value | Condition for release |
|---|---|---|
| Motion lock T-036 | `BENCH_MOTION = "LOCKED"` | The 11 prerequisite safety tasks are on main. The one line that lifts the lock must be **approved by the user** (execution 12's permission check refuses it). It is lifted when the user is ready for the first test on the microscope PC |
| Approach lock T-029d | `BENCH_APPROACH = "MEASURED"` (**lifted**, the user, 2026-10-02) | **Partly lifted**. Q13, Q20 and the stage limits have not been measured yet. On the real instrument every move that raises Z (approach, sweep, move_to) goes only up to the per-objective ceiling: 3200 µm for 4x, 10x, 20x and 2800 µm for 40x WI, 60x, 100x. So 100x focus finding is still refused |

Even with the motion lock lifted, all that works on the real instrument is Z retract and downward moves. XY moves come after T-032 stage 2,
and moves that raise Z after the approach lock is lifted (lifted 2026-10-02; the motion lock stays). The old bench scripts that moved the instrument outside the locks were deleted in R-05 (they are in the history).

### To fix before real login and remote viewing (security, unassigned)

- A sign-up request for an email that already exists is answered with `409 account_exists`, so whether an account exists can be learned remotely. Change it to a neutral answer.
- Login and unlock have no attempt limit. Add per-account and per-client limits and a temporary lockout.

### What the user has to do

1. Microscope PC: check the configuration file (the checklist's commands), device properties, objective working distances, measurements (Q12, Q13, Q20).
2. Three simulation `trajectory.txt` samples and the WSL path.
3. Approve lifting the motion lock (at the first test on the microscope PC).
4. ~~`Operator: kyuchoi` in the 30 September record~~ **Decision: leave it as is** (the user, 2026-10-02).
5. Commit memory on the development desktop: archive finished sessions, or enlarge the page file.

### Starting point (2026-10-01)

| Component | Location | State |
|---|---|---|
| Launcher | `scripts/launcher.py` (tkinter) (deleted in R-05; in the history) + `tools/launcher` exe | Only opens scripts in a console window |
| Live view | `scripts/live_focus.py` (912 lines, one tkinter file) (deleted in R-05; in the history) | Display, map, edge tracing, servo and records mixed in one file |
| Hardware access | `scripts/mm_grab.py` (deleted in R-05; in the history) | Imported directly by each script |
| Motion guard | `FocusAxis` in `C:\agentic_microscope` | Exists only on the microscope PC |
| Task scripts | `scan_4x`, `focus_100x`, `change_objective`, `find_particle_z`, `lights_off` | Used at the 30 September bench. `find_particle_z` judged unusable. All (deleted in R-05; in the history) |
| Focus score | `src/dino_autofocus/live.py`, `backbone.py` | DINO head trained only on synthetic 100x data |
| Records | `D:\AutoFocus\samples\<sample_id>\` | sample.json, map.json, scan, log |

## 4. Computers and Python environments

| Computer / environment | Does | Does not |
|---|---|---|
| Microscope PC, Windows (RTX A4000) | Hardware control, UI, **image synthesis, DINO training**, real-time scoring | — |
| Microscope PC, WSL | Simulation (already running) | Hardware control |
| Development desktop (GTX 1650 SUPER) | UI/engine development and tests in mock | Hardware runs, dataset generation, head training |

Python environment policy (recommendation, **final decision on the microscope PC**):
- On the Windows side, **one uv environment of this repository** runs control, UI and DINO.
  Rather than making one more uv environment, the aim is to remove today's use of the system Python.
- Heavy parts are split into optional dependencies. E.g. `ui`, `hw` (pymmcore-plus), `ml` (torch).
  The development desktop runs the UI and mock tests without `ml`.
- The WSL simulation keeps its current environment. Windows and WSL exchange only files and do not import from each other.
- At the integration stage the control code will run in soft-matter-agents' pixi `mic` environment.
  So the engine's dependencies are kept small.

## 5. Architecture

```
  Web (React + TypeScript, browser)                     <- no hardware logic, calls the API only
     | REST: commands, queries       ^ WebSocket: events, live frames
     v                               |
  Server (FastAPI, one Python process)                  <- owns the engine, turns requests into engine commands
     |
  Engine  (operations + guards + gates + records)       <- importable without web/server, the integration target
     |                     |
  Backend                  AgentStore
  mock | mm-demo | mm-real   mock | soft-matter-agents files (read-only)
```

- **Backend**: camera frames, position reads, light sources, guarded Z/XY moves, objectives.
  - `mock`: a simulator with a virtual sample (hole, particle positions), an objective set, light sources and stage limits.
    Frames are synthetic images that blur with |dz|. **The default backend for M1**.
  - `replay`: plays back saved z-stacks. `data/smoke` on the development PC, later real sample folders.
  - `mm-demo`: Micro-Manager demo devices. `mm-real`: the microscope PC.
- **AgentStore**: an adapter that reads questions, cards and run records and submits questions. The mock has fixed example cards.
- **Engine**: built of operations. Each operation has `plan → preflight → run → abort`,
  emits progress events and writes record files.
- **Gates**: compare the hardware profile file with each operation's requirements to turn operations on and off (F2.2).
- **Guards**: Z window, upward sweeps only, read-back, XY box, large XY moves only with Z retracted,
  lights off at the end, single owner of the core. A UI dialog is only an extra confirmation and never replaces a guard.
- **The large-XY-move threshold is set by one per-objective table inside the guards** (2026-10-01, the lead).
  There is no way for an operation to pass its own threshold (caller override). The table's values come from the free working distance:
  for example 4x (WD 20 mm) allows tile moves at sample Z, which keeps the 30 September scan procedure,
  and 100x Oil (WD 130 µm) retracts Z first when a move exceeds min(field of view, 1 mm).
  The objective is determined by read-back; if it cannot be read or is not in the table, the strictest value is used.
  Every value is `unmeasured provisional`, and at integration they move to the limits file a person owns (soft-matter-agents' `envelope/`).
- **The direction basis follows the 2026-09-30 run record** (the user, 2026-10-01). Evidence: `docs/runs/2026-09-30_substrate-scan.md`.
  - ZDrive: a larger value is toward the sample, a smaller one is retract. The retract position is 0 µm.
  - Z sweeps always measure going up (toward larger values).
  - The camera image is mirrored against the stage. With a stage move in +x, image features move in the +column direction.
    The stage coordinate of pixel p is `stage + inv(M) @ (centre − p)`, and the 4x calibration M starts from that record's value.
    Sample map click-to-move (F4) and edge tracing use this transform.
  - 4x tile scans run in serpentine order.
  - The F5 Y step-out is **set to +Y for now** (the user, 2026-10-01). The distance starts at 15 mm, the shorter end of the
    15–20 mm the user gave. Both are `unmeasured provisional`, and before moving, the stage Y limit is read and a move past it is refused.
    On the real bench the direction and distance are checked before M4 (Q12).
- **Focus**: classical metrics are the default and the final judge. The DINO score is an aid, and torch is imported only when used.
- The old bench scripts were deleted in R-05 after porting finished (they are in the history). Only model building, evaluation and figure scripts remain in `scripts/`.

Web app rules:
- The **Server** is the engine's sole owner. One process, one core. The server makes no judgements;
  it turns requests into engine commands and sends engine events out over WebSocket.
- **The API contract is defined in one place.** Commands, events and responses are defined as pydantic models on the Python side,
  and TypeScript types are generated from the OpenAPI that FastAPI produces. No hand-written copies are kept.
- **Live video**: the server bins frames and sends roughly 800 px JPEGs over WebSocket. Target 10 fps.
  Original frames are kept only in the disk records.
- **Access scope**: by default it binds to `127.0.0.1` only. Viewing from another PC is turned on by a setting.
  Remote connections may only read; commands that move anything are accepted only from the browser on the microscope PC.
- **Deployment**: FastAPI serves the React build output (`web/dist`) as static files.
  Node is needed only to build, not to run. `web/dist` is not put in git.
- **Launcher**: the desktop exe starts the server and opens the browser. The existing tkinter launcher is cleaned up after porting.
- Toolchain: Node 22 LTS, Vite, React, TypeScript, npm. **Node is not installed system-wide; it comes in through the uv dependency group
  `web` (nodejs-wheel).** `uv sync` alone installs the same version on the microscope PC and the development PC.
  Run with `uv run npm ...`, `uv run node ...`.

### Users and login (X3, X4)

```
  run exe -> server starts -> browser opens on the login screen
  login -> choose/authenticate user -> open an experiment session or view earlier sessions
```

- **Accounts**: a local user list on this PC. Kept in a settings folder outside the repository and not put in git.
  **The account id is the email used when the account was made** (D9). Login is email + password.
  Emails are compared case-insensitively, and there is one account per email.
- **Account creation (v0.9 decision)**: users sign up themselves with only **name, email and password**.
  A new account starts as `viewer`, and **an administrator approves it on screen and sets its role**. Users do not pick their own role.
  The creation time and the approving administrator go to the audit log. Items such as affiliation are not collected for now.
- **Administrator account**: the administrator email was chosen by the user. **This value is not put in code or git**
  (the repository becomes public at integration). It is read from a first-run setup screen or a local settings file / environment variable to
  create the administrator account. Tests use only fake addresses such as `example.test`.
  Passwords are hashed with the standard library's `hashlib.scrypt`, and the plain text is kept nowhere.
- **Roles**: `admin` (manages users), `operator` (can move the instrument), `viewer` (view only).
  On first run, admin is created with the administrator email above. Remote viewing connections also have to log in.
  Email verification mail and Google login are not built now, because they need a mail server or external authentication.
- **Device control**: only one user at a time moves the instrument. Everyone else only watches.
- **Auth cookie**: HttpOnly, SameSite=Strict. It locks after a period with no input. Even when locked, running operations and
  guards do not stop, and anyone can press stop (abort).
- **The three logs**
  - App log: server activity, errors. One file per day; old ones are cleaned up automatically.
  - Audit log (`audit.jsonl`): login/logout, every command's proposal, confirmation, execution and refusal, Claude conversations.
    Every line carries the user id and the experiment session id. Append only, never edited.
  - Experiment session log: kept in that session's folder and committed to the record store.
- **mock**: development and tests use fake users from the repository's test seed file.
  Real account information is not put in the repository.

### Experiment sessions and the record store (F7)

v0.9 decision: **the agent architecture stays as it is, and the party that made the data stores it in its own folder.**
No branch is made per session. The folder does the isolating, so there are no conflicts.

```
  D:\AutoFocus\records\                  record store: local git on the microscope PC, one branch, main (D10)
    microscope\sessions\<session_id>\    written only by this app (the microscope side)
      session.json    user, sample, start/end, status, code commit hash, hardware profile file hash
      log\            experiment session log
      records\        per-operation records (jsonl), sample_events.jsonl, flags, manual steps
      manifest.json   list of large files: path, size, sha256
    simulation\runs\<run_id>\            written only by the simulation side (the actual location is decided at integration)
    librarian\                           written only by the librarian: what was reflected, and when
  D:\AutoFocus\data\<session_id>\        large data, outside git: frames, stacks, mosaic originals
```

- **Each writer writes only its own folder.** The microscope app writes only `microscope\`, the simulation only `simulation\`,
  the librarian only `librarian\`. Other parties' folders are only read. This matches soft-matter-agents' principles
  "an agent folder is self-contained", "the files are the truth" and "only the librarian owns knowledge".
- **Nothing is written directly to the soft-matter-agents repository.** That repository is public. Only its folder layout is followed,
  and experiment records are kept in this local git, which is not published.
- **Sample state is written as appended events.** Map changes, flags and particle positions are appended to `records\sample_events.jsonl`,
  and the sample's current state is built from the events. Several sessions can handle the same sample without conflict.
- **Auto-commit**: at the end of each operation, and when a session closes, a commit is made **naming only the session's own folder path**.
  The author is the logged-in user. Git work runs in a separate worker so it does not block the instrument loop.
  If a commit fails, measurement continues and the failure is logged.
- **Large files are not put in git.** A file over the size cap leaves only its path and hash in the manifest.
- **Code version record**: when a session opens, this code repository's commit hash and whether there are uncommitted changes go into `session.json`.
- **Status**: `open` → `closed`. A closed session folder is read-only. The "not yet reflected / reflected" distinction a branch used to make
  is made instead by the status in `session.json` and the librarian's reflection record. A session's history is seen through the per-path git log.
- **Reflecting is the librarian agent's job.** It periodically reads `closed` sessions and reflects them into the knowledge store,
  and records what it reflected only in `librarian\`. This app does not reflect.
- **mock**: before integration, a fake librarian reflection script verifies the same flow.
- **Relation to soft-matter-agents**: an experiment session corresponds to that side's `runs/<run_id>/`. At the integration stage
  the way to link session id and run id is decided.

### Claude integration (X2)

Recommended structure: **call the Claude API inside the server, and expose the app's functions as Claude's tools.**

```
  screen's prompt box --(question + screen context)--> Server /api/assistant
      Server: Anthropic Python SDK, a hand-written streaming loop, model claude-opus-5-5
      tools = functions wrapping the engine and store APIs (the same APIs the screens use)
  <--(streamed answer, tool-call display, action proposal cards)--
```

- **Implementation (updated 2026-10-01)**: the Anthropic Python SDK's Messages API is called through **a hand-written streaming loop**.
  The loop is written by hand instead of using Tool Runner so that the approval gate sits inside our code, and so that fake-provider tests
  pass through the real gate unchanged (T-013). What the loop must keep to:
  - Check `stop_reason` first on every response. On `refusal` or `max_tokens`, run no tools.
  - When one response has several tool calls, run them all and return the results gathered in **one user message**. A failed tool is returned with `is_error`.
  - The conversation history is append only. The response's content blocks (thinking blocks included) are sent back unchanged.
  - Forced tool choice (`tool_choice` any/tool) is not used. On `claude-opus-5-5` it is a 400. `auto` + prompt instructions + `strict: true`.
  - Set `effort` explicitly (this model's default is medium). Thinking cannot be turned off, so it is not configured.
  - Server-side refusal fallback (`fallbacks`) is on by default.
  - Tool input is validated against the schema before it runs.
- **There are two kinds of tools.**
  - Read tools: hardware state, sample records, map, questions and cards, simulation progress and results. They run immediately.
  - Action tools: moves, light sources, objective change, starting a scan, etc. **They do not run; they only make a proposal card.**
    They reach the engine only when a person presses confirm on screen. The engine's gates and guards apply unchanged.
- **The same tools are later also opened as an MCP server.** Then soft-matter-agents' Claude Code sessions
  can use the same functions too. That is work for the integration stage.
- **Compared with the other options**
  - Claude Agent SDK: the whole Claude Code harness (files and bash included). Its permissions are too broad
    for an instrument UI. It suits a development agent.
  - Managed Agents: Anthropic runs the loop and the sandbox. The instrument tools have to run on this PC
    anyway, so there is little to gain.
- **Caching**: the system prompt and the tool list are fixed and cached; the screen context and the question are attached after them.
  No time or other value that changes each call goes into the system prompt.
- **Credentials**: the API key stays on the server only (an environment variable or an `ant auth login` profile).
  It is not sent to the browser. Without a key the prompt box shows "not connected" and the other functions keep working.
- **mock first**: tests and development use a fake LLM provider. The tool-call flow is verified
  with no network and no cost. Real calls happen only when the user turns them on.
- **Records**: every conversation, tool call, proposal and human confirmation/refusal is kept in record files.
  Numbers Claude produces are marked "model" and never mixed with measured values.
- **Cost display**: the tokens used are shown with every answer.

Directory layout:

```
src/dino_autofocus/engine/              backend.py events.py records.py guards.py gates.py sample.py
src/dino_autofocus/engine/backends/     mock.py replay.py mm_demo.py mm_real.py
src/dino_autofocus/engine/operations/   status.py hardware_scan.py edge_trace.py scan_4x.py
                                        sample_map.py objective_change.py focus_100x.py lights_off.py
src/dino_autofocus/agents/              store.py mock_store.py sma_files.py
src/dino_autofocus/focus/               classical.py dino.py verdict.py
src/dino_autofocus/server/              app.py api/ (one router per area) ws.py schemas/ static.py
src/dino_autofocus/assistant/           tools.py (read/proposal tools) runner.py providers/ (anthropic, fake) records.py
src/dino_autofocus/auth/                users.py (accounts, scrypt) sessions.py (login cookie) audit.py (audit log)
src/dino_autofocus/records/             session.py (experiment session) gitstore.py (path-scoped auto-commit) manifest.py mock_librarian.py (fake reflection)
web/                                    package.json vite.config.ts
web/src/app/                            shell: layout, navigation, status bar, API client
web/src/api/                            types generated from OpenAPI (generated, never edited by hand)
web/src/features/<area>/                console hardware sample map objective live simulation
web/src/app/assistant/                  the prompt box component shared by every screen
web/src/app/login/                      login screen, user display, lock
web/src/features/sessions/              open/close/list experiment sessions, view earlier sessions
tests/engine/  tests/agents/  tests/focus/  tests/server/   tests in web/ use vitest
```

## 6. Design rules (preparing for integration)

1. **The UI never calls hardware directly.** Every call goes through the engine.
2. **Safety is decided by code.** Guards and gates are in the engine, and a model takes no part in safety judgements.
3. **Model output is a verdict, not a Z.** Display vocabulary: `in_focus | step_up | step_down | no_sample_here | unsure`.
   Z comes from the encoder reading of the chosen frame. Model numbers are marked "model" in the records.
4. **Every operation leaves a record.** Start state, commands sent, values read, end state, manual steps.
5. **Lighting is always left in a defined state at the end.** When an operation ends normally, the lighting goes back to its state before the operation
   (lights the operator turned on stay on). Abort, error, server shutdown and `lights_off` all turn it off (2026-10-01, T-011).
   In every case the final lighting state is recorded.
6. **The engine runs without hardware.** Every function must first work end to end in mock.
7. **Commands and events are serialisable data.** The UI and the engine can later be split into separate processes.
8. **The engine does not import a UI toolkit or torch.** Heavy imports happen at the point of use.
9. **The agent store is read-only.** The UI writes no cards.
10. **The 30 September operating rules go into code.** Edge tracing in brightfield, then switching to particle illumination,
    re-tracing each session, waiting for the immersion loading confirmation, extending 100x upward only after the user approves.
11. **Claude only proposes.** Action tools run only after a person confirms, and even after confirmation they pass the engine's gates and
    guards unchanged. Claude takes no part in safety judgements or motion limits.
12. **Every command and record carries the user id and the experiment session id.** Without a logged-in operator and an open experiment session,
    commands that move the instrument are refused. On this PC (loopback) only stop (abort) and lights off (lights_off) are accepted even without a login,
    because both stop or switch off the instrument. Remotely, only a logged-in user's stop is accepted (D13).

Correspondence with soft-matter-agents (handled at the integration stage):

| This repository | soft-matter-agents |
|---|---|
| Backend | preflight / apply / read / abort in `devices/*.py` |
| Engine operation | a step of an approved plan, executed by `operator.py` |
| Gates, hardware profile file | the device registry and `envelope/` |
| Guards | `GuardedCore` allow list + orchestrator interlocks. **ZDrive, XYStage and Nosepiece are currently refused** |
| Records | `runs/<run_id>/log.json`, grade marks |
| AgentStore | `*/questions/`, `*/runs/`, `inbox/` |

## 7. Items needing a decision

| # | Question | Status / recommendation |
|---|---|---|
| D1 | UI technology | **Decided: local web app, FastAPI + React** (the user, 2026-10-01). Reasons below |
| D2 | Python environment | Policy in §4. **Final decision on the microscope PC** (the user, 2026-10-01) |
| D3 | Engine process | **Decided: the engine runs inside the FastAPI server process** (follows D1). The engine can be imported without the server |
| D4 | First scope | **Decided: every feature in mock first** (the user, 2026-10-01) |
| D5 | Public/private | **Decided: this repository is made public at integration** (the user, 2026-10-01). Private until then |
| D6 | How Claude is integrated | **Going ahead with the recommendation**: the Messages API on the server, a hand-written streaming loop (T-013, approved by the lead 2026-10-01), actions as proposal cards. MCP exposure at the integration stage |
| D7 | Data that may be sent to Claude | **Decided: text only, no images are sent** (the user, 2026-10-01). Policy below |
| D8 | Cost cap | **Decided: no limit for now** (the user, 2026-10-01). Usage is still shown and recorded. Model `claude-opus-5-5` |
| D9 | Login method | **Decided: log in with the email used at account creation** (the user, 2026-10-01). Implemented as email + password. The administrator account email was chosen by the user and is kept only in local settings |
| D10 | Record store location | **Decided: a local git repository on the microscope PC** (the user, 2026-10-01). No remote push is built |
| D11 | Record structure and reflection | **Decided: each party stores in its own folder, no per-session branches, the librarian reflects periodically** (the user, 2026-10-01). The period is decided at the integration stage |
| D12 | Account creation | **Decided: self sign-up with name, email and password → administrator approval and role assignment** (the user, 2026-10-01) |
| D13 | Stop from a remote connection | **Decided: a remote screen too can press stop (abort), and only that** (the user, 2026-10-01). Stop also needs a login (T-009b). Every other remote command, remote lights off included, stays refused |
| D14 | When every browser disconnects | **Decided: during an operation a person runs while watching, if every browser connection on the microscope PC drops, it stops automatically after 10 s** (the user, 2026-10-01). A screen on this PC whose login is locked also counts as connected. So does one refreshed while locked, and a locked screen is sent only the lock state, no data (the user, 2026-10-02, aligned with X3). Remote screens do not count |
| D15 | Light sources in M3 | **Decided: turning light sources on/off is allowed in M3 (microscope PC read-only)** (the user, 2026-10-01). Nothing moves, and every exit path turns the lights off. Aura and DiaLamp only |
| D16 | Writes by view-only users | **Decided: not allowed** (the user, 2026-10-01). Submitting questions and map flags are for an operator on the microscope PC only |

D7 data policy (enforced by one server setting; the default is `text`):

| Level | What goes to Claude |
|---|---|
| `prompt_only` | Only the prompt the user wrote and the screen context (short text such as ids and names). Read tools are not used |
| `text` (default) | The above + the text read tools return (state, records, cards, numbers). No images, frames or map pictures are sent |
| `images` | The above + images. **Not turned on until the user separately allows it** |

- If images are mixed into a tool result, the server strips them and records that it did.
- The level is shown at the top of the screen so the user knows what is going out right now.

Why D1 was set to web: in v0.1 the scope was only the microscope screen, so PySide6 was recommended. F1 widened the scope
to the agent console. Question entry, browsing cards and run records, sample map clicks and a status dashboard
are easy to build on the web. The same screens can also be opened in a browser in WSL or on another PC. With the engine behind an HTTP API,
it is also easy for agents to use the same API later. The cost is two languages (Python, TypeScript) and
live video streaming. Live video can reach 10 fps if the server bins it and sends roughly 800 px JPEGs.

## 8. Milestones

| | Content | How it is checked |
|---|---|---|
| M1 | **All features in mock**: engine contract, mock backend, mock agent store, F1–F7 screens, login and logs, the prompt box on every screen (fake LLM) | Run end to end from login through F1–F7 on the development desktop with no hardware. `uv run pytest` |
| M2 | Real data reading: reading soft-matter-agents files, real sample stacks through replay | The user checks |
| M3 | Microscope PC read-only: hardware detection, profile file, gates, status display. As an exception, turning light sources on/off is allowed (D15) | The user runs it on the microscope PC |
| M4 | Motion: sample map, click-to-move, objective change and immersion liquid loading, 100x focus | Bench records match the 30 September results |
| M5 | Focus verdict: classical metrics + DINO, head trained on the microscope PC | Microscope PC training/latency measurement records |
| M6 | Integration preparation: soft-matter-agents adapter design | Review by the lead |

## 9. Work packages and file ownership (assigned by the manager)

| Package | Content | Owned paths | Prerequisites |
|---|---|---|---|
| WP-A engine contract | Backend protocol, events, records, guard/gate skeleton | `engine/{backend,events,records,guards,gates,sample}.py` | None. First of all |
| WP-B backends | **mock simulator first**, replay, mm-demo, mm-real | `engine/backends/` | WP-A |
| WP-C porting existing operations | status, lights_off, edge_trace, scan_4x, focus_100x | the matching files in `engine/operations/` | WP-A, WP-B mock |
| WP-D1 server skeleton | FastAPI app, router structure, WebSocket event/frame bridge, static file serving, access scope setting | `server/{app,ws,static}.py`, the shared part of `server/schemas/`, `tests/server/` | WP-A event format |
| WP-D2 web shell | Vite + React + TS project, layout, navigation, status bar, generated-types client, live view | all of `web/` except `web/src/features/` | Node install, WP-D1 OpenAPI |
| WP-E focus + training runbook | classical metrics, DINO wrapper, verdict mapping, microscope PC training procedure | `focus/`, `docs/runbooks/` | None |
| WP-F agent console (F1) | AgentStore adapter, mock store, question/earlier-question/simulation/experiment screens | `agents/`, `server/api/console.py`, `web/src/features/console/` | None for the adapter; the screens need WP-D1·D2 |
| WP-G hardware detection (F2) | detection, profile file format, gate verdicts | `engine/operations/hardware_scan.py`, the rules in `engine/gates.py`, `server/api/hardware.py`, `web/src/features/hardware/` | WP-A |
| WP-H sample loading (F3) | geometry data model, input window, loading check | the geometry part of `engine/sample.py`, `server/api/sample.py`, `web/src/features/sample/` | WP-A |
| WP-I sample map (F4) | transmitted-light mosaic, particle candidates, flags, click-to-move | `engine/operations/sample_map.py`, `server/api/map.py`, `web/src/features/map/` | WP-B mock, WP-C scan_4x |
| WP-J objective change (F5) | the F5 sequence of §2, XY step-out/return, manual step | `engine/operations/objective_change.py`, `server/api/objective.py`, `web/src/features/objective/` | WP-A, WP-B mock |
| WP-K simulation status (F6) | progress, download, trajectory viewer 2D (Canvas)·3D (Three.js), result graphs. mock run generator | `server/api/simulation.py`, `web/src/features/simulation/`, the simulation-reading part of AgentStore | WP-F adapter, WP-D1·D2 |
| WP-L Claude integration (X1, X2) | tool definitions, streaming tool loop, fake provider, proposal card flow, D7 data policy, usage display, records, shared prompt box | `assistant/`, `server/api/assistant.py`, `web/src/app/assistant/` | WP-A, WP-D1·D2. Real calls when the user enters an API key and turns them on |
| WP-M login and logs (X3, X4) | accounts, roles, login cookie, lock, audit log, app log, login screen, the exe opening the browser on the login screen | `auth/`, `server/api/auth.py`, `web/src/app/login/`, `tools/launcher/` | WP-D1·D2 |
| WP-N experiment sessions (F7) | session lifecycle, session folder layout, path-scoped auto-commit, manifest, code version record, fake librarian reflection, sessions screen | `records/`, `server/api/sessions.py`, `web/src/features/sessions/` | WP-A record format, WP-M user id |

- Each function's screen, `server/api/<area>.py` together with `web/src/features/<area>/`, is owned by one package.
  The shell (WP-D2) keeps open only one registration point that attaches each area to the navigation, and the area packages do not edit that file.
- `web/package.json` and `web/package-lock.json` follow the same rule as `pyproject.toml`: only one session edits them, through the manager.
- `engine/gates.py` and `engine/sample.py` get their skeleton from WP-A; after that, G and H
  split the contents. The same file is never assigned to both at once.
- Shared files: `pyproject.toml` and `uv.lock` are edited by only one session, through the manager.
  `docs/PLAN.md` is written only by the lead. Session rules and task cards are in the internal notes (`dino-autofocus-internal`).
  `scripts/*` is edited only when a task says so explicitly.

## 10. Open items

To be decided later:
- F1.1 where questions are actually written. To be settled with soft-matter-agents.
- F3.2 contents; confirming the F3.1 field list.
- F5 step-out direction and distance. Set after measuring the stage Y limit and which way the sample's 24 mm side faces.
- In F5 the water objective (40x WI) is on hold because it has no working distance value (soft-matter-agents task 026 §5).
- F7 simulation data location: whether the WSL simulation writes directly to `records\simulation\`, or stays where it is now and
  the librarian and the screens read that path. **Decided at integration** (the user, 2026-10-01). No effect on mock.
- F6 progress: whether the WSL simulation leaves its progress in a file, and where the trajectories and logs are; to be checked on the microscope PC.
- X2 and the soft-matter-agents rules: that side's task 026 treats calling an external service as "the person's decision, not approved".
  This repository's Claude integration is something the user asked for, and at integration it has to be recorded in that side's records too.

Carried over from the 30 September bench:
- The particle discrimination in `find_particle_z.py` cannot be trusted (real particles are about 6.7 µm).
- An Aura flicker produced one frame with brightness −23 %.
- The 4x→100x parfocal offset was measured at about −60 µm and needs re-measuring with a reference sample.
- The A4000 latency and the measured performance of the fp16 head have not been measured yet.
- The current head was trained only on synthetic 100x fluorescence data. A brightfield glass/water interface is not simulated.
