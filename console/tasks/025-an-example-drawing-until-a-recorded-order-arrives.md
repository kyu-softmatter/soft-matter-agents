# 025 — an example drawing until a recorded order arrives

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 024.
If you are not that seat, take nothing from this card and report up.

**Start line: not yet. Build nothing from this card** until plan.md 15.1
item 11 carries the sentence under "What plan.md must say first", committed,
and this seat amends this line to name that commit. Read ahead, and send
questions to this seat. Until then card 023's "No example drawing is built"
still holds: no example file, no server field, no page code.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

This is still the interface step (I-20261029-office-06, `d3b71d83`). Nothing
here connects to a run, and nothing here stands in for the mock connection.

## Why

Until the mock connection lands, the light-path page shows card 017's list,
because no recorded order reaches it (card 023, top). The person has the
running console checked every three hours for whether the light path shows,
and the check finds the list. So this seat asked the person, through the
intake seat, whether the page should show an example drawing before then
(Q-20261029-office-05). Option (2) as it was put, in English:

> Show a drawing before the mock connection too. Put an order made up for
> the screen into the console's sample data, with made-up element names
> such as "Source A" and "Filter B", so it cannot be mistaken for this
> microscope's path, and show "Example: not this microscope's path" large
> on the screen. No draft can be signed on this drawing. Once the real
> order arrives, the real drawing appears instead of the example.

The person answered (D-20261030-office-01, `f8e361dc`): "예시 그림"
(example drawing). That is option (2), on the terms above, and it adds no
name, layout or date of its own.

**Why the start line waits.** plan.md 15.1 item 11 says the order is the
librarian's and reaches the page through the runtime, and that the console
holds no list of element names and keeps none. Item 8 has the page read two
places. Card 023 forbids an order of the console's own. A card may not
license what plan.md forbids, so plan.md has to say first that an example
of this kind is allowed. That is item 11's author's,
`architecture-scope-20261019-5` on the microscope computer, reached through
`architecture-scope-20261019-6`.

## What plan.md must say first

The ask, for `architecture-scope-20261019-5`, worded so item 11 can take it
as it stands or reword it:

