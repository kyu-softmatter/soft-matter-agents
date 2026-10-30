# Instruments screens (console card 012)

Area `instruments` (`web/src/features/instruments/`, hash `#/instruments/<tab>`). Six sub-tabs that do
three things only: **show, draft and stop**. Nothing here sends a command to an instrument or saves a draft. The one
connection to the live-view host is the [Lights off] press (below), and it is made only when the person presses it. A piece the runtime has not built yet says "not built yet", and the console
builds no stand-in for it.

Server routes (`server/api/instruments.py`), all reads except the draft, which composes and writes nothing:

| Route | What |
|---|---|
| `GET /api/instruments/status` | `microscope_runtime/.runtime_status/idle_status.json` as data, checked against `contracts/schemas/idle_status.schema.json` read from the tree. Absent is `none`, an invalid file is `invalid` with why, and no reading is taken from either |
| `GET /api/instruments/limits` | the person's own limits from `microscope_runtime/envelope/safety.json`: the piezo range and the tweezers ranges. Never written into code; a limit the file lacks is `null` |
| `GET /api/instruments/latest-run` | the newest microscope run's events: the traps and strengths last sent (all "sent": the tweezers report nothing back) and the piezo snapshots (read back) |
| `POST /api/instruments/lights-off` | [Lights off] (card 023, part 5): sends the live-view host the one line `{"lights_off": true}` and answers with what the host said, checked against `lights_off_reply`. An ordinary write: it needs the login and is refused from another computer. It is neither the assistant's lights-off nor a stop |
| `POST /api/instruments/draft` | a plan draft built from what the person chose, checked against `contracts/schemas/plan.schema.json` read from the tree, **returned and saved nowhere** (`saved` is always false). The login must be one that may draft, on the microscope computer |

The schema is checked by `agents/schema_lite.py`, because the console's environment has no `jsonschema` and
installs nothing. It supports the keywords the contract schemas use and **raises on one it does not know**
instead of passing over it; its tests run it against every example and every rejected fixture in
`contracts/examples/`.

## Status

- Absent file: **No status yet**, which does not mean that nothing is connected.
- Present: "As of <written_at>, from <written_by_run>", then each reading's name, value, how it was read and
  when. `read_back` reads "read back", `not_readable` reads "sent, cannot be read", `not_read` reads "not
  read" with the value unknown. Nothing is carried forward from an older file.
- "Which program holds which instrument" reads "not checked yet" while ownership is `not_built`.
- **One row always**: "Tweezers laser · set by hand · not known · assumed on". The trap strength last sent, if
  any, is "sent through the tweezers program".
- **Check now** is offered to the person's login only. Until the runtime has it, and the person has connected
  the console to the live-view host, pressing it says "not built yet" and sends nothing.

## Optics and control

The light path is **drawn in the order light travels** (card 023, part 2), from the order the run's source gives and
from nothing else: each branch the order names, each element in its sequence, and no part, branch or position that
the order does not name. No picture of the stand and no list of parts is kept on the page.

- **Each drawn element** shows its name, its state in the four words below, how it was read, whether it is "moved by
  hand", "drafted" or "no draft is offered yet" (or "control not given"), and the order's entry ids **as text, never followed**.
- **The state is joined by the pair the order gives the element** (its read-back channel and name), matched exactly
  against a row's channel and name; never by the element's id, and no normalisation and no table of names live on the
  page. The pair's channel may differ from the element's own, which still decides its control and its tab. An element
  with no pair joins no row, whatever a row is called. An element no row answers reads "not open" (its channel was
  not opened), "no channel" (it has none and no pair) or "not read" (naming the pair, or saying the order names none),
  with the reason, and **never a value**. A hand-moved part's slot list is joined by the same pair.
- **Lines show order only.** One fixed style joins neighbours; no source being on or off changes a line, none ends in a
  detector, and none says which camera a state reaches.
- **A branch with a hole is drawn only as far as its order goes.** Elements with no recorded place are listed beside
  it with their live value, never drawn into a position.
- **The banner**: an order taken from a description reads exactly "from a description, not checked on this
  microscope"; an observed order replaces that with "observed at this microscope" and its grade; a kind of source the
  page does not know shows the grade as given, never as observed (the page's table of kind words starts empty).
- **No order, or an order not in the snapshot, is the list of card 017** with its words and the file's reason and no
  drawing; an order that fails the schema reads "not understood" with the problems, and is the list too.

**The look the drawing follows** is the person's file, kept as a reference in `docs/light-path/` (card 023,
part 1; its README says where it came from and gives both hashes). It is data: a reference mockup that is
replicated and not copied whole, carrying no fact or number into a card or the drawing. Nothing serves, builds or
imports it, and no source file names the folder.

