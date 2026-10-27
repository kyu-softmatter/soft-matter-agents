# Instruments screens (console card 012)

Area `instruments` (`web/src/features/instruments/`, hash `#/instruments/<tab>`). Six sub-tabs that do
three things only: **show, draft and stop**. Nothing here sends a command to an instrument, connects to the
live-view host, or saves a draft. A piece the runtime has not built yet says "not built yet", and the console
builds no stand-in for it.

Server routes (`server/api/instruments.py`), all reads except the draft, which composes and writes nothing:

| Route | What |
|---|---|
| `GET /api/instruments/status` | `microscope_runtime/.runtime_status/idle_status.json` as data, checked against `contracts/schemas/idle_status.schema.json` read from the tree. Absent is `none`, an invalid file is `invalid` with why, and no reading is taken from either |
| `GET /api/instruments/limits` | the person's own limits from `microscope_runtime/envelope/safety.json`: the piezo range and the tweezers ranges. Never written into code; a limit the file lacks is `null` |
| `GET /api/instruments/latest-run` | the newest microscope run's events: the traps and strengths last sent (all "sent": the tweezers report nothing back) and the piezo snapshots (read back) |
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

A picture of the stand in three rows, each part showing the reading of its channel in the status file, or
"unknown". Four parts take no channel: the stand's parts share one channel, and which of the two widefield
channels is the LED and which the lamp is not recorded, so neither part takes either. Double-clicking a part
opens the tab it belongs to (Light source, Filters, Magnification, Camera).

A draft is offered where the runtime's list of what software may command names the part: the Aura LED, the
transmitted lamp (state and intensity) and the red camera's exposure. Each says **refused until you write a
limit**. Every other part reads "set by hand; software may not move it", and the laser combiner reads "close
was sent; assumed open until a shutter that reads back shows it blocked".

`plan.schema.json` has no operation that sets a light or an exposure, so these three drafts are composed,
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
    control) or the draft link (the Aura and the transmitted lamp only).
  - **Beside every draft link** for the Aura, the lamp and the red camera, on every page that offers them: the
    draft can be made and signed and the run will refuse it, because the runtime cannot yet match the element to
    what software may command. The Aura stays refused longer, until which light engine feeds which channel is
    settled. The piezo's draft is not affected.
  - The registry gives no order, so it is a list. The two known traps (the turret label that names the wrong
    position, splitter states that send no light to one camera) and "a position read back is the stand's
    report, not proof of which element is in the beam" stay beside it. "Not built yet" shows only where there
    is neither a snapshot nor a status file.
- **Cameras**: the frame is asked for and shown to the person's login only, and only while a run is running.
- **Piezo stage**: x, y and z as three plots of the run's snapshots ("read back"), and **a piezo move as an
  `operation` plan draft** (a step with its return, or a host-timed sine behind its approach step; the
  tolerance is the person's and has no default). It is checked against `plan.schema.json` and the person's
  range, shown, and saved nowhere.
