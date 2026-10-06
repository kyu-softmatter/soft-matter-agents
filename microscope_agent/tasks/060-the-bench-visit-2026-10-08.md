# 060 — the bench visit, Thursday 2026-10-08

Written by `manager-microscope-20261003-1` on the person's approval, given to
architecture on 2026-10-05. You read this; you do not edit it.

**Two readers.** The lines marked **For you** are for the person and use
plain words. The lines marked **For the seat** are for the microscope seat
the person seats for the bench that day, and keep their references. If you are
a seat and the person has not seated you for 2026-10-08, take nothing from
this card.

**This card commands nothing and writes no safety value.** Everything on
the instrument happens on the day, with the person at the microscope. **No
software focus move happens on this visit.** The search is only shown
refusing; its first real move is a later visit.

## Before Thursday — the seat prepares, and nothing runs

**For the seat:**

- Write the plan cards the visit needs, so the person only has to read and
  sign on the day:
  - one focus-search plan per refusal shown in step 2;
  - one plan that turns the two lamps on and is then stopped, for step 3.

  They are ordinary plans, checked by the validator. The person approves
  them on the day, not before.
- Confirm on mock that each refusal in step 2 refuses with no Z write, and
  that the abort in step 3 records every lamp and shutter row. Bring that
  output.
- Make one copy of the record forms below for the person, on paper or on
  screen.

## Joined with dino-autofocus's forms — so nothing is measured twice

The `dino-autofocus` bench session has written its own half of this visit: a
checklist (`docs/runbooks/bench-visit-1.md`) and record forms
(`docs/runs/templates/bench-visit-1.template.{yaml,md}`), on its branch
`merge-plan/B-01-bench-prep`. The two halves split like this.

| what | recorded once, in | this card |
|---|---|---|
| Camera ceiling (step 5) | dino's yaml, `camera_kinetix_red.saturated_frame_max_adu`: one saturated frame, one value | **cites it and does not re-measure** |
| Spinning-disk shutter's closed value (step 4) | dino's checklist item 8, `light_path_followups.csuw1_shutter_closed`: one reading | **cites it and does not re-read** |
| Evidence for each focus limit (step 1) | dino's section 10, one record per key in the envelope's own shape (`kind`, `by`, `on`, `how`) | the person writes the safety file from that evidence. **Neither half proposes a value** |
| Watched refusals (steps 1–2) and the first real abort (step 3) | **only here.** These runs are this repository's plans, approved by the person on the day | dino issues no software motion on the day |
| Card 018's open items (step 6) | here, unless dino's forms record one; then it is cited, not repeated | |

**For you:** if a reading is already on the other form, it is not taken again.

**For the seat:**

- **The camera value carries its readout mode, or it closes nothing.** The
  gap is per camera *and* readout mode. If dino's record does not say which
  readout mode the frame was taken in, ask the person on the day and record
  the answer beside the value. One value closes one mode. Every other mode
  stays a gap.
- **After the visit**, dino sends the record paths and their sha256 to
  architecture. Your `findings/` file cites them by path and hash. It does not
  copy their values, because a copy is a second record, and the two drift.

## The visit, in order of safety

Each step says who does it, what is recorded and where, and **when to stop**.
A stop means: stop the visit there and write down what happened. It does not
mean try again.

### 1. Watch the focus search refuse when there are no limits — then write the limits

**For you:** Before you write any focus limits, the seat runs a focus search
and you watch it refuse. With no limits written, it must refuse **without the
focus motor moving at all**. Then write the focus limits into the safety file
yourself: a lowest and a highest focus-motor position for each of the six
lenses (4x, 10x, 20x, 40x, 60x, 100x).

- **The highest value is the closest that lens may ever come to the
  coverslip.** Read it off the focus motor's position display with that lens
  in place, at the closest you are willing to allow.
- **For each dry lens you have released, write a wide range.** Leaving a lens
  out does not mean "no limit". It means that lens can never be searched.
- For each value, record that you set it physically, and how. The file asks
  for this beside every limit.

**Stop if:** the focus motor moves at any point during the refusal; or you
are not sure of a lens's closest safe position. Leave that lens unwritten,
and it stays unsearchable.

**For the seat:** the search runs through card 055's gate on the instrument.
The expected refusal names the missing `focus_z_<objective>` key. Record the
run under `runs/`, with the Z encoder read before and after; the two must be
equal. The person writes `envelope/safety.json` themselves. You may not
write it, and you do not touch the values. Afterwards, run the validator. If
check 1 or check 88 objects to a value's shape, show the person and let the
person correct it.

### 2. Watch the other refusals, before any focus move

**For you:** The seat runs four more searches that must each refuse **without
the focus motor moving**:

- the lens you name is not the lens the plan names;
- focus hold is still switched on (switch it on first; you switch it off
  again after);
- the plan has not been approved;
- the next step would go above your highest value for that lens.

You watch the motor display for each. **Stop if:** it moves on any of them.
That ends the visit's motor work for the day.

**For the seat:** these are card 055's instrument gate. For each one, record
the refusal reason, the run id, and the encoder before and after. Put a note
in `findings/` naming each refusal and its run. The fourth one needs a plan
whose target lies above `focus_z_<objective>_max`. That command must be
refused before it goes out, so the limit is never approached.

