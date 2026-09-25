# 047 — sim to real: readiness for the double-well round (context, NOT an assignment)

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Revised the same evening it was written. This card no longer assigns the
double-well measurement.** It first did, at `a4a93f1`, on architecture's
request. Architecture withdrew the request on the person's word: **the task
arrives through the bridge.** The simulation writes the ask, the bridge
delivers it into `microscope_agent/inbox/`, and a microscope seat takes that
round as its goal (`plan.md` 4.4 rule 8, the tracer thread's shape). A
manager card assigning the measurement would duplicate the delivery and put
the task at the root. **The direction is the person's: simulation to
experiment.**

**So: start no measurement work from this card.** When the round is in the
inbox, this seat writes a short card naming the seat that takes it, as
`microscope_agent/CLAUDE.md` requires ("taking a round is S2, and it is
assigned by a task card like an axis is"). The person opened
`microscope-20260924-6` (`a04285b`) for this work, so that seat is the
expected one.

## What to have ready when the round arrives

Kept here as context, from architecture's list, so the seat that takes the
round does not rediscover it. **Read `plan.md` 11-23 first**: the person's
model (two Gaussian wells that add) and the four conditions under which the
observables are comparable across the two sides.

**The camera while trapping.** The Tweez300 takes one Kinetix and locks it
both ways (`camera_red` `exclusive_with: optical_tweezers_gui`). **Which body
records the bead while the tweezers hold the other is settled by serial,
never by label** (`camera_bodies_are_told_apart_by_serial`; today's runs
read `Kinetix_red` as `A24M723015`). Which body the tweezers GUI opens is
card 037's open line 0b, the person's to answer. Then **the frame rate**:
residence times and hops need a sampling interval well under the shortest
residence. **That decides whether the first run needs orchestration at
all.**

**Trap calibration, trap by trap, in SI.** **The stiffness method,
equipartition or a power spectrum, is declared before any data.** Each
trap's width and the separation. Pixel size **from the store for the
objective used, never from frame metadata**: 20x at 1x is measured (E2), and
the other objectives are computed (E4), so the grade travels with the
number. **An objective change invalidates both of the tweezers' own
calibrations** (`objective_change_invalidates_trap_calibration`), and they
are redone by hand in its GUI.

**Feasibility, by measurement, first.** At the stiffness ratios the person
wants, 1 to 100, is the weak well deeper than a few kT at achievable powers?
**A weak trap that cannot hold the bead gives a record with no hops**, which
bounds a rate and does not measure one.

## What is already known about the camera, and one estimate

**The person's answers to `microscope-20260924-6`, 2026-09-24**, the
person's word, not yet read off the GUI by serial:

- **the Tweez300 opens the red-arm body**, the one Micro-Manager reads as
  serial `A24M723015`. Confirm it by serial at the bench before relying on it
- *"we always release the camera, and you cannot see anything on the
  tweezer software"*: **the tweezers GUI records nothing, and it releases
  the camera.** So frames come from Micro-Manager after the release, while
  the tweezers keep trapping. **One camera, owned in turn**, and the first
  run may need no second camera. Card 037's line 0b is answered by this

**The one piece of work this card does assign**, records only:
`microscope-20260924-6` writes those two answers as `person_statement`
items in `microscope_agent/findings/microscope-20260924-6-20260924.json`,
with `recorded_at` naming the commit that adds it and a commit message
quoting the person. It then points the librarian at it. The estimate below
does **not** go there: a model's number is E6 and enters nothing.

**An estimate for the plan, NOT measured**, from the same seat: for a 5 µm
bead, `eps ~ k w^2` with `w` near the bead radius gives wells **hundreds of
kT deep at any holding stiffness**. If so, **hops need the barrier to be set
by the trap separation and overlap, not by a 1:100 power ratio.** The
feasibility measurement is what tests this. **The store holds no trap
stiffness at all**, and that gap is what the calibration fills.

## From the bridge manager's readiness review (`bridge/tasks/006`, `3ea532b`)

For the microscope side, as context:

- **the capability table now declares the four observables** (`0a4fae4`),
  on every imaging configuration that produces the trapped position
  distribution, each requiring trapping. Without that, the round would have
  been held and not delivered
- **trap naming, shared with the simulation**: `trap_1` is the deeper, stiffer
  trap, and **+x points from `trap_1` to `trap_2`**
- **say how each trap's Gaussian width and the separation are measured, in
  µm.** The barrier comes from the width, and nothing yet says how it is
  measured
- **the frame interval and the exposure go on the result card**: exposure
  averaging narrows the position histogram, and so the barrier read off it
- **"reached the minimum" needs a tolerance** that both sides apply to the
  same camera track. How close to a well's minimum counts as reaching it is
  part of the milestoning definition, and it must match the simulation's
- **what the simulation asks back** for its re-prediction: the calibrated
  `k1`, `k2`, `w` and the in-situ diffusivity `D`. The targets arrive as
  order-of-magnitude scalars plus prose, because no schema slot holds a
  requested range yet

## Today's protocol, 2026-09-25 (the person's words, relayed by architecture)

*"today we are going to trap one particle and make two trap to observe the
particle position data in time depending on the potential well depth. we can
start with same trap strengths in Tweeze300 software for both traps. then
decrease one trap's strength sequentially."* The particle is the Abvigen
5 µm bead, excited green, emitting red. **Relayed, so the seat that takes
the round logs the person's own words at hand-over.**

**Where the round stands** (~10:20 PDT): the simulation's ask is committed
(`sim-20260923-101`, `735a1a0`) and **not yet delivered**. There is no thread
in `bridge/threads/` and nothing in `inbox/`. The taking card waits on the
delivery.

**How the protocol meets the ask.** From the ask's own notes, every number
**simulated or assumed (E5), targets and not predictions**:

1. **equal traps first**, at 0.1 to 1 pN/µm. **Before any trap is weakened,
   tune the separation** from the projected position histogram until there
   are two peaks with a 1 to 4 kT barrier. Start near 2.1 trap widths
   (assumed `w` = 1 µm, so about 2.1 µm); about 0.5 kT per 10 nm at 1 pN/µm.
   So the run starts with a loop: a short record, its histogram, and the
   person nudging the separation
2. **the weakened trap is `trap_2`**, by the shared naming. The steps must be
   small: the tolerance is a few per cent at 1 pN/µm and about 40% at
   0.1 pN/µm, and **a strength ratio of 0.5 or less gives no hops at any
   separation**. The soft end is what makes a sequential decrease workable.
   The asymmetric target is `trap_2`'s well holding about 1/3 of the time
   (1 kT)
3. **at least 10 minutes per setting**, at 10 to 50 ms frames, with the
   exposure stated. About an hour at the asymmetric point to tell 1 kT from
   equal
4. **returned per trap**: calibrated stiffness and width, the separation as
   set, the in-situ diffusivity from the same record, and the temperature if
   read

**Two options architecture is putting to the person, not decided here:**
- **strengths changed by the person's hand** in the Tweez300 GUI and stated
  at each step is the cleanest record, since the tweezers report nothing
  back. **Strengths sent over TCP are motion**, and must sit inside the
  approved plan
- yesterday's runs bound dimming at a few per cent per 5 minutes at the low
  lamp setting, so **for hour-long records, transmitted light may track the
  bead better than fluorescence**

Disk: 1.6 TB free on D:.

## The person's bench procedure for 2026-09-25

Relayed from architecture, the person's own description. The task still
arrives via the bridge. This is only how the bench will be handed over:

1. **the person traps one bead by hand** in the tweezers GUI
2. **the person brings it up into the solution by hand**
3. **the person hands the bench to the seat, in that seat's own window**
4. the seat runs the double-well experiment from there, **under the round's
   approved plan**. It adds the second trap and sets strengths **only
   inside that plan**

**At hand-over, before the seat's first command, log four statements from
the person** as answered gates, in the person's own words, not relayed. This
is the laser-off case's shape, and the opposite state:

1. **the bead is trapped, and the bench is the seat's**
2. **the trapping laser's power setting at the hand control.** Software
   cannot read it (`trap_laser_power_has_no_software_path`)
3. **the bead's height above the coverslip, and how the person judged it**
4. **the objective in place**, because the tweezers' GUI calibrations are
   valid only for it

**At hand-over the tweezers are ON and holding a bead**, blind and assumed
on. So every trap command after it is motion. Check 85's laser-off
exception does not apply, and the round's plan is what covers it.

**Two physical points for the plan. They are general knowledge, NOT
measured here, and are labelled so wherever they are used:**

- **near the coverslip, the bead's drag rises**, while the simulation
  assumes bulk drag. A height of a few tens of µm keeps that small, inside
  what `P15` treats as a tie. **The cleanest fix is to measure the drag in
  situ**: the power-spectrum corner frequency from the same position record
  that calibrates stiffness. Then hand the simulation that measured
  diffusivity, which `plan.md` 11-23 condition 2 allows ("viscosity or
  diffusivity")
- **trapping through an oil objective into water weakens the trap with
  depth**, from spherical aberration, and it **hits the weak well hardest**,
  which is exactly the feasibility question at a stiffness ratio of 100.
  Calibrate at the depth used, and go no deeper than the wall effect needs.
  **If the 40x water-immersion objective (collar 0.17) is an option, the
  person may want to know.** Ask; do not decide

## The rules that will bind that work

- **the trapping laser has no software path**: its power is the person's
  hand, and nothing verifies `optical_power_max`
- **the tweezers are blind and assumed on** after any command, and nothing
  irreversible goes through them. A return code is not a verification, and
  a missing reply is never retried
- **the bench is the person's to hand over, in the seat's window**, and the
  tweezers hold it alone while they hold a camera
- **no software motion outside an approved operation plan.** At 100x oil,
  the clearance floor has zero margin
- **trap motion is motion** under check 85, except the laser-off, no-sample
  case with both of the person's statements asked first
- **the measurement bound for the comparison is a planned run**, through S1
  to S5 and the dispatcher. Card 041 gates the camera through the
  dispatcher

**Re-read this card, and the inbox, before starting anything.**
