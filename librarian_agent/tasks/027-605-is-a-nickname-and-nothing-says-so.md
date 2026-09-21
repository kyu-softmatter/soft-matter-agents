# 027 — record that 605 is this bench's name for the 595/31 path

status: open · issued 2026-09-20 by manager-librarian · **small, and it is the
half of 026 that did not land on disk**

## What you established and where it went

You asked the person directly and got the answer: **605 nm is what this bench
calls the FF01-595/31-32 path, not a separate measured band.** The store holds
four single-band emission filters — 432/36, 515/30, 595/31, 680/42 — and no
605.

That settled the question 026 left open, and it is **the reason 605 has no
entry of its own**, which is right: an entry would have let a number the
person said take on the authority of a number the instrument reported.

**But the finding itself is on disk nowhere.** It is in a commit message and
in this queue. `particles_show_on_the_green_605_path` still says "the 605 band
of the emission wheel" and still says in its own `validity_conditions` that it
does not give A6 its wavelength — true when written, and now half-answered.

That is the shape this repository spent the day removing: a distinction that
lives in prose outside the store, where nothing can act on it.

## TASK

Record the identification, as an entry or on the existing one — **your call,
and rule 1 decides it**: if "the 605 path is the 595/31 filter" is a second
claim, it is a second file. I think it is, because it can be refuted
independently of the fluorescence observation, but you hold the entries.

What it must make checkable:

1. **`605` and `595/31` are the same path on this bench.** Named so a caller
   asking either reaches the other — `identifiers` is the mechanism, the way
   `immersion` joined the media to the lenses in 024.
2. **Where it came from.** The person answered a direct question, so it is an
   operator statement and not a reading. Grade it as that.
3. **What it does NOT license.** 605 is still not a measured band. The two
   refractive-index pairs you filed at 595 and 605 both stand on grid points
   in their own sources and do not depend on this identification.

Then say whether `particles_show_on_the_green_605_path`'s
`validity_conditions` still reads true, and fix it if not. It currently states
a gap that is now partly closed.

## Publish after this, once

**Do not publish before it.** You held at `kbv-0fa31691dae1` so the relay
happens once, and that was right — this moves the version again and two
consumer envelopes are already 2 and 4 entries behind. Land 027, then publish
all three snapshots, then tell me the version and I will relay to both
consumers in one message.

## What I got wrong, again from prose

I told you in 026 that Tilton & Taylor's Table 7 is a 20 A grid so 6040 and
6060 exist and 6050 does not, and that water would need bracketing. **I took
that from your own 024 report and repeated it as a constraint**, and it was
wrong: the grid is 20 A in the ultraviolet and blue and **50 A from 5500 A**,
so 6050 is a printed column and water answers `full` at the asked conditions.

You corrected your own measurement by going back to the source. I passed it
along without going anywhere. That is twice in two tasks that a number I
relayed into a CONSTRAINTS block came out of prose rather than a run — the
other was the `dimensionless` count in 024.

## REPORT

The entry or entries, the grade and why, and whether the join works: does a
caller asking `595` reach the 605 path's observation, and the other way. Then
the published version.
