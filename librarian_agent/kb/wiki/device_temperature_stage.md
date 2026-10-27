# Device: temperature_stage

Every entry in the store about the device temperature_stage.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, retired row, verbatim:

```json
{
  "id": "temperature_stage",
  "retired_at": "2026-09-17",
  "why": "it has never been connected. Nothing controls the sample temperature, so it is not a control channel. Listing it as one with driver, automatable and read_back all unknown claimed a channel that does not exist.",
  "what_it_had_claimed": "a channel at grade E5 sourced to an operator statement, justified as existence being the only thing established.",
  "the_fact_is_not_deleted": "it moved to the entry sample_temperature_not_actuated and to the gaps below. Omitting it from the channel list and erasing it are different things.",
  "resolved_by": "operator_read:kyuhwan_20260917",
  "entry_ref": "sample_temperature_not_actuated"
}
```

## Values

None.

## Claims

### [sample_temperature_not_actuated](../entries/sample_temperature_not_actuated.json)

Sample temperature is not under control on this instrument. A temperature stage exists but has never been connected, so nothing actuates the sample temperature and there is no setpoint to appeal to: any temperature a plan uses is an ambient value of the room, not a commanded one.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260917).

Conditions, verbatim:

> This instrument as of 2026-09-17, operator read. Two consequences travel with it. A temperature stage being present is not a control channel, so it is not listed as one. And any plan needing the viscosity or the thermal energy carries temperature as an uncontrolled condition: in explore mode a drift of about a kelvin does not move a decade and can be ignored, while in confirm mode it cannot and there is no actuator to appeal to. The ambient value itself, its drift band and where it is read are not in the store -- see the sample_temperature_value gap. Falsified by the stage being connected and driven.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-058ce14eea72. Do not edit by hand: correct the store and regenerate.
