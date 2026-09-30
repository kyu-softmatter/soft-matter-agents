# Strings and gels of dipolar active Brownian spheres in 3D (Kelidou et al. 2024)

**Claim** At low density, active spheres whose dipole points along their
propulsion form one of three states, set by the dipolar coupling lambda and
the active force f_a:

| packing fraction | gas | string fluid (chains and rings) | active gel (network) |
|---|---|---|---|
| 0.010 | lambda below 6 | lambda 6 to 9 | lambda above 9 |
| 0.08 | lambda up to 4 | lambda above 4, up to 9 | strong coupling |

The string fluid and the gel appear only below an active force that rises
with lambda. Above it, activity breaks the aggregates back into a gas; at
lambda = 16 and packing fraction 0.010 the network holds up to f_a = 50. At
0.08 the string fluid and the gel survive over a wider range of active force.

**Under what conditions** A model: overdamped active Brownian spheres with a
WCA core and a point dipole parallel to propulsion, in three dimensions, with
no hydrodynamics. Reduced units are sigma, 1/Dr and kT, with
gamma_t* = 3, so the Peclet number is f_a/3.

**What it does not cover** Denser suspensions, where passive dipoles order,
and external fields or shear. Hydrodynamics is also left out, and it is known
to matter for dilute magnetic swimmers. The authors map the parameters onto
magnetotactic bacteria (roughly lambda 0.1-20, f_a 5-200) as a rough estimate
only.

**The limit worth remembering** The active gel keeps the passive gel's
structure but rearranges faster. Bonds live shorter, and particles diffuse
faster in both translation and rotation; the rotational diffusion of strongly
coupled active particles is about twice that of isolated ones. Structure
alone therefore cannot tell an active gel from a passive one; dynamics can.
The state boundaries in f_a are only drawn in the paper's figure. The authors
estimate them as the active force that matches the head-to-tail dipole force
at the neighbour distance, 6 lambda/r_nn^4.

## How it was simulated

Most runs used **HOOMD-blue on GPU (version not stated)**: time step 2e-4
(in units of 1/Dr), 8,788 particles in a cubic periodic box. The dipole sum
had no Ewald correction. This was justified where the largest dipole energy
at half the box is below 1e-3 kT, and checked against LAMMPS runs with Ewald
correction, which gave identical g(r). The dense, strongly coupled runs
(packing 0.08, lambda 9 to 12.25) used **LAMMPS with full Ewald** and 10,648
particles.

The protocol:

1. Equilibrate passive systems first, starting from an fcc lattice and
   raising the dipole step by step.
2. Raise the activity gradually.
3. Run 100 to 1e4 time units to reach steady state, then produce for another
   100 to 1e4.

At lambda of 12.25 or more with little activity, the runs never
equilibrated. Clusters were found with a 1.2 sigma cutoff. The states are
defined by two fractions: the gas has less than half the particles bound; the
string fluid has more than half bound and the largest cluster under 70% of
the particles; the network has a largest cluster of 70% or more.

**Entries** `dipolar_active_brownian_spheres_stay_a_gas_below_coupling_6_at_packing_0_01`,
`dipolar_active_brownian_spheres_form_string_fluid_at_coupling_6_to_9`,
`dipolar_active_brownian_spheres_form_active_gel_above_coupling_9`,
`dipolar_active_brownian_spheres_state_diagram_at_packing_0_08`,
`dipolar_active_brownian_spheres_dipole_sum_without_ewald_at_low_density` ·
**Grade** E3 (peer reviewed) · **Source** `src_kelidou_2024_dipolar_active_brownian`
