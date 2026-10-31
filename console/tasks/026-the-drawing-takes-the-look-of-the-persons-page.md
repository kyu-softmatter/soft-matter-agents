# 026 — the drawing takes the look of the person's page

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 025.
If you are not that seat, take nothing from this card and report up.

**Start line: build now, to this card's commit.** Nothing in plan.md has to
change first. plan.md 15.1 item 11 already says what the console's copy of
the export is for: "It gives the drawing its look: the page's README calls
it a reference mockup, to be replicated rather than copied whole." This card
says what that look is, which card 023 left unsaid. Where this card and
item 11 differ, item 11 wins. Send questions to this seat.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

This is still the interface step (I-20261029-office-06, `d3b71d83`). Nothing
here connects to a run, and nothing here stands in for the mock connection.

## Why

The person asked (I-20261030-office-01, `c3231fa2`): "광로를 만드려고
했던것은 이해를 했어 근데 왜 내가 줬던 그 자료들을 그대로 이용하지 않은거지?"
(I understood that you set out to build the light path, but why did you not
use the material I gave you as it is?)

Part of the answer is the rules. The page takes no names, order or places
from the file, because those are this microscope's facts and reach the page
only from the recorded order. The rest of the answer is this seat's miss.
Card 023 part 2 said only "The look follows part 1's file, rebuilt in the
console's own components and CSS", and it named nothing to follow. Card 025
then drew the example "with part 2's look". What both built is a bordered
box per branch holding a vertical line of text per element, "name · state ·
reading · control · entry [open]", with the click opening inside the line.
That does not read as the person's page. This seat's own check of 023 part
2 compared the drawing's order and labels and never the file.

## What the file looks like, in words

`console/docs/light-path/Main.dc.html` (sha256 `15995359…`, card 023 part
1), read as text. Open nothing in it, run nothing in it, and follow none of
its links.
- **The parts are boxes.** Each part is a rounded white box with a visible
  border. Its name is in bold on the first line, and its setting is on a
  smaller, quieter line beneath. The whole box is what a click lands on.
- **The parts are grouped into areas.** Each group is a softly tinted
  rounded area, a shade off the page's background. A small upper-case label
  in a monospaced face with wide letter spacing names the group, in a muted
  colour.
- **Lines join the boxes.** They run between neighbours in the order light
  meets them.
- **The clicked part opens in a panel beside the drawing**, white and
  rounded, headed by the part's name. Everything about that part is in the
  panel, not under the box.
- **The page is calm.** It has a light background, a white rounded card
  holding the drawing, generous space between areas, and no heavy rules.

## What to build

Both the real drawing (`drawing.tsx`) and the example (`example.tsx`) take
the look below. What each one shows does not change: the same words, the
same labels, the same entry ids, the same click contents, the same draft
fields. Only how it is laid out and drawn changes.

1. **Each branch is an area.** It is a tinted, rounded area with the
   branch's name as its label, in small upper-case monospaced letters.
   - The label's text in the page is the order's spelling exactly. An
     upper-case look comes from CSS only, so the text a test or a screen
     reader gets is still `transmitted`, not `TRANSMITTED`. No word is
     translated, prettified or added.
   - The example's areas carry no label, because the example file names no
     branch.
2. **The areas stand side by side, in the order's own sequence.** They wrap
   onto a new row when the panel is too narrow for the next one. Below the
   shell's narrow breakpoint they stack in one column, with no horizontal
   scroll.
   - **The file's own arrangement is not taken.** The file puts transmitted
     light on top, the stand in the middle, epi illumination to the right,
     confocal and cameras to the lower left, and the eyepiece output at the
     bottom. That arrangement says where each part of this microscope sits.
     The order the page reads gives a sequence of branches and a sequence
     within each, and nothing else ("the array's order is the only position
     there is", in the status file's schema). So the page draws that
     sequence.
   - **No line joins two areas.** The order does not say where one branch
     meets another.
3. **Each element is a box.** It is a rounded box on the page's panel
   colour with a visible border.
   - The first line is the element's name, in bold.
   - Beneath it, in a smaller, quieter line or lines, comes what 023 shows
     today in the same order: the state label, the reading, the control
     label with the refusal notice where 023 puts one, "place not
     recorded" where it applies, and the entry id as text.
   - For the example, the label is the first line and the setting is the
     line beneath, and nothing else.
   - Boxes in an area stack top to bottom in the order's sequence.
4. **Lines show order, never light** (card 023, unchanged). Between two
   neighbours in a branch there is one short plain line.
   - Every join has one fixed style, whatever any element reads.
   - No arrowhead. An arrow into a camera's box reads as light arriving
     there, which the drawing may not say.
   - No `svg`, no colour by wavelength or by a source being on, and no
     thickness or brightness standing for intensity.
   - The last box in a branch has no join after it. A box whose place is
     not recorded has none at all.
5. **Elements whose place is not recorded** stay inside their branch's
   area, below its joined boxes, behind a dashed rule under the words
   "place not recorded". They are drawn as boxes with no join and no
   position among the others.
6. **A click opens the element in a panel beside the areas.**
   - On a wide screen the panel stands to the right of the areas. Below the
     narrow breakpoint it falls beneath them.
   - It is headed by the element's name. It holds exactly what opens under
     the box today: 023 part 3's and 024's contents for the real drawing,
     and for the example "{label}: {control}" and "Example: nothing here
     can be changed or drafted."
   - One element is open at a time. A click on another box moves the panel
     to it, and a click on the open box closes it.
   - No panel shows until a click, and **the panel has no close button**,
     so the example's panel still holds no button at all (card 025's test).
   - Item 11 says drafted elements "open their draft fields in place".
     That is read as on this tab and this page, against the old link to
     another tab, and the panel is on this page. Report it if you read the
     plan otherwise.
