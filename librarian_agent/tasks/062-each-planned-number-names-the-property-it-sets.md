# 062 — each planned number names the property it sets, and each path word names the state it is

Written by `manager-librarian-20261007-1` on 2026-10-27. You read this; you do
not edit it.

**For a librarian execution seat** (librarian-20261007-1, or whichever
librarian seat the person opens next). It comes after 061, because a binding
and a state resolution sit on a row that already carries its `mm_label`. If you
are not a librarian seat, take nothing from this card and report up.

## Why

Read **plan.md 15.1 item 10** (`efbd679a`, and its later edits). Microscope
cards 095, 096 and 097 build the runtime's side of it.

- A plan's acquisition carries `exposure_time` in seconds. Micro-Manager's
  camera takes `Exposure` in milliseconds. Nothing says which property a
  planned number sets, or in what unit.
- The light engines take each line's intensity per mille (entry
  `light_engine_line_intensity_is_per_mille`), so a value of `10` gives one per
  cent. A read-back cannot catch a wrong scale, because the device repeats the
  wrong value exactly.
- A plan writes a hand-set position in the path table's words, such as `empty`
  for the confocal unit's port slot that reaches the red camera only. The
  runtime compares it with the device's own state label, and nothing maps one
  to the other.

Which property a quantity sets, in what unit, and which device state a word
names are facts about this instrument. So they are yours (P14), and they reach
the runtime only through the snapshot's `devices` table, as a label does.

## The form: bindings

**A row that carries `mm_label` may also carry `mm_bindings`, a list of
`{"quantity", "property", "unit", "entry_ref"[, "config_sha256"]}`.**

- `quantity` is an id in `contracts/quantities.json`. A binding keys on a
  registered name only. If a plan needs a name that is not registered, do not
  bind it. Report the name to this seat, and it is registered first.
  `exposure_time` was registered on 2026-10-27 for this card.
- `property` is the exact Micro-Manager property name on the device under the
  row's label, character for character: `Exposure`, `GREEN_Intensity`.
- `unit` is a symbol in `contracts/units.json`, and it is **the property's**
  unit, not the quantity's. The runtime converts between them.
  - When the two are one dimension, such as `s` and `ms`, the factor comes
    from `units.json` and is exact.
  - A property that takes a fraction of full scale, such as the engines'
    per-mille intensity, needs a unit that names that scale. **Never `1`**:
    `1` cannot tell 10 from 1 per cent, which is the card-018 error over
    again. `units.json` has no per-mille symbol today. Report the need to
    this seat and enter no binding for it until the symbol exists.
  - A physical quantity into a control value, such as a power in milliwatts
    into a per-mille setting, also needs a calibration (below). The binding
    still names only the property's own unit.
- `entry_ref` names the entry that holds the binding. Its `identifiers` carry
  `mm_label`, `mm_property`, `quantity` and `unit`, equal to the row's, and the
  row's `mm_label.label` is the entry's `mm_label`. **The row is a copy of the
  entry.** It has no `grade` or `source` of its own.
- `config_sha256` follows 061's rule exactly. It is the entry's
  `identifiers.mm_config_sha256`, and only an entry from `measured:<run_id>`
  carries one.
- **One binding per quantity on a row, and one per property.** Two
  quantities into one property, or one quantity into two properties, means
  one of them is wrong.
- **A verb's argument is not a binding.** `frame_count` is `acquire_series`'s
  argument, and no property holds it. The runtime's code lists those, so do
  not bind it.

**What the entry records beside the binding.** The reading run (microscope
card 096) logs each property's value, type, read-only flag, and the limits or
allowed values the adapter reports. Enter those as the entry's numbers in the
usual four-part form. They are what the adapter accepts, **never a safety
limit**. What may be commanded is `envelope/safety.json`'s and the person's,
and no limit crosses into the store (10.3 rule 4). Say so in the validity
conditions, as `light_engine_line_intensity_is_per_mille` already does.

**Where the device reports no unit, the unit is measured.** Micro-Manager
does not say `Exposure` is in milliseconds. Card 096's exposure step sets
three values and records the exposure each frame's own metadata reports. A
binding's unit stands on that comparison, not on the property's name. An
entry whose unit comes from a manual or the prior project is E3.

**Grade.** One rule for every binding, as for labels.
- E1 from a run on this instrument, under the approved configuration, with its
  digest. This is the only kind the runtime will command through.
- E3 from the maker's manual or the prior project. This is knowledge for
  planning, and it commands nothing.

**Calibrations for control values.** Where a physical quantity becomes a
control value, the conversion is a `kind: calibration` entry, E2, with
`valid_until` set (a date and the event that ends it, like
`tracer_diameter_measured`) and `validity` giving the range of the physical
quantity it covers. Its `identifiers` carry `mm_label`, `mm_property` and
`quantity`, the same as the binding it serves, so the runtime finds it by
that key. Do not put it on the row. Outside its range, expired or absent, the
runtime refuses and names the calibration it needs. That is the ruling
working, and it is not a gap for you to fill with an estimate.

