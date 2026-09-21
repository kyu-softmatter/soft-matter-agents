# 018 — what to test the first time the hardware is connected

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Not assigned yet: this is a checklist to have ready, not work to start.**
It becomes a card with a seat on it the day the instrument is on the bench.
Written now because every line below is a thing the store already knows and
a person at the instrument would otherwise rediscover.

**Order matters and it is P0's order** — people, then instrument, then
sample. Do not skip to the interesting part; §2 comes before §4 because a
mis-set light engine is a person problem and a mis-set nosepiece is a
collision.

## 0. Before anything moves: does the plan's vocabulary exist?

```
getLoadedDevices()
```

Compare against every name the plan calls. **MM labels are not product
names** — `LightEngine` is the Spectra III, `Aura` the Aura III,
`Kinetix_red` the red Kinetix 22, `Nosepiece` the Ti2-E turret. Calling one
`SpectraIII` fails as *device not found*, which reads as the wrong stand
rather than the wrong string.

A name in neither the channel table nor its elements is a `GapError` and
stays one. **Do not invent a mapping at the bench.**

## 1. PEOPLE — the light engines, and the fault that looks like a result

**1a. The master `State` gates everything, silently.** Both Lumencor engines
carry `State` taking 0 or 1. **With `State` at 0 no light leaves the engine
however a line and its intensity are set, nothing reports an error, and both
properties read back exactly as written**
(`light_engine_master_state_gates_every_line`, E3).

> Over there the first run produced a field whose median was **below a dark
> frame** and a ratio computed from hot pixels — **and it looked like a
> result.**

**Test it deliberately, in this direction**: set `State = 0`, set a line to
maximum, take a frame, and **confirm it is dark**. A run that cannot
demonstrate the dark case cannot claim the bright one. Then `State = 1` and
repeat.

**1b. Intensity is per-mille, 0–1000, not per cent**
(`light_engine_line_intensity_is_per_mille`, E3). **The person's 10% is
`100`. Writing `10` gives one per cent.** Over there 5% written as `50` is
recorded, with the warning that `5` gives 0.5%. **Read one line's intensity
back and confirm the scale before trusting any exposure.**

**1c. The trapping laser has no software path at all.** Its power is a hand
control (`trap_laser_power_has_no_software_path`, E3), so
`optical_power_max` in `envelope/safety.json` is the only control there is.
**Nothing here can verify compliance with it.** Do not write a test that
implies otherwise.

## 2. INSTRUMENT — the collisions

**2a. A nosepiece write runs no objective escape**
(`nosepiece_write_runs_no_escape`, E3). Rotating at the stand or in NIS does
run one; **a Micro-Manager write does not.** Z stays where it was and the
incoming objective arrives at the outgoing one's height.

**Test with the stage low and nothing mounted.** Command a rotation from the
longest working distance to the shortest, read Z before and after, and
**confirm Z did not move.** That is the failure, and seeing it once is worth
more than the entry.

**The retract is a step the plan issues and verifies.** It is not a property
of the stand and must never be assumed.

**2b. The nosepiece is a state device, indexed from 0.** Read with
`getStateLabel`, set with `setState`; there is no `Position` property
(`nosepiece_is_an_mmcore_state_device`, E3). **Six positions run 0 through
5.** `operator.resolve_limits` already refuses 6 with that message —
confirm the labels here carry the objective designations you expect, because
the clearance floor is keyed off which lens is in the path.

**2c. Clearance at `100x@1x` has zero margin.** The person chose that pair.
Its working distance is **0.13 mm, the shortest of the six**, and
`objective_clearance_absolute_min` is **130 µm** — the lookup and the
backstop **coincide exactly**. That is the consequence of the lens choice,
not a defect, but it means **nothing is left over** at that objective. Know
it before the first approach.

**2d. PVCAM hands a camera to one process at a time.** The tweezers GUI
opens a Kinetix body, and whoever opens first locks the other out **in both
directions** (`camera_red` `exclusive_with: optical_tweezers_gui`). **Test
the ordering you intend to use**, and test the failure: open the GUI first,
then try to acquire, and see what the error actually is.

