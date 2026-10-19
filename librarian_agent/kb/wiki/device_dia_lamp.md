# Device: dia_lamp

Every entry in the store about the device dia_lamp.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the device table, kb/staging/devices.v0.json, element of channel stand_ti2e, verbatim:

```json
{
  "id": "dia_lamp"
}
```

## Values

None.

## Claims

### [dia_lamp_reports_state_and_intensity](../entries/dia_lamp_reports_state_and_intensity.json)

The transmitted-light lamp, Micro-Manager device DiaLamp, reports two properties, State and Intensity, both readable at load; on 2026-09-24, with no software having set them, they read State "0" and Intensity "2100".

How it is known: measured on this instrument; a recorded run of this system (E1 · measured:run-20260924-008).

Conditions, verbatim:

> Event 17 of the run. Both values are strings as the adapter returned them and are recorded as settings read back, not as quantities: the unit of Intensity is not stated by the adapter, and what State "0" means for light is not established by this reading -- nothing measured light that day. The abort commands this lamp to State "0"; that it then emits nothing has been seen only on mock, which echoes the value it is given. Read back in a preparatory run with no plan, which wrote nothing to any device. A device's report of itself may enter citing such a run (11-21 condition 4 as narrowed at 20a688b), graded as an observation by this system, E1. Not a value of any registered observable. KNOWLEDGE, NOT POLICY: what the device reports, never a limit and never permission to command it. Checked by this seat against microscope_agent/runs/run-20260924-008/log.json, read by this seat at 144ab62 (last changed at 9c9f598); body sha256 with CRLF normalised to LF f7a8f673fd630b7252b8ec30f10e71abafe0aea58ae12c85cbb2ed4f2e187818.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
