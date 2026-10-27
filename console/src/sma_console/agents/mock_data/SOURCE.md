# mock_data: where these files come from

Copied byte for byte, by reading only, from the soft-matter-agents repository on this desktop
(`D:\codes\github\soft-matter-agents`, working tree clean) at

    commit baf6f1e5b7e2012ab6c6d1e1d13d643f7b98d083  (2026-09-29, "plan.md 8: check 87 declared, ...")

on 2026-10-01 for T-008. The folder layout is the same as there, so `SmaFiles` reads this
folder the way it reads the real one. Nothing here is edited; to refresh, copy again from a
newer commit and update this file.

What was taken, and what was left out to keep the sample small:

| Path | Kept | Left out |
|---|---|---|
| `simulation_agent/questions/sim-20260923-001/` | goal, v2_goal, v3_goal; axis a7 in all three versions; refusal_s4 (version 1); v3 plan; v3 synthesis; the question's markdown | axes a1–a5 of every version, v2 plan and synthesis, plan markdown |
| `microscope_agent/questions/mic-20260925-001/` | goal, analysis_method_declared | nothing |
| `microscope_agent/questions/mic-20260925-002/` | plan (a question with a plan and no goal) | nothing |
| `microscope_runtime/runs/run-20260924-003/` | commands.json, log.json (a run that stopped at its gate) | nothing |
| `simulation_agent/runs/run-20260924-001-smoke-g2k2/` | config, log, observables, trajectory_meta (a run of sim-20260923-001) | the trajectory, which was not in the repository |
| `microscope_agent/inbox/thr-tracer-diffusivity-001/` | r1 and r2 ask_experiment, markdown | the JSON copies of both asks (50 KB) |
| `bridge/threads/thr-tracer-diffusivity-001/` | status.json | round hashes, the asks |

Because axes and the v2 plan were left out, version 2 of sim-20260923-001 here has a goal and
one axis and no plan. That is an artifact of the copy, not of the question.

The cards carry their grades and `numbers` as written. They are sample data for the console;
none of their numbers is to be used for anything on the bench.

The run row was `microscope_agent/runs/run-20260924-003/` until 2026-10-26: the runtime's runs moved
to `microscope_runtime/runs/` (soft-matter-agents card 080), and the sample follows, with the one
folder and never both.

## Refreshed 2026-10-26 for console card 014 (the Experiments screens)

Copied byte for byte from the soft-matter-agents repository on this desktop at commit
`244274faa207407e08c63caec8663bb2f3131f6f`; each path's content was last changed at the commit
named, and the copies were checked equal to `git show` of that path at the first commit.

| Path | Last changed at | What |
|---|---|---|
| `microscope_runtime/runs/run-20261013-001/` | `a36e49d000ac37f9b81be011042969bc0864a6e0` | deviations.json, events.jsonl, log.json: a run the runtime refused (plan `plan-mic-20261008-001-r1`, no plan card here) |
| `microscope_runtime/runs/run-20261013-004/` | `a36e49d000ac37f9b81be011042969bc0864a6e0` | the same three files: a second refused run (plan `plan-mic-20261008-004-r1`, no plan card here) |
| `microscope_runtime/approvals/appr-mic-20260925-002-r1.json` | `1b90be9e5c970064c65f6976e75fc1cf9f1af1f1` | an approval whose plan hash is not the sample plan's |
| `microscope_runtime/approvals/appr-mic-20260925-002-r2.json` | `1b90be9e5c970064c65f6976e75fc1cf9f1af1f1` | the approval whose plan hash is the sample plan of `mic-20260925-002` |

`microscope_runtime/.claude/settings.json` is written here, not copied: the folder is named like the
runtime's, so the validator's guard check reads it as an execution folder and asks for the same six
denials. No session is rooted in this folder.

The sample grew past the earlier 200 KB because the two refused runs carry their event logs; the
size test now allows 400 KB. Everything in this folder is example data: what a screen shows from it is
labelled as such, and nothing reads it as a real run, plan or approval.

## Synthetic additions (not copied)

Two result cards were written here in dino-autofocus, not copied, so the Results screen has
something to draw. They say `"origin": "dino-autofocus mock (synthetic)"` and `"status": "MOCK"`,
and their numbers are made up (a model curve plus noise):

| Path | What |
|---|---|
| `simulation_agent/questions/sim-20260923-001/v3_result_psi6_relaxation.json` | psi6 relaxation and an MSD, each with a `<y>_theory` column |
| `microscope_agent/questions/mic-20260925-001/result_well_occupancy.json` | well occupancy over time and a dwell survival, each with a `<y>_theory` column |

Two question requests were written here in dino-autofocus, not copied (console card 010), so the
Questions screen has earlier questions to show and to offer. They follow
`contracts/schemas/question_request.schema.json`; the second is the repository's own example
(`contracts/examples/question_request.json`). They are practice data: nothing reads them.

| Path | What |
|---|---|
| `console/requests/questions/qr-20261023-091500-w3k8.json` | a question addressed to the microscope, by a practice login |
| `console/requests/questions/qr-20261024-174512-k3p9.json` | the contract's example request |

## The librarian's pages and answers (console card 016)

Four wiki pages were copied byte for byte from `librarian_agent/kb/wiki/` of the soft-matter-agents
repository on this desktop, at commit `c260712a91de16b2f99a352e2a399b18cfe7d622` (2026-10-26); each path's
content was last changed at the commit named, and the copies were checked equal to `git show` of that path.

| Path | Last changed at |
|---|---|
| `librarian_agent/kb/wiki/index.md` | `3d167ea1eb2fe52b8bc54ff6a87e7f69fb4e1176` |
| `librarian_agent/kb/wiki/device_dia_lamp.md` | `ba6c2439bdfd0196e629ad750177c9540fe3da92` |
| `librarian_agent/kb/wiki/device_csuw1_dichroic.md` | `ba6c2439bdfd0196e629ad750177c9540fe3da92` |
| `librarian_agent/kb/wiki/quantity_na.md` | `ba6c2439bdfd0196e629ad750177c9540fe3da92` |

Only these four pages are here, so the front page links to pages this sample does not hold; a link to one of
them shows "page not found". That is an artifact of the copy.

Written here, not copied:

| Path | What |
|---|---|
| `librarian_agent/kb/index.json` | only `kb_version`, the version the four pages' footers carry; the real file is 185 KB and the console reads nothing else from it |
| `librarian_agent/answers/ca-20261020-1000NN-exNN.json` (nine) | **example answers**, written to the shape of `contracts/schemas/store_answer.schema.json`, one for each of the seven outcomes of a request (entered, waiting for a name, refuted, in conflict, superseded, kept, no entry of that name), and one `answered` and one `not_in_the_store` answer to a question. The numbers in them are made up. No answer of the real librarian is copied |

The librarian's real answers folder is never read by the console, from the mock store or the real one.
