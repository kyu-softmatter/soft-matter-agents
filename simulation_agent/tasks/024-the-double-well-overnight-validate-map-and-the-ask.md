# 024 — the double well overnight: validate the engine, map where hops happen, write the ask

**For:** `simulation-20260924-1`, the one simulation execution seat alive this
evening. Nobody else takes this card.

Written by `manager-simulation-20260924-1`. You read this; you do not edit it
(§6.2-2). Report to me by session message at each checkpoint below, and commit
at each one -- a night's work that exists only in a working copy is work
anyone can revert.

## The clock and the machine

**The person gave the night: about 13 hours, until 09:00 on 2026-09-25**, when
the person starts the experiment. Everything the experiment needs from us must
be committed by **08:00**, so the bridge has an hour. **If the data are
enough earlier, stop** -- the person said so, and idle is better than burning
the microscope computer for numbers nobody reads. The stages below are in
priority order; a later stage is dropped before an earlier one is shortened.

**This is the microscope computer.** Use **at most 24 of its 40 cores**, and
set `OMP_NUM_THREADS=1` per process. No hardware, no `microscope_agent/`, and
nothing outside `simulation_agent/`. The engine runs in WSL (root
`CLAUDE.md`: `wsl.exe -d Ubuntu-24.04 --cd /mnt/d/soft-matter-agents --
/home/takalab/.pixi/bin/pixi run -e sim --frozen python <script>`); never run
git inside WSL. The `.pixi/envs` link each run leaves is harmless now.

## What is decided, and what is already measured

**The model** is declared at `4ab86d9`:
`bd_overdamped_gaussian_double_well_2d` in `contracts/capabilities/simulation.json`.
Read its entry whole. Two Gaussian wells that add, each exactly the person's
`0.5*k_i*dr^2` at its centre (`k_i = eps_i/w_i^2`) and zero far away. The
person confirmed this shape in my window tonight. **Two dimensions**, not the
prototype's one, and the entry says why with numbers.

**Measured by this seat tonight, in scratch, not run records** -- they are the
reference you validate against, not results you cite:

| 2-D point: eps 6 and 5 kT, w1 = w2, d = 3 w, milestone radius 0.5 w | occupancy of well 1 | rate per w^2/D |
|---|---|---|
| numpy Euler-Maruyama, 4000 walkers x 400, dt 2e-3, **no burn-in** | 0.6025 | 0.0447 |
| HOOMD 7.2 CPU, `md.force.Custom`, 2000 walkers x 400, burn-in 20 | 0.5990 | 0.0418 |
| exact Boltzmann basin weight (split at the saddle) | 0.6428 | -- |
| same potential in **one** dimension, numpy | 0.6902 | 0.0741 |

The scripts are in my scratch directory and are not yours to import; the
engine form they prove is written into the configuration's `executed_by`:
walkers packed in widely spaced cells so one HOOMD run is an ensemble of
independent single-particle records, the wells as an `md.force.Custom`, and
**positions read back sorted by tag** -- the CPU snapshot is not in tag
order, and a 1000-bead run read widths 200x too large before that was fixed.

**What the microscope side expects** (`microscope_agent/tasks/047`, read it):
a **5 µm bead** (`tracer_diameter_measured`, E2 in the store), water, room
temperature. Its seat's estimate -- **an estimate, not measured** -- is that
with a trap width near the bead radius **each well is hundreds of kT deep at
any holding stiffness**, so **hops need the barrier set by separation and
overlap, not by a 1:100 stiffness ratio.** The store holds no trap stiffness
at all; the experiment calibrates each one after the traps are set. And the
time unit is slow: `D = kT/(6 pi eta a)` is about 0.09 µm²/s for this bead, so
`w^2/D` is about 12 s at w = 1 µm and about 70 s at 2.5 µm.

## Stage 1 — the backend, validated (target: done by ~23:00)

Write `double_well_hoomd_backend` and whatever configuration module and
operator dispatch the other configurations have (`config_bd_overdamped_trapped.py`
and the `bd_overdamped_trapped` branch in `operator.py` are the pattern; the
dispatch must **refuse**, not fall back, when the module is missing). Then:

1. **Reproduce the table above** at its point, and **settle the 7% rate gap**
   between the two engine rows. My guess is the numpy row's missing burn-in
   (it started at 50/50 against a 64/36 equilibrium), and a guess is all it is.
   Run numpy with the same burn-in, and run both at dt and dt/2.
2. **Occupancy against the exact Boltzmann weight**: milestoning occupancy is
   not the basin weight (0.60 against 0.64 above), so state which the
   estimator reports and show the gap closes as the milestone radius and the
   saddle split converge, or say why it should not.
3. **Timestep**: at the stiff end of Stage 3's range (eps of hundreds of kT)
   the in-well relaxation time is `1/eps` in reduced units. Show the
   observables do not move between dt and dt/2 there, and use that dt.

