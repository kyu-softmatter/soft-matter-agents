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

**Wait for the emission wavelength entry.** A6 abstains on two bounds for want
of `emission_wavelength`, and the number now exists: **605 nm**, measured on
this setup, so `calibration:` and **E2**. It beats the vendor sheet's 680 nm,
which is `spec:AFR-0500-COOH` at E3 and describes the product family rather
than this bottle. **Do not compute on either value yet** — the E2 entry is not
in the store. A `calibration:` source requires `validity` and `valid_until`,
and the `cal_id`, the date and the conditions are still being asked of the
person. Computing now would cite a value with nothing for `kb_refs` to point
at.

**When it lands, A6's diffraction limit computes.** NA is E3 for all six
objectives, λ is E2, and a computed value inherits the worst input (§5.8), so
the interval is **E3**. That would be this fan-out's second real interval
after A4's two.

**Carry its validity onto anything built from it.** Dye loading varies lot to
lot, so that calibration's `valid_until` is *discard when a new lot is
opened*. 605 nm is a fact about **this bottle**, and an interval standing on
it inherits that boundary. An A6 bound that outlives the bottle is a bound
about nothing.

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
