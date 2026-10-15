# mock_data: where these files come from

Copied byte for byte, by reading only, from the soft-matter-agents repository on this desktop
(`D:\codes\github\soft-matter-agents`, working tree clean) at

    commit baf6f1e5b7e2012ab6c6d1e1d13d643f7b98d083  (2026-09-29, "plan.md 8: check 87 declared, ...")

on 2026-10-01 for T-008. The folder layout is the same as there, so `SmaFiles` reads this
folder the way it reads the real one. Nothing here is edited; to refresh, copy again from a
newer commit and update this file.

What was taken, and what was left out to stay under 200 KB:

| Path | Kept | Left out |
|---|---|---|
| `simulation_agent/questions/sim-20260923-001/` | goal, v2_goal, v3_goal; axis a7 in all three versions; refusal_s4 (version 1); v3 plan; v3 synthesis; the question's markdown | axes a1–a5 of every version, v2 plan and synthesis, plan markdown |
| `microscope_agent/questions/mic-20260925-001/` | goal, analysis_method_declared | nothing |
| `microscope_agent/questions/mic-20260925-002/` | plan (a question with a plan and no goal) | nothing |
| `microscope_agent/runs/run-20260924-003/` | commands.json, log.json (a run that stopped at its gate) | nothing |
| `simulation_agent/runs/run-20260924-001-smoke-g2k2/` | config, log, observables, trajectory_meta (a run of sim-20260923-001) | the trajectory, which was not in the repository |
| `microscope_agent/inbox/thr-tracer-diffusivity-001/` | r1 and r2 ask_experiment, markdown | the JSON copies of both asks (50 KB) |
| `bridge/threads/thr-tracer-diffusivity-001/` | status.json | round hashes, the asks |

Because axes and the v2 plan were left out, version 2 of sim-20260923-001 here has a goal and
one axis and no plan. That is an artifact of the copy, not of the question.

The cards carry their grades and `numbers` as written. They are sample data for the console;
none of their numbers is to be used for anything on the bench.

## Synthetic additions (not copied)

Two result cards were written here in dino-autofocus, not copied, so the Results screen has
something to draw. They say `"origin": "dino-autofocus mock (synthetic)"` and `"status": "MOCK"`,
and their numbers are made up (a model curve plus noise):

| Path | What |
|---|---|
| `simulation_agent/questions/sim-20260923-001/v3_result_psi6_relaxation.json` | psi6 relaxation and an MSD, each with a `<y>_theory` column |
| `microscope_agent/questions/mic-20260925-001/result_well_occupancy.json` | well occupancy over time and a dwell survival, each with a `<y>_theory` column |