**A click opens an element and offers only what the rules already allow** (card 023, part 3):

- **The red camera's element** opens its exposure field in place, with the refusal notice, and no link to another tab. It is
  found by its channel. **The Aura and the transmitted lamp open words and no fields** (card 024): "No draft is offered for
  the Aura yet. A plan will name the light engine by its model, and the console has nowhere to read that model from yet, so
  it guesses none." and "No draft is offered for the transmitted lamp yet. The run has no recorded quantity for its
  brightness, and no table of its on and off states." The server's row carries the words; the page shows them as given.
- **A part moved by hand** opens the slot list the order gives, by the store's names, with **no slot marked as the
  current one**: nothing gives the page which slot a position read back means, so beside the list it shows the value the
  element's row read back, how it was read and when, and says which of the slots that is has not been given. A value
  equal to a slot's number or name marks nothing. Choosing a slot adds a **required state**, not a command: it is shown at the bench hand-over and set
  by hand, and software never writes it. A slot a plan cannot name is refused, naming the word and why. With no slots
  given, the click says the slot list is not given and offers nothing.
- **The laser combiner and the trap** open to say why they have no control, with what was last sent in the run's events.
- **No click offers** a laser line, a power, a level beyond the three drafts, or a software move of a hand-moved part.
- **An element with a section tab** links to it. The page's table is keyed by channel and by exact match, and changes only
  what a click on an order-named element offers; a channel the table does not hold gets no link and the plain words.
- **Changes collect in one list**, "These changes will be made:", in the order added, each removable, kept only on this
  screen. Nothing is requested while the page renders, an element is opened or a slot is chosen.
- **[Check the draft] and [Apply]** each ask the server once, on the press, to collect the list into one ordinary plan card
  and check it with `plan.schema.json`; the schema's refusal is shown as it words it. **The one part draft** (the red camera's
  exposure) is refused before signing, and the page says no limit has been named for that quantity yet; nothing is read
  from the safety file for it. **[Apply] is shown and refused**: signing is over a plan card on disk and this draft is saved nowhere, so it says
  "This draft cannot be signed yet, because it is saved nowhere." No password is asked and nothing is written. The run
  button that follows signing sends nothing; on the instrument a run starts only after the bench hand-over.
