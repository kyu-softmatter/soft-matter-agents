# 054 — the abort turns the lights off

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`.** If you are not that seat, take
nothing from this card and report up.

## The gap, measured at 7159f67

`Orchestrator.abort()` (`src/orchestrator.py:1123`) says it does three things:
*"Shutters first, then power down, then everyone else"*. Plan 4.6.8 interlock 1
says the same: close the shutters, **then lower power**. The code does the
first and the third and skips the second:

1. it closes every shutter `shutters()` recognises and records one row each;
2. it calls every channel module's `abort()`.

`devices/micromanager.py` `abort()` (`:436`) only sets `_ABORTED`, and this is
deliberate: its docstring says the safe state is the orchestrator's sequence
and not the backend's. So **no code anywhere turns the Aura or the DiaLamp
off**. An abort today leaves both lamps lit behind closed shutters. Nothing
stops anyone from opening a shutter by hand afterwards, and nothing in the
record says the lamps are still on. Both lamps are already on
`SOFTWARE_MAY_COMMAND` (`micromanager.py:115` for `Aura`, `:122` for
`DiaLamp`, which allows `State` and `Intensity`), so this card opens no new
permission.

## What to build

**A power-down step between the shutter loop and the per-channel `abort()`
fan-out.** It must come after the shutters, which beat a ramp. It must also
come before the fan-out, and for a reason the order alone does not show:
both the micromanager and mock `apply()` refuse every command once their
module's `_ABORTED` is set, so a power-down placed after the fan-out would be
refused by the very abort it belongs to. Say in the code why it sits where it
does.

For each declared light source, the step does three things:

1. **Write its off state.** For the DiaLamp that is `State` = `0`. For the
   Aura, use **its own off property, which you find and name.** Read it off
   the loaded configuration's device property names, from
   `getDevicePropertyNames("Aura")` on the instrument or from the
   configuration file 033 loads. Do not take it from memory or from a manual
   for a different adapter. If you cannot identify it, the Aura row says
   *off property not identified*, claims nothing, and you report up instead
   of guessing.
2. **Read it back** through a real read of the device: `getProperty` on the
   same pair, the way `micromanager.apply` already does. The write returning
   does not count as a read.
3. **Record one row**, the way the shutter rows are recorded, under a new
   `report["light_sources"]` and logged as its own event. Each row carries
   `source`, `channel`, `commanded` (what was written, or `null` if nothing
   was), `read_back` (what came back, or `null`) and `matched`
   (`true` / `false` / `null`). Any refusal or exception goes in `error`.

**A failure does not stop anything.** A light source that raises, refuses or
reads back wrong is recorded, and the step goes on to the next source and
then to the fan-out. Refusing to finish an abort is worse than the gap.

**The shutter rows have a defect your rows must not copy, and it is not
yours to fix in this card.** The shutter loop sends
`apply({"element": ..., "state": "closed"})`. `micromanager._settings()`
reads only `params["settings"]`, so on that backend the call writes nothing,
returns an empty `applied`, and the row still records `closed: True`. I read
this in the code and have not run it on the instrument. Your rows go through
`{"settings": {device: {property: value}}}` and judge `matched` from
`verified`/`disagreed`, never from the call returning. **Report the shutter
defect up as a finding** with the lines you read. A fix to it is a separate
card.

## Which elements are light sources: declared, never inferred

The registry has no role field to read. Its `role` is free prose, and plan
8 check 80 forbids deciding a role from how an identifier is written. So the
list is **an explicit declaration in `orchestrator.py`**: one module-level
table, with one entry per source, holding the registry channel the write
routes through, the device and property, the off value, and whether software
may command it. Iterate the table. Do not test registry ids against it with
`in` or `==`, which is the membership form check 80 counts. The table is
exactly these five entries, no more:

| source | routed through | off | software-commandable |
|---|---|---|---|
| Aura III | `widefield_source_a` | the property you name, at its off value | yes |
| DiaLamp | `stand_ti2e` | `State` = `0` | yes |
| optical tweezers | `optical_tweezers` | — | **no**: `LASER_ON` stays refused and the power dial is the person's |
| Spectra III (`LightEngine`) | `widefield_source_b` | — | **no**: refused by name in `micromanager.py`, and this card does not lift that |
| confocal laser lines | `laser_combiner` | — | **no, by this card**: its fast cut-off is `laser_shutter`, already in the shutter rows |

For the three non-commandable rows, `commanded`, `read_back` and `matched` are
`null`, and a `note` says *not software-controllable* and why. **They do not
claim off.** That a person must turn them off is the whole content of these
rows, and a reader must be able to see it.

The pairing *Aura is `widefield_source_a`* comes from `micromanager.py`'s
header and card 033. The registry itself leaves the branch assignment
unconfirmed (`lapp_branch_assignment`). Cite that in the table's comment.
If you find another emitter on this instrument, report it up. Do not add it
silently.

## The test

In `microscope_agent/tests/`, on the mock backend with no hardware. It
asserts:

- `report["light_sources"]` exists and holds exactly the five declared rows;
- the DiaLamp row has `commanded` = `"0"`, `read_back` = `"0"` and
  `matched: true`, and the Aura row is `matched: true` too;
- the optical-tweezers row has `commanded`, `read_back` and `matched` all
  `null` and a note saying it is not software-controllable;
- in the log, the light-source event comes after `abort_shutter_coverage` and
  before any channel's `abort()` ran;
- a light source whose `apply` raises is recorded with an `error`, and every
  channel still appears in `report["channels"]`.

Add one more case through `micromanager.apply` against a fake core, in the
pattern of `test_dialamp_allowlist.py`, so the `settings` shape and the
`verified` read are exercised on the backend that matters.

**Run it on today's code first and watch it fail.** Put the failing output in
your report, then the passing output. A test you never watched fail is not
known to test anything.

## Boundaries

Write in `microscope_agent/src/` and `microscope_agent/tests/` only. Never
write or reword `envelope/` or `approvals/`. Lift nothing on
`SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS`. **Open no device for this card**:
the test runs on mock and on a fake core. Running an abort on the instrument
is a separate step, and the person watches it.

Run the validator to `0 failed`, read its `tree:` line, then
`git diff HEAD -- <paths>`, then `git commit -F <file> -- <paths>` under your
seat, naming each new file. Confirm with `git log -1`. Push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat, 8 lines at most: the commit, the Aura off property and where you
read it, the test's failing and then passing output, the validator's verdict
and `tree:` lines, and the shutter-row finding.
