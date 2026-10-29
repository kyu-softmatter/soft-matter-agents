# Quantity: depth_of_field

Every entry in the store about the quantity depth_of_field.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/quantities.json:

> The axial distance over which an objective images a plane acceptably sharp, for one objective, immersion medium and emission wavelength. Whether a value is a full width or a half width is part of the value and is stated with it: a tolerance written as a fraction of it changes by a factor of two on that choice alone.

- unit: `um`
- kind: physical

## Values

None.

## Claims

### [objective_depth_of_field](../entries/objective_depth_of_field.json)

The total depth of field of a microscope objective imaging onto a detector is the sum of a wave-optical term, the wavelength times the medium's refractive index over the numerical aperture squared, and a geometric term, the refractive index times the detector's smallest resolvable distance over the lateral magnification times the numerical aperture; it is the full axial distance between the nearest and farthest planes in focus.

Identifiers: none

How it is known: computed; computed from other values (E4 · computed:depth_of_field_total).

Conditions, verbatim:

> WHICH FORM AND WHY: the total form, wave plus geometric, because a focus search scores against frames on a pixel camera, and at low magnification the geometric term is not small -- the wave term alone understates the in-focus depth most for the lenses a search starts with. IT DIFFERS FROM THE RESOLUTION AXIS, which uses the wave term alone, n*lambda/NA**2 (microscope_agent/src/axis_a6_resolution.py, inequality depth_of_field). That is a finding for the microscope seat and is not changed here; the two agree when the geometric term is negligible, at high NA and magnification. FULL WIDTH: nearest to farthest plane in focus, not a half width either side of best focus, so a tolerance written as a fraction of this is half as tight as the same fraction of a half width. CONDITIONS: wide-field imaging; for fluorescence imaging_wavelength is the emission's, in um like the depth, since the image is formed by emitted light (the source writes illuminating light, for transmitted imaging); n is the medium between coverslip and front lens -- air, water or oil per objective. e AND M ARE NOT DEFINED FOR A PIXEL CAMERA BY THE SOURCE. With e taken as the camera's pixel pitch (camera_sensor_geometry, E3), e/M is the sample-plane pixel size the store holds per objective at E2, which a plan may use instead; whether e is one pixel or two is the plan's stated choice. The source notes that digital detection gives a shallower depth than the equation predicts. Not for confocal imaging, where the pinhole sets the axial extent. NOT A LIMIT: a scoring tolerance only. The focus limits are the person's, per objective, in the envelope; nothing moves further because of this. INPUTS ARE FORMAL PARAMETERS, as for tau_d: per objective, what the store holds and what a plan brings is listed in the source record's inputs_per_objective. No per-objective value is entered here; a computed value belongs to the card that computes it, with its inputs named. RENAMED 2026-10-07 under task 045, same formula, source and grade (rule 8: a rename is not a supersede): the inputs now use the registry's names -- numerical_aperture became na, and emission_wavelength became imaging_wavelength, with detector_resolvable_distance and lateral_magnification kept and all three registered at d92410b -- so a card computing from this formula finds each input by the name the objective entries and the registry use.

## Disputed and withdrawn

None.

## Reading

None.

## Related

None.

---

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