> Before any recorded order reaches the page, the console's own sample data
> (the server's `--store mock`, never a real tree) may hold one example path
> for the screen. Its element names are made up and cannot be registry ids,
> and it carries no grade, no store entry and no number. The page marks it
> "Example: not this microscope's path", shows it beside card 017's list and
> never in place of a source's own state, and offers no draft, slot or apply
> on it. It is not an order: it is never read from the runtime's two places,
> never validated or cited as one, and gone whenever the source gives any
> order state other than none.

**This replaces the ask recorded with the person's answer**, that a
sample-data status file may carry a made-up `read` order labelled as
example. That shape cannot be honest. `light_path_order` in
`contracts/schemas/idle_status.schema.json` requires a `read` order to name
a store entry (`entry_ref`) and a grade from E1 to E5, so an example in that
shape would carry an entry and a grade nobody recorded, and the page's
`orderViewOf` would read it as a real order. The example is therefore a
thing of its own, beside the order and never inside it.

## What to build, once the start line is met

1. **One file**, `console/src/sma_console/agents/mock_data/console/example/light_path.json`.
   Its shape is yours, within these limits:
   - It says `"status": "EXAMPLE"`, the way the sample's synthetic result
     cards say `"status": "MOCK"`.
   - It holds branches, each a list of elements in the order drawn. An
     element has an `id` that begins with `example_`, a made-up `label`
     ("Source A", "Filter B", "Splitter C", "Camera D" and so on), its kind
     of control in words (drafted, moved by hand, or no control here), and a
     `setting` in words ("in", "open", "slot B").
   - **No number anywhere**: no JSON number, and no digit in any string.
   - None of the order's or the read-back's keys at any depth: `entry_ref`,
     `grade`, `source`, `source_kind`, `read_back`, `channel`.
   - Add it to `mock_data/SOURCE.md`'s synthetic additions: written for the
     screen, not copied, and nothing in it is this microscope's.
   - Not under the sample's `microscope_runtime/`. That folder is read as
     the runtime's, and the example is not the runtime's.
2. **The server.** Only the sample store offers the example: `MockStore`
   gains a method that returns the file, and `SmaFiles` and `Store` return
   nothing for it. The instruments payload carries it as `path.example`,
   beside `path.order` and never inside it, only when the store is the
   sample and `path.order.state` is `none`; otherwise `path.example` is
   null. `order_state` and the order's validation do not change, and the
   example never passes through either. It is not read from
   `runtime_root()`, the status file or any `snapshot` event.
3. **The page.** When the order's state is `none` and `run.path.example` is
   given, `PathPanel` shows the example in a section of its own **above**
   017's list. The list, `NO_ORDER` and its reasons stay below it, unchanged.
   - The section's heading is the mark, "Example: not this microscope's
     path", at least as large as the panel's own "The light path, now". Its
     frame differs from the live panel's (a dashed border, say), so the two
     cannot be read as one.
   - It is drawn with part 2's look (`drawing.tsx`), so the person sees the
     interface: each element's label and setting from the file, and nothing
     else. No grade banner, no entry id, no tab link, no read-back value, no
     "not open" or "not read". The page adds no word or number to the file's.
   - The screen is in English like the rest of the console, labels and mark
     both. The person was shown the mark in Korean and is told it reads in
     English on screen.
4. **A click on an example element** opens it where a real element opens,
   says its kind of control in words, and says "Example: nothing here can be
   changed or drafted." No field, slot list, selector or button. Nothing done
   on the example changes the draft, the changes list or [Apply]. [Lights
   off] is not in the example's section.
5. **The example gives way.** An order state of `read` draws the order as
   card 023 has it, with no example. `not_in_snapshot` and `not_understood`
   show 017's list with their reasons, as now, and no example. With
   `--store sma` the example never shows.

## Tests, each watched failing first

- **Server.**
  - The sample store with its recorded runs gives `path.example` equal to
    the file.
  - A source with each of `read`, `not_in_snapshot` and `not_understood`
    gives `path.example` null.
  - `SmaFiles` over a scratch tree holding a file at the same relative path
    gives null.
  - The file: every `id` begins with `example_`; no JSON number; no digit in
    any string; none of the six keys above at any depth; `"status":
    "EXAMPLE"`.
  - `SOURCE.md` names the file, and the sample's size test still passes.
- **Page.**
  - With an example and order state `none`: the section, headed by the mark
    at a heading level no lower than "The light path, now"; the labels in the
    file's order; 017's list below it. 017's tests and 023's still pass.
  - With a `read` order and an example given together (a payload the server
    never sends): the order's drawing and no example. The page keeps its own
    guard.
  - A click on an example element: the sentence, and no input, select or
    button in what opens.
  - The collected draft after clicks on the example equals the draft before.
  - The section shows no entry id and no grade.
  - No request leaves the page because of the example.
- **Nowhere else.** No file under `console/src/` outside `mock_data/`, and
  none under `console/web/src/` other than tests, names an example id or
  label. Labels reach the page from the file only.

## What not to do

- Change no file under `contracts/`, and add no key to the status file's
  schema.
- Put no example into a real tree, a scratch copy's runtime folder or the
  sample's `microscope_runtime/`.
- Give the example no grade, entry, source or number, and draw no light on
  it.
- Let nothing on the example reach a draft, the sign dialog, a request or an
  inbox item.
- Write nothing outside `console/`, and install nothing.

## Done when

When the start line is met, this seat also amends card 023's "No example
drawing is built" to point here.
- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest -p no:cacheprovider` passes.
- The validator ends `0 failed`. Quote its tree line.
- One commit, made through `contracts/tools/seat_commit.py`. Report its hash
  to this seat, with the plan.md commit and this card's commit it was built
  to.
