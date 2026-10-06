# 061 — the console against the real orchestrator, on mock

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`.** If you are not that seat, take
nothing from this card and report up.

## Why

`dino-autofocus`'s console (main `e49dc04`) now follows `events.jsonl`, sends
Abort through the stop channel, and views the frame tap. **It has been tested
only against a stand-in for `_StopChannel` and `_FrameTap`.** Its session was
right not to run this repository's orchestrator itself: the console runs no
code of ours (plan.md 11-25). So **this side runs the real thing, and the
console only connects to its loopback sockets.**

## What to run

**Mock backend only. No device but `devices/mock.py` is loaded, and nothing
touches the instrument.**

- **A plan whose run stays open long enough to connect**, built from a mock
  `sequence` of N frames. Mock waits `FRAME_DELAY_S` per frame, so the run
  lasts about N × `FRAME_DELAY_S`. **Choose N from that product**, an integer
  count and not a timed loop, for **at least 10 minutes**, so the console
  is never racing the clock. The sequence also feeds the frame tap, so there
  is a frame to pull.
- Run it through `operator.run` exactly as any plan runs, so `run_started`
  announces `stop_channel` and `frame_tap` as usual. **Do not special-case
  anything for the console.**
- **Write the run to a scratch runs root outside this tree**:
  `operator.run(..., runs_root=<scratch>)`, never `microscope_agent/runs/`.
  An end-to-end test is not a measurement record, so its folder is not
  committed. What is kept is your findings record, below.
- If the gate asks for an approval, the person gives it in your window. **Do
  not write one.**
- If a hold step exists and is simpler, it is acceptable, but then there is
  no frame for the tap. Prefer the sequence.

## The sequence

1. Start the run. Read the first line of `events.jsonl` and copy it **exactly
   as written** into your record.
2. Message the session **"AF 화면 · SMA 실행 보기와 멈춤 연결"** with the run
   id and the folder path. Nothing else; the console reads the rest from
   `run_started`.
3. The console then connects:
   - it follows `events.jsonl`;
   - it pulls one frame from the tap;
   - it sends **one** Abort.
4. Wait for the run to end. Do not stop it yourself unless the console has
   not sent its Abort before the sequence finishes. In that case let it
   complete, and record that the abort was never exercised.

## What you record

In `findings/`, one record. It names the scratch folder's path and **the
sha256 of its `events.jsonl`**, so the record points at bytes and not at a
folder that will be cleaned up:

- **the abort ran from outside**: `stop_requested`, then `abort_begin` with
  the reason that names the outside stop, then `abort_end`, and **no command
  after the stop**. `stopped_from_outside` is set;
- **the `run_ended` line**, exactly as written. Its `how` must be
  `stopped_from_outside`;
- **the light-source and shutter rows**, as mock wrote them. **On mock they
  are not confirmations.** Mock's `apply` returns no read-back, so the light
  rows should say none was reported and `matched` stay `null`. Record what
  they say, and if any row says `true`, report that as a defect: mock cannot
  have confirmed it;
- **the stop reply this side sent**, from the stop channel's own record, beside
  **the console's classification of it** (`begun`, `refused`, or
  `no_answer`). The console session reports that classification. Say it is
  the console's report, because a message is not a record;
- **the frame**: the `ImageNumber` the console reports it pulled, against the
  frames the run's sink received. It must be one of them;
- **`log.json` against `events.jsonl`**: the same events in the same order,
  between `run_started` and `run_ended`, as card 057 requires.

Check 15 cannot see a scratch folder, so this run does not test its
in-flight reading. That waits for the first real run in the tree.

**Stop and report up** if any of these happens:

- any socket is bound to anything but `127.0.0.1`;
- the console's connection changes anything but by the one Abort;
- the reply shape differs from what the console pins (`{"abort": "begun"}`;
  close without reply = refused; 15 s silence = no answer);
- `run_started`'s keys differ from what the console pins.

The console's tests pin both shapes. A change to either goes to that session
first; do not change it here.

## Boundaries

Write in `microscope_agent/findings/`, and `microscope_agent/src/` or `tests/` **only if
a defect needs a fix**, which you then report. Never write `envelope/` or
`approvals/`. No change to `SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS`. **Mock
only.**

Run the validator to `0 failed` under the interpreter `CLAUDE.md` names, and
read its `tree:` line. Then `git diff HEAD -- <paths>`, then
`git commit -F <file> -- <paths>` under your seat, naming each new file.
Confirm with `git log -1`, and push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat, 8 lines at most: the run id, the scratch path and the
`events.jsonl` sha256, and the commit; the `run_ended` line; the stop reply and the console's classification;
the frame's `ImageNumber`; the light and shutter rows on mock; and any stop.
