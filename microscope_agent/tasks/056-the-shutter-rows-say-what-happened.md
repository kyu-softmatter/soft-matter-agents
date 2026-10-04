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

Do not touch `SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS` in this part.

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

## Part 2 — a proposal for the person. Do NOT build it until the person says yes

**An abort-only, close-only exemption for `Turret1Shutter` and
`Turret2Shutter`.** Each would get its `State` set to its closed value and read
back. The closed value is read off the loaded configuration's property values,
not from memory; if you cannot find it, the proposal says so. Only the
orchestrator's abort could reach the exemption. It never opens a shutter, and
no plan, operation or exemption list can reach it. The same could cover
`CSUW1-Shutter`. Closing is the safe direction, but it is still a change to
what software may command, so it is the person's call.

**What to put in your report**:

- how you would make it unreachable from anything but `abort()`, and how a
  test would prove that, for example a plan that names the device and is
  refused;
- how the turret shutters get declared, given that the registry does not list
  them as elements;
- the question for the person, in one sentence:
  *"When the microscope aborts, may the software close the two filter-turret
  shutters (and the spinning-disk shutter) — close only, never open — so that
  light is cut even if no one is at the bench?"*

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
`{"enable": []}`, and part 2's proposal with the closed value and where you
read it.