## The form: state words

**A row for a device software may not command may carry `mm_states`, a list
of `{"word", "state_label", "entry_ref"[, "config_sha256"]}`.**

- `word` is a value the path table writes for that selector, in
  `optical_paths.v0.json`'s `required_selectors` or the row's own
  `slot_contents` or `states`: `empty`, `out`, `inline`. Where the path table
  says a sentence instead of a word ("the slot that reaches the camera being
  used"), the plan cannot name a value from it. List each such selector in
  the report. Do not invent a word for it.
- `state_label` is the device's own state label, exactly as Micro-Manager
  reports it.
- The entry's `identifiers` carry `mm_label`, `path_word` and
  `mm_state_label`, equal to the row's. The grade and digest rules are the
  bindings' rules.
- One label per word on a row, and one word per label.

**A state word's meaning is observed, not read off a label.** This is the
store's own evidence rule, and `label_warning` in `optical_paths.v0.json` is
why. On this instrument a label and a state read back consistently while the
light went somewhere else: the branch selector's mapping was inverted for
weeks. The disk's bright-field label also serves widefield fluorescence. And
two of the port's three slots starve one camera, in an order nobody has
recorded (`slot_order: null`). So:
- An entry that resolves a word on a row marked `verify_by: "acquisition"`
  (today `csuw1_port`), or on `lapp_branch` or `csuw1_disk_position`, which
  `label_warning` names without that mark, must cite a run that acquired in
  that state and recorded which detector got light. A run that only read the label back supports "the device has a state
  labelled X". It does not support "X is `empty`", and it grades nothing
  higher than that.
- **Where that record sits** (added 2026-10-27, with check 98): the entry's
  `identifiers` carry `lit_detectors`, the list of device rows that recorded
  light in that state, by their ids in the device table (`camera_red`,
  `camera_blue`). On `csuw1_port` the list equals what the row's
  `slot_contents` says that slot `reaches`. A run that disagrees with the
  table is a finding about the table: report it, and enter no resolution
  until the two agree.
- For `lapp_branch`, `inline` and `side` resolve only from such a run. While
  `lapp_branch_assignment` is open, the resolution says which branch, never
  which engine.
- A row with no supported resolution gets no entry in `mm_states`. An absent
  word is what makes the runtime refuse a required state, which is right.

## Not decided here, and not yours to decide

- **Which quantities a plan sets, and whether a parameter is a setting, a
  verb argument or refused.** That is the runtime's derivation (card 095).
- **Whether a per-mille unit is added to `units.json`, and under what
  symbol.** That is the manager's, on your report.
- **What a calibration's range must be for a given plan.** The plan's number
  decides it, at derivation.

## What to do

1. For each row carrying `mm_label` after 061, read the entries that say
   which property a quantity sets and which state a word names. Add
   `mm_bindings` and `mm_states` where an entry backs them, citing the entry
   after you have read it yourself. Today most will be E3, or absent. Card
   096's run is what brings E1 bindings, and they reach you as findings in
   the ordinary way.
2. Rebuild the exports and the snapshot through `src/export_snapshot.py`, and
   confirm the snapshot's `devices` table carries both fields.
3. **Self-tests**, each watched failing before it passes, beside 061's:
   - every binding's and resolution's `entry_ref` names an entry whose
     `identifiers` match the row field for field, and whose `mm_label` is the
     row's label;
   - every `quantity` is in `contracts/quantities.json`, and every `unit` is in
     `contracts/units.json` and is not `1` on a fraction-of-scale property;
   - no quantity or property appears twice on a row, and no word or state
     label either;
   - no binding names `frame_count`;
   - a resolution on any of those three rows cites a `measured:` entry whose
     run acquired, not only one that read a label back, and whose
     `lit_detectors` names rows of the table -- on `csuw1_port`, exactly the
     slot's `reaches`;
   - the snapshot's `devices` table text equals staging's.
4. Run `python src/kb_index.py` and the validator.

## Report

Send manager-librarian-20261007-1, 6 lines at most:

- each binding and resolution entered, with its entry, grade and digest, or
  that it has none;
- each quantity you could not bind and why, including names not registered
  and units `units.json` lacks;
- each selector whose path-table value is a sentence, not a word;
- the commit hash, and the self-tests you watched fail.

Also send the runtime seat, microscope-office-20261017-1, the two field names
and the commit. It reads them through the same function that reads
`mm_label`.

A validator check that each row's bindings and resolutions match their
entries is the manager's, and it lands with its fixtures, separately from this
card, like check 96 for 061. It is check 98 (2026-10-27). Beyond the
self-tests above it holds three things this card already says: a row carrying
either field carries `mm_label`, a word is one the path table or the row can
write, and a binding's unit is not `1` when its quantity is registered in a
unit that is not `1`.
