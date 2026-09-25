# 049 — the double-well measurement: build what the dispatcher lacks, then run

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

## REVISED, 2026-09-25 ~10:40: you do NOT drive hardware today

**Read this section first. It overrides everything below it.**

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
