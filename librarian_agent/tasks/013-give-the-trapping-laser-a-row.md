# 013 — give the trapping laser a row, without giving it a permission

status: closed · issued 2026-09-19 by manager-librarian · **012 is blocked on this** · **closed 2026-09-19** (closing commit not recorded here)

## GOAL

012 stalled on a real prerequisite: the store holds no IR laser, so a heating
observation about it has no subject to name. The person supplied the identity:

> 1064 nm, maximum 5 W — **power at the laser generator**. 20% is of that.

File it. The person's statement is enough on its own — see below — and the
prior repository stays shut for this, see the last section.

## Why the person's statement is sufficient, and a datasheet is not needed

`spec:<device_id>` and `operator_read:<who>_<date>` are **both E3** (§5.3).
A vendor sheet would not raise the grade. What it would add is a `source_ref`
pointing at a document and a `part_number` that 009 made addressable — worth
having, not worth blocking on.

The precedent is on disk and is exactly this shape:
`cameras_both_kinetix22`, `operator_read:kyuhwan_20260917`, E3, with
`identifiers: {model: "Kinetix 22"}`. A device the person described, filed
from their description, cited to them.

If you want the model for a handle, ask the person. Do not wait on it.

## THE GUARD — a rated maximum is not a permission

**"Maximum 5 W" must not come to mean "we may use 5 W."** A rated output is a
property of the device. What this lab permits is `envelope/safety.json`, and
**that file does not exist** — check 5 reports `PENDING: no envelope/safety.json
yet; a person writes it (2.1 rule 7, 10.3 rule 4)`.

This is not a hypothetical worry. §10.2 keeps the whole *device spec values*
row — NA, magnification, pixel size, **output limits** — shut until that file
exists, and states the reason: **a spec number not placed alongside a limit
gets used as a limit.** That gate binds transfers from the prior repository
and not the person's own statement, so this entry may be written; the hazard
it was built against is the same one and does not care where the number came
from. So the entry says, in itself, that the maximum is the device's rating
and not an operating allowance.

## What the number is attached to

**5 W is at the generator.** Not at the objective, not at the sample. An entry
that says "the laser is 5 W" without saying where is false everywhere the
beam actually goes: between the generator and the sample sit losses nobody
here has recorded and the objective's transmission at 1064 nm, where the
person's standing ruling applies — visible-range curves stop well short of
1064 nm, **use the end of the graph and do not extrapolate**, because the
purpose is an order of magnitude and not an accurate power.

Put the location in `validity_conditions` where matching can reach it, not
only in `claim` where it cannot.

## TASK

1. Enter the laser: 1064 nm, rated maximum 5 W at the generator, `operator_read:`
   at E3, with the guard and the location above carried in the entry.
2. Decide whether it also needs a row in the device table (`kb/staging/`), or
   whether the entry is enough for 012 to name a subject. Say which and why.
3. Report to 012 that its subject exists, and file the heating observation
   against it — still E5, still not a limit, still leaving `sample_heating_rate`
   open.

## CONSTRAINTS

- **If you add a row to the devices table, `tables.devices` moves, the
  snapshot hash moves, and the microscope has to copy again.** Publish from a
  committed tree and tell me when, and I will tell the microscope seat — that
  is the coordination that went wrong once already today.
- **The prior repository stays shut for the measured power.** The person chose
  this route over opening it. Do not reach for it to fill the power-at-sample
  gap; that gap stays open and is the honest state.
- One claim per file. Wavelength and rated maximum may or may not be one
  claim — that is your call, and rule 1 is the test.

## REPORT

The entry sha, and whether you added a table row. Then the thing 012 will
need: **what is still absent after this.** The subject exists now; the power
at the sample does not, and nothing here supplies it.
