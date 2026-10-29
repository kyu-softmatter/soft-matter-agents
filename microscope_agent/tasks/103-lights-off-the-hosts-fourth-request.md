# 103 — lights off, the host's fourth request

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** Build and
test on mock only. If you are not that seat, take nothing from this card and
report up.

## Why

plan.md 15.1 item 11 gives the console a [Lights off] button (the person,
`27139a5a`). The button sends exactly `{"lights_off": true}` to the live-view
host, and the host turns the lights off:

- outside a run, in a run of its own kind;
- during a run, as that run's stop.

The request and its reply are pinned in
`contracts/schemas/run_interface.schema.json`, `$defs` `lights_off_request`,
`lights_off_reply` and `light_source_row`, each with `examples` and
`x_refused`. They were agreed with manager-console-office-20261017-1, whose
page shows each source's row as the reply gives it. `idle_status`'s
`last_run.kind` gains `lights_off`. Build to those files. If one of them
does not fit what the code can honestly say, stop and report it to this seat.

## What to build

In `microscope_runtime/src/`:

1. **The host accepts `{"lights_off": true}` and nothing else on that
   key.** Any other value, any extra key, refuses with
   `{"lights_off": "refused", "reason": ...}` and writes nothing to any
   device, as `_handle_run` refuses. Record each refusal as the host records
   the others.
2. **Outside a run: a run of its own kind, `lights_off`.**
   - Take the run lock **without waiting**. A held lock goes to part 3 if the
     host can name and stop the holding run, and otherwise refuses at once,
     naming the holder. Never wait for the lock and never break it.
   - Pass the ownership check, as any run does.
   - **Open only the channels that `LIGHT_SOURCES` routes a
     software-commandable source through.** A channel the ownership check
     refuses, or whose opening is not known to be inert (item 3), is not
     opened.
   - **Write the power-down with the abort's own routine**, `_power_down`,
     and nothing else: no shutter, no other channel, no value but each
     table entry's `off`. Record its rows as an event
     `lights_off_light_sources`, in the same row shape as
     `abort_light_sources`.
   - Write `events.jsonl` and `idle_status` as any run does, with
     `run_ended` and `last_run.kind` `lights_off`. Add `lights_off` to
     `idle_status.KINDS`.
   - **It needs no approval and no bench hand-over**, because it can only
     reduce light. It still goes through the one execution path, the run
     lock and the ownership check.
3. **During a run: that run's stop.**
   - The host sends `stop_request` on the holding run's own stop channel,
     read from that run's `run_started`. The reason is fixed text:
     `the console: the person pressed Lights off`.
   - The run's `abort()` then turns the lights off in the abort's order:
     shutters, then power, then everything else. Nothing here changes the
     abort.
   - The host waits for that run's `run_ended`, up to a limit named as a
     constant in code, and reads the run's `abort_light_sources` rows.
   - If the rows are not there within the limit, reply `stop_sent` with the
     run id. Never claim a source from the stop's acceptance alone.
   - It never takes a device from a run that holds the lock.
4. **The reply is derived from the rows, one per `LIGHT_SOURCES` entry, in
   the table's order**, as `light_source_row` defines:
   - not software-commandable, not opened, refused or raised:
     `not_turned_off`, with the note or error as the reason;
   - written, and read back equal (`matched` true): `off`, with the read-back;
   - written, and read back different (`matched` false): `not_turned_off`,
     with the read-back and the written value in the reason;
   - written, with no read-back for the pair: `sent`, `read_back` null.

   `done` carries `as` (`own_run` or `run_stop`), the run id whose log holds
   the rows, and the rows. Nothing in the reply is read from anywhere but
   those rows.
5. **Nothing else changes.** `LIGHT_SOURCES`, `NAMED_REFUSALS`, the abort and
   every limit stay as they are. A source refused to software stays refused;
   its row says so.

## Tests, each watched failing first

1. The schema's own `examples` and `x_refused` for the three `$defs`, as
   `T7TheInterfaceSchema` does for the others.
2. Each `x_refused` request sent to the host on mock refuses with a reason,
   and no device module receives any write.
3. Outside a run, on mock:
   - the reply is `done`, `as` `own_run`, one row per `LIGHT_SOURCES`
     entry, in order;
   - the Aura is `off` with read-back `0`;
   - every not-software-commandable source is `not_turned_off`, with a
     reason;
   - only the software-commandable sources' channels were opened;
   - the run log holds `lights_off_light_sources`;
   - every reply validates against `lights_off_reply`.
4. A mock whose read-back of the off property disagrees gives
   `not_turned_off` with the read-back. A mock with no read-back for the pair
   gives `sent`.
5. During a mock run the host started, the request makes that run end
   `stopped_from_outside` with the fixed reason. The reply is `done`, `as`
   `run_stop`, with that run's id.
6. During a run whose `run_ended` does not arrive within the limit (a test
   limit), the reply is `stop_sent`.
7. A lock held by a holder the host cannot name refuses at once. The lock is
   untouched and no device is written.
8. The existing suite is unchanged. Name any test you change and say why.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, no `console/`.
- The first lights-off request on the instrument is watched at the bench,
  as for any new command kind (item 6). Nothing in this card reaches
  hardware.
- Whether this unsigned request needs a line in plan.md 2.1 is 2.1's
  holder's question, not this card's.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most: the commit; each test, watched failing, then
passing; the suite's counts; and any existing test you changed, by name.
