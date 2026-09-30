# Driven 2D melting is set by defects, not by a temperature (Vyas et al. 2026)

**Claim** A two-dimensional colloidal crystal melts the same way whether it
is heated or stirred by spinning particles. Both routes go through the
hexatic phase. Dislocations appear first and disclinations second, and in
both routes hexatic order falls along one curve against disclination
density. In the stirred crystal, the orientational correlation exponent
reaches the textbook value 1/4 at the hexatic-fluid transition. No single
effective temperature describes the stirred system, though: each transition
follows its own defect density.

**Under what conditions** Experiment: charged PMMA microspheres at an
oil-water interface, repelling as dipoles, with magnetic spinners held
beneath a fraction of the sites. Simulation: dipolar-repulsive particles in
two dimensions whose spinner sites add transverse rotlet forces. Both are
run far from equilibrium when driven.

**What it does not cover** Where the transitions lie in the paper's control
parameters (figure only), sheared crystals (no steady hexatic phase), odd
elasticity (not detected; a rough estimate of order 1e-2), and other active
systems -- which the authors name as the open question.

**The limit worth remembering** Defect densities predict the transitions,
and temperature does not. The stirred fluid is superdiffusive, so no
effective temperature can be read from a diffusion constant. A simulation
compared with this experiment has to be compared through defect statistics,
not through a temperature.

## How it was simulated

**HOOMD-Blue v4.4.1 with custom plug-ins**, described only in the
Supplementary Information: a pair potential that mimics spinner-neighbour
coupling, with a rotlet flow cut off at 1.5 particle radii. Integrator,
thermostat and time step are not in the file. Systems hold roughly 1e5 to
1e6 particles, far more than the 1e3 to 1e4 per experimental sample, which
is why the simulation shows the loss of translational order more clearly.
Correlation exponents are fitted out to a quarter of the box. Thermal melting
is controlled by Gamma = A (pi rho)^(3/2)/kT, driven melting by the ratio of
spinner drag to dipolar force. Simulation data: doi 10.7302/mvmb-3j46.

**Entries** `driven_2d_dipolar_crystal_melting_follows_defect_densities_in_simulation`,
`driven_2d_dipolar_crystal_has_no_single_effective_temperature`,
`charged_colloids_2d_driven_melting_follows_defect_densities_in_experiment` ·
**Grade** E3 (peer reviewed) · **Source** `src_vyas_2026_nonequilibrium_melting`
