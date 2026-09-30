# A few active particles fluidise a soft glass (Shee, Bandyopadhyay, Yue 2025)

**Claim** In a dense mixture of soft passive and active spheres under steady
shear, a small active fraction does most of the fluidising. Five per cent
active particles move the glass transition strongly, while going from 35% to
50% changes little. One combination, the active fraction times the Peclet
number squared, sets the glass-fluid boundary: about 22 at volume fraction
0.66. The same combination collapses stress and viscosity across a broad
range around the transition.

**Under what conditions** A model: a dry three-dimensional bidisperse
mixture (radius ratio sqrt 2) of soft repulsive spheres, active ones as
overdamped active Brownian particles. Lees-Edwards shear, kT = 1e-4, Peclet
number 0-20, active fraction 0-0.5, volume fraction 0.60-0.72, all chosen to
avoid motility-induced phase separation.

**What it does not cover** Hydrodynamics, friction, non-spherical particles,
and active and passive particles of different sizes. Also spatially
non-uniform doping, where the authors expect the mean-field collapse to fail
first. The passive and fully active glass densities (0.61, 0.68) come from
earlier papers and are not this paper's results.

**The limit worth remembering** The active fraction times Pe squared is a
total active energy, and treating it as one global effective temperature is
a mean-field step that sparse doping need not allow. The collapse fails at
the high-activity end of the lowest-shear-rate curve. The authors suggest it
holds elsewhere near the transition because growing correlation lengths let
sparse active particles act on large regions. The shape of the stress fluctuations is a sharper
glass-fluid marker than the mean stress: the fluid has a half-normal stress
magnitude (skewness about 0.995); the glass has skewness near zero and
negative kurtosis.

## How it was simulated

**HOOMD-blue (version not stated).** Euler-Maruyama integration at time step
1e-2, overdamped active Brownian dynamics plus imposed shear with
Lees-Edwards boundaries. The harmonic repulsion is approximated with a Morse
form (details only in the Supplemental Material).

- Four species: small or large, crossed with active or passive.
- Each run covers a total strain of 10, with the first 5 discarded.
- Yield stress comes from Herschel-Bulkley fits; it is set to 1e-6 where
  the fit fails, meaning fluid.
- The Peclet number v0/(a0 Dr) uses the small diameter, which is the store's
  steric Peclet number.
- The particle count is not stated in the main text.

Data: zenodo 10.5281/zenodo.17188736.

**Entries** `active_passive_sphere_mixture_glass_fluid_boundary_at_alpha_pe_squared_about_22`,
`active_passive_sphere_mixture_small_active_fraction_shifts_glass_density_most`,
`shear_stress_fluctuation_shape_marks_the_glass_fluid_transition` ·
**Grade** E3 (peer reviewed) · **Source** `src_shee_2025_active_dopants_rheology`
