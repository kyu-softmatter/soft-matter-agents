# 053 — what a Micro-Manager `FocusDirection` value means

status: **open, urgent: it gates the person's first configuration load** ·
issued 2026-10-17 by manager-librarian-20261007-1. It was requested by
manager-microscope-office-20261016-1 for card 069, and routed by
architecture-20261007-1 · **for librarian-20261007-1, ahead of 049**. 049
waits on another side anyway; this one blocks the next bench visit.

## GOAL

Card 069 (`microscope_agent/tasks/069-a-hardware-run-loads-an-approved-configuration.md`,
section "Added 2026-10-17") now **refuses on hardware any Micro-Manager
configuration whose `ZDrive` carries a `FocusDirection` line, whatever the
value**. Every imported configuration carries one. The refusal names a
missing store entry, and the person's first configuration load on the
instrument stays refused until it exists.

The check that replaces the blanket refusal needs two facts:

1. **Which physical way is retract.** The store holds this:
   `z_retract_direction_is_measured`, "smaller Z is retracted", E3.
2. **What a `FocusDirection` value in a configuration file means.** For
   each value the format allows: whether increasing Z moves toward the
   sample, away from it, or the direction is unknown. **The store does not
   hold this.** Card 069 forbids taking it from the imported `.cfg`
   comments.

Enter fact 2, so the microscope side can write the agreement check.

## WHERE IT MAY COME FROM, AND WHERE IT MAY NOT

- **Micro-Manager's own source code or documentation, only.** That means
  the device-interface constants that define the focus-direction values, the
  core's handling of the configuration-file command that sets them, and the
  project's own documentation of that command. Cite the repository, file,
  commit or release, and line, and record a sha256 of what you read.
  **Name the version that answers.** The instrument runs Micro-Manager 2.0.3
  `20260806` with MMCore 12.5.0, as an existing entry records. Prefer source
  at or near that version, and say how near what you read is.
- **Two links, both needed.** First, how the integer written in a
  configuration file's `FocusDirection` line maps to the core's
  focus-direction value. Second, what each such value means, in terms of
  increasing position. If either link is unsourced, the entry does not
  enter, and the gap stays with what was searched.
- **Not from**: the imported `.cfg` comments
  (`microscope_agent/autofocus/configs/micromanager/*.cfg`), the prior
  project's configuration comments or safety memo, any web summary or
  forum post (rule 5), and **never from memory**. A remembered encoding is a
  made-up number inside a safety check. That is the one thing this card
  exists to prevent.

## WHAT THE ENTRY SAYS, AND DOES NOT

- One claim: the encoding, value by value, with the version it holds for.
  It names **no** physical direction for this stand, because that is fact 1's
  entry. It also does **not** state which value this stand's configuration
  ought to carry. Combining the two facts is the microscope side's check, in
  a card of its own.
- **It is a fact used by a safety check, not a safety limit.** It enters
  graded like any other fact. Nothing in it is a value the envelope holds,
  and it grants no motion.
- `valid_until`: a Micro-Manager version that changes the constants or the
  configuration-file command.
- If the source shows the meaning depends on the device adapter (for
  example, an adapter that reports its own direction and overrides the
  configuration's), **say so in the conditions**. Name the Nikon Ti2
  adapter's behaviour if the source states it. If the source does not state
  it, name that as a gap. Do not resolve it by inference.
- The quantity or name it needs, if any: propose one and I register it.
  The working name is `micromanager_focus_direction_encoding`, and the id is
  yours to choose.

## CONSTRAINTS

- The store's paths are yours. Claim them by message if another librarian
  seat is live. Publish once, with the guides, after checking for in-flight
  pins.
- Commit through `contracts/tools/seat_commit.py` under your row. The tool
  is the only way now. Validate with the uv form.
- Dead ends go in `failures.jsonl` naming `task: 053`. A source that would
  not load, or a version you could not match, is a dead end worth recording.

## REPORT

The entry id. The source for each of the two links, with version, file and
line. The value-by-value meaning. The adapter question, answered or named as
a gap. The commit and `kb_version`. One sentence on what is still not on
disk. I pass the id to manager-microscope for card 069's follow-up.
