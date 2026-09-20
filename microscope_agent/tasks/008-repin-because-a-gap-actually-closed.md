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

**The wavelength A6 needs is the filter band, and it is not the dye's peak.**
Settled by the person on 2026-09-19, asked twice because the first question
conflated two things: **555/605 is read off the filter cube's markings**. So
it is `operator_read:` at **E3**, not a calibration at E2 — an earlier
revision of this card said E2 and lot-bound, and both were wrong. A cube's
marking does not depend on the bead lot, and no `cal_id` or validity date is
needed to file it.

**It does not conflict with the vendor's 680 nm.** Those are two different
quantities: 680 is the dye's emission peak from the product sheet, 605 is
what this instrument's emission filter passes. **A6 wants the second** — the
diffraction limit is set by the light actually collected, not by where the
dye would emit if you could see all of it.

**The mismatch is now a configuration finding, not a data conflict, and it is
worse than a conflict.** A dye emitting at 680 read through a filter passing
~605 returns almost nothing. Both facts can be true at once, and if they are,
this bead and this cube do not go together. Two readings, and the second is
the more likely: either the product identification is wrong — the person
matched a vendor listing, not a bottle label, and this is the strongest
evidence yet against it — or the cube named is not the one that will be used.

**So A6 computes on 605 and says what it is standing next to.** With NA at E3
and λ at E3 the interval is E3. But an A6 that returns a resolution while A1
cannot say the tracer is visible has answered a narrower question than it
looks, and the card should say so rather than leave S4 to notice.

**A1 changes too, and that is not this card's task** — its abstention stops
being "no number for `tracer_brightness`" and becomes "this combination may
produce no signal at all". Report it; I will card it.

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
