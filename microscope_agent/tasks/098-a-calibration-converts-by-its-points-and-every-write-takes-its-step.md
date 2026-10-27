# 098 — a calibration converts by its points, and every write takes its binding's step

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** It comes
after card 095, whose conversion routes it completes, and after cards 092 and
096 unless the runtime holder, architecture-office-20261017-1, moves it.
Build and test on mock only. If you are not that seat, take nothing from this
card and report up.

## Why

Card 095 left two gaps, reported at `e852d2fd6`:

- A calibration that passes every gate still refuses with "carries no
  conversion form", because no form was defined.
- The routes write whatever value they compute. The exact-factor route can
  write a float to a property that takes whole steps.

manager-librarian-20261007-1 and this seat agreed the form on 2026-10-27.
Librarian card 063 enters it into the store, and a check enforces it. The
field names are final: `conversion`, `direction`, `rule`, `physical`,
`control`, `points`, and the binding's `step`. The librarian side sends the
hash that lands them, and this card is built against that hash. Until it
lands, build on mock with entries a test supplies.

## The form, as agreed

A calibration entry (`kind: calibration`, E2, found by card 062's key) carries,
beside `identifiers`:

```
"conversion": {
  "direction": "physical_to_control",
  "rule": "piecewise_linear_within_points",
  "physical": {"quantity": "<registered quantity>", "unit": "<its unit>"},
  "control":  {"unit": "<the binding's unit>"},
  "points": [
    {"physical": {"value": ..., "unit": ...}, "control": {"value": ..., "unit": ...},
     "source": "measured:<run>"}
  ]
}
```

A binding (`mm_bindings` item in the snapshot's devices table) carries
`step: {value, unit}`, in the binding's unit. Its cited entry holds the same
step as a number named `property_step`, and the librarian's check compares
the two. The runtime reads the binding's copy.

## What to build

In `microscope_runtime/src/`, in `convert_for_binding` and the write path it
feeds:

1. **Apply `piecewise_linear_within_points`, and only that rule.**
   - Refuse unless `direction` is `physical_to_control` and `rule` is this
     name. Name the calibration and the field.
   - Refuse unless `control.unit` is the binding's.
   - `physical.unit` is the quantity's canonical unit, the same as
     `validity`'s (the librarian's check enforces that). A plan number in
     another unit of the same dimension is first brought into `physical.unit`
     by the exact factor from `contracts/units.json`, as the exact-factor
     route does, and both values are recorded. If there is no exact factor
     between the two units, refuse, naming both.
   - Refuse unless there are at least 2 points, physical values strictly
     increasing, control values strictly monotone, and every point's units
     equal the form's.
   - A value equal to a point gives that point's control. A value between
     two adjacent points interpolates linearly between them. A value outside
     the first and last points refuses, naming the calibration and its span.
   - Compute in exact fractions from the decimal strings, as the exact-factor
     route already does. No floating-point drift before rounding.
2. **Every written value takes the binding's step, on all three routes.**
   This covers unchanged, exact factor and calibration.
   - Round to the nearest multiple of `step.value`, ties to even.
   - A binding with no `step`, or a `step` whose unit is not the binding's,
     refuses the write, naming the binding. Silence does not mean "any value".
3. **The apply event records both**: the unrounded value and the written
   value, beside what card 095 records. Use the binding and the calibration
   entry's id.
4. **The grade is unchanged from card 095**: the worse of the number's and
   E2. Now that a calibration can pass, test it with a number at E1 and at E3.
5. **Nothing else reads the form.** No fit, no reverse lookup, no range
   copied from the form. The range is `validity`'s, which card 095 already
   checks.

## Tests, each watched failing first

1. A calibration whose points are (0 W, 0 permille), (0.002 W, 400 permille),
   (0.005 W, 1000 permille), with a binding step of 1 permille. Plan numbers
   are given in mW, so each passes through the exact factor first:
   - 1 mW writes 200;
   - 2 mW writes 400;
   - 3.5 mW writes 700;
   - 5 mW writes 1000;
   - 5.1 mW refuses, naming the span.
2. A value whose interpolation falls exactly half-way between two steps
   rounds to the even one. Choose the points so it does.
3. Each malformed form refuses, naming the field:
   - wrong `direction`, unknown `rule`;
   - one point, a repeated physical value, a non-monotone control;
   - a point in another unit;
   - a plan number whose unit has no exact factor to `physical.unit`.
4. With a step of 1 permille, both other routes round, ties to even:
   - unchanged route: 12.5 permille writes 12;
   - exact-factor route: 0.0135 in unit `1` writes 14.
5. A binding with no `step`, or a `step` in another unit, refuses the write
   on each route.
6. The written value's grade with the plan number at E1 is E2; at E3, E3.
7. The existing suite is unchanged, apart from card 095's tests that asserted
   "carries no conversion form" or wrote an unrounded value. Name each one you
   change and why.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, no snapshot, nothing in `librarian_agent/`.
- If the run log's apply event needs a field for the unrounded value, stop and
  report it to this seat. The schema is mine to change.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most: the commit; each test, watched failing, then
passing; the suite's counts; and any existing test you changed, by name.
