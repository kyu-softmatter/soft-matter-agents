# sim-20260923-201 — drag calibration of a harmonic trap in uniform flow

*S2 output, for people. The record is `goal.json` beside this file (P3). Written
by seat simulation-8 (window 2) on 2026-09-23 from the person's question,
verbatim in `goal.json` `constraint_notes[0]`.*

## Where this stops, and why

**S3.0 screening returns empty, so this question stops at S2.** Not a refusal:
§11-1's ordering. The observable is unregistered and no declared configuration
produces it, and both files are `contracts/`, which this session reads and
never writes (§6.2). Register, then plan.

## The relationship, which is analytic and is not a result

Overdamped, one sphere, trap centre at the origin, fluid velocity **v** uniform:

    gamma * (rdot - v) = -k_t * r + noise

so the steady-state mean offset is

    dr_ss = gamma * v / k_t ,   gamma = 3 * pi * eta * d

Linear in speed, slope `gamma/k_t`, and the calibration inverts that slope.
This is a `computed:` relation and carries no grade. It is the prediction a run
would test, not a substitute for running one.

## Can the known stiffness be recovered? Three answers, and only one is a result

**1. The central value comes back because it went in.** The estimator inverts
the equation the integrator solved. `k_t` and `gamma` are both inputs, so `k_t`
returns up to statistical error and integration bias. The configuration must
declare `output_independent_of_input: false`, the same way `bd_overdamped` does
for the diffusivity. A run like this confirms the integrator and the estimator
and carries **no independent information about any real trap**. Reading
"recovered to one per cent" as evidence about an optical tweezer is reading a
tautology.

**2. The precision is a result, and the stiffness cancels out of it.** Treat the
trapped coordinate as Ornstein-Uhlenbeck with relaxation time `tau_t = gamma/k_t`
and stationary variance `sigma^2 = k_B*T/k_t`. Over a record `T >> tau_t` the
standard error of the mean is `sigma * sqrt(2*tau_t/T)`. Divide by the signal
`gamma*v/k_t` and the stiffness cancels exactly:

    SE(dr) / dr  =  sqrt(2*D/T) / v ,   D = k_B*T/gamma

The fractional precision of a single-speed drag measurement is the ratio of a
diffusive speed scale `sqrt(2*D/T)` to the imposed speed. Signal and
noise-on-the-mean both go as `1/k_t`, so they cancel.

**So the direct answer to "how does this relationship change over a range of
stiffnesses" is: for recoverability, it does not change at all.** That is the
non-obvious part of the question, it is falsifiable, and confirming or breaking
it is the one genuinely informative thing the sweep produces.

**3. What the model cannot see.** A declared harmonic trap has no escape and no
anharmonicity. A real trap is quadratic only near the centre and loses the bead
once `gamma*v` exceeds the maximum restoring force. Both set the practical upper
end of a real calibration, and this model has neither by construction, so it
will report the method working at speeds where the bench would have lost the
particle. That is A7's, and it belongs in the a7 card rather than in a caveat.

## The asymmetry that decides how useful this is

**Viscosity enters the two sides differently.** In the simulation the same
`gamma` imposes the drag and inverts it, so the recovery is insensitive to how
well `eta` is known. On the bench `eta` is an independent input and its error
lands directly in `k_t`.

`kb:water_viscosity_293k` is **E3** and says *of order one millipascal second*,
with roughly two per cent per kelvin. `kb:sample_temperature_not_actuated` and
`kb:no_thermometer_at_the_sample` say the sample temperature is neither
controlled nor read. **So the experimental error budget is floored by `eta(T)`,
and the simulation is blind to that floor.** A simulated calibration that
returns `k_t` to a per cent says nothing about whether the bench can.

## What changes with stiffness: the axes, and the cost

`tau_t = gamma/k_t` becomes the shortest characteristic time in the problem.

- **A1** — `dt` far below `tau_t`. The **stiffest** trap sets it.
- **A4** — the save interval must resolve `tau_t`. Stiffest again.
- **A2 and the operator** — `T >> tau_t`, and the steady-state criterion must
  wait several `tau_t` after the flow starts. The **softest** trap sets both,
  and the criterion is declared in the plan in advance, never chosen after
  seeing the data.
- **A3** — one particle has no periodic image to meet, but uniform flow in a
  periodic box is a boundary-condition question, and the offset must stay well
  inside the box.
