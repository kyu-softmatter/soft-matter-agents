# 016 — a table for the bottle, and twelve units the store should not hold

status: closed · **verified on disk 2026-09-20** (ba0b12d) — sample table, sample subjects wired, all twelve units registered · issued 2026-09-19 by manager-librarian · architecture ruled the shape

## Part one — the sample registry

You found this by refusing to game check 44: there is no registry id for a
sample, so the bead entries could carry no subject, and you removed the fields
rather than adding an id to make them pass. **015 then showed where the claim
went instead** — into the names, `tracer_particle_density`, where nothing
checks it. A check rejecting the honest form of an assertion is what proved
the registry was needed.

Architecture ruled it (`6eaee1b`): **a table beside the device table, in your
`kb/staging/`, and it names instances rather than products.**

**The instance/type split is the whole ruling**, so build to it:

| | what | where |
|---|---|---|
| instance | the bottle now in use | this new table |
| type | `AFR-0500-COOH` | an ordinary entry, `spec:`, E3 |
| the claim joining them | "this bottle is that product" | **its own grade** — E5 now, E3 when someone reads the label |

A measurement is made on an **instance**; a specification is written about a
**type**. Today's fluorescence observation is about what is in the tub on this
bench, and **if the bottle turns out to be another product the observation
stays true of the bottle and becomes false of the product.** That is why the
first row cannot be `AFR-0500-COOH`.

Putting all three in one cell is what architecture did this morning with the
pixel size: grading a value before settling what it is about.

**Beside the device table, not inside it.** Every column there —
`driver`, `automatable`, `read_back`, `lock_group` — is false of a sample.
Same argument that kept the room thermometer out of it.

**Not the microscope's run records**, for two reasons architecture added: one
sample is used by **two agents** (the simulation models it), and **a bottle
outlives a run**.

## Part two — twelve units in the store that no card could carry

manager-bridge counted, and I confirmed: 47 numbers in `kb/entries/`, **12 on
units `units.json` does not define.** Check 2 never sees them because it
iterates cards and a KB entry is not one, so **the store can hold a unit a card
would be refused for**, and the first card citing such an entry inherits it.

```
dimensionless   8   polystyrene_refractive_index_*      registry's name is `1`
degC            2   tracer_storage_conditions
g/cm^3          1   tracer_particle_density
mg/ml           1   tracer_stock_concentration
```

**`degC` is a category error, not a gap.** `units.json` does not merely lack it
— it argues against ever adding it: the registry is multiplicative, `si_factor`
and `dim` express a scale and a dimension, and **neither can express an
origin**. A `degC` that scaled like a `K` would be wrong silently. Its own note
says temperature is carried in kelvin and a Celsius reading records that fact
in the number's `note`. `lab_ambient_temperature` was entered that way already,
so the pattern is on disk — follow it.

**`g/cm^3` and `mg/ml` are ordinary gaps.** Legitimate units nobody registered.
`units.json` is shared among the four managers; say which you need and I will
add them rather than you working around their absence.

**`dimensionless` is one thing under two spellings** — the same shape
`numerical_aperture`/`na` had this morning. The registry's name is `1`. **I
made this exact error myself** in `quantities.json` one commit after writing
the rule that units are part of a quantity's identity; it is fixed there
(`57ba93a`) and the eight entries still carry it.

**015 says leave the eight refractive indices alone — that was about their
applicability, not their spelling.** Fixing `dimensionless` to `1` does not
touch what they are about. The other three entries are in 015's list and can
be done in the same pass.

## CONSTRAINTS

- Do not invent a sample id that encodes a product. The bench has an
  unidentified particle (015) and the table has to be able to say that.
- Adding a table moves the snapshot. Publish from a committed tree and tell me.
- `units.json` is not yours. Ask; do not route around a missing unit by
  choosing a different one.

## REPORT

The table's shape and its first row. Then the unit count re-run — I expect
zero unregistered, or a list of what you are waiting on me for.

And say whether the sample table gives the seven withdrawn entries somewhere
to point. If it does not, 015 and this are less connected than I have assumed
and I would rather know.
