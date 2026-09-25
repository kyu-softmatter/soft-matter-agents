# 047 — sim to real: one bead in an asymmetric double well

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-6`** (registered at `a04285b`). The person
opened this seat for "sim to real": tomorrow, 2026-09-25, **one particle held
by the tweezers in two traps, measured, and tested against the simulation.**
If your session is not rooted in `microscope_agent/`, stop: the person is
reopening it there, and a seat outside its directory has none of its guards.

**Phase A is tonight, on paper.** Phase B is tomorrow, with the bench.

**Goal**: the microscope side of the first simulation-experiment comparison.
The four double-well observables, `well_occupancy`, `well_residence_time`,
`interwell_transition_rate` and `interwell_barrier_height`, are measured
from one trapped bead in two traps, **as a planned run whose result card can
meet the simulation's at the bridge.**

## Read first

- **`plan.md` 11-23**: the person's model (two Gaussian wells that add,
  each harmonic at its bottom with `k_i = eps_i / w_i^2`), and **the four
  conditions under which the observables are comparable**: the same
  registered estimator (milestoning, with the same well minima and barrier
  region) on both sides; the potential's parameters in SI, mapped
  explicitly; record length and sampling interval stated; and each number
  carrying its own side's grade
- **card 037** and `src/devices/python_tcp.py`, `microscope-20260924-4`'s
  tweezers wrapper, and its live checklist. **Build on it, do not fork it.**
  A change to it is a line on 037, asked of me
- **card 000**, tomorrow's readiness list. **Card 041 (the dispatcher
  reaching the camera) gates any planned run that records frames**

## The rules that bind this work

- **The trapping laser has no software path.** Its power is the person's
  hand, and nothing here verifies `optical_power_max`
  (`trap_laser_power_has_no_software_path`). No test may imply otherwise
- **The tweezers are blind and assumed on** after any command
  (`plan.md` 4.6.6 rule 5, 4.6.6.1 rule 3). **Nothing irreversible goes
  through them.** A return code is not a verification, and a missing reply
  is never retried, because commands are relative
- **The bench is the person's to hand over, in your window**, and **the
  tweezers hold it alone** while they hold a camera (6.2.1)
- **No software motion outside an approved operation plan.** At the 100x
  oil objective, the one in today's tweezers path, **the clearance floor has
  zero margin**. Focus is the person's hand
- **Trap motion is motion**: check 85 refuses a plan-less run that dispatches
  to `optical_tweezers`, except the laser-off, no-sample case with both of
  the person's statements asked first
- rules 4, 8, 10 and 11 of `plan.md` 2.1: power up last and down first; a
  confirmed ceiling bounds what is demanded, not what happened; loading
  saved state turns output on; no laser while the path reaches the
  eyepieces

## Phase A, tonight, on paper: nothing touches the hardware

**1. The camera while trapping.** The Tweez300 takes one Kinetix and locks
it both ways (`camera_red` `exclusive_with: optical_tweezers_gui`). **Settle
which body records the bead while the tweezers hold the other, by serial
and never by label.** The store has `camera_bodies_are_told_apart_by_serial`,
and today's runs read `Kinetix_red` as serial `A24M723015`. Which body the
tweezers GUI opens is 037's open line 0b: **ask the person.** Then say at
what frame rate: **residence times and hops need a sampling interval well
under the shortest residence**, so state the shortest residence you expect,
where that expectation comes from, and the interval it forces. **This
decides whether orchestration is needed for the first run at all.** If the
tweezers' own camera can record the bead, the first run may need no second
camera.

**2. Trap calibration, trap by trap, in SI.**
- **Declare the stiffness method BEFORE any data**: equipartition, or a
  power spectrum. A method chosen after the data is narration
- each trap's width, and the separation
- pixel size **from the store, for the objective used, never from frame
  metadata**. The store holds 20x at 1x as measured, E2; the other
  objectives are E4 computed. At 100x that is a computed figure, and the
  grade has to travel with it
- **an objective change invalidates both of the tweezers' own
  calibrations** (`objective_change_invalidates_trap_calibration`), and they
  are redone by hand in its GUI, by the person

**3. Feasibility, first, by measurement.** At the stiffness ratios the
person wants, 1 to 100, **is the weak well deeper than a few kT at
achievable powers?** Establish it before planning the full sweep. **A weak
trap that cannot hold the bead gives a record with no hops**, which bounds a
rate and does not measure one. Write down tonight what measurement would
settle it, and what result would stop the sweep.

**4. The planned run: S1 to S5**, with **the milestoning estimator
declared on the goal card**, and the same definitions of well minima and
barrier region that the simulation uses. Tonight: S2, the goal card, can be
drafted. The rest waits on 1 to 3.

Then **the first bridge round**: the experiment's calibrated parameters go to
the simulation as an ask, for a prediction at exactly those settings. **The
bridge manager proposes the direction, and the person decides.** Do not send
it on your own.

## Phase B, tomorrow, not by your own decision

Only when the person has said, in your window, that the bench is yours,
and with every other seat off the cameras. Read-only first: the tweezers'
readiness codes, measured, and which camera the GUI opened, by serial. Then
calibration, then the feasibility check, then the planned run. **Each is a
step you report before the next.**

## What to bring back

- the camera answer, by serial, and the frame rate it supports
- the declared stiffness method, before any data
- the feasibility measurement and what it showed
- the goal card, with the estimator declared
- **every place the vocabulary cannot say what you need**, as a list. The
  flag that makes an observable comparable across the two sides is a
  manager's, in `observables.json`, per observable, once 11-23's conditions
  hold. Say which ones hold

## Constraints

- no hardware tonight
- `envelope/safety.json` is the person's alone
- commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`.
  Take your email from `contracts/seats.json`. Hooks are not installed; say
  so. Run `PYTHONUTF8=1 python contracts/validate.py` and read the tree line

**Re-read this card immediately before committing.**
