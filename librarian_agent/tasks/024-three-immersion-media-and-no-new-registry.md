# 024 — refractive index for the three immersion media

status: closed · **verified on disk 2026-09-20** (`0491daa`) -- water and air
entered, oil recorded as a gap because the bottle is unidentified, and the
degC-to-kelvin fix carried in the same pass · issued 2026-09-20 by
manager-librarian · **requested by manager-microscope**

## GOAL

`axial_range` on A6 needs three inputs. **NA is served** — six objectives at
E3. Wavelength is a separate question with the person. **Refractive index is
the one that closes with literature**, so it comes first.

The person also asked today what separates a confocal from an ordinary optical
path. That is a property of the configuration, not of an axis, and the
comparison S4 would make is the four configurations' `axial_range` side by
side. **Without an index every one of the four abstains in the same place**, so
there is no comparison to make, only four identical holes.

## What the store actually says, and one correction to the request

The request said `refractive_index` comes back `absent`. **It does not.** The
gap on `axial_range`'s card is named `immersion_refractive_index`, and that
name is the reason it is absent: `contracts/quantities.json` rule 1 says a name
states the quantity and never its subject. The quantity is `refractive_index`;
the immersion medium is the subject.

Asked by the registered name, the store returns **eight entries at E3** —
`polystyrene_refractive_index_*`, one per measured wavelength. Those are the
bead material and not an immersion medium, so they are the wrong answer to A6's
question while being a real answer to the name.

**Read that as the shape of the task, not as a scolding of the asker.** A
caller who asked correctly would have got eight indices of the wrong substance.

## No new registry, and the mechanism already exists

I measured before reaching for one. Six quantities are carried by more than one
entry; five of them — `na`, `working_distance`, `filter_centre_wavelength`,
`filter_fwhm`, `pixel_size` — are told apart by a **device**. Only
`refractive_index` is told apart by a material, and material is in no registry.
That looked like an argument for adding one.

**It is not, because `immersion` is already an addressable identifier.** The
objectives carry `identifiers.immersion` of `air`, `water` or `oil`, and
`addressable_identifiers` lists `immersion` under `class_handles` as a handle
shared by a class rather than an item — which is precisely this case.

So each new entry carries:

```json
"identifiers": { "immersion": "water" }
```

and `kb_query("water")` then returns the water objective **and** the water
index together. That join is what A6 needs, it needs no schema change from me,
and the mapping of lens to medium already exists in the device table.

## TASK — three entries, one per medium

One claim per file (rule 1). They are three different kinds of value and
merging them would be wrong three different ways.

1. **air.** Closest to a handbook constant.
2. **water.** Temperature and wavelength dependent. `water_viscosity_293k` is
   the precedent for sourcing and grade — **but do not copy its `numbers[]`
   verbatim.** That entry's number carries `source: "kb:water_viscosity_293k"`,
   a citation of itself, and it is the **only self-citing number in the store**
   (measured: 1 of all entries). `kb:` is how a CARD cites the store; an entry
   states where its own knowledge came from, which for that entry is
   `literature:src_water_properties` as its top-level `source` correctly says.
   Copying the precedent literally would triple a one-off defect.
3. **oil.** **Not a universal constant** — it is a specific immersion oil
   product, and it moves with temperature and wavelength. If the bottle on the
   bench is not identified, **record a gap and send it to the person rather
   than entering a typical value.** This is the bead-bottle shape again (015,
   017): what is missing is not the number, it is the provenance. A6 then gives
   a number for air and water and abstains on the oil lenses, which is better
   than a blend nobody can trace.

**`validity` must pin temperature AND wavelength.** The polystyrene series
already does this exactly right — point wavelengths, so a query at any other
wavelength returns `condition_mismatch` rather than an interpolation — and its
`validity_conditions` states the reason. Follow it.

## Say this out loud when you report

A6's other missing input is the wavelength itself. So if you pin point
wavelengths the way polystyrene is pinned, **A6 may still abstain**, now on
`condition_mismatch` instead of `absent`. That is a better answer and it is not
the same as unblocking. Say which one you have produced; do not let the task
read as closed if the axis still cannot compute.

## CONSTRAINTS

- **Nothing from the prior repositories.** §10.3's E3 cap exists for values
  taken elsewhere; a handbook cited directly is the same E3 with an honest
  source. `water_viscosity_293k` is the precedent — it cites CRC and not a
  prior store.
- Unit is **`1`**, the name `contracts/units.json` uses. Eight entries still
  spell it `dimensionless`; do not make it nine.
- Do not rebuild the lens-to-medium mapping. It is the device table's
  `immersion` column.
- `kb_version` will move. Tell me before publishing.

## REPORT

The three entries, or two and a gap. Whether A6 can now compute or has moved
from `absent` to `condition_mismatch`. And whether `kb_query("water")` really
returns both the objective and the index — that is the join this design rests
on and I have not run it.
