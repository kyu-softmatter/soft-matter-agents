# 000 — read this before 001

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

## Tomorrow, 2026-09-25: hardware orchestration — read this first

The person says tomorrow is **one planned run driving several devices
together through the dispatcher.** Readiness list from architecture, carried
here so the day's seats start from it.

**Blocking, in this order:**

1. **Card 041's substance**: the Micro-Manager labels in the registry, and
   `derive_commands` producing settings. **This is the one that gates
   orchestration.** Until it lands, no planned run can command the camera
   or a light source, and a session script is for a preparatory run only.
   040's piezo half has landed (`fc851c1`)
2. **Synchronisation, written before the first multi-device plan** (`plan.md`
   4.6.6 rule 4). For the intended combination (the camera with the piezo
   sine is the obvious first), say **which pairs are bound by a hardware
   trigger and which by software ordering, and how frame times and stage
   positions come onto one time base.** The camera's frame timestamps and a
   host-timed trajectory are different clocks
   (`host_clock_is_not_the_experiment_clock`). **A plan that pairs frames
   with positions without saying how is the silent kind of wrong**
3. **Cross-device interlocks, each held by code on the dispatch path, not
   by a card**:
   - the tweezers' exclusive camera
   - `plan.md` 2.1 rule 11's eyepiece read-back before any laser line
   - blind lasers assumed on
   - power up last and down first, across the whole parallel set (rule 4)
   - a configuration load counts as turning output on (rule 10)
   - PFS off during any Z motion
   - piezo Z still refused until clearance is compared at the moment of the
     move

**The person's, before the first orchestrated run:**

4. ~~commit the confocal command-voltage limit~~ **done by the person at
   `e389d4d`** (policy 7, 0 to 5 V). The per-line mW names are removed from
   the schema at `458c6df`
5. ~~correct the approval~~ **done by the person at `e389d4d`**:
   `approved_at` 2026-09-24T20:08:51Z, the file's own save time, 33 s before
   run `-005` began. It carries a byte-order mark, and the validator reads
   it since `f1e5b0b`. **Run `-005` is committed** at `829f241` by
   `microscope-20260924-6` on card 048; `-2` made it. **Its result card is
   still to write**, carrying the tracking error and the settled read-backs
6. **decided by the person**: a resting read-back may fall up to 10 nm short
   of a piezo floor and still count as at it, on every axis, and commands
   never go below the floor. The schema slot is
   `piezo_position_readback_tolerance` (`458c6df`). **Still to do**: the
   person writes it into `safety.json`, then a card has the piezo wrapper
   use it **only** for the resting check, refusing as today when it is
   absent

**The confocal work is paused for about a month**, by the person on the
evening of 2026-09-24: *"let's give up to connect confocal at this stage.
we can do it later around a month later"*. Do not include the confocal
lines in tomorrow's orchestration. What `microscope-20260924-3` left, from
its release:

- **the eyepiece mapping is recorded, by integer** (run `-008`, `9c9f598`):
  `LightPath` states **0 and 2 reach the eyepieces; 1 and 3 do not**
- after NIS was force-killed, the fiber shutter was left open with nothing
  owning it, and the beam was assumed on. **The person then closed the
  barrier by hand**: *"i turned off both"*, to `microscope-20260924-3`,
  meaning NIS closed and the combiner switched off at its own power.
  **Software read none of it**, so the person is the barrier the blind-laser
  rule accepts. **Read the state at the bench before anything else anyway**
- after that kill, **the stand stopped answering a Micro-Manager load**,
  hanging 2 to 6 minutes (runs `-009` and `-010`). Nobody has tried
  reconnecting or power-cycling its controller. **This may block tomorrow's
  camera work**, so check it first
- `lunf.py` (`3fcf1e0`) takes the person's voltage pair as its covering
  limit, and the person's `safety.json` with it is still uncommitted

**The first simulation-experiment comparison arrives through the bridge.**
The simulation writes the ask for one bead in an asymmetric double well, and
the bridge delivers it into `microscope_agent/inbox/`. **When it lands, a
microscope manager writes a short taking card** that names
`microscope-20260924-6`, points at the round's path in `inbox/`, and carries
**no task content**. It is what stops two of six seats taking one round, and
architecture confirmed it. The goal's `from_round` is the record of the
taking. Card 047 holds the readiness context: the camera, the calibration,
the feasibility question, and the person's bench procedure. **Start nothing
from 047 itself.**

