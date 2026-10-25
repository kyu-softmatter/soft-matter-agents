# 088 — the three approval readers ignore `approvals/harness/`

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. It rides on card 087**, first in the order: it touches the same three readers, and the runtime holder asked that the two go together. It touches only `tests/`, as its own commit. If you are not that seat, take nothing from this card and report up.

## Why

The person's word on a harness proposal may be given through the console. The console writes it into `microscope_runtime/approvals/harness/` and the person commits it (plan.md 8.3, 15.1 item 4; the person at `659c2214` and `881f5119`; the console's completion asked for at `7c33b8c3`).

15.1 lists three things that keep such a word from ever touching the instrument. The first is that the runtime's three readers of the folder read only its top level and never recurse:

- `operator.approvals_on_disk`;
- the live-view host's list lookup;
- `mm_config_gate.read_approvals`.

Each globs `approvals/*.json`. 15.1 puts on this seat's card a test that plants a file there and watches each reader ignore it. Without that test, the safety rests on a glob nobody has watched.

## What to build

In `microscope_runtime/tests/` only, one test file. For each of the three readers:

1. In a temp approvals folder holding one valid file the reader accepts, plant `harness/HP-902-<12 hex>.json`:
   - once as a valid `harness_permission` (`contracts/schemas/harness_permission.schema.json`);
   - once as malformed JSON.
2. The reader returns exactly what it returns without the subfolder, and the malformed file causes no refusal. A malformed file at the top level still refuses, as today, which shows the test can tell the two apart.
3. **Watch each test fail first**: point it at a variant of the reader that globs `**/*.json`, inside the test, without editing `src/`. It must fail. Then it passes against the real reader.

No change to `src/` is expected. If a reader turns out to recurse, stop and report it with the file and the line. Don't fix it on this card.

## Boundaries

- Write `microscope_runtime/tests/` only. No `src/`, no `contracts/`, never `envelope/` or `approvals/`. Every file the test plants is in its temp folder.
- Commit and push through `contracts/tools/seat_commit.py`, naming the path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 3 lines: the commit; each reader's test watched failing against the recursing variant, then passing; the suite's counts.
