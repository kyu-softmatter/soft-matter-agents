# 043 — the camera's full-scale count, one entry per body and readout mode

status: **open, re-issued 2026-10-15: the bench record exists, and the item waits on the microscope side offering it to the store** · issued 2026-10-07 by
manager-librarian-20261007-1, for the item `plan.md` 14 lists as waiting on a
manager-librarian seat ("to card the camera's full-scale count per readout
mode") · **for librarian-20261007-1**, the session the person opened on the
Office computer on 2026-10-07 · nothing in it starts before the person's bench
visit, now Tuesday 2026-10-13, has a record on disk. **The bench moved twice: from 2026-10-08 to Monday 2026-10-12 (the person, directly in manager-librarian's window, 2026-10-09), then to Tuesday 2026-10-13 (the same, 2026-10-12)**; card 060's file still carries the old date in its name).

## GOAL

The focus search needs to know when a frame is clipped, so every
focus-search plan names a `camera_ceiling`. It names either a number cited
from the store as `kb:<entry_id>` or the gap `camera_full_scale_count`. The
store holds no full-scale count, so today every plan names the gap. Check 88
refuses a `kb:` ceiling that names no real entry (`6ac3fdf`), and the code
that reads a gap refuses to run the search rather than guess.

What the store has is near the answer and is not the answer:

- four Kinetix 22 mode entries that name a bit depth in their text and carry
  no count (`camera_read_noise_{speed,sensitivity,dynamicrange,subelectron}`,
  E3 from the datasheet);
- the red camera's adapter describing itself as BitDepth 16 on 2026-09-24
  (`kinetix_red_adapter_properties_as_reported_20260924`, E1);
- the prior project's record that the same property once lied by a factor of
  sixteen (`pixeltype_misreports_bit_depth`, E3). It conflicts with the entry
  above, and both are kept.

A ceiling worked out from a bit depth is a calculation that rests on the
property that has lied before. The answer is a saturated frame. When one has
been read, enter it, one entry per camera body and readout mode, so that a
plan naming that mode can cite a real entry and the search can run.

## WHAT THE BENCH RECORDED (2026-10-13), AND WHERE

**Re-issued 2026-10-15 by manager-librarian-20261007-1**: the person said
this seat keeps 043. The record is not the one this task first expected, so
this section replaces the chain written on 2026-10-07. Re-derive it before
trusting it.

- **The record is a microscope findings file, not dino-autofocus's form.**
  dino's forms were not on the microscope computer that day, so there is no
  dino record to compare with or cite. The only record is
  `microscope_agent/findings/microscope-20261013-1-20261013.json`, committed
  at `1104cc6` (sha256 `468da0cb...` at that commit; recompute it yourself),
  item **`A_camera_saturation`**.
- **What it holds.** Both Kinetix cameras, loaded by the dual-camera file,
  read Port `Dynamic Range` and ReadoutRate `100MHz 16bit`. The person
  saturated the image with the transmitted lamp and read a maximum of
  **65535 ADU from the Micro-Manager histogram**, with many pixels
  saturated. The person first said `100MHz 12bit` and corrected it to
  `100MHz 16bit` on a second look. Binning was 1x1. Exposure was somewhere
  between 30 and 100 ms.
- **What it does not hold**, as the item names its own gaps: which exposure
  gave the 65535; **which camera it was read on** (the person said the two
  read the same); and the image-information maximum, as opposed to the
  histogram.
- **The item says `for_store: false`.** That flag is the microscope seat's
  statement of what it offers the store, and 044 treated it as binding. So
  **do not enter from this item until the microscope side offers it**.
  manager-librarian has asked manager-microscope to have the item marked for
  the store, or to say why not. Start when that lands.

How the record bears on the entry:

- **The source is `operator_read:`** (a person reading the instrument's
  display with no agent running), not `measured:`. The bench record is the
  findings item, so cite it by path, commit and sha256.
- **Do not attribute the reading to a body the record does not name.** If
  the entry is about both bodies, the claim that the second camera reads
  the same rests on the person's statement and is graded as one, not as
  the reading. Rule how to split it, and say why.
- **The value enters as read: 65535.** Compare it with the adapter's
  reported bit depth and the datasheet's for that mode, and with the prior
  project's record that PixelType once misreported. Write whether it agrees.
- **Its conditions are the mode as read back**, in `identifiers.port` and
  `identifiers.readout_rate` verbatim (`Dynamic Range`, `100MHz 16bit`),
  plus 1x1 binning. Exposure does not move a saturation ceiling, but the
  unknown exposure is named in the entry. **Every other Port and
  ReadoutRate stays a gap**, per subject.
- **The histogram is not the image maximum.** Say which was read, in the
  entry's conditions. A plan reading this ceiling should know it came from
  the histogram.

## TASK

For each (camera body, readout mode) the record holds a saturated maximum
for: one entry, `numbers[]` holding one `full_scale_count` in `ADU`, a whole
count of at least 1. The quantity is registered in the commit that files
this task.

Things each entry must get right, because a plan will read it and run:

- **The mode is the readout mode the software reported at the time**, as
  `Port` and `ReadoutRate` read back, in `identifiers` and in `validity`.
  These are what a plan names. **Use exactly the keys `identifiers.port`
  and `identifiers.readout_rate`**, with each string verbatim as
  Micro-Manager read it back, so that the commit-time check can match a
  plan's mode against them. Added 2026-10-07, when manager-microscope
  offered to add that match once it knew which field an entry uses. Say so
  if the record makes these keys wrong; do not silently choose others. Map them to the datasheet's mode names only
  if the record supports the mapping. If it does not, write the mapping as
  open rather than guessing which datasheet row `100MHz 16bit` is.
- **The source prefix follows the evidence and not the answer sheet's
  label.** The staging answer sheet's card SMA-01 accepts only "measured",
  and that word there means "taken on this stand". In the store,
  `measured:` (E1) means this system's run recorded it, with a run id. A
  person reading a maximum off Micro-Manager with no agent running is
  `operator_read:` (E3). Choose by what the record shows, say why, and do
  not lift the grade to match the sheet. If the frame file is on disk with
  its hash and you read its maximum yourself, say so too, and say what prefix
  that reading earns.
- **Whatever the frame reads is the value.** 65535, 4095, 255 or something
  else, it enters as read, with no rounding to a power of two and no
  "corrected" value beside it. Compare it with the bit depth the adapter
  reported and with the datasheet's bit depth for that mode, and write
  whether it agrees. A disagreement is kept under rule 7 and named in
  `conflict_with`. It is not reconciled.
- **The person's own recollection is on dino's form too**, as statement S4
  (cards L-055 and L-056). Name it by that id and say whether the frame
  agrees with it. **Do not enter its number**: the answer sheet accepts a
  measurement for this card, and a recollection beside a reading would hand
  a plan two ceilings.
- **What ends the entry**: the camera body is replaced, or its readout modes
  are changed by firmware or the adapter. Say which event stops it being
  true. A swap between arms is not that event; see
  `camera_bodies_are_told_apart_by_serial`.

**What stays a gap, per subject** (023): `camera_blue` in every mode, every
red-camera mode nobody saturated, and the red camera too if the record says
"not reached". A failed attempt is not an entry. It is a `searched` line for
the next gap: the bench, the date, and why it did not saturate.

**Update the answer sheet's card SMA-01**
(`kb/staging/dino_autofocus_first_questions.v0.json`) to say what was
entered and what stays open. That file is yours.

## CONTRACT

- No entry, staging edit or publish before the bench record and the findings
  item are both on disk. If 2026-10-13 passes without them, report that and
  stop. Do not fall back to the datasheet's bit depth.
- No number from dino-autofocus enters except this one value, through the
  findings item. Nothing on its form is copied as-is. No safety limit
  crosses. A full-scale count is a fact about the camera, not a limit, and it
  must not be written as one.
- Report the entry ids to me. The microscope seat cites them in a plan's
  `numbers[]` as `kb:<entry_id>`, and I tell that seat.
- Do not edit any plan, card, envelope or code. Those files belong to other
  seats.

## CONSTRAINTS

- **Your seat row comes first.** `librarian-20261007-1` was not in
  `contracts/seats.json` when this was filed. Architecture registers it only
  when the person tells that seat directly that they opened you, not on a
  relayed message, and it has asked the person. Do not commit until `git log -1 -- contracts/seats.json`
  shows the row. Run `git var GIT_COMMITTER_IDENT`, commit with
  `GIT_COMMITTER_NAME`/`GIT_COMMITTER_EMAIL` copied from the row, and pass
  the message with `git commit -F <file> -- <paths>`. Never `--amend`.
- **librarian-20261004-1 is live in this directory too.** Claim
  `kb/entries/`, `kb/index.json`, `kb/staging/`, `failures.jsonl` and
  `queries/log.jsonl` by message before writing. Nothing on disk refuses a
  collision.
- **This moves `kb_version`.** The store is at `kbv-1bf657715637`, which was
  never published (the snapshots read `kbv-70754d3df50b`). Check the query
  log for in-flight pins, tell the execution seats before you publish, and
  run the full publish steps, guides included.
- On this computer the librarian server does not start: bare `python` is
  Anaconda without `mcp`. You are on the degraded path. Measure through
  `Store`, not `kb_query`.
- Validate with `uv run --offline --no-project --python 3.12 --with
  jsonschema python contracts/validate.py`. Quote its last line with the
  number. When it ends `0 failed`, push with
  `git -c credential.helper=manager push origin feature/autofocus-ui`.
- Dead ends go in `librarian_agent/failures.jsonl` naming `task: 043`.

## REPORT

- The entries, each with its camera, mode as read back, value, source prefix
  and grade, and why that prefix.
- Whether each value agrees with the adapter's bit depth, the datasheet's,
  and statement S4, and every `conflict_with` written.
- What stays a gap, per subject.
- The commit, and the publish's `kb_version`.
- One sentence on what is still not on disk.
