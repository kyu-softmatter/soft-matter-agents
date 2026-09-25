# 006 — double-well readiness, from the comparer's seat

**For bridge-20260924-1. Paper only.** Open no round, compare nothing while
`comparable` is false, convert no unit. `thr-tracer-diffusivity-001` stays
open and is unrelated. Source: architecture's instruction of 2026-09-24,
recorded as `plan.md` 11-23 (`bbc8fb7`).

The experiment is on 2026-09-25: one particle, two optical traps, an
asymmetric double well, tested against `simulation_agent/src/proto_double_well.py`.
**Goal:** the bridge can carry the first round the moment either side sends a
card, and no gap that blocks the comparison turns up at the bench.

## 1. Readiness review, per observable

Written by `manager-bridge-20260924-1` from `contracts/observables.json`, both
capability tables and the prototype at HEAD `96e496c`. **Re-derive it rather
than trusting it**; your job is to confirm or correct each row and to report
the gaps below to the simulation and microscope managers. Do not fix them.

The four conditions of 11-23: (1) the same registered estimator on the 1-D
trajectory along the line joining the traps; (2) parameters in SI on both
sides, stiffness calibrated trap by trap; (3) record length and sampling
interval stated; (4) each number graded by its own side — `simulated:` from a
declared configuration, `measured:` from a planned run.

| observable | (1) estimator | (2) SI parameters | (3) window | (4) grades |
|---|---|---|---|---|
| well_occupancy | partial — G3 | no — G4, G5 | partial — G6 | no — G1, G2 |
| well_residence_time | partial — G3 | no — G4, G5 | partial — G6 | no — G1, G2 |
| interwell_transition_rate | partial — G3, G8 | no — G4, G5 | partial — G6 | no — G1, G2 |
| interwell_barrier_height | partial — G3, G7 | no — G4, G5 | partial — G6, G7 | no — G1, G2 |

All four are `comparable: false` and `producible_by: [experiment, simulation]`
in the vocabulary. Nothing in the table is "yes" today, which is expected on
the eve and is what this card exists to shorten.

### The gaps

**Simulation manager**

- **G1 — no declared configuration.** `contracts/capabilities/simulation.json`
  declares no double-well configuration; the nearest is `bd_overdamped_trapped`
  (one harmonic trap, produces only `trapped_position_distribution`). So a
  prototype run grades as nothing a card may carry, and answerability for any
  of the four against the simulation reads **`undeclared`** — the round would
  be held at the first gate. **Since `4ab86d9` the simulation side is closed**:
  `bd_overdamped_gaussian_double_well_2d` is declared and produces
  `well_occupancy`. Re-read which of the four it lists. G2 on the microscope
  side is still open, and answerability is checked against the **receiving**
  side, which for r1 is the microscope, so r1 still holds without it.
- **G4 — reduced units.** The prototype works in length `w1`, energy `kT` and
  time `w1^2/D`. `to_physical(temperature, viscosity, diameter, w1)` returns the
  scales, but nothing yet emits a card in SI, and the bridge will not convert.
  Its parameters are `eps_i`, `w_i` and `d`; the experiment will measure `k_i`,
  so the simulation's card has to state its input as `k_i` and `w_i` in SI,
  derive `eps_i = k_i w_i^2` in the open (`computed:`), and say where each
  input came from.
- **G3 (simulation half).** The prototype's milestone is reaching `x1` or `x2`
  exactly, which a discrete step reads as crossing it. That is a choice, and
  the experiment cannot copy it (below).
- **Open, 11-23:** the model is 1-D and what dropping the transverse axes costs
  has not been measured.

**Microscope manager**

