# 076 — the run-time watcher, in shadow mode

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to the seat holding `src/` and `tests/` under card 064**, which
is `microscope-20261007-1` today. **Start after card 069 lands.** Both cards
touch the orchestrator and the operator, and one seat writes code at a time.
If the person seats a different session for this card, card 064 changes
first. If you are not the seat holding `src/`, take nothing from this card
and report up.

## Why

On 2026-10-17 the person settled the run-time watcher in architecture-office-20261017-1's window, and plan.md 13.4 records it in the person's words:

- it watches a run while the run happens;
- which model answers is decided later;
- it only records, so nothing acts on what it says;
- its input is every hardware state value and the preprocessed image values.

So this card builds everything around a model and nothing that needs one:
the inputs, the question, the record, and a run that says whether it was
watched. Read plan.md 13.4 in full before starting. It is the
specification, and this card only divides it into work.

## What is already in `contracts/` (`4619faa2`, `manager-microscope-20261003-1`)

- **`plan.schema.json` has a `watcher` block.** It holds:
  - `options`, in order, each `{id}` or `{id, about}`. `as_planned` and
    `unsure` are always present, and every other option names the rendered
    value it is about;
  - `cadence_s`;
  - `question_budget_s`;
  - `image`, with the arguments for:
    - `frame_stats`: `metric`, `bin_px`, and `camera_ceiling` as a store
      number or a gap;
    - `intensity`: `settle_after_s`;
    - `drift`: `reference_frame`, `method`, `arguments`;
    - `particles`: `detector`, `arguments`.

  Nothing in it has a default. It has no backend field, because the
  backend is a run argument.
- **`run_log.schema.json` has the five events**, each with its payload
  under `watcher`:
  - `watcher_started`: the backend as `{name, version, kind}`, where kind
    is `none`, `test_double` or `model`; the renderer version; the options;
    the cadence; the budget.
  - `watcher_off`: why, either `plan_declares_no_watcher` or
    `did_not_start` with a detail.
  - `watcher_state`: `seq`, the frame index and its `t_mono`, the
    snapshot's `t_mono`, the image values with their method, arguments and
    frame, `state_sha256`, `state_path`, the renderer version, `asked`,
    `skipped_so_far`.
  - `watcher_flag`: `seq`, `state_seq`, `state_sha256`, asked and answered
    `t_mono`, the options in order, `signals` (`probabilities`, `choice`,
    `confidence`), the backend, the renderer version.
  - `watcher_unanswered`: `seq`, `state_seq`, `state_sha256`, asked
    `t_mono`, and why: `time_budget`, `backend_failed` or `run_ended`.

  Every watcher event except `watcher_off` carries `from: "watcher"`. **No
  watcher event may carry `channel`, `action`, `params` or `verification`.**
  An absent image value is `null` with `absent_because`, and never zero. A
  `snapshot` event labelled `watcher` carries `states`.
- The rejected fixtures `bad_plan_watcher_*` and `bad_run_log_watcher_*`
  show what the schemas refuse.
- **The schemas cannot see two rules.** A flag must name a state that
  exists, with the same options as the plan. And a watched run must record
  `watcher_started` or `watcher_off` right after `run_started`. Write both
  so they hold. Manager-microscope adds a commit-time check once your first
  mock run log exists to test it against.

## What to build

All of it goes in flat files in `microscope_agent/src/`, and none of them
imports `devices/`. The one exception is part E.

**A. The renderer**, one pure function with a version string, standard
library and numpy only. It turns a frame, the latest watcher snapshot and
the recent log into text. The same inputs give the same bytes.

- **Image side**:
  - every statistic `focus_classical.frame_stats` returns, called with the
    plan's `metric`, `bin_px` and ceiling. If the ceiling is a gap, the
    saturated fraction is absent, and the absence names the gap;
  - whole-frame intensity normalised to the settled level. The level is the
    whole-frame total from `settle_after_s` after the last light-source
    command whose read-back matched. Before that, the value is absent and
    labelled settling. Never read intensity through a mask fixed at frame 0,
    and never normalise to frame 0;
  - drift, as the whole-frame shift against `reference_frame`, by the
    plan's method and arguments;
  - the particle count, from a deterministic detector run with the plan's
    arguments.
