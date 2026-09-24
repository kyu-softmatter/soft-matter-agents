# 023 — a smoke run that is small, and a cost model that counts frames

**For:** window 2 (`simulation-8`). It is idle, and its drag-calibration runs
have exercised the operator's arm and sweep-point paths more than any other
seat's. Window 3 (`simulation-20260923-3`) found the defect and is fixing the
half that lives in the backend: frames streamed to disk instead of held in a
list. Coordinate with it on the file both of you touch.

Written by `manager-simulation-20260923-1`. You read this; you do not edit it
(§6.2-2).

## What happened (2026-09-23, `398255c`)

`sim-20260923-003` revision 4 was estimated at **40 s** and was still
integrating at **58 minutes, 2.3 GB resident**. The wall-clock ceiling in the
operator is real and would stop it at two hours; nothing before the run could
have. Two defects combined, and neither is the run's:

1. **The cost model has one term.** `_arm_view` computes
   `wall = particle_steps / particle_step_rate`. The run saved 400,000 frames,
   and every one was a round trip out of the engine plus an append to an
   in-memory list. That cost scales with frames, not with particle steps, and
   the model cannot see it at any rate.
2. **The smoke run is not small.** `budget='smoke'` selects the
   `smoke_budget` ceilings and changes nothing else. So a smoke run measures
   the same job against a tighter limit. It cannot yield a small measurement to
   calibrate from, and here it would simply have been refused (0.6 GB against
   500 MB). A refusal is not a calibration. `simulation_agent/CLAUDE.md`
   claimed otherwise for days and has been corrected.

## What to build

**A two-term cost model.** Wall clock per arm is
`particle_steps / particle_step_rate + frames_saved × frame_cost`, where
`frame_cost` is the wall-clock seconds spent per saved frame outside
integration: readout from the engine, conversion, the write. It grows with the
number of particles, so say how it is normalised. Ask the manager to register
the quantity name in `contracts/quantities.json` before using it — do not
invent a local one; the last rename took a revision to reach every window.

**A smoke run that is actually smaller, declared in advance.** The plan
carries the smoke's size as a number before anything runs — for example a
record-length fraction — and the operator derives the smoke's commands from
it, with provenance, like every other command (check 14). Shortening the
record keeps the save interval, so particle steps and saved frames shrink
**together** and the ratio between the two terms survives. That is the point:
a smoke run calibrates only if it holds the dominant term in proportion. The
operator never chooses the size itself — that would be the operator widening
or narrowing what the plan fixed. If the plan schema needs a field for this,
ask the manager, who owns it.

**Timing that separates the terms.** The run log records the integration time
and the frame time separately, with the step and frame counts beside them, so
one smoke run gives both rates. A later plan cites them as
`measured:<run_id>`, which is what turns `particle_step_rate` from a guess into
a measurement.

**Peak memory, reported and not limited.** This run spent a third resource,
and no ceiling covers it. Record peak resident memory in the run log. Whether
memory gets a ceiling is the person's decision; the log is what lets them make
it.

A smoke run is calibration. Its output never becomes a result card for the
question.

## Done when

- a smoke run of `sim-20260923-003` revision 4's arm, at a fraction the plan
  declared, records integration and frame time separately, with counts;
- the two-term estimate built from those two rates predicts the full run's
  wall clock within the same decade as window 3's measured run, once that run
  has finished or been stopped — compare against its log, do not re-run it;
- a plan with no smoke size declared is refused by the operator under
  `budget='smoke'`, naming the missing number — watch it refuse;
- `python3 contracts/validate.py` ends `0 failed`.

Report the two measured rates with their run id, and the predicted and actual
wall clock side by side.