- **G2 — none of the four declared.** `contracts/capabilities/microscope.json`
  declares `trapped_position_distribution` under trapping and none of the four
  double-well observables on any configuration. Answerability against the
  experiment reads **`undeclared`**. Under the growth rule that is an ordering,
  not a refusal: declare them, then plan with them. **Closed at `0a4fae4`**
  (`manager-microscope-20260924-1`): all four are declared on `transmitted`,
  `widefield_inline`, `widefield_side` and `confocal`, each requiring
  composition with `trapping`. Recomputed with the validator's own
  `derive_producible` against that commit: `yes` for all four, on those four
  configurations. Recompute it again against r1's own tree when r1 is
  written.
- **G5 — no per-trap calibration path.** 11-23 asks for each trap's stiffness,
  each trap's width, and the separation, in SI, trap by trap. Nothing in the
  capability table says how the width `w_i` of a trap's Gaussian is measured,
  nor how the separation is read in micrometres rather than set in drive
  units. The stiffness at the bottom (equipartition, or a power spectrum) is
  a known method; the width beyond the bottom is where the barrier comes
  from and is the number most at risk.
- **G6 (experiment half).** A camera frame averages over its exposure;
  `bd_overdamped_trapped` already notes this narrows the width. The sampling
  interval **and the exposure** have to be on the card, and the simulation has
  to either match the exposure or model the averaging.

**Both, and the vocabulary (managers jointly)**

- **G3 — the milestone is not defined for data.** `well_occupancy`'s estimator
  says a particle belongs to the well "whose minimum it most recently
  reached", but not how a minimum is located in a noisy trajectory, nor what
  counts as reaching it: an exact crossing in simulation, a tolerance band in a
  camera track. Condition (1) needs **one** definition — minimum location
  method, reach tolerance, barrier region — registered and used on both sides.
  Until it is, the two sides run estimators with the same name.
  **Owner: `manager-bridge-20260924-1`** (agreed with
  `manager-microscope-20260924-1`, 2026-09-24). Drafted **after the bench**,
  from what the real track looks like, together with `manager-simulation`,
  and sent to both sides before it lands. Not tonight: both sides are writing
  against the current text, and this blocks comparability, not the round.
  G9 is `manager-microscope-20260924-1`'s on the same terms. Both are on
  card 000.
  **The same post-bench work covers residence time** (2026-09-25). The
  simulation's ask computes `well_residence_time` as the mean completed
  dwell, while the registered estimator is the renewal form. This seat found
  it (card 007), and so did `microscope-20260924-6` independently. The
  microscope reports the renewal value as the observable and the mean
  completed dwell only as a secondary figure. Before residence can turn
  comparable, the simulation has to report the renewal form too. Nothing
  changed on 2026-09-25.
- **G6 — sampling interval has no field.** Every entry's `window_parameter` is
  `record_length` only. 11-23 condition (3) also asks for the sampling
  interval, and at a stiffness ratio of 100 the stiff well's dwell is what the
  interval must resolve.
- **G7 — barrier height carries two more numbers.** The estimator says bin
  width and record length travel with the value; there is no named field for
  the bin width. And above roughly 10 kT the inversion gives only a lower bound.
- **G8 — a rate with no transitions is a bound.** The note says so. Check
  whether a card's `numbers[]` can carry an upper bound as such; if not, a
  zero-transition record has no honest shape, and on an asymmetric well that
  is the likely outcome.

## 2. Direction of the first round — DECIDED: simulation to experiment

The person decided it on 2026-09-24, relayed by architecture; the bridge's
earlier proposal (experiment first) is withdrawn. The simulation writes the
ask, and the bridge delivers it into `microscope_agent/inbox/`, where the
microscope seat takes it as its goal (`from_round`).

Because a trap's stiffness is measured after the traps are set and cannot be
dialled to a value, the round has to run as **target, then as-measured,
then re-prediction**:

1. **r1, simulation to experiment**: target trap parameters as ranges or
   decades. **The payload may be a plan or a result** (asked by
   `manager-simulation-20260924-1`, 2026-09-24). A plan opens with
   `trigger: plan_completion`. A result opens with **`trigger: human`**, and
   check 8 refuses a result that arrives under `plan_completion`. The
   simulation chose a result: the result of `sim-20260923-101`'s sweep, which
   carries the conditions each point ran at and the predicted observables.