**The microscope envelope snapshot is behind the store.** The librarian
published `kbv-d2db58512e78` (257 entries) at `b7dcc9b`, including seven
trapping-laser power-at-sample entries from the person's 2026-09-09
calibration and regenerated per-device safety guides in
`librarian_agent/kb/guides/`. Re-copying `kb/exports/snapshot_microscope.json`
into `envelope/snapshot.json` is an execution seat's, from committed export
bytes only, **never under a fan-out already pinned**:
- `mic-20260924-001` (card 034) re-copies once, at its v2 re-pin at S4
- **the double-well round opens a new question, so re-copy before its fan-out
  starts**, and name the export commit taken

**Two contract questions deferred to after the bench, deliberately.**
Changing a definition the night before, while both sides write against the
current text, is the wrong moment:
- **a shared tolerance for "reached the minimum"** in the milestoning
  definition in `contracts/observables.json`. `manager-bridge-20260924-1`
  takes it, drafting with `manager-simulation`, from what the bench track
  shows, and sends it to both sides before it lands
- **no schema slot holds a requested range** on a goal written from a
  delivered round (the bridge review's G9). A microscope manager takes it.
  Tomorrow uses the interim convention: order-of-magnitude scalars read as
  targets, with prose
- **no envelope slot holds tweezers limits** (trap position, strength,
  step). So card 049's exemption refuses every tweezers command, which is
  correct until the person writes limits into a slot a manager adds. On
  2026-09-25 the person delegated today's bounds to architecture, recorded as
  architecture's and not as envelope limits
- **no artifact shape for an analysis declaration.** `microscope-20260924-6`
  declared its double-well method before any data, at
  `questions/mic-20260925-001/analysis_method_declared.json` (`5cd2b54`),
  with no artifact key. It stays there, since it must not move after the
  data is opened
- **the residence estimator differs between the sides**: the simulation's
  ask computes `well_residence_time` as the mean completed dwell, while
  `observables.json` registers the renewal form. **The registered form
  binds.** The microscope reports it as the observable, and the other only
  as a secondary figure. **Fixed on the simulation side at `d42315d`**:
  `double_well.estimate` now uses the renewal form, keeping the dwell mean as
  `residence_*_completed_mean`. **But the delivered r1 card is pinned and
  unchanged, so its residence figures are the dwell mean and are NOT the
  comparison value.** The re-prediction at the microscope's calibrated values
  is

**Worth doing first thing: install the hooks** (`git config core.hooksPath
contracts/hooks`) while someone watches the first commits. A day of
multi-device commits from several seats is when the gate earns its keep.

## Where things stand, the evening of 2026-09-24

Added by `manager-microscope-20260924-1` at the end of the first day on the
microscope computer. **Everything below this section is from 2026-09-19 and
older.** Read it as history.

**What the day produced:**

- **The first real acquisition**, a preparatory run: `-002`, 600 frames on
  the Abvigen particles through the 20x (card 033). Before it, `-001` failed
  at load and harmed nothing
- **Card 038's five-minute run is `-006`** (`adb57f4`): 300 paced snaps,
  the dark test passed again, and the bench was released with the Aura read
  back off. Its first attempt, `-003`, stopped at preload because the
  tweezers program was running, with nothing loaded and no light (`8ee6158`)
- **The photostability numbers first reported for `-002` were wrong.** "80.7%
  after 60 s" was particles drifting off a mask fixed at frame 0, not
  bleaching. Over the whole frame, `-002` stays within 99.2 to 101.0%. `-006`
  rises 3.5% in 5 s, probably the Aura settling, then falls 2.6% over 295 s.
  **That is an upper bound on bleaching, not a rate**: particles drifted a
  median of 17 px (about 5.5 µm at 20x, some leaving the field), and focus
  was not controlled. No decay model can be preferred on 2.6%. **For card
  034's design, drift, not bleaching, is the effect to bound.** Findings
  corrected at `ac20ee4`
- **The repeat at another location is `-007`** (`51cc2eb`), analysed by the
  `CLAUDE.md` method: a 3.6% decline over 299 s from the settled level, with
  a median drift of 9.9 px. **More decline with less drift than `-006` makes
  drift a poor explanation**, so a slow real fade of a few percent per 5 min
  at 10% Aura green is likely. It is still an upper bound, with focus
  uncontrolled, and it waits for card 034's plan, like `-006`
- **A read-only piezo run** (`-004`) and **the first planned motion**: the
  person's approved sine on piezo X (`-005`, cards 035 and 040), through the
  dispatcher
- **Wrappers, on paper and on mock**, for the confocal laser (036) and the
  tweezers (037)
- **The rules these runs needed**, in `contracts/`: preparatory runs (check
  85), operation plans (check 86), the piezo limits in the envelope schema,
  declared exclusions, and the findings file that carries a seat's findings
  to the librarian

**Open, for whoever comes next:**

| | where it waits |
|---|---|
| run `-005` is **committed** (`829f241`, made by `-2`, committed by `-6` on card 048), and check 15 is clear. **Its committed blobs hash differently from the sha256s `-2` recorded** for three of its four files (`deviations.json`, `log.json`, `position_vs_time.svg`). **The content is identical**: `-2` hashed the files on disk with CRLF endings, and git stores them LF on this checkout. Verified by folding CRLF to LF: each folded hash equals the committed blob, and `report.md` matches either way. The out-of-tree copy at `D:\soft-matter-agents-frames\run-20260924-005\` keeps the CRLF bytes the recorded hashes name. **Its result card, the tracking error, is still to write** | a card naming the seat that writes the result card |
| card 041: the dispatcher reaching Micro-Manager, plus the byte-order-mark fix for approvals | `microscope-20260924-1`'s |
| **the day's findings are in the store**: 62 entries, 24 of them self-reports citing today's runs, `-4`'s twelve tweezers entries, and both piezo ranges (the controller's 0 to 600 µm and the person's −100 to 600 µm) naming each other. No observable value cites a preparatory run. Published at `kbv-a1bb4a5acf25`, pushed at `d2162d9` | done |
| `librarian_agent/tasks/037` is untracked | `manager-librarian-20260924-1`'s to commit |
| `manager-librarian-20260924-1` was opened in `librarian_agent/`, where it cannot write its own tasks or settings | the person: reopen it at the repository root under that name (its row is `ff8e673`) |
| **a lead on the unconfirmed Lapp branch** (card 018 §5, `lapp_branch_assignment`). The person, to `microscope-20260924-5` on the evening of 2026-09-24: with a sample reloaded, particles seen under the Aura III, Micro-Manager reading `LappMainBranch1` State 1 (`mirror_in`), *"this is for the Aura3 light source"* (findings at `cd09784`). **Run `-002` lit the particles with the Aura at State 1.** Card 018 says a label cannot settle the branch and an acquisition can. `-002` is an acquisition consistent with the statement, but it did not block one engine to show which state goes dark. **Graded by the librarian: `lapp_state_1_brings_the_aura_to_the_sample`, E3, at `4dce92d`.** `lapp_branch_assignment` is **narrowed, not closed**: whether the Spectra III also reaches the sample at State 1 is not established. The test that would close it is blocking one engine and seeing which state goes dark | a bench session, then 034's S4 |
| `microscope-20260924-5`'s work is delivered (`cd09784`); the seat has nothing further | the person may archive it |
| everything not yet on the remote | push with `git -c credential.helper=manager push origin main` (CLAUDE.md), once the approval and `librarian_agent/tasks/037` are committed |
| card 034's S4, S5 and v2 fan-out, re-copying the envelope snapshot then | a later seat, once 041 lets a planned 20x run through the dispatcher |
| **piezo Z**: it rests 1.7 nm below the person's 0 µm floor. The person asked for a −0.01 µm floor, a change only the person can write. But **the controller reports its own calibrated range as 0 to 600 µm**, so a floor below 0 would allow commands below that range. The alternative put to the person: keep the floor at 0, and let the wrapper accept a *starting* position within a few nanometres below it. Its direction is unmeasured, and software refuses Z until a Z move is checked against objective clearance at the moment of the move | the person, then a card |
| the confocal lines: **the power calibration is in the store**, from the person's 2026-09-09 worksheet with its metadata completed by the person: nine `confocal_power_at_sample_*` entries at E2, for 488, 561 and 640 nm at 100% through 4x, 10x and 20x. They are valid to 2036-09-24. `line_power.calibrated` is true, with coverage naming what is **not** covered: 405 nm, 100x, and any level but 100%. **No limit covers these lines yet**, and a calibration is not a limit | the person: write the limit |
| the tweezers: which camera body the program opens, and the trap power for a first lit check | the person |
| whether the piezo's waveform generator may ever be used | the person |
| the commit hooks are fixed and still not installed in this working copy | the person: install them when someone can watch the first commits |

**The bench rule governs everything live**: a seat opens a device only
after the person says, in that seat's own window, that the bench is its
(`plan.md` 6.2.1). **Read every device's state at the bench before
trusting a note about it**, this one included.

**The hold is lifted.** This file replaces `000-hold-until-the-librarian-
serves.md`, which told you to start nothing. Its premise was the A/B, and
`58064da` deferred the second variant: the person stopped `microscope-2` and
removed the worktrees. §9.3's constraints — the librarian gate, the matched
`qid`, the ban on pre-start rulings — existed to keep two variants even. With
one variant they protect nothing and only cost, so they are off. You are a
microscope execution seat, not half of a comparison.

The old card is in the history, not deleted from it. §9.3 is likewise marked
deferred rather than removed, and the `microscope-2` seat and branch stay
(P16): the branch holds what that variant built, and removing the seat entry
would turn its commits into unattributed ones.

## Where the fan-out stands (2026-09-19)

**`mic-20260918-001` is complete and served.** All seven axes are written,
`A1`–`A7`, all at one pin and all answered by the service. Counted off a run
rather than claimed here — run it yourself, the numbers move:

```bash
python3 contracts/validate.py 2>&1 | grep -E 'check (33|45|49)'
```

At the time of writing: check 33 over 19 axis cards at one `kb_version`,
check 45 over 7 served cards each backed by a call in the log, check 49 over
31 `absent` gaps each carrying `near_names`. **Cards 001 through 006 are
discharged.** Do not redo them.

**Every axis abstains except A4**, which returned two bounds in the shapes
opened for it — an `allowed_set` on `lock_group` and a `precondition` on
`verified_selectors`. Abstention with a reason is the correct outcome
(§4.5.2.1), not a backlog.

## What is left, and what blocks each

| card | state |
|---|---|
| **008** — the deliberate re-pin | **Runnable.** Its preconditions arrived: the twelve calibrated pixel sizes, and λ as `filter_ff01_595_31_32_passband`, 579.5–610.5 nm at `spec:` E3. Expected to give A6 its diffraction limit at E3 |
| **009** — the goal targets | Waits on the bridge manager's list. Nine cards across three trees move together or check 52 refuses the half-move |
| **007** — the operator's decade | Fold into 009; both touch the same goal cards |
| **A4's three remaining bounds** | Blocked on `contracts/`, not on you. `allowed_set.basis` and `precondition.basis` take a `numbers[]` name or `kb:<entry_id>`, and A4's answers live in a **published table** with neither. `manager-microscope` owns that |
| **A5's gaps** | Need the person or a measurement: `drift_rate`, `pfs_behaviour`, `settling_time`, `session_time_budget`, `instrument_availability_window` |

## If you have just restarted and have no seat

**Check `contracts/seats.json` before anything.** On 2026-09-19 the person
withdrew two newly minted microscope seats (`5bc83e9`) and ruled that one is
minted **only on a statement**. A seat named to you in chat is not a seat
until that file says so, and committing without one is check 41 PENDING,
which `--strict` counts as a failure from your first commit.

**A seat cannot be given to you by this card or by any session** (§6.2.2).
Ask the person; do not proceed on a relay. Standing down until then is a
correct outcome, not a stall.

## The librarian answers now

**Settled on 2026-09-19, by measurement rather than inference.** The tools
attach, the service replied, and `librarian_agent/queries/log.jsonl` holds the
first record this repository has ever had of the service answering:
`caller_id` `mic-20260918-001:widefield_inline:a4`, pinned at
`kbv-49feb73662b7`, `answered_from` naming commit `9baf01d` and
`reproducible: true`. The served digest matched that commit's blob byte for
byte, and *differed* from the working-copy file — which is the confirmation,
not a problem: the entry gained a field afterwards and the server correctly
served the version the pin names. Staying on `kbv-49feb73662b7` is therefore
not just permitted, it is demonstrated.

**An earlier version of this card was wrong about why, and the error is worth
keeping.** It said `enabledMcpjsonServers` is empty at every project path, so
no session could see the tools. The first half is still true — it is empty
everywhere — and the conclusion was false: the tools attached anyway. **That
field is not the gate.** What was blocking was the server path, fixed by
`8d4a604`. If a seat ever fails to attach, do not diagnose it from that field;
read the launcher's own log:

```
~/Library/Caches/claude-cli-nodejs/<path with / replaced by ->/mcp-logs-librarian/
```

It records the `cwd` the server started in and any `Server stderr`. Note what
it does **not** record: the `kb_version`. Connection success there does not
tell you which store answered — only a call does, through `answered_from`.

**A contract fix that is not yours to make alone.** `d6999e5` takes an
observable's definition out of the cards, leaving the name to be read from the
vocabulary. `questions/mic-20260918-001/goal.json` carries one, on
`diffusivity`. The bridge manager is coordinating the window because the other
cards belong to other agents and fixing one alone turns HEAD red. **Leave it
until that window opens**; I will card it.

## Your identity

There are no worktrees now — `git worktree list` reports one checkout — so the
`--worktree` mechanism has nothing to attach to. Set it per command:

```bash
GIT_COMMITTER_NAME='seat:microscope-1' GIT_COMMITTER_EMAIL=microscope-1@seat.invalid git commit -F msg -- <paths>
```

**Keep `microscope-1`, not the undivided `microscope`.** You are that seat
whether or not its worktree exists, and the branch keeps the identity if one
is made again. `microscope` stays valid only for the commits already made
under it.

Because you are in the shared checkout, §6.2.1 applies again: name paths
rather than using `-A`, and commit with `git commit -- <paths>`. Other
sessions are editing this same working copy.
