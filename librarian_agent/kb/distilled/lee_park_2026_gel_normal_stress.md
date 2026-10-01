# Normal stresses of a sheared colloidal gel (Lee and Park 2026)

**Claim** In a simulated colloidal gel under startup shear, the shear stress
and the second normal stress difference overshoot at different strains, for
different microscopic reasons:

- **Shear stress** peaks first, at a strain of about 0.1 at shear Peclet
  number 150, when bonds along the extensional axis break.
- **Second normal stress difference** is negative throughout, is larger
  than the first normal stress difference, and peaks later, at about 0.2,
  from compression and near-vertical alignment of bonds along the gradient
  direction.

The two strains converge as shear speeds up, and coincide at Peclet number
300. The strain of the shear overshoot grows with Peclet number when
hydrodynamic interactions are included.

**Under what conditions** A model: Brownian dynamics of Morse-attractive
spheres (depth 15 kT, kappa a = 30) with far-field Rotne-Prager-Yamakawa
hydrodynamics and no lubrication. The gel forms from a random start at
volume fraction 0.2 and is sheared at Peclet numbers from 15 to 300 (Mason
numbers 1 to 20).

**What it does not cover** Lubrication and near-field hydrodynamics, which
were left out on purpose. Also inertia, non-Newtonian solvent, entropic
elasticity of the strands, and other volume fractions or well depths.

**The limit worth remembering** Hydrodynamics changes the answer. The
authors cite gel simulations without it in which the overshoot strain does
not move with shear rate, unlike experiment. Normal stresses are noisy and
need large systems (about 1e4 particles here). The paper's phenomenological
energy metric tracks the normal-stress overshoot only to within 20-30% at the
ends of the Peclet range.

## How it was simulated

Brownian dynamics with the **Positively Split Ewald RPY plugin of Fiore et
al., run on HOOMD 2.4.0 with CUDA 9.2**. The run speed was about 1,500 steps
per hour for 10,648 particles on one GTX 1070. The authors report that the
plugin has compatibility problems across HOOMD releases (the release current
when they wrote was 5.4.0) and point to a Python Stokesian-dynamics code as
the reproducible route. This repository pins HOOMD 7.2.0; reusing this recipe
here means porting or replacing the plugin, and nothing in the paper says
that is easy.

Units: particle radius a = 1, energy kT, time 6 pi eta a^3/kT. The gel forms
at time step 1e-4 over 100 time units. It reaches mean coordination 6.136 and
mean bond number 2.014, close to isostatic. Shear runs at time step 1e-6.
Stress comes from interparticle forces only.

**Entries** `colloidal_gel_rpy_shear_overshoot_strain_grows_with_peclet`,
`colloidal_gel_rpy_second_normal_stress_negative_and_overshoots_later`,
`rpy_brownian_dynamics_plugin_was_run_on_hoomd_2_4_0` ·
**Grade** E3 (peer reviewed) · **Source** `src_lee_park_2026_gel_normal_stress`
