# 015 — the product identification is withdrawn, and sixteen entries rest on it

status: open · issued 2026-09-19 by manager-librarian · **ruling from the person**

## THE RULING

The person was asked whether the bottle's label settles it. **It does not — the
label does not say.** Their ruling:

> **Decide that the product is the wrong one.**

So `AFR-0500-COOH` is **not** established as what is on the bench. This is not
"doubted pending the label"; the label has been checked and is silent, so
doubt is the permanent state until something else settles it.

The evidence that forced it: 620/680 is Cy5 / Alexa-647 and the observed
555/605 is Cy3 / TRITC. A particle emitting at 680 does not light up under
Aura3 green and show through a 605 band. **The observation refutes the
identification**, and the observation is the one made on this bench.

## What this reaches — sixteen entries, and only one link has to break

**Seven carry `spec:abvigen_red_ps_cooh`.** They are still true *about the
Abvigen product*. What is withdrawn is that the Abvigen product is ours:

```
tracer_emission_peak                 680 nm
tracer_excitation_peak               620 nm
tracer_particle_density              1.03 g/cm3
tracer_stock_concentration           10 mg/ml
tracer_particle_material_and_shape   polystyrene, carboxyl, spherical
tracer_storage_conditions            2-8 degC
tracer_number_density_from_diameter  the relation
```

**Eight are `polystyrene_refractive_index_*`, `literature:sultanova_2009`.**
**Leave these alone.** They are correctly sourced facts about polystyrene and
nothing about them changed. What changed is whether *our* particles are
polystyrene — and that came from `tracer_particle_material_and_shape`, which
came from the datasheet.

**So `tracer_particle_material_and_shape` is the load-bearing link.** Break
that one and the refractive indices stop applying here without a single one of
them being wrong. That is the whole repair.

**`tau_d` (E4, `computed:diffusive_time`) stands on the diameter**, which stood
on the product name. It inherits whatever the diameter becomes.

## The mechanism, because deletion is not it

Rule 8: nothing is deleted. Rule 7: conflicts are kept, both sides. So the
seven stay and stop claiming to be about our bottle.

**And the link is in the names, not in `subject`.** Check 44 refused the
subjects you first wrote and you removed them, so these entries have no
`subject` at all — they are reachable by `entry_id` and by `numbers[].name`,
and those read `tracer_particle_density`, `tracer_stock_concentration`,
`tracer_emission_peak`. **The word `tracer` in the name is the claim that
these are ours**, asserted in a string that nothing checks.

That is the thing to fix, and it is the sharpest argument yet in the registry
discussion running with the person: a name that asserts its own subject is a
subject nothing can refuse.

## TASK

1. Withdraw the identification. Whether that is a superseding entry, a
   conflict pair, or a retirement with `supersedes` is yours — rule 8 and rule
   7 are the constraints, and the record has to survive.
2. Break the material link so the eight refractive indices stop applying to our
   particles **without touching those eight**.
3. Deal with the names. The seven say `tracer_*` and are not about our tracer.
4. Say what still stands about the bottle. By my reading it is very little:
   it fluoresces under Aura3 green and shows through the 605 band (E2, once
   filed), and it is a particle suspension in use as a tracer. Correct me if
   more survives.

## CONSTRAINTS

- **The diameter does not resolve, it gets worse.** 5 µm rested on the product
  name. The microscope's `operator_recall:` 5 µm and the simulation's
  `assumed:` 2 µm both stand exactly where they did, and the tie-breaker that
  looked like it was arriving is gone. Do not let a `tracer_diameter` gap close
  or narrow on this.
- **Do not reach for a replacement identification.** No catalogue, no "Cy3
  particles are usually", no inference from the emission. The bench has an
  unidentified particle and that is the honest state.
- The 555/605 entry from the previous instruction still lands as planned, at
  E2, as an optical-path compatibility observation and not a peak.

## REPORT

What you did to each of the sixteen, and specifically **whether the eight
refractive indices came through untouched** — if they moved, something was
over-corrected.

Then: the count of entries that were true, well sourced, and about the wrong
object. You wrote the lesson in `d9d0c29` an hour before it applied to your own
work; say how many it caught.
