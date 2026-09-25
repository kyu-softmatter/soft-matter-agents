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
