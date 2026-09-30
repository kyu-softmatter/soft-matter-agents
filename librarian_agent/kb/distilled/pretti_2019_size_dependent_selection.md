# Square when small, hexagonal when large (Pretti et al. 2019)

**Claim** In a two-dimensional binary mixture with short-ranged attractions,
small crystallites are square and large ones hexagonal, and the change runs
both ways. A 100-particle square crystallite turns hexagonal; a 64-particle
hexagonal one turns square. Free energies put the crossover near 100
particles, although lattice energy alone favours hexagonal at every size.
During self-assembly this shows up as square crystallites converting to
hexagonal as they grow.

**Under what conditions** A model: a 1:1 binary mixture with a Fermi-Jagla
pair potential, like attractions 0.1-0.19 of the unlike one, kT/E_AB from
0.06 to 0.1. Two-dimensional Langevin molecular dynamics in LAMMPS, on
isolated crystallites of 36 to 324 particles and on assembly from a dilute
start (rho sigma^2 = 0.1).

**What it does not cover** Three dimensions, though the authors point to the
analogous CsCl-to-CuAu case. Crystallite shapes other than the chosen compact
ones: longer perimeters stabilise the square lattice further. Asymmetric like
attractions, which open a rhombic phase.

**The limit worth remembering** The selection is thermodynamic and belongs
to the crystallite itself. It does not come from nucleation kinetics or from
contact with a dense fluid: it happens in isolation, far above critical size.
Higher temperature widens the square window, which the authors put down,
probably, to the square lattice being less rigid. The effect sits in surface entropy and heat capacity, not in
bond counting. Fang et al. 2020 see the same square-then-hexagonal sequence
with a different engine.

## How it was simulated

The main engine is **LAMMPS, not HOOMD**: NVT Langevin molecular dynamics,
Fermi-Jagla potential (parameters only in the Supplementary Text), 10
replicates per condition. Structures were identified with a radial-
distribution similarity parameter.

Free energies came from an Einstein-molecule method extended to finite
crystals with free surfaces:

- one particle fixed and others constrained against rotation;
- kT/E_AB from 0.02 to 0.11;
- 32-point Gauss-Legendre integration;
- extrapolation linear in 1/sqrt(N).

**HOOMD-blue (version not stated)** ran only a second model with explicit
DNA strands: 60 strands per particle, time step 5e-3 in its units, between
walls 40 sigma apart. It showed the effect is not an artefact of the pair
potential.

**Entries** `binary_2d_crystallites_small_ones_square_large_ones_hexagonal`,
`binary_2d_crystallite_free_energies_cross_near_100_particles`,
`binary_2d_assembly_gives_square_crystallites_first_then_hexagonal` ·
**Grade** E3 (peer reviewed) · **Source** `src_pretti_2019_size_dependent_selection`