- **No limit is named for these quantities for now** (the person's answer). The page holds no limit name for them, and a
  safety file that holds every limit its schema lists changes none of these refusals; they end when a limit is named.

## Lights off

The **[Lights off]** button sits at the top of the Optics tab (card 023, part 5). One press asks the server once, with
nothing in the request; the server sends the live-view host exactly `{"lights_off": true}` and shows the host's answer.
No password, no draft, no confirmation: a lights-off that waits is a slower one.

- **Which host.** Only the address the server was started with (`--live-host` or `--live-host-file`). With none given the
  server sends nothing and the page says nothing is known about the lights and to use the switches. The default file the
  live view falls back to is never used, and a host that is not on this computer is never connected to.
- **Sent once.** A failure, a silence (the server waits up to 60 s) or a refused reply is shown and never resent.
- **A reply is shown only after the schema accepts it**; otherwise it is "no answer": no light is shown off and the page
  says "Nothing is known about the lights: use the switches."
- **Done** names the run, and says "The running plan was stopped." when the run was a stop of a running plan. One row per
  source in the host's order: *Off* with what was read back; *Sent*, which cannot be read back and is never shown off;
  *Not turned off* with the host's reason and "Use the switch on the device."
- **Stop sent** shows no source and no row: the run, the reason, and "Check each light at its switch".
- **Refused** gives the reason and says nothing was sent to any light and to use the switches.
- **During a run** the button says it also stops the running plan.
- **After the reply** the path shows the result from its two sources as for any run; the press changes nothing on its own.

A draft is offered for the red camera's exposure only: its plan step names `camera_red`, the action `set_exposure` and the
quantity `exposure_time`, which the run's capabilities list. It is **refused before signing, because no limit has been named
for it yet**. The Aura and the transmitted lamp are drawn and listed with their state as read, and say that no draft is
offered yet; their drafts return when a run can take them. Every other part reads "set by hand; software may not move it", and the laser combiner reads "close
was sent; assumed open until a shutter that reads back shows it blocked".

`plan.schema.json` has no operation that sets an exposure, so this draft is composed,
checked and **shown with the schema's refusal, never offered for signing**. Nothing is bent to make one pass.
A schema change for them is architecture's.

## Cameras

Four panels. Camera 1 (red) shows a frame through today's live-view code only while a signed run is
acquiring; Live view is offered to the person's login and **connects to nothing until it is pressed**. The
blue camera is not opened by software yet. The fourth panel draws no traps: their mapping onto the camera is
not measured. The exposure draft is the one in Optics.

## Tweezers

The laser row, then the traps, strengths and the t-x, t-y and x-y plots from the latest run's events, each
labelled "sent". No click-to-hold and no dragging. A pattern (line, circle or grid) is a `trap_steps` draft.
Beside it are the ranges the person's safety file holds, "from your safety file"; a limit the file lacks is
shown as refused, and trap count and flicker rate are refused until a limit exists.

## Confocal

State only, from the spinning-disk channel. The shutter reads "read back; which value means closed is not
recorded".

## Piezo stage

x, y and z of the last snapshot, with when and from which run. The range is read from the safety file and
shown as "from your safety file". The time window and the screen refresh change only the screen (refresh is
off until turned on), and the read rate is a plan field. The pattern generator is "designed later".

## Where a draft goes

Where a console draft goes before the person signs it is **still to be designed**. Until then a draft exists
only on the screen it was made on.

## On the runtime's mock (card 015)

The screens follow a run the runtime executes, mock or instrument: `GET /api/instruments/latest-run` now
reads the newest run that is **still running** (its `events.jsonl`, as it grows), and with none running the
newest run there is. The console starts no run and writes no event; what leaves it is the stop on the stop
channel and the frame tap's `get`, and only from the screens that already did that.

- **Every live tab opens with what it follows.** "Following run-... (running)", or "No run is running", with the
  last run's outcome. A run that has ended leaves its values marked "as of <time>, from <run>". With no run
  there is no value to show.
- **Following re-reads the files every 2 s, only while a run is running**, and stops when it ends. A refresh
  that fails keeps what was shown.
- **Status** is a grid of panels: the summary, **Devices** (the connection state, each channel the run's last
  snapshot tried: opened with the backend that answered, or not opened and why), the status file's readings,
  and **Runtime pieces**: the idle status file's writer, check now, latest frames per camera, and the mock's
  additions (second camera, a piezo trace that moves, trap commands echoed back, confocal elements). Each
  reads "not built yet" until the files show it; the console fills none in.
- **Optics and control** gains **the light path, now** (card 017): the elements the runtime's read-back names, and
  no others. The names come from the read-back and not from a list here; an element the read-back omits does not
  appear. It reads the run's events while a run is running (the latest snapshot gives what was read, and a
  command sent since gives what was sent); outside a run, the runtime's status file, with the time it was
  written; without one, the last run's last snapshot, marked "as of <time>, from <run>". A live view leaves no
  snapshot, so the file's run, its end time and its outcome text are shown as they stand and no element.
  Nothing is requested of the stand, the host or the frame tap.
  - **Each element is in exactly one state.** *Read back*, with the time it was read. *Sent*: the laser
    combiner, which cannot be read back, is shown at the most dangerous state its commands allow (on) until
    something readable shows the beam blocked, and is never shown off on the strength of what was sent; an
    element whose newest command is later than the latest snapshot is also *sent*. *Not open*: a channel the run
    did not open (never "off"). *Not read*: a channel busy at the read, or an element the read returned no
    position for, with the reason and no value. On the mock each state is labelled the mock's own.
  - **Beside the state, exactly one of** "moved by hand" (every light-path selector and the objective; no
    control), "no draft is offered yet" (the Aura and the transmitted lamp), or "drafted" (the red camera).
  - **Beside the red camera's draft**, on every page that offers it: "The run will refuse this draft even when it is made
    and signed: nothing recorded yet tells it how to set the red camera's exposure on this microscope." The piezo's draft is
    not affected.
  - **Where the source gives an order, it is a drawing** (card 023); where it gives none, the list stays, with the
    words "No order is given for these elements, so this is a list, not a drawing of the path." The two known traps
    (the turret label that names the wrong position, splitter states that send no light to one camera) and "a
    position read back is the stand's report, not proof of which element is in the beam" stay beside either.
    "Not built yet" shows only where there is neither a snapshot nor a status file.
- **Cameras**: the frame is asked for and shown to the person's login only, and only while a run is running.
- **Piezo stage**: x, y and z as three plots of the run's snapshots ("read back"), and **a piezo move as an
  `operation` plan draft** (a step with its return, or a host-timed sine behind its approach step; the
  tolerance is the person's and has no default). It is checked against `plan.schema.json` and the person's
  range, shown, and saved nowhere.
