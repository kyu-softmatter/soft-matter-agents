# 102 — a light engine is a registry name, by its model

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** It comes
after card 098. Build and test on mock only. If you are not that seat, take
nothing from this card and report up.

## Why

The librarian is entering 13 `mm_bindings` for `illumination_power`, one per
light line:

- 8 on the Spectra III, `mm_label` `LightEngine`;
- 5 on the Aura III, `mm_label` `Aura`.

All 13 sit under the devices table's `light_engines.installed[]`, one item
per engine, keyed by `model`. They are not on the channel rows
`widefield_source_a` and `widefield_source_b`. That is deliberate: which
source is which engine is an open gap (`lapp_branch_assignment`).
Checks 96 and 98 already judge these items.

`microscope_runtime/src/orchestrator.py` reads only `channels[]`:
`_rows_and_provenance`, `_name_index`, `_mm_labels` and `_mm_row_lists`. So
once these entries land, every plan that sets `illumination_power` on either
engine finds no binding and is refused. The refusal is safe, but it leaves
the bindings unused. manager-librarian-20261007-1 found this on 2026-10-29.

## What to build

In `microscope_runtime/src/`:

1. **Load `light_engines.installed[]` beside `channels[]`, from the same
   table.** Read only items that carry `mm_label`. An item that has no
   `model`, or whose `model` is not a non-empty string, refuses at load.
2. **An engine's registry name is its `model`, exactly** — for example
   `Spectra III 8-NII-XS`. A plan's `device` names the engine by that string,
   compared exactly. Check 96 names these items the same way.
   - A plan never reaches an engine through `widefield_source_a` or
     `widefield_source_b`. Mapping a channel to an engine waits on the
     `lapp_branch_assignment` gap, and the runtime does not guess it.
   - A model that equals a channel id or an element id refuses at load,
     naming both.
3. **The engine's `mm_label` and `mm_bindings` go through the same loaders
   and the same entry-copy checks as a row's**: `_mm_labels`,
   `_mm_row_lists`, digests, one property per binding, and the `line` rules
   from card 098. Nothing about bindings is decided differently for an
   engine.
   - A label held by both a row and an engine refuses at load, naming both.
     This is the existing "label on two rows" refusal, now across both lists.
4. **Card 096's rules apply to an engine as to any light source.** A light
   with no core device refuses the exposure step before its first write. An
   engine is not exempt because it is not a channel row.
5. **Nothing else changes.** No safety limit is added or widened. No
   conversion is inferred. No step is filled in. The `light_engines` text is
   not read for anything except the fields above.

## Tests, each watched failing first

1. A snapshot with one engine carrying two line bindings (`GREEN`, `NIR`)
   and steps. A plan action with `device` set to the engine's model and
   `line` `GREEN` writes `GREEN`'s property. The same action with `device`
   `widefield_source_a` does not reach the engine.
2. At load, each of these refuses and names what clashes:
   - a model equal to a channel id;
   - a model equal to an element id;
   - one label on a row and on an engine;
   - an engine with `mm_label` and no `model`.
3. **The bindings as the librarian enters them today** — unit permille, no
   `step`, no calibration with a conversion. A plan setting
   `illumination_power` on that engine refuses and names the missing `step`.
   With a step and a plan number in W, it refuses and names the missing
   calibration. Neither writes. This is the expected outcome until the
   reading run supplies a step and a calibration exists. Pin it.
4. An engine with no `mm_label` loads as nothing, and naming its model in a
   plan refuses as an unknown name.
5. The existing suite is unchanged. If a test has to change, name it and say
   why.

The history row `lines_steps_and_a_conversion_copied` in
`contracts/history_fixtures.py` (`_line_store`) builds a store with an engine
binding. Read it for the shape. Tests supply their own snapshot.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, no snapshot, nothing in `librarian_agent/`.
- Check 38 refuses a plan whose `device` is neither a channel nor an
  element. This seat is extending it to accept an engine's model, in a
  separate commit. Do not wait for it on mock.
- If a plan needs any field beyond `device` and `line` to reach an engine,
  stop and report it to this seat. The plan schema is mine.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most: the commit; each test, watched failing, then
passing; the suite's counts; and any existing test you changed, by name.
