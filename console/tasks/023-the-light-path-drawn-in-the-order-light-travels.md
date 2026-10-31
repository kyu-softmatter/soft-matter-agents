# 023 — the light path drawn in the order light travels, and a click that drafts

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 022.
The card has five parts, and **each part has its own start line**. As
amended on 2026-10-29, every start line names a commit that is in the
tree. Build each part to the commit its start line names, and cite that
commit in your report. Build nothing to a draft seen uncommitted in the
working copy. If you are not that seat, take nothing from this card and
report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

**This card is the interface, and the connections come after it**
(amended 2026-10-29). The person set the order of the console's work
(I-20261029-office-06, `d3b71d83`): "우선 목적은 인터페이스를 만드는것
까지고 그 이후에 따로 목 시스템과의 연결, 실제 시스템까지 연결을 할거야."
(The aim for now goes as far as building the interface. After that, and
separately, come the connection to the mock system and then to the real
system.) These are plan.md 15.1's three steps, and its item 6 says what the
first one works on: recorded runs, read as data.
- **All five parts are the interface.** Each is built against recorded data
  and the schemas' own fixtures, and none waits on a runtime commit. Part
  5's start line changes for this (below).
- **The connection to the mock is not this card's.** It is what brings a
  real order and a real lights-off reply to the page: librarian card 063,
  runtime card 104 and the reader card after them, and runtime card 103 for
  the host's handling of lights off. Nothing here waits for them, and
  nothing here stands in for them.
- **The connection to the real system comes after that.** It is the
  person's, at the bench.
- **So until the mock connection lands, the running console shows 017's
  list on the light-path page, and the drawing appears only in the tests.**
  The person has the running console checked every three hours for whether
  the light path shows, and that check will find the list. Until then,
  card 025 adds an example drawing above the list, marked as one, which is
  not an order (amended 2026-10-30). See "Not in this card".

## Why

The person chose to have the live optical path drawn in the order light
travels, with each element's setting shown and changed by a click, on
Instruments > Optics and control (Q-20261027-scope-01 at `17e15a9a`).
plan.md 15.1 item 11 is the rule, as amended at `b6f54389` from the
person's `c46095ec`. Read it whole before starting. Item 8 still holds
whole: the same two sources, the same labels, and no request of the
page's own. **No rule loosens.** What is new is the order the page draws
in, and what a click does.

The person then said to write this card now, and that the drawing's look
follows the file they gave this computer on the morning of 2026-10-29
(D-20261029-office-01 at `18ca4a68`). That file is a look and nothing
else. The order itself is the librarian's: card 063 (`20296826`) enters it
from the person's 16 October description, and microscope card 101's
observation at the stand later supersedes it.

Card 017 built the path as a list, because no order existed. This card
turns that list into the drawing once the order reaches the page, and
retires the stand picture.

## Part 1 — the look, copied as a reference (start now)

