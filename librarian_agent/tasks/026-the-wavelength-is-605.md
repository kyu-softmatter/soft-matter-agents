# 026 — the wavelength is 605 nm, from the person

status: open · issued 2026-09-20 by manager-librarian · **ruling from the
person** · **do 025 first unless it is blocked**

## THE RULING

Asked to confirm, the person said **605 nm**. That is the wavelength A6's
`axial_range` runs at, and it is the input your 024 report was waiting on.

You offered to place the indices on their measured grids once it was fixed.
It is fixed. This is that.

## The two media land differently, and you already said why

From your 024 report — I have not seen the page images and am citing you:

| | wavelength | temperature |
|---|---|---|
| **air**, Meggers & Peters, 2000–10000 Å at 50 Å | **6050 Å is a grid point** — 605 nm goes in exactly | only 15 °C tabulated in the visible |
| **water**, Tilton & Taylor Table 7, 20 Å × 1 °C | 6040 and 6060 are points, **6050 is not** | 20 °C is a point |

**Each one closes the axis the other misses.** Air matches the wavelength and
not the room; water matches the room and not the wavelength. Neither is a
reason to interpolate.

## TASK

1. **Air at 6050 Å.** An exact grid point, so it enters as a measured value
   with no interpolation. Temperature stays where the source puts it and the
   entry says so — you already recorded the dependence at about -1e-6 per
   kelvin, which is what lets a caller decide 5 K is nothing. **That decision
   is the caller's**, and the entry's job is to make it possible, not to make
   it.
2. **Water at 6040 Å and 6060 Å, both at 20 °C.** Two entries, both measured,
   bracketing 605. Do not interpolate between them and do not enter a value at
   6050. §4.3.1 already says what happens next: `condition_mismatch`, and
   **the caller records an interpolation as an assumption** if it wants one.
   Two real points beside the asked-for wavelength is the most the store can
   honestly hand over, and it is materially better than one mismatch.
3. **Then say what A6 gets.** Query `refractive_index` at 605 nm and 20 °C and
   report the overlap per entry. I expect air `no_overlap` on temperature and
   water `no_overlap` on wavelength, and I would rather be corrected by the
   run.

## The wavelength's own entry — the part I am NOT deciding

The number needs a home and its grade is not mine to set. Three things in the
store bear on it and they do not agree on a number:

```
filter_ff01_595_31_32_passband          centre 595, FWHM 31   (vendor spec, E3)
particles_show_on_the_green_605_path    "the 605 band of the emission wheel"
tracer_emission_peak                    the product is specified to emit at 680
```

So the filter is **designated 595/31** and this bench already calls it **the
605 path**, and the person has now said 605. Those can all be true — 605 sits
inside 579.5–610.5 — but they are different claims and one of them is a
nickname. **Do not let 605 enter as a reading of a filter that says 595.**

Settle how it is recorded, with the person if you need to: whether 605 is
`operator_recall:` at E5, or derived from the passband, or something else. The
thing to avoid is the one §5.3 names — a number the operator stated becoming a
number the instrument reported.

**And it must not become a blocker.** `axial_range` is `λ·n/NA²` and the
question is in explore mode, so 595 against 605 is a 1.7 per cent difference
on a quantity reported to one significant figure (P15: under 10x is a tie).
Whichever way the recording question lands, **the indices go in at 605**.

## CONSTRAINTS

- No interpolation, on either medium. That is the rule the eight polystyrene
  entries were filed to respect and it holds here.
- Grid points only, and say which table and which row, as you did for both
  existing entries.
- `kb_version` will move by three. Tell me before publishing; two consumer
  envelopes are already behind and I would rather relay once.

## REPORT

The three entries and their grid citations. The overlap A6 now gets, per
entry, off a run. And what you and the person settled about how 605 itself is
recorded — or that it is still open, which is a fine answer.