**Done when** HOOMD and the numpy reference agree within their measured
standard errors (replicates, not one over root-N), the timestep is shown
converged at both ends of the range, and the configuration's `executed_by`
sentence has a run record to replace it with -- tell me the run id and I
replace it; the table is mine.

## Stage 2 — sim-20260923-101 onto the configuration (target: ~00:30)

Bring the double-well question onto `bd_overdamped_gaussian_double_well_2d`
as a new revision, dropping the draft `min(U1, U2)`. Through the pipeline as
usual, librarian on, `kb_refs` and `kb_gaps` filled. The observables are the
four registered ones: `well_occupancy`, `well_residence_time`,
`interwell_transition_rate`, `interwell_barrier_height`. **All parameters in
SI** on the card; reduced units stay inside the engine.

## Stage 3 — where hops happen, in SI (the night's main work)

The question the ask has to answer: **at which trap settings does one 5 µm
bead hop often enough to measure, in a record the bench can take?** Map it,
in SI, over:

- **trap width** `w` in {1, 1.5, 2.5} µm -- unknown, and the experiment
  measures it; the map shows how much the answer depends on it
- **holding stiffness** `k1` over at least two decades around 1 pN/µm
  (1e-6 N/m) -- which with those widths gives eps of tens to hundreds of kT
- **stiffness ratio** `k2/k1` in {1, 0.5, 0.2, 0.1}, and 0.01 if it holds a well at all
- **separation** `d`, scanned **finely** around where the two wells merge,
  so the barrier from the deeper well runs from about 1 to 10 kT

**Compute what needs no simulation first, and simulate only what does.** The
barrier, the saddle position and the Boltzmann occupancy come from the
potential in closed form over the whole grid, in seconds. From that alone,
report **how steeply the barrier moves with separation, in kT per 10 nm** --
if it is several kT per 10 nm, the trap positioning precision decides
feasibility before anything else does, and that is the most important number
the person can have tomorrow. Then simulate the rate and residence times only
where the barrier is 1-10 kT, and report them as **hops per hour** as well as
per second.

Budget it: time a smoke point first, write down the two-term cost (task 023)
and schedule the grid to fit the night on 24 cores, coarse everywhere before
fine anywhere. **Commit the closed-form map as soon as it exists** -- it is
useful on its own if everything after it stalls.

## Stage 4 — what ONE record can show (after Stage 3 picks points)

The experiment gives one bead and one record, so the comparison needs the
spread a single record shows, not only the mean. At two or three operating
points Stage 3 marks as feasible, run **about 1000 walkers each with the
experiment's record length and sampling interval**, and report the
distribution of each of the four estimators over records. Neither is known
yet: take record lengths of 10, 30 and 60 min and sampling intervals of
1, 10 and 50 ms, state them as assumptions, and show which the answer is
sensitive to -- that sensitivity is what the ask requests.

Both sides must apply **the same estimator to the trajectory projected on the
line joining the traps**, with the same milestone definition (plan.md 11-23
condition 1). Write the estimator so the experiment's projected trajectory
can go through it unchanged.

## Stage 5 — the ask (target: committed by 07:30)

The person decided this round goes **simulation to experiment**: we write the
ask and the bridge delivers it. From Stages 3-4:

- **target trap parameters as ranges or decades, in SI**, never reduced
  units: each stiffness, each width, the separation window with its
  tolerance, the temperature, and the record length and sampling interval
- **a stiffness is measured after the traps are set, not dialled in**, so the
  ask asks the experiment to **return the calibrated actual values**, trap by
  trap, and says the simulation **re-predicts at those values** before the
  bridge compares. `manager-bridge-20260924-1` is confirming the round can
  carry target and as-measured values; if it cannot by 07:00, say so in the
  ask rather than waiting
- the in-situ drag: the microscope side proposes measuring the diffusivity
  from the same record that calibrates stiffness (wall effect near the
  coverslip). Ask for it; the re-prediction takes it instead of Stokes drag
- **if Stage 3 finds no feasible window** -- barrier too steep in separation
  for the positioning the tweezers have, or hops too rare for any record --
  **the ask says that plainly and proposes what would make it feasible**.
  That is a result, and a far more useful one tonight than an ask for an
  experiment that returns zero hops

The ask's schema is `contracts/schemas/ask.schema.json`. If something the
ask needs has no field, **tell me** rather than inventing one.

## Done when

The backend is validated and committed; `sim-20260923-101` is on the declared
configuration; the map is committed with the separation sensitivity stated
first; the ask is committed and the bridge seat told -- or the night ran out
and each stage says where it stopped and why. **Stop early if the data are
enough.** Send me a one-paragraph summary at each checkpoint and at the end,
with every number's provenance in words: measured by a run, computed from the
potential, or assumed.
