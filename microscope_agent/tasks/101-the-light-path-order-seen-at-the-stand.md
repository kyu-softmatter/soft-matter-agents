# 101 — the light-path order, seen at the stand

Written by `manager-microscope-scope-20261019-5`. You read this; you do not edit it.

**Assigned to `microscope-scope-20261019-8`, the microscope execution seat on
the microscope computer** (the session "Microscope · planning", rooted at
`microscope_agent/`), once the person has confirmed that row. You record what
the person sees. You run nothing and command nothing. If you are not that
seat, take nothing from this card and report up.

## Why

The console's Optics and control tab is to draw the light path in the order
light travels (plan.md 15.1 item 11, `b7f02558`). The order of elements along
each beam, and which camera each splitter position reaches, is a fact about
this instrument. It has to be read at the stand before the librarian can
enter it. The reading run cannot produce it, because no device reports where
it sits in the path.

The person has a drawing of the path, and pointed to it for this card in
manager-microscope's window on 2026-10-27:
<https://claude.ai/artifact/2huLpZuNgkvok2rASAdJN2>. It labels every fact
with where it came from: the person's statement, a recollection, an
inference, an earlier setup, a spec sheet, or "drawn this way as an
assumption". **The drawing is the checklist, not the evidence.** Every item
below is confirmed, corrected or left open by what the person sees now.

## How: by eye, with every light off

The person chose this in manager-microscope's window on 2026-10-27,
verbatim: **"eye only"**.

- No light source is switched on for this card, the trap laser included:
  not the lamp, not either LED engine, not the laser combiner. If a question
  can only be settled with light, record it as open, naming what would
  settle it. Do not ask the person to switch anything on.
- The person may move hand-set parts (a knob, a slider, the camera splitter)
  to read a label. Record each position as found, and the position it was
  left in.
- Nothing here is sent to the instrument. This seat has no device access.

## What to record

Walk the drawing with the person, element by element, in the order light
travels.

1. **Each beam, from its source to the sample.** These are the transmitted
   lamp; the Aura III; the Spectra III through the DMD; the laser combiner
   through the spinning disk; and the Tweez 300. For each one, list every
   element in the order the light meets it. For each element, say whether
   the drawing has it right, wrong, or missing, and what is actually there.
2. **The path back from the sample** to each camera, the eyepieces and the
   side camera, in the same form.
3. **Each switching part, position by position,** and where light leaving
   that position goes, as far as the labels and the person's eye can tell:
   the light path selector, the eyepiece knob, the Lapp mirror, the dichroic
   port, the camera splitter, both filter turrets, and both emission wheels.

These are the open items the drawing itself marks as inferred, recalled or
drawn. Ask about each one by name:
- filter turret 2, slots 2 to 6;
- filter turret 1, slots 5 and 6;
- the five-band cube's excitation bands;
- the right side port, and whether anything is attached;
- that the spinning disk sits on the left side port;
- the dichroic port's multi-band dichroic, its part number and bands;
- the camera splitter: which slot sits at which position number;
- emission wheel 1 serving the red camera, and wheel 2 the blue camera
  (both recalled as "probably");
- the Lapp mirror with the mirror out: whether the DMD path passes straight
  through;
- the Aura III's and Spectra III's line sets.

A label read off a part, a part number, or a slot seen to hold a cube is a
reading. Where light would go after a part that can only be inferred from
its label is an inference, and is recorded as one.

## Where it goes

- One findings file, `microscope_agent/findings/microscope-scope-20261019-8-20261027.json`,
  in the form `contracts/schemas/findings.schema.json` sets. There is one item
  per element or switching part, each `kind: "person_statement"`, with the
  person's words where they gave them.
- Each item says in its `how` whether it was **seen** (a label, a part, a
  position read by eye) or **inferred** from a label, and what in the drawing
  it confirms or corrects.
- `for_store` is `false` on every item unless the person says, in your
  window, that the item goes to the store. Then it is `true`, with the
  person's words in `note`. The librarian's entry is a later card,
  `manager-librarian`'s, and not yours.
- Open items are listed as open, each with what would settle it. A gap is a
  line, not a silence.

## Boundaries

- Write that one findings file, and nothing else. No `tasks/`, no
  `envelope/`, no `approvals/`, nothing outside `microscope_agent/`.
- Do not edit the drawing. Corrections to it go back through the console's
  owners, from the findings file.
- Commit through `contracts/tools/seat_commit.py`, naming the path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most: the commit; how many elements were confirmed,
corrected, or left open; each correction in one phrase; and which items the
person sent to the store.
