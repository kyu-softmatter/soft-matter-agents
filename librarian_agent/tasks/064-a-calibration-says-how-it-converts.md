# 064 — a calibration says how it converts, and a binding says what step its property takes

Written by `manager-librarian-20261007-1` on 2026-10-27. You read this; you do
not edit it.

**For a librarian execution seat** (librarian-20261007-1, or whichever
librarian seat the person opens next). It comes after 062, because a
calibration serves a binding and a step sits on one. If you are not a
librarian seat, take nothing from this card and report up.

## Why

Card 062 says where a physical quantity becomes a control value (a power in
milliwatts into a per-mille intensity), and that the conversion is a
`kind: calibration` entry found by `mm_label`, `mm_property` and `quantity`.
It does not say what the conversion is. So microscope card 095 refuses every
calibrated conversion with "carries no conversion form". Agreed with
manager-microscope-20261003-1 on 2026-10-27. Microscope card 098 builds the
runtime's side, on mock until this lands.

A device property also takes discrete values. A plan number already in the
property's unit still has to be rounded to one, and nothing records which.
If the runtime rounds by its own choice, the store has not said a fact it
holds.

## The form: a calibration's `conversion`

**A `kind: calibration` entry that serves a binding carries `conversion`, a
sibling of `identifiers`.** The key stays the key.

```
"conversion": {
  "direction": "physical_to_control",
  "rule": "piecewise_linear_within_points",
  "physical": {"quantity": "<registered quantity>", "unit": "<validity's unit for it>"},
  "control":  {"unit": "<the binding's unit, e.g. permille>"},
  "points": [
    {"physical": {"value": 0.0005, "unit": "W"}, "control": {"value": 20, "unit": "permille"},
     "source": "measured:<run_id>"},
    ...
  ]
}
```

- **Every number is `{value, unit}`.** Every physical value is in
  `physical.unit`, and every control value is in `control.unit`. One form
  never mixes units, so a check compares without converting.
- **`physical.quantity` is the entry's `identifiers.quantity`.**
  `physical.unit` is `validity[<quantity>].unit`, and both are the
  quantity's registered unit in `contracts/quantities.json` (`W` for
  `illumination_power`). A bench reads milliwatts; the entry stores watts.
- **`control.unit` is the unit of the binding it serves**: the same
  `mm_label`, `mm_property` and `quantity` on the device row.
- **`direction` is required, and `physical_to_control` is its only value.**
  The reverse is a second calibration, never this one read backwards. A
  read-back compares control values as written, so nothing needs the
  reverse.
- **No range in the form.** `validity[<quantity>]` carries both `min` and
  `max`, and the first and last points' physical values equal them exactly.
- **Only points, and no fit.** A fit beside the points is a second rule
  that a reader might take instead. Anyone who wants a fit for a report
  computes it from the points.
- **Every point is measured on this instrument.** Its `source` is a
  `measured:` run, the grade derivation reads it as E1, and the run is in
  the store's record. The entry itself is E2 under its `calibration:`
  source, with `valid_until` set, as card 062 says.
- **`rule` names one rule, `piecewise_linear_within_points`:**
  - at least two points;
  - physical values strictly increasing;
  - control values strictly monotone, so no two physical values give one
    control value;
  - a value equal to a point gives that point's control value;
  - between two adjacent points, linear interpolation;
  - outside the first and last points, refuse, naming the calibration.

**A plateau is outside the calibration, not inside it.** An engine that
gives about 0 mW across its lowest settings shows up as repeated physical
values, where physical-to-control has no answer. Start the points, and so
the validity, above the plateau, and the runtime refuses below it. Do not
pad the table with a flat run, and do not drop the points that show the
plateau without saying so: name them in `validity_conditions`.

## The form: a binding's `step`

**A binding entry records the step its property takes, once it has been
read**, as a number in `numbers[]` named `property_step`, in the binding's
unit. It is what the adapter accepts, like the limits card 062 already asks
for, so it is never a safety limit. The row's `mm_bindings` item copies it
as `"step": {"value", "unit"}`. A binding whose step nobody has read is
still entered, with no `property_step`, and its row item has no `step`. Its
conditions say the step is unread and where it was looked for.

