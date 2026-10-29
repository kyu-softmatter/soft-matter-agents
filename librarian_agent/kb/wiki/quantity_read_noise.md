# Quantity: read_noise

Every entry in the store about the quantity read_noise.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/quantities.json:

> The rms uncertainty a camera's readout adds to a pixel, in electrons, for ONE readout mode. A value without its mode is not a fact about the camera: the Kinetix 22 offers four and they span an order of magnitude, so naming the quantity without the mode is the same error as naming a working distance without the objective.

- unit: `e`
- kind: physical

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |
|---|---|---|---|---|---|---|---|---|
| read_noise | 1.6 | e | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | bit_depth_designation: 16-bit; camera_mode: DynamicRange; model: Kinetix 22 | device camera_red | [camera_read_noise_dynamicrange](../entries/camera_read_noise_dynamicrange.json) |
| read_noise | 1.2 | e | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | bit_depth_designation: 12-bit; camera_mode: Sensitivity; model: Kinetix 22 | device camera_red | [camera_read_noise_sensitivity](../entries/camera_read_noise_sensitivity.json) |
| read_noise | 2.0 | e | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | bit_depth_designation: 8-bit; camera_mode: Speed; model: Kinetix 22 | device camera_red | [camera_read_noise_speed](../entries/camera_read_noise_speed.json) |
| read_noise | 0.7 | e | from a document, a reading off the instrument, or another project's record; manufacturer's specification | E3 · spec:Kinetix22 | none stated | bit_depth_designation: 16-bit, 8x CMS; camera_mode: SubElectron; model: Kinetix 22 | device camera_red | [camera_read_noise_subelectron](../entries/camera_read_noise_subelectron.json) |

## Claims

None.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [device camera_red](../wiki/device_camera_red.md)

---

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
