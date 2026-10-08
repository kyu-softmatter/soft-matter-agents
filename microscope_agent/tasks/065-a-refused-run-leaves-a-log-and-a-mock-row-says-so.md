# 065 — a refused run leaves a log, and a mock row says it is mock

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`**, which holds `src/` and `tests/` under
card 064. If you are not that seat, take nothing from this card and report up.
Both items came out of card 063, and architecture passed them on.

## 1. A run refused inside `operator.run` leaves a log

**Today:** a refusal raised inside `operator.run`, after `begin_run` has
opened the stream, writes `run_ended` and no `log.json`. Check 15 reads that
folder as *ended, log not written yet, or lost*, and it stays PENDING for
ever. A refusal is a normal outcome, and it is worth a record.

**The contract side is already in place**, at the commit that lands this
card:

- `run_log.schema.json` has an optional `ended` field (`completed`,
  `aborted_by_monitor`, `stopped_from_outside`, `failed`, `refused`) and a
  `refusal` string, which is required when `ended` is `refused`.
- Check 15 passes a log with `ended: refused` and no dispatch event, and asks
  it for no approval, because refusing does nothing. It **fails** a log that
  says `refused` while carrying a dispatch.

**Build:**

- When a `Refusal` is raised inside the run, end the stream with `run_ended`
  `how: "refused"`. Then write `log.json` with `ended: "refused"`, `refusal`
  set to the refusal's text, and the events recorded so far.
- Then raise the refusal to the caller as now. **Nothing about the refusal
  itself changes.** It still refuses before any command, and still sends
  nothing.
- Write `ended` on every log from now on, with the same word as `run_ended`.

**Tests, each watched failing first:**

- a mock run refused at the gate, for instance with no focus limit, leaves
  `log.json` with `ended: refused` and the reason, and check 15 passes it;
- the stream's last line is `run_ended` `how: refused`;
- no dispatch event is in that log.

## 2. A row from mock says it is mock

Cards 054, 061 and 063 disagreed on whether a mock read-back may say `true`.
**The rule, from now on:**

- **every row the abort writes**, for light sources and for shutters, carries
  `"backend": "<the module that answered>"`, read from what the backend
  returned, never assumed;
- **on mock, `matched` and `closed` may be `true`**, because mock reports what
  it was told. The row says `backend: "mock"`, so no reader takes it as an
  instrument read-back;
- **a reader, a person or a check, takes `true` as a confirmation only when
  `backend` is not `mock`.**

This replaces the sentence in cards 061 and 063, "a row reading `true` that
mock could not have confirmed is a defect". What would be a defect now is a
`true` row with no `backend`.

**Tests:** on mock, every light-source and shutter row carries
`backend: "mock"`. On the fake MMCore core, the rows carry the
micromanager module's name.

## Boundaries

`microscope_agent/src/` and `microscope_agent/tests/` only. No change to
`SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS`. Mock and the fake core only.

The hooks are installed, and a commit runs the validator over the tree it
would create. Commit under your seat with `git diff HEAD -- <paths>`, then
`git commit -F <file> -- <paths>`. Push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat, 5 lines at most: the commit, both tests' failing and then
passing output, and check 15 on the refused run.
