# sim-20260923-003 — what the runs measured

*For people. Written by seat `simulation-9` on 2026-09-23.*

**These runs are NOT card-backed and this file says so before it says anything
else.** They were driven straight through `hoomd_backend`'s four-call
interface, not through `operator.py` under a plan, so there is no
`plan_simulation_*.json`, no approval, no directory under `runs/`, and no
`result_*.json`. A result card requires `plan_id`, `plan_revision`,
`plan_hash` and `approval_id`, and this question has none of them. What
stands between here and a card is one missing thing, named at the bottom.

So read what follows as **verification of the declared model on the declared
engine**, which is what it is, and not as a graded result about the world.

## The operating point

One point, the Stokes-Einstein-Debye centre, so every number describes one
real 5 µm particle in water at 293 K.

| | |
|---|---|
| translational diffusivity `D_T` | 8.584e-14 m²/s |
| rotational diffusivity `D_R` | 0.01 s⁻¹ |
| self-propulsion speed `v0` | 2.93 µm/s |
| `Pe_thermal = v0/sqrt((d-1) D_R D_T)` | 100 |
| `Λ = Pe²` | 1e4 |
| early crossover `τ₁ = D_T/v0²` | 0.01 s |
| late crossover `τ_R = 1/((d-1) D_R)` | 100 s |
| persistence length `v0 τ_R` | 293 µm |

Three runs at this point cover three lag windows and are joined into one
curve spanning **8.3 decades** of lag, 1e-4 s to 2e4 s. Five more runs make
the sweep. Total wall clock about four minutes; the ceiling is two hours.

## The answers

**There are three regimes, not two.** The question asked for the crossover
from ballistic to diffusive, which is one crossover. The free model has two.

| regime | where | measured slope | closed form |
|---|---|---|---|
| thermal diffusion | below `τ₁` | 1.004 | 1.004 |
| ballistic | between | 1.985 (max) | 1.977 |
| effective diffusion | above `τ_R` | 1.021 | 1.006 |

At the shortest lags the translational noise beats the propulsion, because
the propelled distance grows as `t` and the diffused distance as `√t`. So the
MSD **starts at slope 1**, bends up toward 2, and bends back to 1.

**The ballistic slope never reaches 2**, and how close it gets is set by `Λ`
alone: 1.12 at `Λ`=1, 1.79 at 100, 1.98 at 1e4. A sweep that stays below
`Pe_thermal` ≈ 20 shows no ballistic regime at all, whatever its resolution.

**The effective diffusivity.**

| | |
|---|---|
| measured, from lags above 50 `τ_R` | 4.18e-10 m²/s |
| predicted `D_T + v0²/(2(d-1)D_R)` | 4.293e-10 m²/s |
| ratio | 0.974 |
| enhancement over `D_T` | 4869× (theory `1 + Λ/2` = 5001) |

**`D_eff(t)` rises from `D_T` to the plateau across the whole ballistic
window**, which is the same physics read as a function rather than a number.
It sits on `D_T` below `τ₁` and reaches the plateau about a decade above
`τ_R`.

**How the scales depend on the parameters.** `τ_R = 1/((d-1)D_R)` and
`τ₁ = D_T/v0²`, so the ballistic window is a factor `Λ` wide in time and the
persistence length is `v0/((d-1)D_R)`. `v0` moves `τ₁` and the length and
leaves `τ_R` alone; `D_R` moves `τ_R` and the length and leaves `τ₁` alone.

## The collapse

**`Pe_thermal = v0/sqrt((d-1) D_R D_T)` is the collapse variable, and it has
no length in it.** Rescaling time by `(d-1)D_R` and length by
`sqrt(D_T/((d-1)D_R))` leaves

    MSD* = 2d·s + 2Λ·(s − 1 + e^(−s))

with `Λ = Pe_thermal²` and nothing else.

Three runs at `Λ`=1e4 with `D_R` spanning **16×** and `v0` spanning **4×**,
under **independent seeds**, collapse to a median fractional spread of
**0.001** and a maximum of **0.086**, against a sampling floor
`sqrt(2/N)` = 0.071. Runs at `Λ` = 1, 100 and 1e4 do not collapse: they differ
by factors of 34 and 3400.

**The first collapse test was worthless and is recorded rather than hidden.**
It ran all points under one seed, and because the rescaling is exact that
gives bit-identical curves — a spread of 0.0000 that tests the code's scale
invariance and not the physics. The same trap appeared in the A1 controls
earlier the same day. Identical numbers from an exact rescaling are what a
correct scaling argument predicts, not evidence about the world.

**The diameter convention cannot be used here.** `v0/(σ D_R)` needs a length,
the free model has none, and `D_T` and `D_R` are swept independently so no
single diameter is consistent with both: across this grid the diameter `D_T`
implies and the one Stokes-Einstein-Debye implies differ by up to 9129×. Both
conventions are registered, `peclet_number_thermal` and
`peclet_number_steric`, and where a real diameter exists they agree to
exactly √3.

## Agreement with theory, and what it does and does not establish

Across 8.3 decades the maximum deviation from the closed form is **4.9 %**,
and the sampling floor at 400 particles is 7.1 %. In scratch the deviation
was shown to fall as `1/√N` over a 64-fold range in `N`, so what is left is
sampling and not a systematic error in the integrator.

**This confirms the integrator, the estimator and the crossover machinery. It
measures no dependence.** `abp_free` declares
`output_independent_of_input: false` for exactly this reason: the MSD of a
non-interacting active particle is a closed form in `v0`, `D_R` and `D_T`, so
the run cannot tell us anything about the dependence that the inputs did not
already fix. A card must not cite it as evidence about the dependence itself.
Interaction or confinement flips that, which is what `abp_wca_2d` is for.

## What is missing, and it is one thing

`synthesis.OPERATING_POINT` holds an entry for `bd_overdamped` and for no
other configuration, so S4 raises `KeyError('abp_free')` and there is no plan
for the operator to run. Everything else is in place: six axis cards at
revision 3, the goal, the declared engine, and a backend that reproduces the
closed form. Adding that entry is the whole distance between this file and a
result card.
