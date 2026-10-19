# Sample: particle_suspension_a

Every entry in the store about the sample particle_suspension_a.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the sample table, kb/staging/samples.v0.json, verbatim:

```json
{
  "id": "particle_suspension_a",
  "what_it_observably_is": "an aqueous suspension of particles in use on the microscope bench, which fluoresce under green excitation and are visible through the 605 band",
  "first_recorded": "2026-09-19",
  "label": {
    "read": true,
    "read_on": "2026-09-19",
    "states_a_product": false,
    "entry_ref": "bottle_label_states_no_product",
    "note": "LOOKED AT AND SILENT, which is different from not checked. This is what makes the identification permanently open rather than pending: the one thing that might have settled it has happened and did not."
  },
  "identified_as": {
    "type": "AFR-0500-COOH",
    "grade": "E5",
    "source": "assumed:person_ruling_20260919",
    "why_e5": "THE JOINING CLAIM CARRIES ITS OWN GRADE AND THIS IS IT. Not `operator_read:` -- nobody read it off the bottle. Not `operator_recall:` -- it is not a memory. It is the person's reasoned judgement from named evidence, which is `assumed:` and E5. EVERY TYPE-LEVEL FACT APPLIED TO THIS BOTTLE INHERITS THIS GRADE by 5.8, worst in the chain. So the material, the density, the 5 um diameter and the number-density relation reach this instance at E5, not at the E3 they carry about the type.",
    "evidence_for": [
      "abvigen_published_data_is_unreliable -- the supplier's page carries errors unrelated to spectra, so `the data sheet is wrong` is a cheaper explanation than `the bottle is not the product`",
      "the prior project tested the same catalogue product and found the same disagreement with the published spectra, independently"
    ],
    "evidence_against": [
      "the label says nothing, so nothing positively identifies this bottle"
    ],
    "what_would_settle_it": "a label, an invoice, or a lot number that names the product. Any of them moves this to `spec:<lot>` at E3 and lifts every type-level fact with it.",
    "history": "Task 015 ruled on 2026-09-19 that the product was the WRONG one, and the person reversed it the same day once the prior project's records were opened. Recorded rather than erased: 015's evidence was a silent label, which is equally consistent with both explanations, and what actually decided it was the asymmetry in how careless the vendor's page is. Anyone re-deriving this from the label alone will reach 015 again."
  },
  "observed_on_this_instance": [
    {
      "entry_ref": "particles_show_on_the_green_605_path",
      "grade": "E2",
      "what": "fluoresces under Aura3 green, visible through the 605 band"
    },
    {
      "entry_ref": "bottle_label_states_no_product",
      "grade": "E3",
      "what": "the label states no product identity"
    },
    {
      "entry_ref": "tracer_diameter_measured",
      "grade": "E2",
      "what": "diameter 5 um, CV within 2 per cent, measured directly"
    }
  ],
  "type_facts_reach_this_instance_via": "identified_as, at E5",
  "what_now_points_here": "Three entries carry `subject: [{kind: sample, id: particle_suspension_a}]` as of a675c4e, which added `sample` to the subject enum and wired check 44 to resolve it against THIS FILE and nothing else. That wiring matters: the `quantity` kind resolves against names used in numbers[] anywhere, which an entry can satisfy by itself -- and on 2026-09-19 renaming one number dangled five subjects that had only ever resolved against a number in the same file. A registry an entry can write itself into is not a registry. Verified: querying `particle_suspension_a` returns all three."
}
```

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |
|---|---|---|---|---|---|---|---|---|
| path_excitation_band_nominal_centre | 555 | nm | calibrated on this instrument; a calibration on this instrument | E2 · calibration:tracer_path_compat_20260919 | path_emission_band_nominal_centre 605 nm; path_excitation_band_nominal_centre 555 nm | none | sample particle_suspension_a | [particles_show_on_the_green_605_path](../entries/particles_show_on_the_green_605_path.json) |
| path_emission_band_nominal_centre | 605 | nm | calibrated on this instrument; a calibration on this instrument | E2 · calibration:tracer_path_compat_20260919 | path_emission_band_nominal_centre 605 nm; path_excitation_band_nominal_centre 555 nm | none | sample particle_suspension_a | [particles_show_on_the_green_605_path](../entries/particles_show_on_the_green_605_path.json) |
| tracer_diameter | 5 | um | calibrated on this instrument; a calibration on this instrument | E2 · calibration:tracer_diameter_20260919 | none stated | none | sample particle_suspension_a | [tracer_diameter_measured](../entries/tracer_diameter_measured.json) |
| tracer_diameter_cv_upper_bound | 0.02 | 1 | calibrated on this instrument; a calibration on this instrument | E2 · calibration:tracer_diameter_20260919 | none stated | none | sample particle_suspension_a | [tracer_diameter_measured](../entries/tracer_diameter_measured.json) |

## Claims

