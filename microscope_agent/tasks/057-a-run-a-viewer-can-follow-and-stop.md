# 057 — a run a viewer can follow, and a stop that reaches it

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`.** If you are not that seat, take
nothing from this card and report up. This is plan.md 11-25 (a) and (b).
`dino-autofocus`'s console reads what this card produces and writes nothing
into this tree (11-25 item 1).

## What exists, read at 3ba8733

- `Orchestrator.record()` appends each event to an in-memory list. Nothing is
  written until the run ends.
- `operator.write_run()` creates `runs/<run_id>/` **at the end**, writes
  `log.json` and `deviations.json`, and **refuses if the folder already
  exists** (P9: a second write makes a new run). So today nothing outside the
  process can see a run while it is going.
- `operator.run` aborts only on its own monitors. Nothing outside the process
  can stop a run.

## Part A — an events stream beside `log.json`

**The orchestrator writes `runs/<run_id>/events.jsonl` as the run happens**:
one JSON object per line, appended and flushed as each event is recorded.

- **Exactly the events `record()` makes, in the same order**, each written
  when it is recorded. Not a summary, and not a second vocabulary.
  `log.json` stays the record. At the end, every event in `log.json` appears
  in `events.jsonl` in the same order, and a test asserts it.
- **The first line is a `run_started` event** carrying the run id, the plan
  id and revision, `t0_wall`, and the stop channel's address (part B).
- **The last line is a `run_ended` event** carrying how the run ended:
  completed, aborted by a monitor, stopped from outside, or failed. A file
  whose last line is not `run_ended` belongs to a run that is still going or
  that died. The viewer says which it cannot tell; it does not guess.
- **Append-only, never rewritten, never truncated.** Open in append mode,
  write a line, flush. Nothing seeks back.
- **The folder now exists from the start**, so `write_run()`'s guard moves
  from *the folder exists* to **`log.json` exists**. The rule is unchanged: a
  second write still refuses, and a run id is never reused. Say in the code
  why the guard moved.
- **Write nothing else in this card.** Frames do not go in this file, and no
  file is read back from it.

Check 15 already allows a run folder whose log comes last. Run it against a
folder holding only `events.jsonl`, and report what it says. If it refuses
that state, report it up: the validator is a manager's to change, not yours.

## Part B — a stop channel the orchestrator owns

**A loopback socket, opened by the orchestrator's process for the length of
one run, that accepts a stop and nothing else.** On a stop, it calls the same
`Orchestrator.abort()` every other path calls. There is no second abort, and
no lighter variant of it.

- **Bound to `127.0.0.1` only**, on a port the OS chooses. Never `0.0.0.0`,
  never another interface. A test asserts the bound address.
- **Its address is announced only in `run_started`.** It is never written to
  a file in the tree or anywhere else. And the channel **never accepts a
  file**, a path, or anything that names one (11-25 (b)).
- **One message form only:** a single line of JSON,
  `{"stop": "<run_id>", "reason": "<text>"}`. It is refused, with the
  connection closed and nothing stopped, if:
  - the run id is not this run's, which stops a late request from hitting the
    next run;
  - there is any other key;
  - the message is over a small length cap;
  - it is not one line of JSON.

  Every refusal is recorded as an event. **There is no other command**: no
  status query, no pause, no resume, nothing that sets a value. A stop can
  only stop (2.1).
- **On a valid stop:** record `stop_requested` with the reason, call
  `abort(reason="stop from outside the process: <reason>")`, and reply with
  one line saying the abort began, then close. The run ends as stopped from
  outside, and `run_ended` says so. The request has to wake the run's loop, not
  wait for its next natural check. Show the time from request to `abort_begin`
  in the test.
- **The socket closes when the run ends**, however it ends. Nothing listens
  when no run is going.
- **Safety stays with deterministic code.** The stop channel adds a way to
  ask for the abort; it removes nothing. Monitors, interlocks and timeouts all
  stand as they are.

## Tests, mock first, each watched failing before the code exists

1. `events.jsonl` exists while the run is going: a reader mid-run sees
   `run_started` and the events so far.
2. At the end, `log.json`'s events equal `events.jsonl`'s, between its first
   and last line, in order.
3. `run_ended` is the last line on completion, on a monitor abort, and on an
   outside stop, each naming how the run ended.
4. `write_run()` refuses when `log.json` exists, and does not refuse because
   `events.jsonl` made the folder.
5. The stop socket is bound to `127.0.0.1` and closed after the run.
6. A valid stop mid-run gives `stop_requested`, then `abort_begin` with the
   reason, then `abort_end`, and no command after the stop.
7. A wrong run id, an extra key, an oversized message and non-JSON are each
   refused, recorded, and change nothing; the run continues.
8. Nothing listens before the run starts or after it ends.

## Boundaries

Write in `microscope_agent/src/` and `microscope_agent/tests/` only. Never
write `envelope/` or `approvals/`. No change to `SOFTWARE_MAY_COMMAND` or
`NAMED_REFUSALS`. **Open no device**: mock only.

Run the validator to `0 failed` under the interpreter `CLAUDE.md` names for
this computer, and read its `tree:` line. Then `git diff HEAD -- <paths>`,
then `git commit -F <file> -- <paths>` under your seat, naming each new file.
Confirm with `git log -1`, and push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## Question only the person can answer

- **Once a stop from outside exists: if the console watching a run closes or
  loses its connection, should the run stop by itself, or keep going until it
  finishes or someone stops it?** Build nothing for this until the person
  answers. Until then the run keeps going, and the card records that as the
  decision in force.

## What comes back

To this seat, 8 lines at most: the commit, the eight tests' failing and then
passing output, what check 15 said about a folder holding only
`events.jsonl`, and the validator's `verdict:` and `tree:` lines.
