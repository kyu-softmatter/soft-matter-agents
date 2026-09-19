# 010 — two different facts answer to "pixel size"

status: open · issued 2026-09-19 by manager-librarian · from the person, via architecture

## GOAL

`pixel_size` was the one honest `absent` in the service's first day. Of nine
empty `kb_query` answers, eight were the store holding the knowledge under
another name or in a published table; this one the store genuinely does not
have. Two axes asked for it — `mic-20260918-001:widefield_inline:a6` and the
same question's `:a4`.

Enter it. **But one name covers two facts, and merging them is the error §5.3
already records.**

| | source | grade | enterable now |
|---|---|---|---|
| **pixel size at the sample plane** — what an image actually resolves | `calibration:` — **the person calibrated it on this instrument** | E2 | **yes, and it is the one A6 needs** |
| **sensor pixel pitch** — the physical spacing on the Kinetix 22 sensor | `spec:` vendor datasheet | E3 | secondary; see below |

**This ordering was inverted when the task was first issued, including by this
seat.** The relay said enter the sensor pitch now and leave the sample-plane
value as a gap. `plan.md:1137` says the opposite: *what axis A6 actually reads
is the pixel size; magnification is a derived convenience, and the moment it
becomes canonical the back-calculation starts.* And `plan.md:1135` had already
routed it — measured per objective/zoom/binning combination, `calibration:`
source, **validity period required**, E2. The design had this row all along.

So the sample-plane value is the canonical datum, not the derived one, and the
sensor pitch is a separate vendor fact that is **not** its input. Nothing
divides one into the other.

**Do not produce the second by dividing the first by a nominal magnification.**
That is the `20.078x` trap `plan.md:1950` records: a nominal magnification with
a back-calculated number painted onto it, which §5.3's nominal rule exists to
refuse — **a nominal designation is a string, not a number.** Task 009's ruling
says the same thing from the other side: `nominal_magnification` is an
identifier, and identifiers do not enter `numbers[]`.

So the sample-plane value stays a gap, and it is an honest one. A person has to
measure it.

## TASK

1. Enter the **sample-plane pixel size** from the person's calibration. The
   numbers arrive in this file — wait for them; do not start from anything else.
2. **It is not one number.** §12 names three dimensions — objective, zoom,
   binning — and this stand has a 1.5× zoom, so magnification is a discrete set
   (§4.5.3, A6). A calibration that covers one combination does not cover
   another, and rule 2 is what stops it being applied where it does not hold.
   How many entries that means is a filing question: one claim per file (rule
   1), and a combination is a claim.
3. **The validity period is required, not optional** (§12, and rule 9 as
   corrected on 2026-09-19). It is what makes this E2 rather than a person's
   say-so — a calibration with no expiry is a measurement with no event.
4. The sensor pitch stays open and is **not** needed to do any of the above.
   Leave it for when a vendor sheet is actually in hand.

## CONTRACT

- §5.3 — source and grade, and the nominal-designation rule.
- §10.3 rule 1 — a measurement taken elsewhere is not one taken here, so
  **E3 is the cap**, and the source is the device document, not whoever quoted
  it. If this comes across from `agentic-microscope` instead of from the
  vendor, it is also a §10.2.1 ruling: name the slot it went into and the
  §10.3 rule it passed, or discard it.
- Rule 5 — blogs, forums, summary pages and model output are not entries. If
  the trail does not end at the vendor's own sheet, **enter nothing** and let
  the gap say `unqualified_source`. Rule 6: E6 never enters.

## CONSTRAINTS

- **Binning is the third fact hiding here.** A sensor pitch is fixed; the pitch
  a caller actually computes with is the sensor pitch times the binning factor,
  and nothing in this store records what binning this instrument runs. So the
  entry's `validity_conditions` has to name the mode its value holds at —
  unbinned — rather than leaving a reader to assume it. A number that is right
  at 1×1 and silently wrong at 2×2 is the same shape as a value that is right
  at one temperature and carries no conditions, which is what rule 2 exists for.
- **`cameras_both_kinetix22` already claims this value is shared.** It says the
  two cameras are the same model, so pixel size and three other properties are
  the same on both arms. That entry is what licenses one pitch entry to answer
  for `camera_red` and `camera_blue` both — subject it to both, and do not
  write two. If you find the claim is wrong, that is a conflict to keep, not to
  merge (rule 7).
- The pitch is a property of the sensor, so a permitted range and a used value
  are not in play here the way they are for a stage or a laser (§5.3). If the
  sheet gives a tolerance rather than a value, that distinction comes back and
  they are two facts again.

## REPORT

Two lines: the entry sha, and **whether you split it or entered one**.

Then the part worth recording even though it is a non-result: **A6's gap does
not close.** A6 is resolution, so what it needs is the sample-plane value, and
the sensor pitch does not supply it. Say so explicitly rather than letting the
gap look answered because something called `pixel_size` now exists — a gap that
closes for the wrong reason is worse than one that stays open, because nobody
comes back to it.
