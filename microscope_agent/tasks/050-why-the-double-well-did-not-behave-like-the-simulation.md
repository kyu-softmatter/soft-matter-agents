# 050 — why the double well did not behave like the simulation's: find it yourself

Written by `architecture-kyuhwan-macbook-20260928-1` at the person's direction,
in place of the microscope manager, for this one card. You read this; you do
not edit it.

## What this is

The person has set this as **a chance for you to work out, yourself, why the
2026-09-25 double-well measurement did not behave like the simulation's
double well.** The person gave one hint, quoted below, and nothing else.
**Nobody has added to it**: not this seat, and not the microscope manager,
which did not write or see this card. What you conclude is yours. The person
wants to see what you find.

**Assigned to `microscope-kyuhwan-macbook-20260928-1`**, the MacBook microscope
window. Your row is in `contracts/seats.json` from `87ef585`.

## What was asked for

- the simulation's ask:
  `simulation_agent/questions/sim-20260923-101/result_run-20260924-101-v3-hold.json`
  at `735a1a0`. Cite it by id and revision; do not copy it
- the model it stands on: `contracts/capabilities/simulation.json`, config
  `bd_overdamped_gaussian_double_well_2d`

## What happened, in the records

Read these yourself. This card does not summarise them.

- runs `run-20260925-004`, `-008`, `-009`, `-010`, `-012`, `-014`, `-015`,
  and their plans under `questions/mic-20260925-002` to `-006`. `-006` was
  drafted and not run: the person set the last setting by hand
- the goal, and the method declared before any data: `questions/mic-20260925-001/`
- `src/analyze_double_well_20260925.py` and `src/report_20260925.py`
- `findings/microscope-20260924-6-20260925.json`
- the commit messages of `8b18356`, `5353a54`, `0b0df94` and `921537b`. Inside
  the tree, these are where Friday's numbers are stated
- card 049, the section "Added 2026-09-25, after run -008"
- the two `failures.jsonl` lines dated 2026-09-25

Friday's record already offers one explanation: the tweezers software's
micrometres were never checked against the camera, so no commanded separation
is a number. **Treat it as one candidate among yours**, neither favoured nor
dismissed.

## The person's hint

The person said this in Korean, in architecture's window, on 2026-09-28. This
English is architecture's word-for-word rendering:

> "The hint is that the double potential seen in the simulation is a clean
> potential, but in the actual experiment it was implemented with optical
> tweezers; and that because of this, nonlinear phenomena appear."

## What to do

1. List the candidate explanations for what Friday showed, your own and
   Friday's.
2. For each one, give:
   - what it predicts for **each** of Friday's observations
   - which runs and records support it or contradict it
   - the observation that would rule it out: its falsifier
   - every number in four parts, with its grade
3. Rank the candidates, and say what decides the ranking.
4. Draft the one measurement that best separates the candidates still
   standing, as a plan the person can approve. **It is a draft.** It runs only
   on the bench computer, after the person approves it and hands over the
   bench, and never from this Mac.

## Rules for this card

- **Open no device.** This Mac is not the bench.
- **Do not ask the person for the cause.** You may ask for a fact about the
  instrument that neither the records nor the store holds. Log each question
  and its answer.
- **Friday's per-recording numbers** (position, spread and stiffness per
  setting) exist only beside the frames on the microscope computer, under
  `D:\soft-matter-agents-frames\`. The folder was a command-line argument and
  is not in the tree. Work from the committed records, and say so. If you
  need more, ask the person for the analysis files (`*_analysis.json`,
  `*_xy_um.npy`), not the frames. State no number you have not read.
- **Take store facts only through the librarian's tools**, as your
  `CLAUDE.md` says. Record what the store lacks as a gap (`plan.md` 4.3.1).
- **Hold the diagnosis in `microscope_agent/`** until the person says
  otherwise. Deliver nothing to the librarian and give the bridge nothing to
  carry. The person may give the simulation side the same chance, and it
  should not have seen your answer first.
- `envelope/safety.json` is the person's. Nothing rescales tweezers commands
  in code (card 049). The three closed repositories stay closed.
- Commit with `git commit -F <file> -- <paths>`, after `git diff HEAD --
  <paths>`. Commit under your seat: name `seat:microscope-kyuhwan-macbook-20260928-1`,
  email from `contracts/seats.json`. Run the validator and read its tree line.

## What comes back

- **In your tree:**
  - one `failures.jsonl` record for the mismatch. `task` names this card, and
    its kind is the one `plan.md` 8.1 gives it
  - the candidates, shaped so the librarian could later distil them into
    lessons (`plan.md` 8.2: claim, evidence as run ids, `n`,
    `condition_range`, falsifier), in an artifact the validator admits. Say
    which artifact
  - the draft plan
- **To the person, in your window:** what you think happened, how sure you are
  and why, and what you would measure next. Use plain words and no internal
  codes. For every claim, say whether it was measured, computed or reasoned.
- **To architecture, by message:** at most 10 lines. One line per candidate,
  the one ranked first and why, and the next measurement.

**Re-read this card immediately before committing.**
