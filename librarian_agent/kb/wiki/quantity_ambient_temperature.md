# Quantity: ambient_temperature

Every entry in the store about the quantity ambient_temperature.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/quantities.json:

> Temperature of the room air. Registered because it is in use, and flagged: by rule 1 this is `temperature` with `at` naming the room, and the name predates that field.

- unit: `K`
- kind: physical

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |
|---|---|---|---|---|---|---|---|---|
| ambient_temperature | 293 | K | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260917 | none stated | none | quantity ambient_temperature, quantity temperature | [lab_ambient_temperature](../entries/lab_ambient_temperature.json) |
| temperature_stability | 1 | K | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20260923 | none stated | none | quantity temperature_stability, quantity ambient_temperature, quantity temperature | [room_temperature_hold_band](../entries/room_temperature_hold_band.json) |
| temperature_resolution | 1 | K | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20260923 | none stated | none | quantity temperature_resolution, quantity ambient_temperature, quantity temperature | [room_thermometer_reads_in_one_kelvin_steps](../entries/room_thermometer_reads_in_one_kelvin_steps.json) |

## Claims

### [no_thermometer_at_the_sample](../entries/no_thermometer_at_the_sample.json)

There is no thermometer beside the sample. The only thermometer in the laboratory reads the room, so any temperature attributed to the sample is a room reading applied to it.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260919).

Conditions, verbatim:

> This laboratory as of 2026-09-19, read by the operator. It REPLACES an inference: lab_ambient_temperature reasoned that its value could only be the room's, from the fact that nothing actuates the sample. The same conclusion is now stated, which is a stronger claim than a consequence of an absence, and it is why the sample-adjacent reading stops being an open question. What it does NOT say is how far the room thermometer is from the sample or how well the two track -- neither is known, and an unknown distance is not a small one. Falsified by putting a thermometer at the sample, which is also what would close the two questions it leaves open.

### [room_temperature_is_controlled](../entries/room_temperature_is_controlled.json)

The room is held continuously by air conditioning. There is a setpoint on this instrument's environment -- it is the room's, not the sample's.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260919).

Conditions, verbatim:

> This laboratory as of 2026-09-19, read by the operator. It runs opposite to how it sounds, and that is the reason it is worth an entry: holding the room does not shrink the sample question, it ISOLATES it. With the room held, whatever still moves at the sample is local -- illumination, a contacting objective, the stage, the trapping laser -- and each of those has its own gap. Do not read 'the room is controlled' as 'temperature is handled'. It also corrected a sentence in this store: lab_ambient_temperature argued that 20 C could not be a setpoint because nothing actuates the temperature, which collapsed 'nothing actuates the SAMPLE' into 'nothing actuates'. That grade never rested on the argument and did not move; the reasoning did. What this entry does NOT say: what the setpoint is, how tightly the room holds it, and how well the sample follows the room. The third is the one that matters and all three are open -- a controlled room is not a controlled sample, and the distance between them is still unmeasured.

## Disputed and withdrawn

None.

## Reading

- [implementing_61_and_62.md](../distilled/implementing_61_and_62.md)

## Related

- [quantity temperature](../wiki/quantity_temperature.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
