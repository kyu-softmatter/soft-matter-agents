# simulation_agent

Translates a computational goal into a parameter set that is stable, sampled
correctly, and inside budget, and runs it under approval. `plan.md` §4.2 and
§4.5 are the specification.

**Milestone M2.** This directory is a skeleton. M1, the microscope agent, comes
first.

## What this session may write

`simulation_agent/` only. `contracts/` and `plan.md` are read, not written
(§6.2).

## Same pipeline, different axes

The five stages are identical to the microscope side (§4.5). The axes are not:
A1 integration stability, A2 statistics, A3 finite size, A4 sampling, A5
resource budget, and A7 driving protocol. There is no A6 — spatial resolution
is an imaging axis — and the gap in the numbering is deliberate: A7 means the
same thing on both sides, which is what lets the bridge put two a7 cards side
by side (M4).

A7 abstains unless the question drives the system, and abstaining is not the
same as being absent: an equilibrium run still leaves an a7 card saying no
driving was requested. Axes are never pruned from `capabilities/`, because a
pruned constraint leaves nothing behind to say that it was dropped (P1).

There is also **no orchestrator and no devices/ folder**. One engine job has
nothing to coordinate, and symmetry is not a reason to add a layer (§4.6.8).

## Units

Cards are authoritative in physical units (D7). Reduced units exist only inside
the backend: `src/hoomd_backend.py` converts on the way in and on the way out,
so a plan does not become invalid when the engine changes (§5.7 rule 4).

Mass-based time units are not used at all. In the overdamped limit they do not
enter the physics and have no experimental counterpart, and a reference point
with no counterpart produces comparisons that are quietly wrong.

## What this agent does not do

- It does not change the physical model. That is a human decision.
- It does not quietly fit parameters to experimental data. Fitting happens only
  when asked for, labelled as fitting.
- It does not delete a diverged run. Divergence is a result.
- It does not submit an over-budget job on its own.

## Before committing

```bash
python3 contracts/validate.py
```