2. **r2, experiment to simulation** (`human`, the only way a result crosses):
   each trap's calibrated values, plus the four observables if measured.
3. **r3, simulation to experiment**: a prediction at the calibrated values,
   its inputs citing the experiment's result card (`measured:<run_id>`) and
   not restated as assumptions. Only then is there a value to compare.
   **With a result as r1's payload, r3 cannot sit in the same thread on the
   same observable** — see the re-prediction row below.

### Can the round carry "target versus as-measured"? — partly; one gap

- **As-measured: yes.** A result card's numbers carry the calibrated values
  with `measured:`/`calibration:` sources, and r3 can cite them.
- **Re-prediction: only in the shape check 8 accepts.** Its duplicate key is
  (direction, observable) within a thread. `supersedes` passes only when the
  two rounds carry **the same card_id at a later revision**. A plan re-issued
  at the calibrated values is a later revision of the same plan, so it
  supersedes cleanly. A result from a new run is a **different card**, and
  gated on the same observable in the same direction it is refused either
  way: as a repeat without `supersedes`, or as "a different card is a
  different question" with it. So if r1 carries a result gated on
  `well_occupancy`, r3 has three options: (a) open a new thread, pointing at
  this one in words; (b) gate on a different observable; (c) carry the plan
  revision rather than its result. (a) is the honest one — r3 asks a
  question at new conditions and is not a repeat. It is not needed until
  after the bench.
- **Target as a range: NO structured slot. This is the gap, G9.** A plan's
  `conditions` point only at scalar `numbers[]`. The goal the microscope
  writes has `constraint_notes`, which is free text. The only structured
  approximation is a scalar marked `precision: order_of_magnitude` ("about
  1 pN/um, to a decade"). That says how precise the target is. It does not
  say the value is a target the experiment may land anywhere inside, as
  opposed to a prediction. `common.schema.json` has an `interval` shape
  (`parameter`, `unit`, `min`, `max`, `basis`), but only axis cards use it,
  and neither plan nor goal can hold one. Raise it to the four managers,
  because the schemas involved are shared. Two possible answers: an interval
  list on the plan for requested conditions, or a stated convention that r1's
  trap numbers are `order_of_magnitude` scalars read as targets. Until one
  of them lands, r1 carries its targets as prose plus decade scalars, and
  a check can hold the experiment to neither.

## 3. Can the envelope carry a full parameter set?

**Yes, as far as the shape goes.** `ask.schema.json` carries `payload_card`
verbatim and forbids numbers of its own, so the parameters live in the
payload card's `numbers[]`, each a `{name, value, unit, source, grade}`
number from `common.schema.json`. Two stiffnesses, two widths, a separation,
temperature and viscosity are seven named numbers, e.g. `trap_1_stiffness`
(pN/um), `trap_2_stiffness`, `trap_1_width` (um or nm), `trap_2_width`,
`trap_separation` (um), `temperature` (K), `viscosity` (Pa*s). Every one of
those units is registered.

Two more points to raise, both to the managers and neither blocking tonight (see also G9 above):

- **Which trap is which is carried by the name only.** `at` must resolve to a
  registry id or `ambient`, and two traps from one 1064 nm laser are one
  device. So `trap_1`/`trap_2` are a naming convention, and both sides must use
  the **same** one — including which trap is the stiff one and which way `x`
  points. Settle it in the plan card, in words.
- **One envelope names one observable.** `answerability` and
  `value_comparison` each take a single `observable`. Four observables from one
  source card is either four rounds or one round gated on one of them. Check
  how §4.4 rule 5's duplicate key treats four rounds on the same source
  revision before one side sends a card, not after.

## Report

One line to the person when the review is confirmed, naming the gaps in plain
words. Gaps go to `manager-simulation` and `manager-microscope` as messages
between sessions; this card does not route them itself.