- **Hardware side**:
  - every channel's state from the latest watcher snapshot, with its age;
  - the recent commands and monitor results from the log;
  - a channel whose interface this run did not open is rendered as not open
    in this run;
  - a channel with `read_back: false` is rendered as unreadable, with its
    last commanded value labelled commanded.
- Every value carries its unit and the frame or event it came from. A value
  with no input is rendered as absent, never as zero.
- **Refuse a plan whose option names an `about` the renderer does not
  render.** Then the run records `watcher_off`, `did_not_start`, and the
  name, and the run itself goes on.
- Frames never leave the renderer.

**B. The watcher thread.**

- It is fed by the same tee as the frame tap from card 058: the run's sink
  first, then a copy swapped in under a lock, with nothing queued.
- It holds no device module, no core, no reference to `abort()`, no stop
  channel and no dispatch.
- One question is in flight at a time. A tick that falls due while one is
  in flight still writes its `watcher_state`, with `asked: false`, and is
  counted in `skipped_so_far`.
- Write each state's text whole into the run folder as
  `watcher_state_<seq, 6 digits>.txt`. That is a flat file, because the
  run-folder path allows no subfolder. `state_sha256` is the sha256 of
  those exact bytes.
- `end_run` closes the watcher before `run_ended`, the way it closes the
  tap. A question still open at that point becomes `watcher_unanswered`,
  `run_ended`.

**C. The orchestrator's sampling.**

- At `cadence_s`, take the same `read()` on every channel that `snapshot()`
  takes, through the run's own core.
- Record each one as a `snapshot` event labelled `watcher`.
- Use `read()` only, and only on interfaces this run already opened after
  the ownership check passed. Never open, re-open or probe an interface.
- Never wait. A channel whose read cannot start at once is recorded inside
  `states` as not read at that tick, with why. It is never given its last
  value.
- Stop taking reads the moment an abort begins.
- Right after `run_started`, record `watcher_started` or `watcher_off`. A
  plan that asked for a watcher which did not start still runs.

**D. The backends**, behind one interface: state text and the options go
in; per-option probabilities, a name and a version come out. The backend
runs out of process and receives text only.

- `none`: records every state and asks nobody.
- A deterministic test double, `kind: "test_double"` in every event it
  produces. It is refused on every backend but mock, so no instrument run
  ever carries its answer.
- The backend is chosen by `--backend` on the run's command line, never by
  the plan.

**E. In `devices/`**, a read that refuses rather than waits when its
device's lock is held. This is the only change to `devices/`, and it is
what part C's "never wait" stands on.

## Tests, each watched failing first

1. The watcher object holds no device module, no core, no `abort`, no stop
   channel and no dispatch.
2. With the watcher on, the only device calls a mock run gains are
   `read()`s: no set, no snap, no sequence. Card 058's tap test is the
   pattern.
3. No code path runs from an answer to the stop channel or to a prompt for
   the person.
4. On mock, measure how long one in-progress read delays an abort, and
   record the number. The bench measures the same bound on the instrument
   before the reads run there.
5. The state text replays byte for byte from the records.
6. These cases are recorded, not silent:
   - no watcher in the plan;
   - a watcher that did not start;
   - a budget timeout;
   - a backend failure;
   - a question still open at run end;
   - a skipped tick.
7. The test double is refused on any backend but mock.
8. An unreadable channel is rendered as unreadable with a commanded value,
   and an absent value is never zero.

## Out of this card

- Any real model and its dependency. The person chooses, and a local one
  enters `pyproject.toml` and `pixi.lock` through architecture.
- Any threshold, and any action on an answer.
- The replay and review tool that lines answers up against the person's
  account of a run. That is a later card.
- Showing flags in the console. That is optional and later.

## Boundaries

- Write `microscope_agent/src/`, `microscope_agent/tests/` and one flat
  test plan per case under a `questions/` folder you create. Nothing else.
- No change to `contracts/`. If a schema field is wrong or missing, report
  it up with the file and the field.
- Never `envelope/`, `approvals/` or `inbox/`. No change to
  `SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS`.
- Nothing runs on the instrument under this card. Mock only.
- Through the gate, naming each path. Never `--no-verify`, `--amend` or
  force.

## What comes back

To this seat, 6 lines at most:

- the commits;
- the renderer's version and the names of the values it renders;
- each test, watched failing, then passing;
- the abort delay measured on mock, with how it was measured;
- one mock run's id, with its `watcher_*` event counts;
- every place the schema did not fit, with the file and the field.
