# 095 — every parameter is a setting, a verb argument, or refused

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** It comes
after card 091, whose snapshot lookup of each label it builds on, unless the
runtime holder, architecture-office-20261017-1, moves it. Build and test on
mock only. If you are not that seat, take nothing from this card and report up.

## Why

Read **plan.md 15.1 item 10** (`efbd679a`); the text is the item itself, and
this card does not restate its reasons. Read off `operator.py` at `58cda9f1`:

- `derive_commands` keys an action's `params` by the plan's number names
  (`exposure_time`, `frame_count`), and a backend writes only
  `params.settings`, `{label: {property: value}}`. So no backend writes or
  reads back any planned number, and every planned command is logged with
  verification `none`;
- selectors go out as `select_<element>` commands, and every device behind
  `mic-20260920-001`'s four selectors except the red camera's mode is one
  software may not command;
- `illumination_line_intensity_permille` is named by no action, so no run of
  that plan would set the light, and nothing says so.

## What to build

In `microscope_runtime/src/`, on the derivation path (`derive_commands`) and
the place the run log records it. Plan runs only: `operation` and
`trap_steps` plans, the live view and check-now are out of scope.

1. **Sort every action parameter into exactly one of three, before anything
   moves, and name the class in the run log**, one event at derivation:
   - **setting**: written into `params.settings[label][property]` from a
     binding (part 2);
   - **verb argument**: listed in code beside `ACQUIRE`, `POWER_UP` and
     `POWER_DOWN`, each argument naming its verification (part 3);
   - **refused**: the run refuses, naming the parameter. Nothing is dropped.
2. **A binding comes from the snapshot, as a label does in card 091**, and
   the runtime keeps no copy. It names, for a registry name and a registered
   quantity, the property it sets and that property's unit or scale. It
   commands only at E1 with the approved configuration's sha256, exactly
   card 091's rule for labels, with one grade for every binding. Anything
   else refuses, naming the binding and what it lacked.
3. **The verb-argument list.** Today it holds `acquire_series`'s
   `frame_count`, verified against the frames the sequence returned, counted
   by image number. Fewer frames is a disagreement, logged as one. Any other
   entry needs this seat's yes first.
4. **Value conversion has three routes and no formula in the runtime:**
   - unchanged, when the plan's unit is the property's;
   - an exact factor from `contracts/units.json`, such as s to ms, read from
     the file and never written into code;
   - an unexpired E2 calibration from the snapshot whose range covers the
     value. Out of range, expired or absent, the parameter refuses, naming
     the calibration it needs. The written value carries the worse of the
     number's and the calibration's grade.
5. **The apply event records both values**: the plan's number with its
   `from`, and the written value with its binding and any calibration.
   `check_software_motion` judges the written value, label and property.
6. **Selectors split by the allow-list, not by role.**
   - On a device in `SOFTWARE_MAY_COMMAND` (the red camera's mode), a
     selector is a setting through a binding, as in part 2.
   - On any other device it is a **required state**. After preflight and
     before the first action, read the device's state, resolve the plan's
     value through the snapshot to the device's own state label (the path
     table's `empty`, for one), and compare. Refuse on a mismatch, on "not
     read", or on a value with no resolution, naming the element. It is
     never written and never reaches the motion check as a write.
   - An action on a device software may not command still refuses, as
     today.
7. **A number that no parameter, selector or limit uses is listed** in the
   run log at derivation, by name with its value and unit, and is not
   refused.
8. **The read-back stays exact string equality** with the device's report.
   No tolerance.

On mock a test supplies bindings, state resolutions and calibrations, as it
supplies labels and digests for card 091. Nothing enters the real snapshot.

## Tests, each watched failing first

1. A parameter that is neither bound nor a verb argument refuses the run,
   naming it, before any command is sent.
2. `exposure_time` 0.1 s with an E1 binding under the approved digest to a
   millisecond property is written as that property's `100` value, through
   `units.json`, and read back. The apply event carries `0.1 s` with its
   `from`, the written value and the binding.
3. The same binding at E3, or under another configuration's sha256, refuses.
4. A physical quantity into a control value with no calibration, an expired
   one, and one whose range misses the value: each refuses, naming the
   calibration.
5. `frame_count` 600 with the sequence returning 599 frames logs a
   disagreement.
6. A selector on a device outside the allow-list is read and compared: a
   match proceeds, a mismatch refuses, "not read" refuses, an unresolved
   value refuses. The fake core records no write to that device.
7. The red camera's mode selector goes out as a setting through its binding.
8. `mic-20260920-001`'s `illumination_line_intensity_permille`, `record_length`,
   `brightness_window` and `bleach_window` appear in the run log's unused list,
   and the run is not refused for them.
9. The existing suite is unchanged, apart from tests that asserted
   `select_<element>` commands for non-commandable devices. Name each one
   you change and why.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, no snapshot, nothing in `librarian_agent/`.
- The derivation record is the run log's `derivation` event
  (`contracts/schemas/run_log.schema.json`, `$defs.derivation`): `from`
  `actions`, and `parameters`, `selectors` and `unused_numbers`, each item
  shaped as the schema says. Parts 1, 6 and 7 write it; write no other shape.
- If another schema field is needed, for the apply event or anything else,
  stop and report it to this seat. The schema is mine to change.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most: the commit; each test, watched failing, then
passing; the suite's counts; and any existing test you changed, by name.
