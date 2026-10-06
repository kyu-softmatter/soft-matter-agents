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

**For the seat:** read `CSUW1-Shutter`'s properties and allowed values
through the guarded core, which is read-only. Record them in `findings/` with
where they were read. **Do not build the close path on the day.** Card 056
part 2's spinning-disk half is built afterwards, from the recorded value.

### 5. Read the camera's highest pixel count, for each readout mode

**For you:** For each readout mode you use, saturate the camera on a blank
slide with the transmitted lamp, in Micro-Manager **with no agent running**
(never two connections to the microscope at once). Then read the highest
pixel value the image shows. That is the camera's ceiling in that mode. The
camera's own label for its bit depth is not enough: it has been wrong before.

**Stop if:** the image does not clearly saturate; record "not reached"
rather than a number.

**For the seat:** record each mode's value in `findings/` as an observation
for the store, unit ADU, with how it was read. The store has no such entry
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

**Form 1 — focus limits (you write these into the safety file yourself)**

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
| spinning-disk shutter: the setting that means closed | | |
| camera highest pixel count, mode: ______ | | |
| camera highest pixel count, mode: ______ | | |

## What comes back

**For the seat**, the same day, to this seat, 8 lines at most: the run ids;
each refusal with the encoder before and after; the abort's rows against what
the person saw; the spinning-disk shutter's values; the camera counts; which
of card 018's items were measured; and every stop, with what happened.
