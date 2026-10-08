# 062 — live view from the console, switched on and off, with no plan

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`.** If you are not that seat, take
nothing from this card and report up.

## The person's decision

On 2026-10-07, directly to architecture, recorded at `f96bbb9` in plan.md
11-25: **the person switches a live camera view on and off from the console,
outside a plan too, because it helps find the sample.** Live view moves
nothing. But it starts an acquisition and may light the sample, so it is not a
free-standing console action. **It is a preparatory run** under 11-21's four
conditions, which check 85 holds. The console never commands a device: it
asks, and the orchestrator runs what the person approved.

## The approved list — the person's, in `approvals/`

A live-view command list is a file **the person writes and approves**. It is
cited by path and sha256, like every preparatory run's `approved_commands`.
The default list may contain only:

- **the transmitted lamp**: `DiaLamp` `State` 1 and `Intensity` at **a value
  the person writes in the list**. Never a default in code;
- **one camera sequence**: exposure as the person writes it, and **a frame
  ceiling, a whole number, also the person's**. That ceiling is the most a
  live view can run. Reaching it ends the run as completed. **This is the
  backstop that stops a forgotten live view lighting the sample for ever**,
  because a run keeps going when its viewer drops (11-25 (d)).

**Not in the default list:** fluorescence excitation, which bleaches. A list
that adds the Aura, or any light but the transmitted lamp, is **a separate
list and a separate approval**. **Nothing in the motion set, ever**: check 85
refuses a preparatory run that dispatches to it, and this card does not ask
for an exception.

## What to build

1. **A live-view run is an ordinary preparatory run.** It goes through
   `operator.run` with `plan_id` null, `no_plan_because` saying it is live
   view, and `approved_commands` naming the list by path and sha256. Its log
   goes to `runs/` like any run's, under check 85 and check 15. **Frames are
   not written to disk.** They feed card 058's tap and nothing else. No
   result card is made and no store entry.
2. **"Off" is the existing stop channel** of that run, announced in its
   `run_started` as for every run. A stop runs the same `abort()`: lamp off,
   shutters closed, the sequence stopped within a frame (`8b4b78c`). There is
   no second way to stop it.
3. **"Live on" is one new request, received by a live-view host the person
   starts**, never by the stop channel. The stop channel accepts a stop and
   nothing else, and that stays true. The host:
   - is started by the person on this side, and is not always on. While it is
     not running, nothing listens;
   - listens on `127.0.0.1` only, on a port the OS chooses;
   - accepts exactly one message, one line of JSON:
     `{"live_on": "<sha256>"}`. Anything else is refused and recorded;
   - **runs only a list the person holds approved**: a file in `approvals/`
     whose sha256 is the one named, which is a live-view list as above. A
     sha256 it does not find there is refused. The console cannot send a list,
     a path, or a value. It can only name a list the person already approved;
   - starts the run, and replies with that run's id (the shapes are below). The console then follows
     it, views it and stops it exactly as card 061 proved.
4. **One run at a time, across processes.** A live view and a plan run would
   be two Micro-Manager cores, which never happens (11-25 item 3). So there is
   **a lock that only one run can hold**, however many processes there are.
   "Live on" is refused while any run holds it, and a plan run refuses to start
   while a live view does. Find whether such a lock exists. If none does, build
   it, and say which mechanism and why. The host itself holds no core when no
   live view is running.

## The live-view host's interface — settled 2026-10-07

The console session proposed it, and this card adopts it. The console builds
to exactly this, and **a change goes to "AF 화면 · SMA 실행 보기와 멈춤 연결"
first**.

**A standing listener is new here, and it is bounded.** Every socket so far
lived only inside a run. This one exists while no run does, so:

- **who starts it, and when:** the person, on this side, by starting the
  host. It is never started by the console, by a run, or at login. It stops
  when the person stops it. While it is not running, nothing listens;
- **what it accepts:** only `live_on` naming an approved list's sha256, and
  nothing else, ever. It is not a second stop channel and not a command
  channel: it cannot stop, set, read or move anything;
- **where it binds:** `127.0.0.1` only, on a port the OS chooses.

**Address discovery:** `%LOCALAPPDATA%\soft-matter-agents\live_host.json`.

- It is **outside this tree** and is never committed. It **holds no secret**:
  exactly `{"host": "127.0.0.1", "port": <int>, "pid": <int>, "started_at":
  "<ISO-8601 time>"}`, and nothing else.
- The host writes it **atomically** on start, writing to a temporary name and
  then renaming, so the console never reads half a file. It deletes the file
  on stop. A file left behind by a
  host that died points at a port nobody answers on, and the console treats
  a refused connection as *no host*.

**The request**, one line of JSON, then the connection closes after the
reply:

```
{"live_on": "<sha256 of the approved list file's raw bytes>"}
```

**The replies**, one line each:

```
{"live_on": "started", "run_id": "<run id>"}
{"live_on": "refused", "reason": "<text>"}
```

A refusal starts nothing and is recorded on this side as well. The `reason`
is for the person to read, and the console does not branch on its wording.
After `started`, the console finds the run and its stop channel the usual
way, from that run's `run_started`.

## Tests, mock first, each watched failing before the code exists

1. `{"live_on": <sha>}` for an approved list starts a preparatory run that
   check 85 passes: plan null, the reason, and the list by path and sha256.
2. A sha256 not in `approvals/`, a list that adds fluorescence without its own
   approval, and a message with any other key are each refused, recorded,
   and start nothing.
3. A stop through the run's stop channel turns the lamp off, closes the
   shutters, and ends the sequence within one frame.
4. Reaching the frame ceiling ends the run as completed, with the lamp off.
5. "Live on" is refused while another run holds the lock, and a plan run is
   refused while a live view holds it.
6. No frame is written to disk; the tap serves them.
7. The host binds `127.0.0.1` only. Nothing listens before the person starts
   it or after it stops.

## The instrument

**One live-view run on the instrument is part of Thursday's visit (card 060)
only if the person wants it.** Ask the person; do not add it on your own.
Until then, mock only.

## Boundaries

Write in `microscope_agent/src/` and `microscope_agent/tests/`. **Never write
`approvals/` or `envelope/`**: the live-view list is the person's. For your
tests, use a fixture list in `tests/`. No change to `SOFTWARE_MAY_COMMAND` or
`NAMED_REFUSALS`. Nothing in the motion set.

Run the validator to `0 failed` under the interpreter `CLAUDE.md` names, and
read its `tree:` line. Then `git diff HEAD -- <paths>`, then
`git commit -F <file> -- <paths>` under your seat, naming each new file.
Confirm with `git log -1`, and push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What the person writes

- **The live-view list**, in `approvals/`, in the shape
  `contracts/schemas/live_view_list.schema.json` gives it: the transmitted lamp's intensity,
  the exposure, and the frame ceiling (the longest a live view may run). The
  seat can draft the list's shape for the person to fill in; the values are
  the person's.

**A draft, for the person** (2026-10-07). The person asked in
manager-microscope's window for everything that can be decided away from the
microscope to be decided now. The values below are taken from the person's
own record, not chosen:
- Intensity 2100 is what the person set for the 2026-09-25 trap run
  (`src/run_trap_plan_20260925.py`, `lamp_at_handover`; also run
  `-20260924-008`);
- 100 ms is the exposure of the 2026-09-24 brightfield runs;
- 6000 frames is about ten minutes at that exposure.

**It is not an approval until the person saves it into `approvals/`**, under
any name, with `written_by` changed to the person's name. No session may
write `approvals/`, and the console reads lists only from there.

```json
{
  "artifact": "live_view_list",
  "schema_version": "0.1",
  "written_by": "<the person's name>",
  "written_at": "<the day it is saved>",
  "label": "Finding the sample in transmitted light: the transmitted lamp at the person's earlier setting, one Kinetix_red sequence, at most about ten minutes.",
  "transmitted_lamp": {
    "device": "DiaLamp",
    "intensity": {
      "value": 2100,
      "note": "As set for the 2026-09-25 trap run."
    }
  },
  "camera": {
    "device": "Kinetix_red",
    "exposure_ms": 100,
    "frame_ceiling": 6000
  }
}
```

## What comes back

To this seat, 8 lines at most: the commit; the seven tests' failing and then
passing output; the lock mechanism; that the host, the address file and
both replies match the shapes above; and the validator's `verdict:` and `tree:` lines.
