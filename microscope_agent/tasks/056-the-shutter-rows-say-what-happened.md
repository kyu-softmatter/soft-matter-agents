# 056 — the abort's shutter rows say what happened

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`**, the seat that landed card 054. If you
are not that seat, take nothing from this card and report up.

## The defect, read at abe6cc1 and not run

`Orchestrator.abort()` sends each recognised shutter
`apply({"element": e, "state": "closed"})` and then writes `closed: True` because
the call returned. Two shutters are recognised today: `csuw1_shutter` on
`confocal_csuw1` and `laser_shutter` on `laser_combiner`. On the real backends:

- **`csuw1_shutter`** routes to `devices/micromanager.py`. `_settings()` reads
  only `params["settings"]`, so the call writes nothing and returns empty
  `applied` / `verified` lists, **and the row says `closed: True`.** The
  device behind it, `CSUW1-Shutter`, is in `NAMED_REFUSALS`, so a correctly
  shaped call would be refused too.
- **`laser_shutter`** routes to `devices/lunf.py`, whose `apply` refuses any key
  but `enable`. So the call raises and the row says `closed: False` with the
  error. That row is honest, but the laser lines were never blanked, though
  `lunf.apply({"enable": []})` closes every line and no permission stands in
  its way.
- **The turret shutters** (`Turret1Shutter`, `Turret2Shutter`, which plan 4.6.8
  interlock 1 names first) are not elements in the registry at all, so
  `stand_ti2e` gets an `identified: False` row. That is honest, and nothing
  closes them. Both devices are in `NAMED_REFUSALS`.

So after an abort, the record a person reads can say the spinning-disk
shutter closed when nothing was sent to it. That claim is false, and it is a
safety claim.

## Part 1 — build now. No change to what software may command

Do not touch `SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS` in this part. Neither
part ever touches them.

1. **A shutter row's `closed` comes from the backend's own read-back**, the
   way card 054's light-source rows judge `matched`: from `verified` /
   `disagreed` for the pair, never from the call returning. Each row carries
   `commanded`, `read_back` and `closed`, which is `true`, `false` or `null`,
   plus `error` or `note`. Use the shape that already sits beside it in
   `_power_down()`.
2. **Send each shutter the command its backend actually takes, from a declared
   table**, as card 054 declared the light sources. Do not reuse
   `{"element", "state"}` for every backend.
   - `laser_shutter`: `{"enable": []}` through `lunf`. That closes every line
     and is already permitted. `lunf` reads nothing back, so the row says
     `commanded` and `closed: null`, with a note saying the close was sent and
     not confirmed. If `lunf` refuses it, for example over missing wiring,
     record the refusal.
   - `csuw1_shutter`: refused by name, so the row says **not commanded** and
     why, `closed: null`, and that a person closes it. Do not send the call
     just to get a refusal.
   - Any shutter whose backend returns no read-back for the pair: `closed:
     null` and *unverified*. **Never `true`.**
3. **Leave the recognition as it is** (`shutters()` and its denominator row).
   Replacing it with a declaration is check 80's backlog and a separate card.
   This card fixes what a row claims, not which rows exist.
4. **A failure stops nothing.** A shutter that raises or refuses is recorded,
   and the abort goes on to the light sources and the fan-out, as now.

**The test**, on mock and on a fake MMCore core in the pattern of
`test_dialamp_allowlist.py`:

- through the micromanager path, today's code records `csuw1_shutter` as
  `closed: True` with nothing written. **Watch that assertion fail on today's
  code first** (that is, assert the row is not `true`) and keep the failing
  output;
- after the fix, that row is `closed: null` and not commanded;
- the laser row carries `commanded` and `closed: null` through a fake `lunf`
  transport, and a fake that raises gives an `error` with the abort still
  reaching every channel;
- no shutter row anywhere is `true` unless its pair is in `verified`.

## Part 2 — APPROVED by the person on 2026-10-04. Build it after part 1 lands

**The person's decision is recorded at `10561c8`, in plan.md 4.6.8
interlock 1.** It was asked directly in architecture's window, and the person
chose all three shutters. Read it there, not here. This card carries the
terms and does not restate them as its own.

**An abort-only, close-only exemption for `Turret1Shutter`, `Turret2Shutter`
and `CSUW1-Shutter`**, on these terms and no wider:

- **close only, never open.** Each gets `State` set to its closed value. Read
  that value off the loaded configuration's property values, not from memory.
  If you cannot find it for any of the three, build nothing for that one and
  report up;
- **reachable only from `orchestrator.abort`, never from a plan**, an
  operation, an exemption list, or any other caller;
- **read back on every close.** A row says `closed: true` only when the
  read-back confirms it, as in part 1;
- **all three stay in `NAMED_REFUSALS`**, and `named_refusals_hold()` stays
  empty. `SOFTWARE_MAY_COMMAND` does not change. The exemption is a separate,
  narrow path, not a lifted refusal.

The turret shutters are not registry elements, so they join the declared
shutter table from part 1, routed through `stand_ti2e`, with the device
names above. Do not infer them from a name (check 80).

**Tests part 2 needs, each watched failing before the code exists:**

1. **No plan path reaches the exemption.** A plan, an operation plan, and a
   direct `apply()` naming each of the three devices with its closed value are
   each refused, exactly as today. The abort, on the same fake core, closes
   all three.
2. **An open value is refused**, on the abort path too. Exercise the exemption
   with each of the three devices at its open value and see it refuse without
   writing. Then confirm the fake core recorded no write.
3. **`named_refusals_hold()` is still empty** after the change, and all three
   names are still in `NAMED_REFUSALS`.
4. **A read-back that disagrees** gives `closed: false`, and the abort still
   reaches the light sources and the fan-out.

**The first run on the instrument waits for the person to watch.** Mock and
fake-core tests only until then.

## Boundaries

Write in `microscope_agent/src/` and `microscope_agent/tests/` only. Never
write or reword `envelope/` or `approvals/`. **Open no device for this card.**
Running an abort on the instrument is a separate step, and the person watches
it.

Run the validator to `0 failed` under the interpreter `CLAUDE.md` names for
this computer, and read its `tree:` line. Then `git diff HEAD -- <paths>`,
then `git commit -F <file> -- <paths>` under your seat, naming each new file.
Confirm with `git log -1`, and push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat, 8 lines at most: the commit, the test's failing and then passing
output, the validator's `verdict:` and `tree:` lines, what `lunf` did with
`{"enable": []}`, and, once part 2 lands, its commit, each shutter's closed
value and where you read it, and the four tests' failing and then passing
output.