### 3. The first real abort — lamps off, filter-turret shutters closed, read back

**For you:**

1. Open the two filter-turret shutters by hand at the stand. Software may
   only close them.
2. Approve the plan that turns the transmitted lamp and the Aura on.
3. While they are on, the seat stops the run from outside.

The abort should then close both shutters and turn both lamps off. The record
should show each one confirmed by reading it back. Look at the stand and the
lamps yourself, and say what you see.

**Stop if:** any shutter stays open or any lamp stays lit after the abort;
or the record says something closed or turned off that you can see did not.
Turn it off by hand, write it down, and end this step.

**For the seat:** this is card 056 (both parts) and card 054 on the real
stand, triggered through card 057's stop channel. Record the run under
`runs/`, and in `findings/` record each row's `closed` or `matched` beside
what the person saw. A row that says `true` where the person saw otherwise is
the most important thing this visit can find. Report it up the same day.

### 4. Read the spinning-disk shutter's closed value

**For you:** Nothing to do but watch. The seat reads which setting of the
spinning-disk shutter means "closed". It only reads; nothing is switched.

**Stop if:** the reading is ambiguous, for instance two settings that could
both mean closed. Then it stays unbuilt, and that is fine.

**For the seat:** this is read once, on dino's form
(`light_path_followups.csuw1_shutter_closed`). Cite it in `findings/` by path
and hash. Read it again only if dino's form leaves it empty; then read
`CSUW1-Shutter`'s properties and allowed values through the guarded core,
read-only, and say where. **Do not build the close path on the day.** Card 056
part 2's spinning-disk half is built afterwards, from the recorded value.

### 5. Read the camera's highest pixel count, for each readout mode

**For you:** This is taken once, on the dino-autofocus form. Saturate the
camera on a blank slide with the transmitted lamp, in Micro-Manager **with no
agent running** (never two connections to the microscope at once). Then read
the highest pixel value the image shows. That is the camera's ceiling, **in
the readout mode the camera was in**. Say which mode that was. The camera's
own label for its bit depth is not enough: it has been wrong before.

**Stop if:** the image does not clearly saturate; record "not reached"
rather than a number.

**For the seat:** cite dino's `camera_kinetix_red.saturated_frame_max_adu`
in `findings/` by path and hash, with its readout mode, as an observation for
the store, unit ADU. The store has no such entry
today, so every focus-search plan carries the gap. A librarian card enters it
and closes the gap; do not write it into any plan or into code.

### 6. The focus measurements still open from earlier

**For you, if time allows, and on a test slide, never the real sample.** All
of these use the focus knob turned by hand at the stand, never by software:

- **a.** Pixel size is already measured for every lens at 1×1 binning. Skip it,
  unless you plan to use other binning.
- **b.** A focus curve through a bare-particle slide, once in transmitted
  light and once in fluorescence. The two behave differently.
- **c.** The focus offset between the glass surface and the plane you want,
  and between ports and channels.
- **d.** Which way focus hold's offset moves the focus. It is the one
  direction of motion that has never been measured.
- **e.** How far a first lens's focus misses when you switch to another lens.
- **f.** The 40x water lens's working distance at collar 0.17, read from the
  focus display at the glass surface.

**Stop if:** anything needs the turret turned by software, or the real sample.

**For the seat:** these are card 018 section 6 items b to f; item a is closed
at 1×1 by the twelve pixel-size entries. Record each in `findings/`, with how
it was read, for the librarian. Card 018 has what each one unlocks.

## Record forms

The person fills these in, on paper or by saying them to the seat. The seat
transcribes them into `findings/` and, for step 1, the person's own file.

**Form 1 — focus limits (you write these into the safety file yourself).**
The evidence for each one, meaning how you set it, is recorded once, on
dino-autofocus's section 10. This form is only the list of what goes into the
file, so you can tick each lens off as you write it.

| lens | lowest position (µm) | highest = closest allowed (µm) | dry and released? | how you set it |
|---|---|---|---|---|
| 4x | | | | |
| 10x | | | | |
| 20x | | | | |
| 40x | | | | |
| 60x | | | | |
| 100x | | | | |

**Form 2 — refusals watched**

| refusal | motor display before | after | refused? | what it said |
|---|---|---|---|---|
| no limits written | | | | |
| wrong lens named | | | | |
| focus hold on | | | | |
| not approved | | | | |
| above your highest value | | | | |

**Form 3 — the abort**

| | before the abort | what you saw after | what the record says |
|---|---|---|---|
| filter-turret shutter 1 | open | | |
| filter-turret shutter 2 | open | | |
| transmitted lamp | on | | |
| Aura | on | | |

**Form 4 — readings**

| what | value | how it was read |
|---|---|---|
| spinning-disk shutter: the setting that means closed (on dino's form) | | |
| camera highest pixel count (on dino's form), readout mode: ______ | | |

## What comes back

**For the seat**, the same day, to this seat, 8 lines at most: the run ids;
each refusal with the encoder before and after; the abort's rows against what
the person saw; the spinning-disk shutter's values; the camera counts; which
of card 018's items were measured; and every stop, with what happened.
