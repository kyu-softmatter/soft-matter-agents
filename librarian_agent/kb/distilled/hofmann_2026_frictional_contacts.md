# Frictional contacts need their own thermal noise (Hofmann et al. 2026)

**Claim** If colloids in a simulation feel tangential contact friction, the
friction needs its own matching random force and torque. Without them the
particles cool below the bath, and translation and rotation cool by
different amounts, so the system is no longer in equilibrium. The paper
derives that noise for any friction law and stochastic convention; its HOOMD
implementation is documented in HOOMD-blue 6.1.0 as `hoomd.md.pair.friction`.

**Under what conditions** WCA spheres with linear, Coulomb or Coulomb-Newton
tangential friction, underdamped, in a Langevin bath or without one. Tested
in 2D (area fraction 0.6), in 3D (volume fraction 0.3), in walled
pressure-driven flow at 0.15, and in 2D active Langevin disks.

**What it does not cover** Spinning friction, static friction (friction with
memory), the overdamped limit -- which the authors call tricky with friction
present and leave for later -- and hydrodynamics between the particles.

**The limit worth remembering** The noise changes results, not just
equipartition:

- in the flow, dropping the frictional noise lowers the viscosity roughly
  fivefold and raises wall slip;
- in the active disks, the inconsistent model phase-separates by motility at
  a state point where the consistent one does not.

Contact friction also widens the phase-separated region, as reported before
for active Brownian particles. The linear-response window of a frictional
fluid is narrow: stronger driving makes flows plug-like, or turns them into
vortices without walls.

## How it was simulated

**HOOMD-blue** was used for the equilibrium tests and the flows; the version
is not stated beyond the module documented in 6.1.0. **LAMMPS** was used for
the active-particle phase separation. The stochastic forces are integrated
Euler-forward, which is the Ito convention.

- Equilibrium tests: 10,000 particles, time step 0.001 t0 (0.0001 for pure
  Coulomb friction), 20 t0 to equilibrate and 200 t0 sampled, with
  t0 = sqrt(m sigma^2/kT).
- Flows: walls of immobilised particles, no background medium, bulk force
  0.01 kT/sigma, 6,000 t0 sampled, and Couette runs to separate slip from
  the hydrodynamic boundary.
- Active disks: 20,000 particles, mass 0.05 kT (t_R/sigma)^2, WCA 10 kT,
  time step 1e-5 t_R.

Scripts and data: doi 10.48328/tudatalib-1838. This repository pins HOOMD
7.2.0. Before relying on `hoomd.md.pair.friction`, check that it is there and
unchanged; the paper cannot say.

**Entries** `contact_friction_without_its_own_noise_breaks_equipartition`,
`hoomd_blue_6_1_0_documents_a_contact_friction_pair_module`,
`active_langevin_disks_mips_depends_on_whether_friction_noise_is_kept`,
`frictional_contact_fluid_viscosity_drops_without_frictional_noise` ·
**Grade** E3 (peer reviewed) · **Source** `src_hofmann_2026_frictional_contacts`
