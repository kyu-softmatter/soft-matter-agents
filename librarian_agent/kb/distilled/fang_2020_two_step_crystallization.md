# Two-step crystallisation in a 2D binary mixture (Fang, Hagan, Rogers 2020)

**Claim** In a two-dimensional binary mixture with a short-ranged attraction
and no A-A binding, the crystal that forms is set by the like attraction
E_BB: square with checkerboard order while E_BB is weak, hexagonal once E_BB
exceeds 1.2 kT. Between the two, at E_AB = 7.0 kT and E_BB = 1.6 kT, the
square crystal is favoured while small and the hexagonal stripe crystal once
large, so crystallisation goes square first and then turns hexagonal. The
experiment on DNA-coated colloids shows the same sequence, driven by the
mixing ratio of complementary strands on one species.

**Under what conditions** A model: grand canonical Monte Carlo in two
dimensions with a measured DNA potential rescaled to a range of about 5% of
the diameter, a dilute reservoir (0.5% area fraction) and no hydrodynamics.
The experiment: 619-nm polystyrene spheres, about 1% volume fraction, 1:1,
between two coverslips, quenched to just above melting.

**What it does not cover** Dense quenches, three dimensions, longer-ranged
attractions, or any system with hydrodynamics in the simulation. How the
square-hexagonal boundary moves with E_AB is only in the paper's figure.

**The limit worth remembering** The two-step path is thermodynamic, not
kinetic: one crystal has the lower bulk free energy and the higher surface
free energy, so which one wins depends on how big the crystal is. The paper's
evidence is that simulations without hydrodynamics reproduce the experiment's
sequence. The two lattices also differ in packing -- checkerboard 0.76,
stripe about 0.84 -- and the floppier checkerboard is stabilised by entropy
that simple bond counting leaves out.

## How it was simulated

The main engine is **the authors' own C++ grand canonical Monte Carlo, not
HOOMD**. The set-up: a periodic 53.3 x 53.3 diameter box, displacement,
insertion/deletion and species-flip moves (the last two once per 1,000
displacements), at least 2e10 displacements per run, and umbrella sampling
with WHAM over crystal size and a symmetry parameter built from Psi4 and
Psi6. HOOMD-blue appears only as the engine of a preliminary
molecular-dynamics check, detailed in the Supplementary Information, which is
not in the file.

**Entries** `binary_2d_gcmc_hexagonal_crystals_need_like_well_above_1_2kt`,
`binary_2d_gcmc_two_step_crystallisation_square_then_hexagonal`,
`dna_colloids_2d_mixing_ratio_selects_checkerboard_stripe_honeycomb` ·
**Grade** E3 (peer reviewed) · **Source** `src_fang_2020_two_step_crystallization`
