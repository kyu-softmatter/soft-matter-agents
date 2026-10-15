# 073 — retire dino-autofocus's mirror of the six focus-core files

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-1`, after cards 071 and 072.** If you
are not that seat, take nothing from this card and report up.

## Why

Card 059 copied six files of `dino-autofocus`'s focus core into
`microscope_agent/src/` and `tests/`:

- `focus_classical`, `focus_verdict` and `focus_search`;
- their three tests.

From then on this repository held the original, and dino kept a pinned,
read-only mirror of them. plan.md 14 says: **no mirror is re-pointed after
the freeze at `95eee95`**, and once the import lands the mirror copy inside
`microscope_agent/autofocus/` is retired, while `microscope_agent/src/focus_*`
stays the original. Two copies of one file in one repository drift, and
nothing would say which is meant.

## What to do

1. **Find the mirror** inside `microscope_agent/autofocus/`: the copies of
   the six, and whatever check or test in dino compares them with SMA. dino
   called it its shape test. List each path.
2. **Point dino's code at the original.** Wherever the imported code imports
   one of the six, it imports this repository's `microscope_agent/src/` copy,
   in whatever way dino's own environment can reach it. If no clean way
   exists, stop and report the shape you would need, rather than inventing a
   path hack.
3. **Remove the mirror copies and the shape test** that compared them, in
   one commit. Say in the message which original each removed file mirrored.
4. **Re-run card 072's suite**: it must still be green, apart from what had
   already failed at `95eee95`.

## Boundaries

Write inside `microscope_agent/autofocus/` only. **Never edit
`microscope_agent/src/focus_*` or its tests**: they are the original and the
other microscope seat's under card 064. If they need to change, report up.
Through the gate, naming each path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most: the commit, the paths removed and what each
mirrored, how the imported code now reaches the original, and the suite's
result.