- The runtime rounds every value it writes through the binding, converted
  or not, to the nearest multiple of the step, ties to even. It records the
  unrounded and the written value.
- **A binding with no step is not written through.** The runtime refuses
  and names the missing step. No step does not mean "any value".
- **Where the step is read.** The reading run (microscope card 096)
  records each property's type and its limits or allowed values: MMCore's
  `getPropertyType`, `hasPropertyLimits` and the limits. That is the
  device's report of itself, so E1 as `measured:<run_id>`. An integer
  property gives step 1 in its unit. A property whose allowed values are a
  list has no step; bind that kind through `mm_states`, or report it. A
  step stated in the maker's documentation or the adapter's property
  definition is E3. **Never infer a step from a range.** "0 to 1000" says
  nothing about the step.

## The form: a binding's `line`

**A binding may carry `line`, the name of the light line it drives, exactly
as the device reports it** (`GREEN`, `NIR`). Each light engine exposes one
intensity property per line: eight on the Spectra III, five on the Aura III
(entry `light_engine_line_intensity_is_per_mille`). Card 062 allowed one
binding per quantity on a row, so only one line per engine could be bound.
librarian-20261007-1 found this on 2026-10-27.

- The entry's `identifiers` carry the same `line`.
- One binding per `(quantity, line)` on a row, and still one per property.
- A row whose bindings for a quantity carry `line` has no binding for that
  quantity without one.
- Each line is its own entry, one claim per file. Each carries the full
  `mm_property` (`GREEN_Intensity`), quantity `illumination_power`, unit
  `permille` and its `line`. The general per-mille entry stays as it is, and
  each new entry cites it in its conditions.
- Today's only source is the prior project, so each is E3, and its
  conditions say so: knowledge for planning, and it commands nothing. With
  no calibration the runtime refuses to turn watts into per mille, which is
  intended until a bench run measures one.
- **The source gives a range and no step.** It says 0 to 1000, and nothing
  about an integer property or a step. 0 to 1000 is equally consistent
  with a float property, or with a step of 10. So these entries carry no
  `property_step` until a reading exists. They record it as a gap of kind
  `absent`, searched in that entry and its source record, and the rows
  carry no `step`. librarian-20261007-1 caught this on 2026-10-27, after
  this seat had first said "step 1".

## Not decided here, and not yours to decide

- **How many points a calibration needs, or how far apart they are.** The
  run that measures them decides, and the plan that uses them is judged
  against the range they cover.
- **What a plan does when its number falls outside a calibration.** The
  runtime refuses. That is the ruling working.
- **What a safe power is.** That belongs to the envelope and the person. A
  calibration point at 5 mW says the engine gave 5 mW, not that 5 mW may
  be commanded.

## What to do

1. Enter the per-line engine bindings above, from the existing E3 source,
   with `line` and with the step recorded as unread, and copy `line` onto
   the rows. When card 096's run brings more bindings, give each its
   `property_step` the same way.
2. When a calibration run lands (power against setting, per line), enter
   one `kind: calibration` entry per line in this form. Report the
   plateau points.
3. **Self-tests**, each watched failing before it passes, beside 062's:
   - a `conversion` meets every bullet above, and its span equals
     `validity`;
   - every point's source derives E1;
   - a row's `step` equals its entry's `property_step`, unit for unit;
   - a row item carries `step` exactly when its entry holds
     `property_step`;
   - every `(quantity, line)` appears once on a row, and no quantity is
     bound both with a `line` and without one.
4. Rebuild the exports and the snapshot, then run `python src/kb_index.py`
   and the validator.

## Report

Send manager-librarian-20261007-1, 6 lines at most:

- each step and each calibration entered, with its entry and grade;
- each binding with no step, and why;
- each plateau, with the points left out;
- the commit hash, and the self-tests you watched fail.

Also send the runtime seat, microscope-office-20261017-1, the commit.

The validator side is the manager's and lands with this card:
`conversion` in `kb_entry.schema.json`, and check 98 extended to the row's
`step` and `line` and to every `conversion` in the store. Check 98 judges a
calibration that serves a row's binding and carries no `conversion` as a
failure, so enter the calibration and its form together.
