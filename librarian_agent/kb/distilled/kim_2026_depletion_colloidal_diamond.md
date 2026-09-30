# Colloidal diamond by depletion (Kim, Shen, Lee, Hocky, Pine 2026)

**Claim** Tetrahedrally lobed patchy particles crystallise into cubic diamond
with a plain depletion attraction and no site-specific binding. The
particles' concave faces let a pair add contacts one at a time as they
interlock. Depletion therefore turns the free-energy landscape into a broad
funnel toward the staggered bond. With enough depletant, the rotational-
entropy barrier of the DNA-patch version disappears. Crystals then form
about ten times faster and at lower particle concentrations.

**Under what conditions** Experiment: 1-um polystyrene lobes on TPM cores,
with F127 micelles (or silica, titania, PEO) as depletant in 500 mM NaCl at
room temperature. Simulation: a five-sphere particle with brush repulsion
plus Asakura-Oosawa depletion, Langevin dynamics in HOOMD-blue v2.9.7.

**What it does not cover** Large depletants on these shapes: pairwise
depletion potentials overestimate the attraction there by up to 30%. That
limit bounds the potential this paper itself uses, and its own case (ratio
0.02) sits safely inside. The DNA melting temperature (the text and a figure
caption disagree). The phase diagram as numbers (figure only).

**The limit worth remembering** Depletion diamond forms at size ratios at or
below the kissing geometry. The authors say DNA-patch diamond forms above it.
The two papers do not contradict each other. They use different interactions,
and depletion rewards the fully interlocked state with six lobe contacts. The
F127 window is narrow: diamond at 0.60% (w/v), nothing at 0.55%, dendrites
above 0.60%. In simulation, direct nucleation was mostly out of reach, so the
stability map comes from melting runs started in the crystal. It tells where
diamond is stable, not where it will nucleate.

## How it was simulated

**HOOMD-blue v2.9.7, Langevin dynamics.** Each particle is four lobe spheres
plus one central sphere for the patches. The pair potential is an
Alexander-de Gennes brush plus Asakura-Oosawa depletion, detailed only in the
SI.

- Stability map: 600 particles started in cubic diamond, 1e8 steps at time
  step 0.0001, judged by common-neighbour analysis in OVITO.
- Pair free energy: umbrella sampling with a harmonic restraint of
  3,333 kT/um^2 over 40 windows from 1.16 to 3 um, 2e8 steps each, WHAM on
  the second half; parameters matched to experiment (compression 0.6, size
  ratio 1.21, depletant/lobe radius 0.02).
- Excluded-volume overlap: Monte Carlo integration for a fixed staggered
  pair, which is where the pairwise-additivity check comes from.

Code: zenodo 10.5281/zenodo.18841631.

**Entries** `lobed_patchy_particles_depletion_removes_the_rotational_entropy_barrier`,
`pairwise_depletion_potentials_overestimate_for_large_depletants_on_lobed_particles`,
`lobed_patchy_diamond_nucleation_out_of_reach_stability_mapped_by_melting`,
`lobed_patchy_particles_f127_depletion_threshold_near_depletant_fraction_0_03`,
`depletion_driven_lobed_diamond_forms_at_or_below_the_kissing_size_ratio` ·
**Grade** E3 (peer reviewed) · **Source** `src_kim_2026_depletion_colloidal_diamond`
