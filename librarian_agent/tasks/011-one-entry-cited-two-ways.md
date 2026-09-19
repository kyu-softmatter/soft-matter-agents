# 011 — one entry, cited by two sides, meaning two different things

status: open · issued 2026-09-19 by manager-librarian

## GOAL

Two independent paths reached the same absence today. The simulation's carried
plan has `sample_adjacent_temperature` in its `kb_gaps`, and the microscope's
A3 arrived at it from the other side, neither having consulted the other.
manager-bridge raised it and asked whether the absence should become an entry.

**It should not, and it already is covered.** The store holds both halves:
`sample_temperature_not_actuated` says nothing controls the sample and there is
no setpoint to appeal to, and `lab_ambient_temperature` already says its own
value is a reading of the room rather than of the sample. Absence has a
mechanism — a gap — and promoting one to an entry gives it a citable identity,
after which a plan can cite *unknown* as though it were knowledge.

**What is not recorded is what manager-bridge actually found: the two sides
cite the same entry and mean different things by it.**

- In the **simulation**, the thermostat realises the declared value. Citing
  `lab_ambient_temperature` there records **why the number was chosen**. It is
  not evidence about the model's temperature — the model's temperature is
  exactly what was declared.
- In the **experiment**, nothing actuates the sample, and the thermometer's
  position relative to it is unrecorded. Citing the same entry there is a
  **claim about the sample**, and it is the weakest link in the chain.

Same `entry_id` in two `kb_refs`, two different epistemic roles. Nothing on
disk says so.

## Why this is load-bearing and not tidiness

`thr-tracer-diffusivity-001` is live. When the bridge puts two
`tracer_diffusivity` values side by side, **the temperature uncertainty lives
entirely on the experiment side.** Treat both as equally certain and the
experiment's error vanishes; treat both as equally uncertain and the
simulation is charged for an error it cannot have. Either way the comparison
the bridge exists to make is wrong, and it is wrong quietly — both sides cite a
real E3 entry and every check passes.

## TASK

1. Enter the asymmetry as a claim. It is a fact about this instrument and this
   engine, not a methodological aside: **a declared temperature in the
   simulation is realised, a temperature in the experiment is inferred from a
   reading of unrecorded position.** Both halves are falsifiable — connect the
   stage, or record where the thermometer sits.
2. Subject it so both sides find it. It is about the pair, so a caller coming
   from either direction should reach it; work out from §4.3.1 whether that is
   two subjects or one, and say which you chose.
3. Do **not** enter the absence itself, and do not enter where the thermometer
   is. The second is not yours to know — see below.

## The person answered, 2026-09-19 — the gap closes, and its weight changes

Asked and answered in the manager session rather than yours, so it is recorded
here with who said it. Three statements, and the second and third are not
detail on the first — they change what the gap is worth:

1. **There is no thermometer next to the sample. The one we have reads the
   room.** The position is now recorded, so `sample_adjacent_temperature` stops
   being an open absence. `lab_ambient_temperature` already *inferred* this
   from the absence of actuation; it is now stated, which is a different claim
   and a stronger one.
2. **For most of this lab's work the sample temperature does not matter much.**
3. **The temperature-sensitive case is liquid crystals.**

**Do not file 2 as a flat claim.** Written plainly it reads as "temperature is
unimportant here", and the next person applies it to a sample where it is not
— which is exactly what statement 3 warns about. The honest form is
conditional, and §5.8 already supplies the condition: at this system's stated
precision, room-scale drift is below what changes a decision. Diffusivity
through viscosity moves a few percent per kelvin, and P15 calls differences
under 10× ties. So the claim is about **precision**, not about physics.

**And 3 is not merely the strong end of 2.** A liquid crystal near a phase
transition does not give a slightly wrong number when the temperature moves —
it gives a different phase. That is a discontinuity, not a sensitivity, so a
rule shaped as "usually small, sometimes larger" describes it wrongly. Whatever
you file has to keep those two apart, or the exception reads as a matter of
degree.

Ask the person directly if you need the wording tightened for an entry — they
are the source and you are the seat that files it.

## CONSTRAINTS

- The thermometer's position was a question for a person and has now been
  answered above. Everything else about it stays unknown: **do not infer how
  far the room thermometer is from the sample, or how well the two track.**
  That is the next question of this kind, and it is not answered.
- The two-path convergence is evidence the gap is **real and load-bearing**,
  not evidence it should be filed. It is an argument for raising its priority
  with the person, which is a different action.
- Rule 1 still holds: one claim per file. If the asymmetry will not fit in one
  claim, that is a signal it is two.

## REPORT

The entry sha and which subjects you gave it.

Then say whether the existing two entries need anything. `lab_ambient_temperature`
already carries the room-not-sample distinction in its prose — check whether
that is in `validity_conditions` where matching can reach it, or only in
`claim` where it cannot. **A distinction that lives only in prose is one a
query cannot act on**, which is the same defect as a validity period written in
`validity_conditions` and not in `validity`.
