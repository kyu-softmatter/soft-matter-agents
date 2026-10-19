# Device: intermediate_magnification

Every entry in the store about the device intermediate_magnification.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
{
  "id": "intermediate_magnification",
  "values": [
    "1x",
    "1.5x"
  ],
  "values_note": "nominal designations, so string identifiers rather than numbers (5.3). They were written 1.0 and 1.5, which gave a nominal name a decimal point and an implied precision it does not have."
}
```

## Values

None.

## Claims

### [intermediate_magnification_is_not_a_state_device](../entries/intermediate_magnification_is_not_a_state_device.json)

In the Micro-Manager NikonTi2 adapter, IntermediateMagnification is not a state device: asking it for a state raises 'is of the wrong type for the requested operation'. Its value has to be read as a property.

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-002).

Conditions, verbatim:

> Read back in a preparatory run -- the first real acquisition on this computer, with no plan, the person having placed the 20x and moved the microscope by hand, software moving nothing. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system: E1 from `measured:`. Not a value of any registered observable. A fact about the adapter in the Micro-Manager copy that loaded today (MMCore 12.5.0, device API 75). Slot: A6 -- a pixel size depends on the intermediate magnification, and code that reads it with a state call gets an error, not a value. Delivered as item intermediate_magnification_not_a_state_device of microscope_agent/findings/microscope-20260924-1-20260924.json at bf8f91f (card 042). Checked by this seat against microscope_agent/runs/run-20260924-002/log.json read at bf8f91f (unchanged since): event 15.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device stand_ti2e](../wiki/device_stand_ti2e.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