- **A5** — total steps go as `T/dt`, so they scale with the **ratio** of the
  stiffness range: a decade of stiffness costs about a decade of steps. This is
  the A1-against-A2 collision S4 exists to surface and is this question's cost
  driver.
- **A7** — live for the first time on this side. `bd_overdamped` abstains
  because it drives nothing; this configuration drives.

## Why this is worth asking on the bench and not only on the engine

The store says there is no instrumented route to `k_t` on this instrument:

- `kb:trap_laser_power_has_no_software_path` — the trapping power is neither
  readable nor settable, and a level used in a run leaves no record.
- `kb:tweez300_reports_nothing_back` — no readback of any kind, and a return
  code of 0 means the GUI accepted a command, nothing more.
- `kb:objective_change_invalidates_trap_calibration` — changing the objective
  silently voids both trap calibrations.

So a drag calibration is close to the only route to `k_t`, and its independent
variable, the stage speed, is the one quantity in the chain that is commanded
rather than guessed. `kb:trapped_bead_is_the_one_that_does_not_translate`
already identifies a trapped bead by exactly the relative stage motion this
question imposes. Getting the protocol's error model right is worth doing, and
that error model is what part 2 above delivers.

## Requests, and who they go to

### 1. To `manager-simulation` — register the observable

Proposed id **`trapped_particle_drag_offset`**: the steady-state mean
displacement of a trapped particle from the trap centre under uniform relative
flow, per axis, along the flow. `window_required: true` with
`window_parameter: record_length`, because the mean converges as `sqrt(1/T)` and
an offset written without its record length is not one number.
`producible_by: [experiment, simulation]`. Units `um`, `nm`.

**It is not `trapped_position_distribution`, and the mismatch is exact rather
than close.** That estimator *takes the mean position as the trap centre and
subtracts it*, then reports the standard deviation. The mean it subtracts is
this question's entire signal. The two are complements read off one trace, so
**both entries want a cross-reference**, or a later reader reaches for the
registered name and computes the one quantity that cannot answer this.

Check 60 also requires every observable to be a declared quantity in
`contracts/quantities.json`.

### 2. To `manager-simulation` — declare the configuration

Proposed **`bd_overdamped_trapped_uniform_flow`**: one sphere, overdamped, no
pair interaction, an external harmonic potential of stiffness `k_t`, and a
uniform background fluid velocity. `devices: [hoomd_backend]`. **Driven**, so
A7 no longer abstains. `output_independent_of_input: false`, with the reason in
part 1 above — and that field is the whole reason this cannot be settled once
for all configurations.

### 3. To the person — five things S2 cannot decide

- **The purpose.** Proposed `verify`, default intent `confirm`. This matters
  more than usual: `characterize` defaults to `explore`, where anything within
  10x is a tie (P15), and a calibration that recovers `k_t` to within a factor
  of ten has answered nothing.
- **The stiffness range**, in decades. It sets the cost directly.
- **The speed range**, in decades. The natural sweep variable is dimensionless:
  `dr/sigma = gamma*v/sqrt(k_B*T*k_t)`, the per-frame signal-to-noise.
- **The target accuracy on the recovered stiffness.**
- **Whether a maximum trap force belongs in the declared model.** If yes, the
  potential is no longer purely harmonic and it is a different configuration,
  not a parameter.

## The librarian

**The service did not answer.** A `kb_query` under `sim-20260923-201:v1:s2` was
refused by the session harness before reaching the server, so there is no log
line and none should be looked for. The reading is the degraded path: the
envelope snapshot on disk at `kbv-30966d978fbe`, and `degraded` carries
`librarian_agent` accordingly.

The envelope is one publication behind `kbv-4b981dc870d3`. The two entries that
differ, `objective_40x_collar_setting` and `mm_label_zdrive_is_the_focus_axis`,
are both microscope rows this question does not cite — counted against the
published export, not assumed.

`trapped_particle_drag_offset`, `trap_stiffness` and `flow_velocity` are all
**absent** at that version. See `kb_gaps`.

## One thing fixed on the way

`fanout.issue()` composed only `<qid>:v<N>:<config>:<axis>`, while the server
names **four** forms it calls issued and refuses everything else. S2 asks the
store whether a name exists *before* screening can pick a configuration, so the
axis form cannot be built yet and a seat needing an id at that moment had
nowhere to get one. The server cannot catch a hand-composed id — it says so
itself, that the check is at the launcher and not there. `issue_s2()` now
composes that form, so the id above was issued rather than chosen (§4.3.1
rule 3).
