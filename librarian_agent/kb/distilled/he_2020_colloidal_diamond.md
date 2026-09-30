# Cubic diamond from compressed tetrahedral patchy clusters (He et al. 2020)

**Claim** Tetrahedral clusters of four partly fused spheres, with sticky
patches recessed into their four faces, lock into the staggered orientation
that cubic diamond needs, and they crystallise into cubic diamond. In
experiment this happens for compression ratios from 0.63 to 0.78 with size
ratios near 1.2, and it happens in a simulated model of the same shape.

**Under what conditions** Experiment: DNA-coated TPM patches on 1.0-um
polystyrene lobes, in a density-matched buffer, crystallised overnight in a
tilted capillary across a small temperature gradient spanning the DNA
melting temperature. Simulation: rigid lobed clusters with a short-ranged
patch attraction in HOOMD-blue, cooled slowly at 5% volume fraction.

**What it does not cover** Where exactly in compression-size-ratio space the
simulated crystal region lies (it is only in a figure), kinetics, or any
depletion-driven version -- that is Kim et al. 2026, which finds a different
region.

**The limit worth remembering** The shape does the selecting, not the
attraction's direction. Patches only reach each other when the lobes
interlock, and interlocking fixes the staggered bond. Shape alone is not
enough, though: with the patch attraction removed, the particles form
amorphous structures. The crystals pack to a volume fraction of about 0.68,
close to fcc's 0.74 and far above the 0.34 of a diamond of touching spheres,
which is why they survive drying. A shorter-ranged patch attraction moves the
crystal region to larger size ratios.

## How it was simulated

**HOOMD-blue, version not stated** -- nor integrator, thermostat, time step
or cooling rate. The model:

- each particle is four overlapping lobes plus one central patch sphere;
- patch-patch attraction is a 48-24 Lennard-Jones form (n = 24) of depth 10,
  with its minimum at 1.03 sphere radii;
- lobe-lobe attraction is the same form with depth 3, standing in for weak
  depletion;
- lobe-patch interaction is repulsive;
- the patch melting temperature is 1.6 to 1.7 in the model's energy units,
  which are not kT;
- a shorter n = 48 variant was also run.

Runs held 216 to 8,000 particles, cooled near aggregation. OVITO classified
the final states. The photonic calculations used MIT Photonic Bands: a
complete gap between bands 2 and 3, opening for the inverse lattice at
compression ratios from 0.1 to 0.8 and widest near 0.6. That is optics, and
no entry is filed for it.

**Entries** `tetrahedral_patchy_clusters_crystallise_cubic_diamond_in_hoomd_model`,
`dna_patchy_tetrahedral_clusters_crystallise_diamond_at_compression_0_63_to_0_78` ·
**Grade** E3 (peer reviewed) · **Source** `src_he_2020_colloidal_diamond`
