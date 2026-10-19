# Sample: particle_suspension_b

Every entry in the store about the sample particle_suspension_b.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the sample table, kb/staging/samples.v0.json, verbatim:

```json
{
  "id": "particle_suspension_b",
  "what_it_observably_is": "a bottle of fluorescent beads the person calls the 100 nm beads, asked about by mic-20260930-001 and sim-20260930-401. Nothing about it has been observed on this bench yet; the description is what the person said it is for, not what anyone has seen.",
  "first_recorded": "2026-10-01",
  "label": {
    "read": false,
    "note": "NOT CHECKED, which is different from read-and-silent (particle_suspension_a). The person named the product by pasting the vendor page; nobody has recorded reading the bottle."
  },
  "identified_as": {
    "type": "F8801",
    "grade": "E5",
    "source": "operator_recall:person_statement_f8801_20260930",
    "entry_ref": "particle_suspension_b_identity",
    "why_e5": "the person's statement, made by pasting the product page and not by reading the container. Every type-level fact applied to this bottle inherits E5 by 5.8."
  }
}
```

## Values

None.

## Claims

### [particle_suspension_b_identity](../entries/particle_suspension_b_identity.json)

The 100 nm fluorescent beads on this bench, instance particle_suspension_b, are Invitrogen FluoSpheres carboxylate-modified microspheres, catalogue F8801. This is the person's statement of 2026-09-30, made by pasting the vendor's product page, not a reading of the container.

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:person_statement_f8801_20260930).

Conditions, verbatim:

> THE JOINING CLAIM, filed the way particle_suspension_a_identity was. Every type-level fact about F8801 reaches these beads through it, so a caller applying the 0.1 um nominal diameter, the 580/605 nm spectra, the polystyrene material or the storage range to the bench cites this entry as well and takes E5, not the E3 those entries carry about the type (5.8). WHY E5. The record says the person pasted the product page and did not read the bottle, so this is a statement about which product they have and not an observation of the container. Nothing on this bench has been observed of these beads yet: no measurement on the instance exists, so unlike particle_suspension_a there is nothing that would stay true if the identification were overturned. WHAT WOULD MOVE IT TO E3: the lot number read off the bottle by a person (operator_read:, E3). It would also yield the lot's Certificate of Analysis, which the vendor page says exists per lot and which gives a measured mean diameter -- the number that the nominal 0.1 um stands in for. WHAT IS NOT KNOWN about this bottle and is not filled from anything: stock concentration, lot number, the dilution to the coverslip, and any photobleaching data. Each is a gap in kb/staging/samples.v0.json. NOT RELATED TO THE 5 um BOTTLE. Every tracer_* entry and particle_suspension_a_identity are about the Abvigen AFR-0500-COOH bottle; none of them applies here, and none was used.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
