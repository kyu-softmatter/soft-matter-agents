# Quantity: full_scale_count

Every entry in the store about the quantity full_scale_count.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/quantities.json:

> The highest value a camera reports for a saturated pixel, in ONE readout mode of ONE camera body. Read from a frame, not from the camera's own description of its bit depth: a ceiling taken from a bit depth is a calculation, and on this kind of camera the reported bit depth has been wrong before. A value without its readout mode is not a fact about the camera, the same way a read noise without its mode is not.

- unit: `ADU`
- kind: physical

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |
|---|---|---|---|---|---|---|---|---|
| full_scale_count | 65535 | ADU | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20261013_bench_readings | none stated | binning: 1x1; mm_configuration: DMD_dualcam_LUNF.cfg; model: Kinetix 22; port: Dynamic Range; readout_rate: 100MHz 16bit | quantity full_scale_count | [kinetix22_saturates_at_65535_adu_dynamic_range_100mhz_16bit](../entries/kinetix22_saturates_at_65535_adu_dynamic_range_100mhz_16bit.json) |
| full_scale_count | 65535 | ADU | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20261013_cameras_read_the_same | none stated | binning: 1x1; model: Kinetix 22; port: Dynamic Range; readout_rate: 100MHz 16bit | device camera_red, device camera_blue, quantity full_scale_count | [kinetix22_both_bodies_saturate_alike_per_the_person](../entries/kinetix22_both_bodies_saturate_alike_per_the_person.json) |

## Claims

None.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device camera_blue](../wiki/device_camera_blue.md)
- [device camera_red](../wiki/device_camera_red.md)

---

Generated from the knowledge store at kbv-058ce14eea72. Do not edit by hand: correct the store and regenerate.
