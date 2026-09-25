# 049 — the double-well measurement: build what the dispatcher lacks, then run

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

## REVISED AGAIN, 2026-09-25 ~12:00: you DO drive the tweezers, once five conditions hold

**Read this section first. It overrides the ~10:40 revision below it.**

In your window the person asked who should send the tweezers commands, and
chose **"Switch to me"** over "Architecture does it". **So phase 2 is
restored for you**, and the ~10:40 withdrawal is superseded. You send
**nothing** until all five of these hold, as you listed them:

1. **architecture confirms it has stopped** and holds no open TCP link to the
   Tweez300. Its bench process was stopped by the person at about 11:40,
   having sent only a readiness probe
2. **the person has written tweezers limits into `envelope/safety.json`**.
   The slots landed at `b64d967`: `optical_tweezers_{x,y}_position_{min,max}`
   in µm, each with a **required `objective`**; `optical_tweezers_strength_max`
   (unit `"1"`, at most 1); `optical_tweezers_position_step_max` (µm). The
   person's values are ±40 µm at 100x, strength up to 1, and a 1 µm step.
   **Only the person writes them.** Your scaled table for other objectives is
   your calculation, not a limit. **The wrapper refuses while the objective
   in place is not the limit's named one**
3. **the plan-derived exemption for `optical_tweezers` is built, tested with
   each safeguard watched failing, and taken by this seat to architecture**
   before live use (phase 1 item 2 below)
4. **a plan the person approves**, through the dispatcher
5. **the bench handed to you in your own window**, with the four hand-over
   statements from card 047 logged first