7. **The box is what is clicked, and the keyboard reaches it.** Each box
   acts as one button.
   - Its accessible name still begins `Open <element>`, or `Open <label>`
     on the example, so 023's, 024's and 025's tests keep finding it.
   - It carries `aria-expanded`.
   - Its state lines stay readable to a screen reader.
   - Nothing interactive is nested inside a box.
8. **The frames.**
   - The real drawing sits in a white rounded card on the page. The banner,
     the "Order … · grade … · source …" line and "Lines show the order
     light travels through the elements, and nothing else." stay above the
     areas, unchanged.
   - The example keeps its own dashed frame and its large heading, the mark
     "Example: not this microscope's path", above 017's list. Its panel
     opens inside that frame and never in the live panel's place. The two
     must still not read as one.
9. **The colours are the console's own.** Use the tokens in
   `web/src/app/shell.css` (`--bg`, `--panel`, `--line`, `--muted`,
   `--ink`). Add one token of the console's own there or in
   `instruments.css` if an area tint needs it.
   - The look is matched by eye and not by value. No colour, size, radius,
     position or font name is copied out of the file.
   - Use a monospaced face from the system stack (`ui-monospace`,
     `monospace`). No outside fonts.

What does not change:
- 017's list under `NO_ORDER`.
- The source line, the run banner, the three known-trap lines.
- [Lights off], the changes list and [Apply].
- What the server sends, `order.ts`, `join.ts` and the example file.

## What is not carried from the file, and why

Say this in your report, so the seat telling the person can repeat it.
- **Beams coloured by wavelength, and their thickness and brightness.** They
  draw light as on and as reaching a camera on the strength of a drawing.
  Which camera a state reaches is the optical-path table's.
- **Per-line laser power sliders and percentages.** The console offers no
  laser power, and the store holds that per-line power is not transmitted.
- **"What is known", the models and the safety notes about each part.**
  Those come from the store, and the console shows only the store's wiki
  pages.
- **Positions and names from the canvas.** Where an element sits and what it
  is called come from the recorded order only.
- **Presets, the "Check this path" section, and settings that "change the
  drawing only".** On the console a change is a draft the person signs.
  Presets wait for a card of their own (card 023, "Presets are not
  built").

## Tests, each watched failing first

- **Real drawing**, with 023's fixtures:
  - One area per branch the order names, in the order's sequence, each
    labelled with the branch's name exactly as spelled. No area for a
    branch the order does not name.
  - In each box the name comes first and the state line or lines after it,
    as separate elements. The text 023's tests read is unchanged.
  - A click on a box opens one panel, outside every branch's list, headed
    by that element. A click on a second box moves it. A click on the open
    box closes it. `aria-expanded` names the open box and no other.
  - Every test of 023 part 3 and of 024 that opens an element passes
    against the panel.
  - The drawing holds no `svg`, no element with a `marker-end`, and no
    inline `style` naming a position (`left`, `top`, `transform`).
  - 023's test that joins look alike whatever any element reads still
    passes.
- **Example**, with 025's file:
  - Areas with no label, boxes with the label first and the setting
    beneath, in the file's order.
  - The panel opens inside the example's frame and holds no input, select,
    textarea, button, link or role that acts.
  - The draft before and after clicks on the example is equal.
  - All of 025's tests pass.
- **Changed tests.** Where an existing test asserted the old shape (the
  opened content inside the `li`, the `[open]` text button), change it to
  the new shape and list each change in your report with why. Remove no
  assertion about what is shown.

## Look at it

Start the console on the sample only, `--backend placeholder --store mock`,
and open Instruments > Optics and control. The example shows there. Say in
your report what you saw: the areas side by side, the boxes, a click
opening the panel beside them, and the narrow width stacking them. This
seat checks it again on a clean clone.

## What not to do

- Read nothing new: no store, no snapshot, no canvas, and nothing from the
  file but its look in words.
- Take no markup, text, script, font, colour value or position from the
  file.
- Draw no light, no arrowhead and no line between areas.
- Add no word to the example's, and no word or number to the order's.
- Change no file under `contracts/`, nothing in the server, and nothing
  outside `console/web/`. Install nothing.

## Done when

- Card 023's "What the page shows" points here, amended in this card's
  commit.
- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest -p no:cacheprovider` passes.
- The validator ends `0 failed`. Quote its tree line.
- One commit, made through `contracts/tools/seat_commit.py`. Report its hash
  to this seat, with this card's commit.
