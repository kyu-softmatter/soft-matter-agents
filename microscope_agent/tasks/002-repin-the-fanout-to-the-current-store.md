# 002 — re-pin the fan-out to the store that exists

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

## Where this picks up

`51c0e93` re-filed `tau_d` and moved the store from `kbv-9bc3910f1886` to
`kbv-ec984bc852e7`. This fan-out is pinned to the old one, two axes of seven
in. The librarian seat edited the entry without first checking who was pinned
to it and has said so; the rule it crossed is its own.

The old version is not on disk any more, and the MCP server refuses a stale pin
by design (`librarian_agent/src/mcp_server.py:276`). So the remaining five axes
cannot reach the librarian while pinned where they are, and §9.1's completion
condition — one pass with the librarian **on** — cannot be met by going
backwards. **The pin moves forward.** That is my decision; the reason is written
here rather than carried in a message, so that you can check it.

## Why moving is cheap here, and the one place it is not

I checked the delta rather than taking it on report. `51c0e93` touched
`kb/entries/tau_d.json` and `kb/index.json` and nothing else, and no commit
since has touched either. **`entry_count` is 25 on both sides: no entry was
added, none was removed, one was re-filed.**

Two consequences, and together they are what makes this a re-pin rather than a
re-derivation:

- **Every `kb_ref` in this fan-out survives the move.** The five are
  `csuw1_disk_position_states` and `csuw1_disk_speed_exposure_constraint` (a1),
  `water_viscosity_293k`, `lab_ambient_temperature` and
  `sample_temperature_not_actuated` (a7). Not one of them is `tau_d`, and each
  entry is identical across the two versions.
- **Every `kb_gap` survives it too.** A gap claims *absent at this version*.
  Nothing was added between the two, so absent-at-`9bc3910f1886` gives
  absent-at-`ec984bc852e7` for every observable except `tau_d` itself — and
  `tau_d` is no gap's target.

**The exception is a single line, and it is the whole of the care this task
needs.** `goal.json`, `kb_gaps[0].nearest[0]`, names `tau_d` — the one entry
that changed — as the near-miss for `tracer_radius`, at `overlap:
"unconstrained"`. That judgement was made against an entry filed as a
dimensionless group carrying no unit. It is now a `derived_quantity` in seconds
over `bead_diameter**2/diffusivity`, and `bead_diameter` is a length.
**Re-read the near-miss against the current entry and record what the re-read
says**, rather than carrying the old verdict across. If the answer moves, move
it: a near-miss that reads differently once the entry is correct is a finding,
not a failure of this task.

## The task

1. Move every `kb_version` under
   `microscope_agent/questions/mic-20260918-001/` from `kbv-9bc3910f1886` to
   `kbv-ec984bc852e7` — `a1`, `a7`, `configs.json`, and the gap in `goal.json`.
2. Re-read the `tau_d` near-miss as above, and leave it correct.
3. While you are on that field, its value word becomes `no_overlap`. The
   architecture seat settled the rename in `b8f7f15` and `408a973` widened the
   enum so both words are accepted — so this is not urgent by itself and is
   here only because it is the same line of the same file. `goal.json` is the
   last holder of the old word, named as the holder in
   `contracts/schemas/common.schema.json`.

Nothing else moves. No interval, no abstention, no `kb_ref` added or dropped.

## What holds

**A re-pin is a claim.** After this commit those cards say they were answered
against `ec984bc852e7`. That is true of the refs and the gaps by the argument
above, and true of the near-miss only if you do the reading. Do not move that
one pin without it.

**Nothing outside this directory.** The simulation fan-out is stale too and its
cards *do* cite `tau_d`, so the same move is not free there. That is another
seat's card and another seat's judgement.

## Done when

Every pin in the directory reads `kbv-ec984bc852e7`, `python3
contracts/validate.py` ends `0 failed` with the five check-25 PENDING lines for
this directory gone, and one commit as `seat:microscope`.

Then one sentence up: re-pinned, and whether the near-miss re-read changed.

## Not this task

**A2 to A6** — task 001, still open, and the reason this one comes first: the
five should be written against a store the librarian will actually serve.

**Removing `unconstrained` from the enum.** That is in `contracts/`, it is a
manager seat's, and it comes after this commit.
