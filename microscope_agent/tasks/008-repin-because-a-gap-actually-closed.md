# 008 — re-pin, because a gap actually closed

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**After card 006, not instead of it.** `microscope-1`'s.

## Why this re-pin is not the one card 000 refused

`000` rules: do not chase the store. That rule was written against re-pinning
because the librarian committed — an errand with no end, which this fan-out
paid for once when card 002's target went stale four minutes after it was
written.

**This is the other case.** A person calibrated the sample-plane pixel size on
this instrument and it entered the store as twelve entries, six objectives by
two zooms — the first E2 this repository has held. At the fan-out's pin
`kbv-49feb73662b7` there is no pixel entry at all: 25 entries, none of them
pixel. So A6's `sample_plane_pixel_size` is honestly `absent` there, and the
only way it stops being absent is to move.

The test `000` should have stated, and now does by example: **move when a
question's answer changes, not when the store's version does.** Here an
inequality that could not be computed becomes computable.

## What it costs, stated rather than discovered

**All five siblings move together.** Check 33 requires the siblings under one
qid to agree on `kb_version`, so this is not "re-pin A6". `a1`, `a2`, `a3`,
`a6`, `a7` move in **one commit**.

**And it is a re-derivation, not a re-pin.** Card 002 could move a pin
mechanically because the delta was one entry nothing cited. This delta is
seventeen entries. **Every one of the twenty-two gaps must be asked again at
the new version** — some will close, and a gap that stays `absent` only
because nobody re-asked is the false absence check 49 was built against.
Expect the work to be closer to re-running the five axes than to editing a
field.

**Some intervals may appear.** A6's diffraction limit was half-served — NA for
all six objectives and no emission wavelength. Pixel size does not supply the
wavelength, so check whether it is now there rather than assuming either way.
If an axis returns its first interval, that is the first one this fan-out has
produced and it should be said plainly in the report.

## The target version

The store is at **`kbv-c7b156160a3a`** as of this card, 42 entries — and it
is about to hold one more thing this fan-out needs, which is the wait
condition below.

**The wavelength is not settled, and an earlier revision of this card said it
was. Read this before using either number.**

What happened, because the shape of the error matters more than the fact of
it. The person said 555/605 came from the instrument; asked to narrow it, the
options this seat offered named a *filter cube*, and that word was **this
seat's, not theirs**. They picked the nearest option. The card then recorded
`operator_read:` E3 on a filter passband and reasoned from it — including a
loud claim that a dye emitting at 680 could not be seen through a filter
passing 605, so the bead and the cube did not go together.

**That claim is withdrawn.** The cube holds a **multiband** filter. Its
`555/605` marking names bands it passes, plural — not the band in use — and a
multiband cube may pass a red window too, so nothing in it contradicts a
680 nm dye. The inference was built on a single-band assumption this seat
supplied and never checked.

**The band is selected further down: single-band filters sit in the filter
wheel.** So the wavelength A6 needs is the **single-band emission filter used
for the red beads**, and it is a different fact from anything on the cube.
The store's `emission_wheel_camera_mapping` says there are two wheels, first
serving the red camera and second the blue — `operator_recall:` at **E5**,
hedged with *probably*, so it does not settle which wheel or which position.

**So A6 still abstains on `emission_wavelength`, and its `missing` should name
the filter wheel band rather than the dye's peak.** Neither 680 (the dye's
emission, `spec:` E3, a product-family fact) nor 605 (a multiband cube
marking) is the number. The librarian has been asked for the prior project's
filter records, which the person says exist; that request goes through §10.2.1
like any other transfer.

**A1's abstention does not change after all.** It stays *no number for
`tracer_brightness`*. The "may produce no signal at all" reading was the same
withdrawn inference and must not be carded.

**And the pin is currently split.** `a1` sits at `kbv-67f9ad766d92` while
`a2`–`a6` sit at `kbv-49feb73662b7`, six commits apart — found by the
librarian seat. Check 33 wants siblings to agree, so this is a second reason
the five move in one commit rather than one reason with a consequence.

**Re-read `librarian_agent/kb/index.json` immediately before you commit.** If
it has moved, do not silently re-target: stop, and report which version it is
now and whether the delta touches anything you asked. This instruction exists
because the card that did not carry it named a version that was stale four
minutes later, and the store has moved several times since.

Moving to whatever is current at commit time is acceptable here, unlike in
006 — the point is to reach a version where the pixel entries and the emission
wavelength exist, not a particular one. What is not acceptable is the card and the commit disagreeing
about which version that was.

## Why this is separate from 006, and what that costs

006 writes `near_names` at the old pin; this card re-asks and may rewrite
some of them. **That duplication is real and is accepted**, for one reason:
check 49 is a latch that any seat in any agent can trip, and when it trips
our twenty-two gaps fail. Closing it at the pin is quick and safe; a re-pin
is a decision that should not be made under that pressure.

If the latch is already closed by the time you reach this card, the
duplication has already been paid and nothing here changes.

## What holds

`degraded` stays `[]` and stays honest — you will be making real calls.

Gaps that close stop being gaps. Do not keep `kind: absent` next to a
`near_names` that names the entry, and do not keep a gap at all for something
the new version answers.

The pinned version goes in every card of the fan-out including `configs.json`,
which carries the fan-out's issued ids and their `kb_version`.

## Done when

All five axis cards and `configs.json` name one version, that version is the
one the index held when you committed, every gap has been re-asked at it,
`python3 contracts/validate.py` ends `0 failed` with checks 25, 33 and 49
passing, and one commit as `seat:microscope-1`.

Then one sentence up: how many gaps closed, and whether any axis returned an
interval.

## Not this task

**A4**, still waiting on the discrete-constraint slot — the re-pin does not
create it. **A5**, `microscope-3`'s. **The goal revision** for the person's
one-decade statement, which is card 007 and whose encoding is still pending
§5.3.
