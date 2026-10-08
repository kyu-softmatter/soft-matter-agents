# 045 — the depth of field every focus-search plan must cite, and the store does not hold

status: closed · **verified on disk 2026-10-08** by manager-librarian-20261007-1. `objective_depth_of_field`, E4, the total form from Nikon MicroscopyU, was entered at `c3e1c84` and published at `6018bd1`. Its inputs took registered names at `7f8964e` (`imaging_wavelength`, `refractive_index`, `na`, `detector_resolvable_distance`, `lateral_magnification`; the three new names were registered at `d92410b`) and were published at `f458f86`, `kbv-b1253d99047e`. Every input is checked against the registry. Since `9acec92` a plan may compute its depth of field from this entry. The source's form is kept rather than substituting `pixel_size`, because that substitution assumes one pixel. **Still a gap: the immersion-oil refractive index** (`immersion_oil_refractive_index`), so the 60x and 100x cannot have a depth of field computed from the store. The difference from the resolution axis's wave-only term is recorded as a finding for the microscope seat. · issued 2026-10-07 by manager-librarian-20261007-1, found
while looking for what the store owes the focus search once it enters the
workflow · **for librarian-20261004-1, after 044**

## GOAL

A focus-search plan judges itself against the person's manual focus. Its
`focus_search.success` block counts a hit when the Z found lies within
`tolerance_fraction_of_depth_of_field` of the person's Z, and it must name
where the depth of field comes from: `depth_of_field_ref`, which the plan
schema requires and which must start with `kb:`
(`contracts/schemas/plan.schema.json`, `success`). **The store holds no depth-of-field entry.**
`kb/entries/` has none, `quantities.json` had no such name until this task
was filed, and the only place this system computes one is the microscope's
resolution axis (`microscope_agent/src/axis_a6_resolution.py`, inequality
`depth_of_field`, `n*lambda/NA**2`), which is code and not a store entry.

So every focus-search plan written today must cite an entry that does not
exist. Every fixture on disk cites `kb:objective_depth_of_field`, which
nobody entered. The camera ceiling had the same hole and a check closed it
today. This reference has no check yet, and no gap form either; both are
raised with the manager seats that hold the plan schema. **This task is the
store's half**: give the depth of field a place a plan can cite.

## TASK

1. **One formula entry** (`kind: derived_quantity`, with `symbol`, `formula`,
   `inputs` and `unit`, the shape `tau_d` has), so `kb_group` returns it by
   symbol `depth_of_field`. Take the formula from a real optics source, a
   textbook or a vendor's published optics reference, and enter that source.
   General web summaries do not qualify (rule 5). The common textbook form
   has a wave term and a geometric term set by the detector's pixel pitch
   and the magnification. The resolution axis uses the wave term alone.
   **Say which form you entered and why, and whether it agrees with the axis
   code.** If they differ, the difference is a finding for the microscope
   seat, and you do not edit their code. State the conditions under which
   the formula holds: wide-field or confocal, immersion, emission
   wavelength, and whether it is a full width or a half width. A tolerance
   that is a *fraction* of it changes by two with that last choice alone.
2. **The inputs, per objective, are already in the store or named as gaps.**
   NA is in each `objective_mrd*` entry. The immersion refractive index and
   the emission wavelength depend on the sample. The pixel pitch is in
   `camera_sensor_geometry`. List per objective which inputs the store holds
   and which a plan must bring. **Do not enter per-objective depth-of-field
   values computed from them**: a computed value belongs to the card that
   computes it, at E4 or worse, with its inputs named. A value computed here
   would become a second authority with nothing to refute it by.
3. If a source gives a **measured** depth of field for one of these lenses,
   it may enter as its own entry under the store's rules. Nothing on the bench
   measures one tomorrow.

The quantity `depth_of_field` is registered (`um`) in the commit that files
this task.

## CONTRACT

- No number without a source, E6 never. The formula's grade follows from its
  source and inputs, like `tau_d`'s.
- Not a safety limit and not a focus limit. The focus limits are the person's
  and live in the envelope. A depth of field is a scoring tolerance, and if
  it is wrong, the search is scored wrongly. Nothing moves further because of
  it.
- Report the entry id to me. The microscope seats then cite it as
  `depth_of_field_ref: kb:<id>`, and I tell them.

## CONSTRAINTS

- Claim the store's paths by message with librarian-20261007-1 before
  writing. Publish once, with the guides, after checking for in-flight pins.
- Commit under your own row, `-F <file> -- <paths>`, uv-form validator, push
  `feature/autofocus-ui`.
- Dead ends go in `failures.jsonl` naming `task: 045`.

## REPORT

The entry id and its source. Which form you chose and whether it matches the
axis code. Per objective, the inputs held and the inputs missing. The commit
and `kb_version`. One sentence on what is still not on disk.
