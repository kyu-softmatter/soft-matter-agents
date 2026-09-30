# Passive disks clustered by correlated active noise (Frechette, Baskaran, Hagan 2025)

**Claim** Purely repulsive disks pushed around by a noise field that is
correlated in space and time -- a stand-in for an active fluid -- gather into
dynamic, finite, often rotating clusters, and do not if the noise field is
made divergence-free. Clusters grow with the noise correlation length and
time, reach far beyond the correlation length, and span the system only at the
higher of the two packing fractions studied (0.4, not 0.1). The structure
depends on the noise only through the correlation length and the product of
noise speed and correlation time.

**Under what conditions** A model: WCA disks, overdamped, no thermal noise
term, moved only by the potential and the imposed field; two dimensions (one
3D run at packing fraction 0.02 clusters too); reduced units of diameter,
repulsion energy and friction time.

**What it does not cover** Hydrodynamic coupling between the particles and
the active fluid, attractive particles, or quantitative prediction: the
authors do not expect the numbers to hold for a real active fluid. The model
predicts, without testing it, that repulsive colloids at a 2D interface of an
incompressible active nematic would not cluster.

**The limit worth remembering** Clustering needs sinks in the noise field,
because particles collect where the noise is weak. A single tracer in the same
field is an ordinary persistent random walker, and becomes an active
Ornstein-Uhlenbeck particle when the correlation length is infinite, so
tracer statistics alone cannot reveal the many-body effect.

## How it was simulated

Particle dynamics runs in **HOOMD-blue (version not stated)**. The noise field
comes from the authors' Python/CuPy generator, joined to HOOMD by their own
package; both are published at github.com/Layne28, with an archive at
osf.io/7ha8j. Each Fourier mode of the field evolves as an Ornstein-Uhlenbeck
process on a grid of spacing 0.5, interpolated bilinearly to the particle
positions. Box 200 x 200, time step 1e-4, 250 time units, 50 independent runs
per state at packing fractions 0.1 (5,016 disks) and 0.4 (20,372). One 2.5e6-step
run of 20,372 disks took about 1.5 h on one A100 GPU. For experiments, the
parameters are read off a measured velocity field: the correlation length and
time from its autocorrelation decay, and the speed from its rms value. The
paper's kinesin-microtubule example gives about 150 um and 1,100 s.

**Entries** `repulsive_disks_in_active_noise_cluster_only_if_the_noise_is_compressible`,
`repulsive_disks_in_active_noise_span_the_box_only_at_packing_0_4`,
`repulsive_disks_in_active_noise_structure_set_by_lambda_and_va_tau` ·
**Grade** E3 (peer reviewed) · **Source** `src_frechette_2025_active_noise_clustering`