### [bottle_label_states_no_product](../entries/bottle_label_states_no_product.json)

The label on the particle bottle in use does not state a product identity. The operator examined it on 2026-09-19 and reported that it does not say.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260919_bottle).

Conditions, verbatim:

> AN ABSENCE THAT WAS LOOKED FOR, WHICH IS WHY IT IS AN ENTRY. 'The label does not say' is a reading; 'nobody has checked the label' is not, and 4.3.1 draws exactly that line for gaps. This entry is what converts the product identification from unconfirmed-and-pending into unconfirmed-and-permanent: before the label was examined, a look at the bottle might have settled it, and now nothing further is scheduled to arrive. Anything that settles it in future has to come from somewhere else. It says nothing about what the particles ARE. It bounds what the bench can tell us, not the sample. IT HAS A SUBJECT NOW. This entry carried none because check 44 rightly refused one -- there was no registry a sample resolved against, and an id was not invented to make it pass. `samples.v0.json` now exists and `subject.kind` takes `sample` (a675c4e), wired to resolve against that table and nothing else. The refusal is what produced the registry: a check rejecting the honest form of an assertion is the strongest evidence that the thing being asserted had nowhere to live.

### [particle_suspension_a_identity](../entries/particle_suspension_a_identity.json)

The particle suspension in use on this bench, instance particle_suspension_a, is the Abvigen product AFR-0500-COOH. This is the person's ruling of 2026-09-19 from evidence on record, not a reading of the container.

Identifiers: catalog_number: AFR-0500-COOH; instance: particle_suspension_a; supplier: Abvigen Inc; what_it_joins: the instance in kb/staging/samples.v0.json to the type facts filed as tracer_particle_material_and_shape, tracer_particle_density, tracer_stock_concentration, tracer_storage_conditions, tracer_number_density_from_diameter, tracer_emission_peak and tracer_excitation_peak

How it is known: recalled or assumed; an assumption (E5 · assumed:person_ruling_20260919).

Conditions, verbatim:

> THE JOINING CLAIM, AND IT IS AN ENTRY BECAUSE A STAGING TABLE CANNOT CARRY A GRADE ANYTHING CHECKS. Architecture's instance/type split (6eaee1b) puts three things in three places: the bottle is an INSTANCE and lives in the sample table, AFR-0500-COOH is a TYPE and its facts are ordinary entries at E3, and the claim joining them carries its own grade. This is that claim. It was written into kb/staging/samples.v0.json first, where check 43 does not reach, kb_index.py does not index, and -- decisively -- check 54 cannot resolve it: a `kb:` basis resolves to an entry, so a card applying a type fact to this bench had no citable link and inherited E3 by default, which is the exact over-claim 017 forbade. WHAT EVERYTHING ELSE INHERITS FROM IT. 5.8 gives a chain the worst precision and grade of its inputs, so every type-level fact reaching this bottle passes through E5 here: the material and shape, the density, the stock concentration, the storage range, the number-density relation, and through the material, the eight polystyrene refractive indices. A caller applying any of them to the bench cites this entry as well and takes E5, not the E3 those entries carry about the type. WHAT DOES NOT PASS THROUGH IT. A measurement made ON the instance does not, and that is the whole point of the split rather than a technicality. tracer_diameter_measured is E2 about this bottle; particles_show_on_the_green_605_path is E2 about this bottle; bottle_label_states_no_product is E3 about this bottle. None of the three is weakened by this entry, and if the identification is ever overturned all three stay true while every type fact above stops applying. WHY E5 AND NOT E3. The person did not read it off the container -- bottle_label_states_no_product records that the label was examined and does not state a product identity, which is what makes the doubt permanent rather than pending. It is not a recollection either. It is an inference, and the inference is an asymmetry rather than a measurement: the observation on this bench (green excitation, visible at 605) is equally consistent with `this is not the Abvigen product` and with `this is the Abvigen product and the published spectra are wrong`, and a silent label separates them not at all. What separates them is abvigen_published_data_is_unreliable -- the supplier's page carries two errors unrelated to spectra, a monoclonal-antibody filing and the product name printed in the Particle Size field -- which makes the second explanation far the cheaper one. Cheaper is not proven, and E5 is the grade that says so. WHAT WOULD MOVE IT TO E3. A label, an invoice, or a lot number that names the product, read by a person: any of those is `operator_read:` at E3 and lifts every type fact with it. The lot number is the cheapest and the prior project's own record says `lot: null -- not on the product page, read it off the tube`, which nobody has done. THIS WAS RULED THE OTHER WAY EARLIER THE SAME DAY. Task 015 ruled the product wrong and was executed (8646426); the person reversed it (ed373e0, 017) once the prior project's records were opened. Kept in this entry rather than only in the task file because a caller meeting this claim at E5 will want to know the doubt has been resolved once already, and in which direction. Anyone re-deriving the identification from the label alone will reach 015 again.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
