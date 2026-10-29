# 104 — the light-path order, written beside the elements

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** Build and
test on mock only. If you are not that seat, take nothing from this card and
report up.

## Why

plan.md 15.1 item 11 draws the light path in the order light travels. The
order is the librarian's. It reaches the page only through the runtime, in
the status file and in each `snapshot` event, because the page reads those
two places and nothing else. "The runtime reads the order from the snapshot.
It writes the order, by element id with its `entry_ref`, beside the elements
in the status file and in each `snapshot` event."

The shape is pinned in `contracts/schemas/idle_status.schema.json`, `$defs`
`light_path_order`, with `examples` and `x_refused`. It was agreed with
manager-console-office-20261017-1, whose page builds to it. The status file
gains it as the optional top-level property `light_path_order`. Build to that
file. If it does not fit what the code can honestly say, stop and report it
to this seat.

**The store holds no order yet.** Librarian card 063 enters the person's
16 October description, and its entry's form is not known yet. So this card
builds everything up to the snapshot reader. The reader comes in a later
card, once 063's entry has landed and its form can be named.

## What to build

In `microscope_runtime/src/`:

1. **Every status file carries `light_path_order`.** The same object goes
   into every `snapshot` event the run records, as the field
   `light_path_order`. The run reads it once, at the start, and writes the
   same object everywhere, unchanged during the run.
2. **`not_in_snapshot` is what every run writes for now.** It carries the
   envelope snapshot's path and the sha256 of its bytes, and a reason naming
   what was looked for and not found. Look for no order anywhere else, the
   console's copy of the drawing and the canvas included: neither is a
   source.
3. **`hand_set` is written in both cases, from the registry the run read.**
   It holds one entry per element that `check_software_motion` refuses to
   move by software, or that the registry marks as moved by hand.
   - Each entry gives the element's id, its channel (or null), and one slot
     per position the registry gives it.
   - `name` is the slot's word as the registry spells it, or null when the
     registry gives none.
   - `resolves` is true only when the registry gives the slot both a name and
     an entry. The entry goes in `entry_ref`.
   - Otherwise `resolves` is false, and `why` says which part is missing: no
     word, only prose, or no entry. A slot left unfilled on purpose says so.
   - Invent no slot name and no count. An element with no slot table in the
     registry is listed once, with an empty-reason line in your report, and
     not given made-up slots.
4. **The `read` assembly is built and tested against a test-only order.**
   Branches go in order and the array's order is the only position.
   Elements whose place is not recorded go in `place_not_recorded`, against
   their branch, with no position. `grade`, `source` and `source_kind` are
   taken from the entry as the store spells them; `source_kind` is the part
   of `source` before its first colon. No code path outside the tests can
   produce `read` until the reader lands.
5. **Every element and every `hand_set` entry carries `read_back`** (added
   after the first issue of this card, when manager-console found the page
   could not join the lamp or the Aura to their rows). It is
   `{channel, name}`: the channel whose `snapshot` event carries the
   element's read-back row, and the key that row is under, spelled exactly
   as the snapshot spells it. For a stand element this is its registry id
   (`nosepiece`). For a device that the Micro-Manager backend reports by
   label, it is that label (`DiaLamp`, `Aura`), taken from the registry's
   `mm_label`. It is `null` when no snapshot row exists for the element. The
   page joins on this pair and nothing else, so it must hold on the backend
   the run actually used. Do not assume that `channel` and `read_back.channel`
   are the same: write whatever the snapshot code does.
6. **Nothing else changes.** No device is opened, read or written for this,
   and no limit is added. An element absent from the registry is still
   written by its id, with channel null if it has none.

## Tests, each watched failing first

1. The schema's own `examples` and `x_refused` for `light_path_order`.
2. A mock run's status file and each of its `snapshot` events carry the same
   `light_path_order`, `not_in_snapshot`, naming the snapshot by path and
   sha256, and the status file validates against `idle_status.schema.json`.
3. `hand_set` on the mock registry: one entry per hand-set element, with
   slots, names, `resolves` and `why` as item 3 says. A slot with a word and
   no entry gives `resolves` false.
4. The `read` assembly on a test order with a hole: the hole's element is in
   `place_not_recorded` and in no branch's `elements`. The output validates.
5. On a mock run, every order element and every `hand_set` entry whose
   `read_back` is not null names a key of its `read_back.channel`'s snapshot
   `elements` or `state`, in that run's own `snapshot` events, under exactly
   `read_back.name`. Test it for the lamp, the Aura and one stand element
   (the nosepiece), on the test order from test 4. A `read_back` that points
   at a row the snapshot does not have fails the test.
6. The existing suite is unchanged. Name any test you change and say why.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, no `console/`, no `librarian_agent/`.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most: the commit; each test, watched failing, then
passing; the suite's counts; each hand-set element whose slots the
registry could not name, by id; and, for the lamp and the Aura, the
`read_back` pair your code wrote.