- **Copy two files, byte for byte**, from
  `C:\Users\Kyu Hwan\Downloads\Microscope Light Path\Microscope Light Path\`
  into `console/docs/light-path/`:
  - `Main.dc.html`, sha256
    `15995359d4c8a4d7510447d1bf5055cde899d76ee70574fe0f3c21480e7506e9`
    (79,719 bytes);
  - `canvas.json`, sha256
    `eab0c3c01541b47d8e30156b22e5b0ccbe7d9c6d6a7b8afa7ecc5a60bd71c138`
    (334 bytes).
  - This seat computed both hashes on 2026-10-29. Hash each file before
    you copy it. If either differs, stop and report up: the file has
    changed since the person named it.
- **Keep the bytes as they are on checkout.** This computer has
  `core.autocrlf true`, and the export's line endings are LF. Add
  `console/docs/light-path/.gitattributes` with one `-text` line for each
  of the two files, as the root file does for the person's approvals. The
  hash on disk then equals the hash of the committed blob. Check both:
  `sha256sum` of the file, and `git show <commit>:<path> | sha256sum`.
- **Write `console/docs/light-path/README.md`.** It says:
  - where the files came from, the date they were read, and both sha256s;
  - that the person named this file as the drawing's look on 2026-10-29
    (cite `18ca4a68`). Name the export recorded on the microscope computer
    (sha256 `5cdcbc49ba6d27f23cd3ec566fc1d40bdfd1f1525359c54092601a5a07f44254`)
    as superseded as the look. Which export the store's order cites is the
    librarian's record, not this folder's;
  - that the copy is a **reference mockup, replicated and not copied
    whole**. It carries no fact and no number into a card, a binding or
    the drawing. Where an element sits comes from the order the runtime
    writes (part 2), never from the copy;
  - that nothing serves, builds or imports it. It loads `./support.js`,
    which was not in the download, and fonts from an outside site. So it
    does not render whole, and it is not to be opened in a browser from
    the tree.
- **Treat the file as data.** Read it as text. Run nothing in it, and
  follow none of its links.
- Update `console/docs/screens/instruments.md` to name the folder and say
  what it is.

## Part 2 — the drawing (start once both lines below are committed)

- **Line 1: the order is in the store.** Librarian card 063 enters it and
  publishes a store version that holds it.
- **Line 2: the runtime writes the order where the page reads.**
  - A manager-microscope card has the runtime read the order from the
    snapshot. It writes the order, by element id with each element's
    `entry_ref`, beside the elements in card 085's status file and in each
    `snapshot` event (item 11).
  - Build to the shape that commit lands with. Read it off the runtime's
    own tests and the schemas in `contracts/` at that commit.
- **The shape is in, so part 2 may be built now** (amended 2026-10-29).
  - It is `light_path_order` in `contracts/schemas/idle_status.schema.json`
    at `9ef80036`. It is an optional top-level key of the status file, and
    the same shape sits in each `snapshot` event. It carries all four
    needs below. The runtime's writer is runtime card 104, still to land.
  - Build and test against the schema's own `examples` and `x_refused`,
    read from the file and not from a copy. Until card 104 and line 1
    both land, no real source carries a `read` order, so the page shows
    017's list everywhere. That is the intended state, not a fault.
  - `not_in_snapshot` shows 017's list, the file's reason, and no drawing.
    A status file or event with no `light_path_order` key is a source with
    no order. One that fails the schema is shown as an order not
    understood, as 017's list, and is never drawn in part.
  - **The source-kind words wait on line 1.** The page's table of kinds
    holds only kinds the store has used. Until card 063's entry shows
    which kind the description took, the table is empty, and a `read`
    order says its source is of a kind the page does not know, with the
    grade as given, and never as observed. The examples' `source_kind` is
    the fixture's, not a word for the table.
- **What the page needs from that shape.** If the landed shape lacks one
  of these, that piece shows that it is not given. Report up, naming the
  missing field. Fill nothing in.
  - each branch, with its elements in order;
  - the elements whose place is not recorded, against their branch;
  - the order's grade and the kind of its source, for the banner;
  - for each element moved by hand, its slots by the store's names, and
    whether each slot's word resolves in the store (part 3).

**Where it reads, and nothing else.** These are card 017's rules, unchanged:
- during a run, the run's `events.jsonl`: the latest `snapshot`, and the
  `apply` events since it;
- outside a run, card 085's status file, with its time;
- never a request of its own.

Element names, the order, places and slot words come from those two places
only. They never come from:
- the snapshot's device table, or the store other than its wiki pages;
- the look's copy, the canvas, or the stand picture's `ROWS`;
- intake's reading of the export (I-20261029-office-03).

**What the page shows.** The look follows part 1's file, rebuilt in the
console's own components and CSS: no outside fonts, no `support.js`, and no
markup or text taken from the file. What that look is, in words, is card
026's (amended 2026-10-30): areas per branch, boxes per element, and the
clicked element in a panel beside them.
- **Each branch the order names, in its order, and no other.** Rename,
  reorder or remove an element in the order, and the drawing follows.
- **Each drawn element shows** its name and its state, by 017's labels:
  - read back, with the time;
  - sent;
  - not open;
  - not read, with the reason.
- **It also shows its control label**, "moved by hand" or "drafted", as
  in 017. The refusal notice 017 put beside every draft of the Aura, the
  lamp and the red camera stays, word for word, until the card that lifts
  it.
- **It shows its entry's id as text.** That is how the console shows any
  link to an entry: never followed, and the entry itself not shown.
- **An element the order names and the read-back omits** shows:
  - "not open" for a channel the run did not open;
  - "no channel" for an element with none, such as the polarizer or the
    eyepieces.
  - No value is invented for either.
- **An element is found in the read-back by its `read_back` pair and
  nothing else** (amended 2026-10-29; the pair is in the shape since
  `1974438a`). Beside each element the order places, each one whose place
  is not recorded, and each `hand_set` entry, the runtime writes two
  things: the channel whose snapshot carries the element's row, and the
  row's key exactly as that snapshot spells it (`nosepiece`, `DiaLamp`,
  `Aura`). The page matches that pair exactly against a row's channel and
  name.
  - The pair's channel may differ from the element's own channel, and is
    used as given. The element's own channel still keys part 3's table and
    the tab link. The pair only finds the row.
  - The page never matches on the element id, never translates one name
    into another, and holds no table of names.
  - `read_back: null` means the element has no row. It reads "no channel"
    when the element has no channel, "not open" when the run did not open
    the element's own channel, and "not read" otherwise, with the reason
    that the runtime names no read-back row for it. It is never matched on
    its id instead.
  - A pair on a channel the run did not open reads "not open". A pair whose
    row the read-back does not hold reads "not read", naming the pair.
  - An order without the field fails the schema, so it reads as an order
    not understood, with nothing drawn.
  - The count of read-back rows the order names nowhere counts the rows
    that no pair names.
- **Lines show order, never light.** A line joins two neighbours in the
  order. No line is drawn lit, coloured by whether a source is on, or
  ending in a detector as if light arrives there. Which camera a splitter
  state reaches belongs to the optical-path table, and the page does not
  draw it.
- **A branch with a hole is drawn only as far as its order goes.** An
  element whose place is not recorded is listed beside its branch as
  "place not recorded", with its live value and its click. It is never
  drawn into a position, and no line closes the hole.
- **The banner says the order's grade in words.** An order from a
  description reads exactly "from a description, not checked on this
  microscope". When an observed order replaces it, the drawing is redrawn
  from that order alone, and the banner names its grade. Nothing of the
  description is kept beside it. A source kind the page has no words for
  shows the grade as given, never a stronger word.
- **The stand picture and its hard-coded `ROWS` are deleted in this
  part's commit.** The picture's double-click to a section becomes the
  drawing's click (part 3).
- **A source with no order is shown as card 017's list**, with its
  `NO_ORDER` words, and no drawing. An older run's events, from before
  line 2 landed, are such a source.

On the mock every state stays labelled the mock's, as in 015 and 017.

## Part 3 — what a click opens (with part 2)

A click opens the element and offers only what the rules already allow for
it.
- **Drafted elements** (the Aura, the transmitted lamp, the red camera's
  exposure) open their draft fields in place. They no longer link to
  another tab. 017's refusal notice shows with them.
- **Moved-by-hand elements** (the turrets, wheels, port, disk, light-path
  selector and nosepiece) open their slot list.
  - The slots appear by the store's names, as part 2's shape carries
    them.
  - **A slot is marked current only where the runtime says which slot the
    read-back is** (amended 2026-10-29). The shape does not say it yet.
    Until it does, no slot is marked. Beside the list, the page shows the
    value the element's row read back, as read and with its source, and
    says which slot that is has not been given. Matching that value to a
    slot's name or number is a translation, and the page makes none.
  - Choosing a slot adds a **selector** to the draft, in the plan schema's
    `selectors`. The runtime makes it a required state: shown at the bench
    hand-over, set by the person's hand, then read and compared. Software
    never writes it, and the click says so.
  - A slot whose word has no resolution in the store is refused in the
    draft, naming the word.
  - If the shape carries no slots for an element, the click says the slot
    list is not given, and offers nothing.
- **The laser combiner and the trap** open to say why they have no control
  here, and show what was last sent.
- **No click offers a laser line, a power, a level beyond 017's three
  drafts, or a software move of a hand-moved part.** Each of those is
  refused until its own fence lands (item 11's widenings), and the click
  says so.
- **An element with a section tab** (the cameras, the tweezers, the
  confocal unit, the piezo) also shows a link to that tab.
- **What a click offers may come from one table in the console's code,
  keyed by channel and never by element.** It names the channels whose
  click opens a draft form (the red camera, for its exposure), the
  channels with no control (the laser combiner and the trap), and the
  channels with a section tab.
  - A key is matched exactly. Nothing in the table is keyed by an
    element, a branch, a place or a slot.
  - It changes only what a click on an element the order already names
    offers. It draws nothing, and adds no element, line or position.
  - Each key is a device id in `contracts/capabilities/microscope.json`.
    A key that file does not hold (the piezo stage) is named in the test,
    with why it is there.
  - A draft form it names is one the server's draft list holds, and the
    test reads that list from the server's models or the generated
    types, never from a copy.
  - The Aura and the lamp keep the draft the server's row gives them.
  - An element with no channel, or on a channel the table does not hold,
    gets no tab link and the plain words for its control.
  - The words for "no control" and "moved by hand" are 017's, unchanged.

## Part 4 — the changes list and [Apply] (the list with part 3; signing waits)

- **The clicks collect into one draft, an ordinary plan card.** The tests
  validate it against `contracts/schemas/plan.schema.json` itself, never a
  copy. A plan the schema refuses shows the schema's refusal, as card 014
  does.
- **Show "These changes will be made:"** with the draft's settings and
  required states, in the order they were added, each removable. It keeps
  the words "Not saved. This draft exists only on this screen."
- **A draft that touches a quantity with no limit in the safety file is
  refused before signing**, and the page says so (amended 2026-10-29).
  - The console names no limit and holds no table of limit names. Which
    limit covers a quantity, and in what unit, is a safety decision. It is
    the person's. The pairing will be one contract that the runtime's
    refusal and the console both read. It has not landed.
  - **The person has answered: none of the three is set for now**
    (D-20261029-office-04, `698ba049`): "세 상한은 당분간 정하지 않는다.
    Aura 광원 세기, 투과광 램프 밝기, 빨간 카메라 노출 시간을 바꾸는 초안은
    지금처럼 서명 전에 모두 거부한다." (The three limits are not set for
    now. Drafts that change the Aura's power, the lamp's brightness or the
    red camera's exposure time are all refused before signing, as now.)
  - So nothing covers the Aura's power, the lamp's intensity or the red
    camera's exposure, and every part draft is refused before signing. The
    page says no limit has been named for that quantity yet. This is the
    intended state, not a placeholder, and it changes only on a later
    decision of the person's and a card that follows it.
  - For these three the page reads nothing from the safety file. It
    guesses no limit, looks none up by a name it made up, and does not
    take `illumination_power_max` or `exposure_time_max` as covering any
    of them.
  - When the pairing lands, a later card points the page at it. The page
    then takes the limit's name from the pairing and its value from the
    safety file the run snapshotted. A null name, a missing limit and an
    unreadable file each refuse.
- **[Apply] is signing, then the run button.**
  - Signing is card 013's dialog. It shows the same list beside card 021's
    numbers nothing uses, and takes the password.
  - Then comes the run button, which stays as built: it sends nothing
    until its own card.
  - On the instrument, the run starts only after the bench hand-over at
    the microscope.
- **Signing waits on a draft's home.** Card 013's writer recomputes the
  plan's fingerprint from the plan card on disk, and a console draft is
  saved nowhere. Where it is saved is still to be designed (cards 012 and
  014 said so too).
  - Until a later card names that place, [Apply] is shown and refused. It
    says the draft cannot be signed yet, because it is saved nowhere.
  - Build the list, the refusal and the tests now. Build no place to save
    a draft.

## Part 5 — [Lights off] (start after part 4: its message is pinned)

- **Start line: the message is pinned, so part 5 may be built now**
  (amended 2026-10-29, for the person's interface-first order above).
  - Build the button, the server's route and the reply's display to
    `lights_off_request`, `light_source_row` and `lights_off_reply` in
    `contracts/schemas/run_interface.schema.json` at `99eec48d`. Read their
    examples and `x_refused` from that file.
  - The host's handling on the mock is runtime card 103, still to land. It
    is the mock connection and not this part's. Build no handling of the
    console's own in its place.
  - The server reaches a host only through the host address it is started
    with, and every session starts it with none. With no host given, the
    server sends nothing, and the page shows the press as no answer: nothing
    is known about the lights, use the switches. That is the intended state
    in the interface step, not a fault.
- **The message is exactly `{"lights_off": true}`.**
  - The page sends the server a press and nothing else.
  - The server sends the host those bytes and nothing else: no source, no
    value, no run id.
  - It is not the assistant's imported `lights_off` command and not the
    server's `STOPS`, which are the old engine's stop kinds. Their
    retirement is a later card's.
- **It is immediate and unsigned.** No password, no draft and no
  confirmation step.
- **During a run, the button says that it also stops the running plan.**
- **The reply is checked against `lights_off_reply` before anything is
  shown.** It is one of three cases, and the page shows each as follows:
  - **Done.** The reply names the run that turned the lights off. During a
    run that is the run that was stopped, and the page says the plan was
    stopped. The rows are shown one per source, in the reply's order:
    - off, with what was read back;
    - sent, where the device cannot read back;
    - not turned off, with the reason. That row says to use the switch on
      the device.
  - **Stop sent.** The running plan accepted the stop, but its lights were
    not read back in time. The page shows no source as off and no row,
    names the run, gives the reason, and says to check each light at its
    switch. It does not build rows from the run's log itself: the rows are
    the host's to derive.
  - **Refused.** Nothing was sent to any light. The page gives the reason
    and says to use the switches.
- **Anything else is shown as no answer, and no light is shown off.** That
  covers a reply that fails the check, a connection that fails, and no
  reply within the server's wait. The page says that nothing is known
  about the lights and to use the switches. It never resends on its own;
  a second press is the person's.
- A light is never shown off on the strength of what was sent.
- After the reply, the path shows the result from its two sources as for
  any run.
- **On the instrument, the first lights-off request is watched at the
  bench.** That is the person's act, and nothing on the page says it
  happened.

## Not in this card

- **Presets are not built.** A preset is a named draft saved in the
  console's own folder (item 11). A draft has no saved place yet, so
  presets wait for part 4's place and a card of their own.
- **The eyepiece confirmation is not taken on this page.** It belongs to
  the bench hand-over.
- **The connection to the mock and to the real system** are later steps,
  each with its own cards (see the top of this card).
- **The example drawing is card 025's, not this card's** (amended
  2026-10-30). The person chose it (D-20261030-office-01, `f8e361dc`), and
  plan.md 15.1 item 11 allows it at `02980384`. It is not an order. Add no
  status file with an order to the console's sample data, and build the
  example only as card 025 says.

## Tests, each watched failing first

Use recorded fixtures inside `tests/`, in the landed shapes: an events file
with a snapshot carrying the order and later applies, a status file
carrying the order, and, for part 5, the pinned message and reply fixtures.
- **Part 1.**
  - Each copied file's sha256 equals the one above, on disk and from the
    commit.
  - No file under `src/` or `web/src/` names `docs/light-path`.
  - The build output holds nothing from the folder.
- **Order.**
  - The drawing follows the fixture's order: reorder, rename or remove an
    element, and it follows.
  - A branch the fixture does not name is not drawn.
  - A source with no order shows 017's list and draws nothing.
  - Each of `light_path_order`'s examples shows as its status says, read
    from the schema file. Each of its `x_refused` shows 017's list as an
    order not understood, with nothing drawn.
  - A `read` order whose source kind is not in the page's table never
    reads observed.
- **Holes.**
  - A branch with a hole stops where the order stops.
  - An element with no recorded place reads "place not recorded" beside
    its branch, with its value and its click. It is never drawn in a
    position.
- **No light.** Turning a source on in the fixture changes that source's
  label and nothing on any line.
- **Values.**
  - An element in the order and missing from the read-back reads "not
    open" or "no channel", with no value.
  - An element with `read_back: null`, whose id equals a row's name on its
    own channel, reads "not read" and shows no value. Watch it fail
    against an id match first.
  - A pair naming a row on a channel other than the element's own shows
    that row's value, and the element keeps its own channel's control and
    tab link.
  - A pair whose row is missing reads "not read", naming the pair. A pair
    on a channel the run did not open reads "not open".
  - Once runtime card 104 reports the pairs it wrote for the lamp and the
    Aura, a fixture with exactly those pairs shows both rows' values.
    Until then, any fixture pair for them is the test's choice, and the
    test says so.
  - 017's tests still pass, its draft-refusal notice among them.
- **Banner.**
  - A description-graded fixture shows exactly "from a description, not
    checked on this microscope".
  - An observed-order fixture replaces the drawing whole, and the banner
    names its grade.
- **Entries.** Every drawn element shows its entry id as text, and nothing
  follows it.
- **Clicks.**
  - A drafted element opens its fields in place.
  - A moved-by-hand element lists the fixture's slots and marks none
    current. It shows the read-back value as read. A value equal to a
    slot's number or name still marks nothing.
  - Choosing a slot adds a selector to the draft.
  - An unresolved slot word is refused, naming the word.
  - The combiner and the trap explain and show what was last sent.
  - No click offers a laser line, a power, or a software move.
- **Draft.**
  - The collected draft validates against `contracts/schemas/plan.schema.json`.
  - A quantity with no limit is refused before signing.
  - Every part draft is refused before signing, saying no limit has been
    named for its quantity. A fixture safety file that carries every limit
    the safety schema names changes none of those refusals.
  - No file under `src/` or `web/src/` holds a limit name for a part
    draft.
  - [Apply] is refused with its reason while a draft is saved nowhere.
  - The run button sends nothing.
- **Lights off (part 5).**
  - The bytes the server sends equal the pinned message.
  - A press adds no key.
  - The reply's rows follow the fixture.
  - A sent row never reads off.
  - A not-turned-off row says to use the switch.
  - Each of `lights_off_reply`'s examples is shown as its case says, read
    from the schema file and not from a copy.
  - Each of its `x_refused`, a failed connection, and no reply within the
    wait are shown as no answer, with no light off and nothing resent.
  - Stop sent and refused show no row.
  - During a run, the button says it also stops the plan.
  - With no host given to the server, a press sends nothing and is shown
    as no answer, with no light off.
  - Neither the assistant's lights-off nor `STOPS` is on its route.
- **No request.** None leaves the page while it renders or refreshes.
  After part 5, the only one is the lights-off press.

## What not to do

- Read no snapshot, and nothing of the store but its wiki pages.
- Take no name, order, place, number or slot word from the look's copy,
  the canvas, `ROWS` or intake's reading.
- Send no request to a device, the host or the frame tap, beyond part 5's
  one message once it lands.
- Build no stand-in for a runtime piece: no order of the console's own,
  and no lights-off walk of the console's own. Card 025's example is not an
  order and stands in for none.
- Load no outside font or script.
- Write nothing outside `console/`, and install nothing.

## Done when

Each part is done with its own commit.
- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest -p no:cacheprovider` passes. Without the flag, a
  `.pytest_cache` folder in the shared copy fails the validator's
  file-placement check.
- The validator ends `0 failed`. Quote its tree line.
- One commit per part, made through `contracts/tools/seat_commit.py`.
  Report each hash to this seat, with the commits that part was built to.