**2e. Changing the objective invalidates both trap calibrations**
(`objective_change_invalidates_trap_calibration`, E3) — the GUI's
pixel-to-micrometre magnification and the AOD's field response — and
**neither is readable over TCP.** So this is not a test, it is a rule: after
any rotation, both are unknown until re-done by hand.

## 3. READ-BACK — what the instrument will and will not tell you

**3a. Two channels report nothing back**: `laser_combiner` and
`optical_tweezers` carry `read_back: false`. On the Tweez 300 there is **no
query command of any kind** — no position, no force, no trap list, no
calibration — and **a return code of 0 means the GUI accepted the text**;
six distinct ways a command can be ignored all return 0
(`tweez300_reports_nothing_back`, E3).

**A return code is not a verification.** Every dispatch on those two writes
`verification: "none"` in the run log, and check 66 reads it. **An
acknowledgement is `none`**, and a `readback` claimed on either of them is a
failure the check will catch.

**3b. A missing reply is never retried; an explicit rejection may be.** The
"busy" code is the GUI saying *I did not run this*, so re-sending is safe. A
**missing** reply leaves the command's fate unknown, and **several trap
commands are relative** — re-sending one that did land moves the trap twice.

**3c. Re-measure their readiness codes before trusting any of them.** The
prior project treats three codes as "up" and five as "up but unusable", and
**one of the three is there on measurement and not on the manual**: the
vendor's reference implies one code and the instrument answers another.
Take the shape; **the numbers are theirs and are not ours until measured
here.**

## 4. SAMPLE AND DATA — the quiet ones

**4a. `PixelType` misreports the bit depth.** Micro-Manager reports 12-bit
while the data delivered is **16-bit**, so trusting the property **scales
every count by sixteen** (`pixeltype_misreports_bit_depth`, E3). **Test by
measuring, not by reading**: take a saturated frame and find the actual
maximum. A brightness that is wrong by 16× is exactly the kind of number
that looks plausible.

**4b. A dropped frame raises nothing and is recorded nowhere.** MMCore
writes no error and Micro-Manager's own metadata does not record the loss;
**gaps in the `ImageNumber` sequence are the only evidence**
(`dropped_frames_raise_nothing`, E3). **So check the sequence, every run.**
A bleaching curve with silent holes in it fits fine and means nothing.

**4c. Derive durations from integer counts.** Frames, triggers, steps —
multiply, never accumulate. Adding a timestep ten thousand times gave
19.999999999999794 against a planned 20 and reported a completed run as
unfinished; the direction flips with the step size. **And do not add an
epsilon** — the limit came from the plan and widening it at run time changes
an approved number.

**4d. The spinning disk and PFS.** Nothing acquires while the disk is still
coming up to speed or while the optical-path lock is held. PFS is disabled
across turret and path changes and **re-acquired after** — confirm it
re-acquired rather than assuming it did.

## 5. The one that needs an acquisition, not a look

**`lapp_branch_assignment` cannot be closed by reading a label.** The
registry marks `widefield_source_a`'s branch unconfirmed, and the prior
project's record says why in the sharpest possible way:

> The record was right; **the `.cfg`'s labels were swapped.** Following it
> turned the light off and cost a diagnosis session, and the branch was
> **booked as falsified for two days** before an operator mapping showed the
> mislabelled enum was the fault. **Everything now pins the integer.**

So the label cannot settle it and neither can a careful reading. **Two
acquisitions that can**: block one engine and switch the branch, and see
which state goes dark; or pattern with the DMD and see which engine's light
carries the pattern.

**Until it is closed, name `LightEngine` and not `widefield_source_a`** — a
plan naming the MM label is verified by `getLoadedDevices()` and asserts
nothing about the branch, while naming the source asserts the disputed
mapping. **Setting its power is exactly that assertion.**

## What this list is not

**It is not a transfer of their test suite.** Every item names an entry in
our store or a rule in `plan.md`, and the prior project's numbers — codes,
timeouts, retry counts — are **theirs until measured here** (§10.3 rule 1).
Where a line says "re-measure", that is the §10.2.1 ruling and not caution.

**And it tests the instrument, not the plan.** Whether a plan is inside the
envelope is `operator.resolve_limits` and check 57; whether anyone read back
what a command did is check 66. Those run without hardware and should be
green before any of this is attempted.