**Condition 2 and 3 status, 2026-09-25 afternoon:** the person's limits are
in `safety.json` (policy 8, valid, uncommitted, the person's to commit), and
the schema follows the person's names at `4ba2d1c`. **The trap-step
exemption (`759e9f0`) is accepted by architecture** (`plan.md` 11-23 at
`4a64512`), after this seat and architecture each re-ran its 19 tests and 11
mutations independently. **One note, not a condition: a strength change has
no step limit**, so one step could drop a trap from 1 to 0 and release the
bead. **Write strength trims as small, separate steps.** That also matches
the simulation's few-per-cent tolerance at the stiff end. **Conditions 4
and 5 remain.**

The analysis and record-committing work of the ~10:40 revision still
stands. Architecture's stopped run's logs sit at
`D:\soft-matter-agents-frames\run-20260925-001\`, for you to commit when
there is a run worth the name. It is a stand read, eight snaps and a probe.
**No two particles**: the person told architecture *"no two particles, it
was my mistake"*. The experiment is the one-bead asymmetric double well,
and your analysis declared at `5cd2b54` applies. The person also told
architecture *"session 6 will do"*, and architecture has released the bench
and holds no device. That is condition 1.

**The dia lamp: added to what software may command, State and Intensity
only** (a card decision, as the allow-list's own comment requires, made here
2026-09-25). Architecture found that after the person's configuration
loads, `DiaLamp` reads State 0, so **brightfield frames are dark**, and
`DiaLamp` is refused by name. Transmitted light is also what hour-long
records want, since the green line fades the bead a few per cent per 5
minutes. The person told architecture *"you can turn the lamp on
yourself"*. So:
- add `DiaLamp` to `SOFTWARE_MAY_COMMAND` with **only `State` and
  `Intensity`**, each read back after it is written, and nothing else on the
  stand. A test watched failing: any other `DiaLamp` property, or any other
  stand device, is still refused
- **say the lamp's state at hand-over and at release**, like every device you
  open. Architecture left it ON (State 1, Intensity 2100), so your first
  read will show it on
- the lamp is transmitted white light, not a laser. The eyepiece rule does
  not bind it, and nothing here needs a power limit for it

## Added 2026-09-25, after run `-008`: a declined hold, and the trap scale

**A hold answered with anything but yes is a planned stop, not a failure.**
Log it as `hold_declined` with the person's words, leave the traps as they
are, and send no abort and no `LASER_OFF`. **An explicit "abort" or "stop"
from the person at a hold does abort**, logged as the person's call. Abort
otherwise stays for failures: a rejected command, or a missing reply. Run
`-008` aborted on a "no", and the abort's fan-out switched the tweezers'
emission off. Switching it back on is the person's hand; the wrapper refuses
`LASER_ON`.

**No position command until the tweezers GUI's µm scale is confirmed for the
objective in place.** **Corrected the same evening:** the person's "second
trap is x = 2um" at `-008` meant *"I wanted it at 2 um"*, asked directly in
`-6`'s window, and **not** that it appeared there. So the person's words do
not show a scale error. The rule stands on different grounds: in the
strength scans, `trap_2` pulled the bead about 1 µm at a commanded +6 and
not at all at +5, which is backwards and unexplained. Until the GUI's µm are
checked against the camera, no commanded separation is a number, and "no
hops" cannot be told from "wrong separation". If the GUI's pixel-to-µm calibration is off, or
stale from another objective, every commanded µm is a GUI unit, and so are
the person's position limits. Make the person's confirmation, recorded
through `python_tcp`'s `confirm_calibration` (who, objective, pixel_to_um),
**a precondition the exemption checks**, with a test watched failing. If the
calibration is off, the person re-calibrates in the GUI. **Never scale
commands in code to compensate**: a silent factor is a limit nobody wrote.

## Superseded, ~10:40: you did NOT drive hardware then

After this card was written, the person told architecture in its window:
*"or you can operate tweez300. I can run micro-manager myself."* and then
*"i still prefer running it yourself."* So **today architecture operates the
Tweez300 over TCP** (trap creation, strengths, separation), and **the person
runs Micro-Manager and the camera by hand.** Asked directly in this seat's
window which to follow, the person stated no preference. **Two drivers of one
instrument is the outcome to avoid**, so the person's direct instruction to
architecture stands, and **phase 2 below is WITHDRAWN.** Open no device and
send no command. The bench is not yours today.

**What this card assigns you today, instead:**

1. **the analysis**, from the person's frames and architecture's command log:
   the position along the trap axis, the projected-trajectory histogram,
   occupancy, residence, rate and barrier, **by the simulation's milestone
   rule** (below), and each trap's stiffness from its own record, **with
   the method declared before you look at the data.** Pixel size from the
   store for the objective used, never from frame metadata. Architecture
   holds the command log outside the tree until a microscope seat commits
   it
2. **committing the run records architecture writes**, the way run `-005`
   was committed on card 048: verify each file against the hashes
   architecture records, change nothing, commit only those paths, and say in
   the message who made the run and that you are only the committer.
   Check 35 refuses architecture's commits into `microscope_agent/`, which
   is why this falls to you
3. **phase 1 may go on as code only**, at lower priority: never used live
   today, and it touches no device. It is what a later planned run needs.
   The exemption in item 2 still comes to me before any live use

**This run is not a planned measurement** through this agent's dispatcher,
so its numbers are a preparatory record. Whether they reach the store, and
how they meet `plan.md` 11-23's comparability conditions, is architecture's
and the person's to settle. **Do not write a result card for it on your
own.**

**Assigned to `microscope-20260924-6`.** The person decided on 2026-09-25,
to architecture and then in this seat's window:

- **this seat drives the instrument today**: the camera, the trap strengths
  over the network, and the stage, **inside a plan the person approves**.
  The person declined architecture driving it, and declined setting
  strengths by hand
- **start now**, without waiting for the bridge to deliver r1. **This card
  supersedes 047's "start no measurement work"** for this round. The
  bridge files r1 afterwards, so that `from_round` can be linked then
- **build first, then run.** Asked how to start, given that today's software
  cannot run it, the person chose to build the missing pieces before the
  first trap moves

**The target** is the simulation's committed ask, **cited by id and
revision, never copied**:
`simulation_agent/questions/sim-20260923-101/result_run-20260924-101-v3-hold.json`
at `735a1a0`. Its `bench_*` numbers are **targets, graded E5**, not
predictions. Card 047 holds the context: the person's protocol, the
hand-over statements, how the protocol meets the ask, and the physical
points.

**From the ask's payload, via the bridge manager** (r1 is carded to
`bridge-20260924-1` at `39dea86`, and lands at
`microscope_agent/inbox/thr-double-well-001/` when filed, marked delivered
after the run started, on the person's decision; link `from_round:
thr-double-well-001:r1` onto the goal afterwards):
- **the simulation's milestone rule**: a core around each of the two
  histogram peaks, radius a fixed fraction of their spacing, sticky at the
  frame interval. **Declare the same rule on the goal**, or the numbers will
  not be comparable later. It is the working answer to the shared-tolerance
  question until that lands in `observables.json`
- **`trap_1` sits at negative x**, and +x points from `trap_1` to `trap_2`
- **step down gently from equal traps; do not halve them.** At a ratio of
  one half or below there are no hops at any separation

## Why it cannot run yet, checked in the code

- **the allow-list refuses every tweezers command.** `optical_tweezers` is
  not in `SOFTWARE_MAY_COMMAND`, and the only exemption, from card 040,
  covers an approved **operation** plan's piezo X/Y moves
- **the camera cannot be dispatched from a plan.** That is card 041's two
  gaps: no Micro-Manager labels in the registry, and no settings from
  `derive_commands`
- **nothing turns a plan's trap steps into tweezers commands**
- **piezo moves inside a measurement plan**, as opposed to an operation
  plan, are refused as well

## Phase 1: build. Each piece has a test watched failing

**Card 041 is reassigned to you**, since you need it and you will be in the
same files. `microscope-20260924-1` is not open. **You are the only seat in
`src/orchestrator.py` and `src/operator.py` until this card is done.** Check
`git status` for anyone else's work there before starting, and stop if you
find any.

1. **041's substance**: the Micro-Manager labels as registry fields, asked of
   the librarian with the evidence from runs `-002`/`-006`/`-007`, never
   mapping `Aura` onto `widefield_source_a`; `derive_commands` producing
   settings that are read back; and the approvals read as `utf-8-sig`
2. **commands to `optical_tweezers` and `piezo_stage` from an approved
   measurement plan**, as a second exemption in
   `check_software_motion_for`, built exactly like card 040's:
   - **granted only in the same call that finds a `plan_approval` for this
     plan's revision and hash**
   - **only for commands identical to what the plan derives**. A hand-built
     command cannot ride an approved plan
   - **every derived position or strength checked against the envelope's
     limits** before the first is sent, and **a missing limit refuses**. The
     tweezers have no position or strength limits in the envelope today.
     **Ask the person what bounds them, and do not invent one.** A limit is
     the person's to write
   - **piezo Z still refused** until a Z target is compared against
     `objective_clearance_min` at the moment of the move
   - the tweezers are **blind: every dispatch records `verification: none`,
     and the beam is assumed on**. A missing reply is never retried
   - each exemption logged as its own event
3. **`derive_commands` for trap steps**: create a trap, set its position, set
   its strength, all from the plan's own fields. Extend
   `src/devices/python_tcp.py` (card 037's) only where the plan needs it,
   and name each change in the commit
4. **the plan**, S1 to S5, for a new question: **the milestoning estimator
   declared on the goal**, with the same well minima and barrier region as
   the simulation's; `trap_1` deeper and stiffer, +x from `trap_1` to
   `trap_2`; the target cited as above. **Re-copy the envelope snapshot
   first** (card 000), from committed export bytes, naming the commit

**Before any of phase 1 is used live, tell me, and I take the exemption in
item 2 to architecture**, as card 040's was. It is a policy change to where
"software moves nothing" binds.

## Phase 2: run, only after phase 1 has landed and the person approves the plan

Only when the person hands you the bench **in your own window**, logging the
four hand-over statements from card 047 as answered gates: the bead
trapped and the bench yours; the laser power at the hand control; the bead's
height and how it was judged; the objective in place. Then the person's
protocol:

1. **equal strengths first, and tune the separation** from the projected
   histogram to two peaks with a small barrier. That is a loop of short
   record, histogram and separation step, each step inside the approved plan
2. **weaken `trap_2` in small steps**. At a ratio of 0.5 or less there are no
   hops at any separation
3. **at least 10 minutes per setting**, with the frame interval and
   exposure stated; about an hour at the asymmetric point
4. **return per trap**: calibrated stiffness and width, the separation as
   set, the in-situ diffusivity from the same record, and the temperature
   if read

## Constraints

- **the trapping laser's power is the person's hand.** Nothing here reads or
  verifies it
- **the bench is held alone** while the tweezers hold a camera
- `envelope/safety.json` is the person's alone
- commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`,
  naming new files individually. Take your email from `contracts/seats.json`.
  Git hooks are not installed; say so. Run `python contracts/validate.py`,
  and read the tree line

**Re-read this card immediately before committing.**
