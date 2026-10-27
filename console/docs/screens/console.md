# Console screen contract (T-100 stage A)

> **Renamed at console card 008:** this screen is now the area `questions` (`web/src/features/questions/`, hash `#/questions/...`; the file keeps its name here). `#/console` lands on it as any old hash does. Its own redesign is a later card.

Area `console` (PLAN.md §2 F1, §9 WP-F). This is the contract between the screen, the server router
`server/api/console.py` and the AgentStore. The panels themselves are in `docs/ui-spec.md` 7.1, which is
not repeated here (on main since T-004 merged).

Sources read: AgentStore `agents/store.py` (T-008, `exec6/T-008-agent-store` 28eaec8), server skeleton
`server/app.py` and `server/api/__init__.py` (T-009, `exec7/T-009-server-skeleton` a4e3671), roles and
control `auth/roles.py`, `auth/control.py` (T-018, in progress in exec13), web shell `web/README.md`
and `src/app/route.ts` (T-010 a5fb986, in review).

## Endpoints

All are mounted at `/api/console` by T-009's area-router mechanism. Bodies are the store dataclasses'
`to_dict()` output wrapped in pydantic models, so the OpenAPI types reach `web/src/api/`. Card contents
(`Card.data`, `RunDetail.records`, `InboxThread.status`) stay `Any` and pass through untouched; grades and
`numbers` are never re-computed (PLAN §6 item 3, ui-spec 7.1 "Number table").

| Method, path | Query / body | Response | AgentStore |
|---|---|---|---|
| `GET /store` | | `{store, writable}`: `"mock"` / `"soft-matter-agents"` (see "Rules") | store kind, `store.writable` |
| `GET /questions` | `agent=microscope\|simulation`, optional. Omitted: both, merged newest first | `QuestionSummary[]` | `list_questions(agent)`, once per agent |
| `GET /questions/{qid}` | `version=N`, optional. Omitted: latest | `QuestionDetail` (`summary.versions` lists the others) | `get_question(qid, version)` |
| `GET /runs` | `agent=`, optional, as for questions | `RunSummary[]` | `list_runs(agent)` |
| `GET /runs/{agent}/{run_id}` | | `RunDetail` (`not_opened` lists big or unreadable records) | `get_run(agent, run_id)` |
| `GET /runs/{agent}/{run_id}/stream` | `since=N` (the last answer's `total`) | `RunStream`: `followed`, `state` (`running` / `ended` / `not_followed`), `ended_how`, `can_stop`, `stop_unavailable` (words), `frame_tap`, `events[since:]`, `total` | `run_stream(agent, run_id)` (`agents/sma_run.py`) |
| `GET /runs/{agent}/{run_id}/frame` | | `image/jpeg` of the run's latest frame (binned, 0.5–99.5 percentile), metadata in `X-DinoAF-Frame`; 204 before the first frame | the run's frame tap |
| `POST /runs/{agent}/{run_id}/stop` | `{reason}` | `StopOut`: `outcome` `begun` / `refused` / `no_answer`, `message` | the run's stop channel |
| `GET /inbox` | | `InboxThread[]` with messages | `list_inbox()` |
| `GET /approvals` | `agent=`, optional | `Approval[]` (the seats' `approvals/` plan_approval cards, newest first; `plan_found`: a plan card of the question hashes to `plan_hash`) | `list_approvals(agent)` |
| `POST /question-requests` | `{words, addressed_to}` (nothing else is accepted) | `201`, `QuestionRequest`: `contracts/schemas/question_request.schema.json`, exactly as written | `write_request(store.request_write_folder(), ...)` |
| `GET /question-cards` | | `{requests: RequestCard[], questions: QuestionProgress[]}`: requests written in the console (newest first), and the agents' questions with five steps | `read_requests`, `list_questions`, `get_question`, `list_runs` |
| `GET /signing` | | `SigningState`: `person_named`, `is_person`, `practice`, `approvals_folder` (the screen's offer to this login) | `settings.json` `person_login`; `approvals_target_present()` |
| `POST /sign-check` | `{qid, plan_hash, password}` (nothing else) | `SignCheck`: `outcome` `written` (with `file_name`) or `practice_signed`, `message`. **Writes one approval on a real tree, nothing under the mock store** | `AccountStore.person_login()`, `LoginSessions.check_password` |
| `GET /suggestions` | | `[{text, kind}]`, `kind` `earlier question` or `registered name`: strings already on disk | `read_requests`, `registered_names()` |

Error mapping (all T-009b refusals: `detail = {code, message}` and the `X-DinoAF-Refusal` header):
`NotFoundError` → 404 `not_found`; blank or too-long words (`RequestError`) → 422 `invalid`
(a bad `addressed_to`, an extra key or a lone surrogate is FastAPI's own 422, with the input left out of
the answer when it cannot be written back); an id taken five times → 409 `request_exists`; a store that
cannot take a request → 409 `read_only_store` with
`"Submitting to soft-matter-agents is not connected yet (read-only)"`; other `StoreError` → 500
`store_error`.

Versions: the picker lists every entry of `summary.versions` as the store returns it (1 for unprefixed
files, N for any `vN_` prefix; v4_, v5_ exist). The screen assumes no upper bound and no fixed set, unlike
the `r1`/`v2_`/`v3_` example in ui-spec 7.1.

The status and date filters and the two-version diff (ui-spec 7.1) run in the browser over these
responses: the list is small, and the diff fetches `?version=` twice. No server diff endpoint.

Refresh: when the area opens and on the `"Refresh"` button. No polling, no file watching (ui-spec 7.1).
After a successful send the screen re-reads `GET /question-cards` and `GET /suggestions`. One exception: a running followed run
(below) is read again every second until it ends.

## The question window (console card 010, plan.md 4.5)

The first screen of the Questions area is one field ("Your question"), an "Ask" choice (let the agents
decide, the microscope, the simulation, the librarian) and Send. The old form's purpose and observable
fields are gone: the agents settle those. A card per question sits below it.

**Send to the microscope or the simulation delivers the question into that agent's inbox** (card 019, the
person's decision in `plan.md` 7.1.1); **Send to the librarian or to "Let the agents decide" writes a question
request** into the console's own folder and delivers nothing. The request is written exactly in the shape of
`contracts/schemas/question_request.schema.json` and no other: `id` is `qr-<UTC yyyymmdd>-<UTC hhmmss>-<4 random lowercase letters or digits>` and the file
is `<id>.json`; `words` is the text exactly as typed (not trimmed, not rewritten; only a blank field is
refused); `asked_by` is the session's login and its console role; `asked_at` is UTC; `addressed_to` is the
choice. There is no key the schema does not name and no claim that the asker is the person's own.
Until the admin card brings console-side roles the role is derived from today's role: admin and operator
get may_ask, may_draft, all three agents and may_ask_model_run; a viewer gets none and cannot send.

- **Where a request goes.** `--store sma`: `<root>/console/requests/questions/`. `--store mock`: the mock store's own
  write folder (a temporary one by default), in the same layout, which is the practice copy. The shipped
  sample (`mock_data/console/requests/questions/`, two practice requests) is read, never written, and
  the real tree is not written under the mock.
- **Atomic, never rewritten.** The file is written whole to a temporary name in the same folder and then
  linked to its final name; a link to a name that exists fails, so an existing id is refused
  (`RequestIdTaken`; the route tries another suffix up to five times, then 409). A failed write leaves
  neither a file nor a temporary.
- **Who may send** stays the server's present rule (the access middleware, then `server_action_why` for
  `submit_question`: operator or admin, on the microscope PC), with the refusal said in words. A viewer is
  told the login can only look; another computer is told questions are asked from the microscope computer.
- **A delivered question** is one `console_question` item, `contracts/schemas/console_inbox_item.schema.json`
  exactly, written whole into `<root>/<agent>_agent/console_inbox/<item_id>.json` and nowhere else of the
  agent's tree. `item_id` is `ci-<UTC yyyymmdd>-<UTC hhmmss>-<4 random lowercase letters or digits>`;
  `question_id` is `mic-` or `sim-`, the UTC date, `-c` and three digits, the next after the highest that
  date already carries in that agent's inbox (the two agents count apart). After `c999` nothing is written and
  the asker is told that the agent has had 999 questions from the console today and to ask again after
  midnight UTC. `words` are as typed; `asked_at` is UTC; `asker_mark` is `other_login` (only the person's own
  login is ever marked as the person); `attachments` is empty. The item is checked against its schema before
  it is written.
- **How it is written.** The inbox folder must already be there: the console never makes it, and without it
  nothing is written and the asker is told "This agent's inbox is not there, so nothing was sent." The file
  is written whole under a temporary name in `console/requests/outgoing/`, **linked** to its final name in
  the inbox and the temporary name removed; a taken name gets another `item_id`, up to five times. An item
  is never rewritten, renamed or removed (a correction is a new item), and the console commits nothing.
  Reading the inbox, numbering and linking happen under one lock in the server; one console server runs
  against a tree. Under `--store mock` the item goes into the mock's own write folder as
  `<agent>_agent/console_inbox/`; the shipped sample is never written.
- **What the form says after Send.** To an agent: "Sent to the microscope as question mic-20261026-c001."
  (or the simulation, with its id). To the librarian: "Not delivered: the console does not send to the
  librarian yet." To "Let the agents decide": "Not delivered: no agent takes a question left to the agents
  yet." The route's answer tells the two apart by its `artifact` (`console_question` or `question_request`).
  The audit line `question_submitted` carries the login, `origin: "console"`, the addressee, and for a
  delivery the `item_id` and `question_id`; for a request the request id; never the words.
- **Autocomplete** offers only strings already on disk: the `words` of earlier requests and the quantity
  names in `contracts/quantities.json`, each labelled "earlier question" or "registered name". Never a
  model's completion and never the store's contents (the cards' titles are not offered). The list is read
  once when the screen opens and after a send, and matched in the browser, case ignored; an empty field
  offers nothing. Choosing a suggestion inserts its text (an earlier question replaces the field, a name
  replaces the word being typed); it registers nothing and sends nothing. A file in the requests folder
  that is not a request is skipped, never offered.
- **The cards.** A request written in the console: the words, who asked, when, whom, "written in the
  console · not delivered", and that every run from it waits for the person's signature. Beside them, **every
  item in the two inboxes**, newest first by `asked_at` (`item_id` breaks a tie): the words, login, time,
  agent and question id, with exactly one state read from the agent's `answers/` (`console_answer` files that
  name the item): "delivered · not answered yet"; "taken up as <question id>"; "refused · <the reason as
  written>"; or "an answer is on disk and cannot be read", which the card says rather than guess. An
  agents' question on
  disk, with a five-step bar read from the files: asked (a goal card exists), designed (a plan card
  exists), signed (a plan_approval card for that plan's hash exists and its status is APPROVED), run (a
  run log names the question), result (a result card exists). When the runs folder cannot be read the run
  step says "not known": that is not "no run". A click opens today's view of an agents' question (the
  detail is card 011).

## One question and the sign dialog, writing nothing (console card 011; plans 006 and 007)

A question's card opens its page (`#/questions/questions/<qid>`; a request written in the console opens
`#/questions/requests/<id>`, where nothing has started). The page shows the question verbatim (the goal
card's own words), who asked and when, the five steps of card 010, a **summary put together from card
fields** (the goal's purpose and observable, the plan's steps) labelled as such, and **every card made
from the question, one row each**: goal, design (axes), synthesis, each plan and its revision, refusals,
approvals, runs that name the question, results, other cards, and the bridge's rounds for the goal's
thread. A row opens on a click to its main fields. Anything a card says the assistant wrote ("author" or
"origin" naming the assistant) is labelled "Written by the assistant". A number's `source` is also said
in the person's word: computed, guessed (assumed, operator recall), measured (calibration, result),
measured elsewhere (the library), read back, sent; a source it does not know is shown as written. The old
card tabs and the two-version diff are gone; the version picker stays when a question has several.

- **Who sees Sign.** Only the login named `person_login` in `settings.json` outside the tree (the same
  file as `admin_login`). With the key absent, or not a plain id, no login sees it and the box says the
  person's login is not named yet. Any other login sees "Waits for the person's signature" and no
  button. This decides the screen only: the runtime decides from the person's own file beside the safety
  policy, never from the console's settings (plan.md 6.1). `POST /sign-check` repeats it: 403
  `person_not_named` or `not_person`.
- **A plan waiting.** A plan with no approval of its fingerprint whose status is APPROVED (a draft is not
  a signature) shows a box with "Review and sign".
- **The dialog** shows the plan and its revision, its steps, its light (the light sources among its
  devices, and the numbers named for power, illumination, laser or exposure), what cannot be undone (an
  action that does not say it is reversible is not trusted to be), and the **full fingerprint**: the sha256
  of the plan card with `status` removed, the rule of `contracts/validate.py`'s `card_sha` and of a
  plan_approval's `plan_hash` (a test runs that function's own source against the contracts' example plan
  and its approval's `plan_hash`). A password field is typed again and never pre-filled, and is cleared
  after every try.
- **Numbers in this plan that nothing sets** (card 021). After the devices the dialog lists each number the
  plan card carries that nothing at run time uses: one line `name: value unit (provenance)`, the provenance
  in words from the card's own `numbers[i]` entry at the list's `from` (the list carries no source), a unit
  of null or "1" printing nothing. The list is `QuestionDetail.unused_numbers`, worked out in
  `get_question` from **the same plan dict the fingerprint hashes**, so the two are always of one card.
  It is `sma_files.unused_numbers`, a copy of `unused_numbers(plan)` in `contracts/validate.py` at
  `f5699603` (follows the rule as data, imports nothing from `contracts/`); `tests/agents/test_unused_numbers.py`
  holds the copy to `contracts/examples/unused_numbers_case_*.json` and to the three rejected cases. Three
  states: no plan card, no list and no section; a list, possibly empty ("Every number in this plan is one
  the run sets, hands to a step, sizes itself by, or checks against."); and **could not be worked out**,
  with a reason in words, wherever the rule would raise (an action, criterion or number that is not an
  object), shown as an alert. **It decides nothing**: no control is disabled by it, `POST /sign-check` and
  `signing/` do not read it. Read-only: no run log, derivation or snapshot is read, and nothing is written
  into a plan card.
- **Sign writes one approval, or refuses and writes nothing** (card 013). The route keeps the name
  `sign-check`. The order is: the person's login; the store is real; the plan is the question's current
  one by fingerprint (409 `plan_changed`, "The plan changed; review it again."); the approvals folder;
  then the password, counted by the login's own attempt limit (401, then 429 with Retry-After); then the
  person's own login file `microscope_runtime/envelope/console_login.json` (409 `login_file_missing`,
  `login_file_invalid` or `login_file_other_login`; the console reads it and never writes it); then an
  approval of that name is not already there (409 `already_approved`). The fingerprint and the folder come
  before the password so that a password is counted only for something that could be signed. All hold in
  the same request, or nothing is written. The answer, `written`, says: "Approval written. The runtime
  reads it from disk now. Commit it yourself when you choose: no session may commit a file under
  approvals/." and names the file, `appr-<qid>-r<revision>.json`. Under the mock store a practice login is
  shown as signed, with "Nothing was written". No password, and no hash of one, is in a file, a response,
  a log or an audit line; the audit line `approval_written` names the login, the question, the plan, its
  revision, its fingerprint and the file name (a practice signing stays `sign_checked`).
- **What is written.** One `plan_approval` card, built to `plan_approval.schema.json` and validated
  against it first, with `approved_by` the login, `approved_at` UTC now and
  `signed_through: {via: console, login}`. It is written whole under a hidden temporary name that does not
  end in `.json` (the runtime reads every `*.json` there), then linked to its name so a file is never
  replaced; nothing else in the folder is touched.
- **No approvals folder.** Only `microscope_runtime/approvals/` counts. Without it in the tree the console
  reads, the dialog says nothing can be signed and offers no form and no other place; the old
  `microscope_agent/approvals/` is read for display and is not a place to sign.
- **The writer is part of the person's guard.** `src/sma_console/signing/approval_writer.py` is the one
  place the console writes into `microscope_runtime/`, built on the person's word (Q-20261024-office-01,
  `b4f340ee`). Any change to it needs the person's word through the intake seat.

## A run soft-matter-agents executes (C-04, C-08)

soft-matter-agents plan.md 11-25: a run its orchestrator follows writes `runs/<run_id>/events.jsonl`
(`run_started` … `run_ended` with `how` = completed, aborted_by_monitor, stopped_from_outside or failed),
announces a loopback stop channel and a frame tap in `run_started`, and keeps going if a viewer drops.

- The run list shows such a run by its stream while it has no `log.json`: outcome `running`, then `how`.
- A microscope run's detail starts with a "Followed run" box: state, the events so far, the latest
  frame (only while the run's own acquisition produces frames; the tap never snaps and the console
  opens no camera, OD-13), and `"Abort this run"` with an optional reason.
- Abort sends one line on the run's own stop channel; the run calls the same abort() as its other stop
  paths and records `stop_requested` with the reason and who pressed it. The server treats it as a stop:
  the microscope PC always, a logged-in remote viewer when remote abort is on (D13), otherwise 403.
  The answer is shown next to the button: began to abort / refused (the run records why) / no answer
  in 15 s (watch the events).
- `"Closing this page does not stop the run."` (OD-30): nothing sends a stop except the button.
- An ended run: the button is disabled with `"the run has ended (<how>)"`. A run without events.jsonl:
  no button, and `"Abort: this run is not followed (no events.jsonl), so the console has no stop channel
  for it; stop it at the instrument or in the operator terminal"`. Simulation runs have no Abort here.
- Nothing is written in the soft-matter-agents tree (the audit line goes to the console's own folder).

## The shell around every screen (card 008, plans 006 and 007)

The app is a **left sidebar** and a **footer on every screen**; the header with twelve areas is gone.

- **Sidebar**, "Soft-matter agents" at the top, then Questions, Instruments, Experiments, Simulation,
  Library, Results, and **Admin below a rule, for an administrator only**. At phone width it stacks above
  the screen. An administrator-only area is not opened for anyone else: `#/admin` opens Questions.
  Old hashes (`#/console`, `#/hardware`, `#/map`, `#/accounts`, ...) land on Questions, as an unknown one
  does. Experiments and Library are plain screens (title, one sentence, "not built yet") that request
  nothing. Instruments has its six screens since card 012 (`docs/screens/instruments.md`).
- **Footer**: STOP at the left (`StopAllRuns`, the one stop the lock screen has; one request to
  `POST /api/console/runs/stop`, no confirmation), a chip "Example data" while `GET /api/console/store`
  says the store is `mock` (never on a guess: an unreachable or other store shows none), and at the right
  the logged-in user's name and Log out. No password is shown or filled.
- **Left out of the shell**: the lights reading, the assistant's status, the take and release control,
  the focus readout, the status bar, the last-shutdown notice and the assistant side panel. The modules
  stay in the tree and nothing in the shell renders them. The last-shutdown notice read
  `last_shutdown_lights` from the engine status, and **the only engine here, the placeholder, never sets
  that field** (its snapshot in `server/__main__.py` has no such key, and the field is `None` in
  `server/schemas/state.py`), so the notice had nothing real to show and went with the status bar.
- Gone with the old header: the user menu (Lock, Manage accounts) and the "remote · read only" badge. The
  idle lock still works, and a remote login is still refused by the server and the refusal shown in words.
- The seven retired areas (hardware, sample, map, objective, patterns, tweezers, sessions) and their
  "not connected here" notice are removed from the tree.

## Where the microscope's runs and approvals are (card 005, plan.md 15)

The microscope's `runs/` moved to `microscope_runtime/runs/` in card 080, and its `approvals/` moves to
`microscope_runtime/approvals/` later, in the person's own commit. The shapes did not change. One rule,
`agents/layout.py` `run_side_folder`, says where each is read from, and every reader asks it: the run
list, run following, both stops, the approvals and the live-view lists. **Each folder is read from
`microscope_runtime/<folder>/` when that folder exists, else from `microscope_agent/<folder>/`, each
decided on its own**, so runs moved with approvals not yet reads correctly. One place is read, never both
merged. The old place is for a tree from before the move (a scratch copy, the mock sample); a later card
removes it after the person's step. The simulation seat keeps `simulation_agent/`, and the questions, the
inbox and the plan cards stay in `microscope_agent/`.

**A runs folder in neither place is not "no runs".** The run list, a run's detail and "Stop all runs" say
that the project's runs folder was not found (404 `runs_not_found` for the list and the stop), and the
lock screen shows it in words: the stop was not sent, and it is not known whether a run is running. An
empty runs folder that exists is still "No run is running".

## Stop all runs, with no login (card 004)

The person asked for a stop on the lock screen that works without a login (committed at `cee4f8c1`)
and for it to stop at once, with no confirmation step (`27029ddc`). `POST /api/console/runs/stop`
sends the one pinned stop line (`run_interface.schema.json`, `stop_request`) to every microscope
run whose `events.jsonl` says it is running, each on the stop channel that run announced, all at
once. It answers each run's id and outcome (`begun`, `refused`, `no_answer`, `unreachable`, or
`no_channel` for a running run that announced none and so got nothing), or that nothing was running.
The button, "Stop all runs", is on the lock screen and on the setup and logged-out screens; one
press makes one request, and a second press while it is in flight does nothing. It lists nothing
first: no read works without a login, and none was added.

- **Who may ask.** From the microscope PC with no login, always. From another computer only with a
  login and with remote abort on (D13), as for the per-run stop. A page from another origin is
  refused before anything else.
- **It does one thing.** POST only, and no body, no query, no run id and no reason: the server
  composes the reason, "Stop all runs pressed (by <who>)", with "the microscope PC (no login)" when
  there is no login. Anything else is 400 `stop_takes_nothing` and reaches no run.
- **Every stop is audited**, one `sma_stop_all` line per run, and one with outcome `none_running`
  when none ran. A failing audit log never holds a stop back: the answer then says `audited: false`.
- **With the mock store** the server answers 409 `not_connected` and sends nothing; the lock screen
  cannot know the store before it asks, because no read works there.
- **The guard on the person's words**: a test lists every write the app mounts and fails if any one
  other than the login and setup paths, the shutdown from this PC and the two stops works without a login.

## Microscope live view from the console (C-15, soft-matter-agents card 062)

The person decided on 2026-10-07 that a live camera view is switched on and off from the console,
outside a plan too, to help find the sample. The Live area shows a "Microscope live view" bar:

- `GET /api/console/live`: whether soft-matter-agents' live-view host is running (its address file
  `%LOCALAPPDATA%\soft-matter-agents\live_host.json`, or `--live-host-file` / `--live-host
  127.0.0.1:N`), and the live-view lists the person approved (JSON files in
  `microscope_agent/approvals/` marked `"artifact": "live_view_list"`, the shape of
  soft-matter-agents `contracts/schemas/live_view_list.schema.json`), each with the person's values.
- `"Live on"`: `POST /api/console/live/on {sha256}`, an operator action on the microscope PC
  (`/api/permissions?ops=live_on`). The console names the list by its sha256 and nothing else; the
  host checks the list and starts an ordinary run, then the screen follows it (frames from its tap).
  A refusal is shown with the host's reason (`"a run holds the lock"`, ...).
- `"Live off"`: the run's own stop, `POST .../runs/microscope/{id}/stop`. The text says: `"Live off
  stops the run (lamp off, shutters closed). Closing this page does not stop it; it ends by itself
  at the frame ceiling."`
- Fluorescence is not in the default list; a list with any other light is the person's separate
  approval on the soft-matter-agents side. Nothing is written in that tree by the console.

## Which store (C-03)

`python -m sma_console.server --store sma --sma-root DIR` (default root `$DINO_AF_SMA_ROOT`, else the
repository this console sits in: the first folder above it that holds both `contracts/` and `console/`; with none found the start-up stops with that reason) shows the soft-matter-agents files themselves: questions, runs, inbox and approvals of
both seats, read only. A root with no seat folder stops the start-up with the reason. Without `--store`
the console shows the mock sample (`agents/mock_data`, pinned at baf6f1e). `GET /questions/{qid}` carries
`plan_hash` (sha256 of that version's plan card with `status` left out, as soft-matter-agents computes it)
and every approval naming the question; the screen says which plan each approval signs. JSON is read as
utf-8-sig. The console writes nothing in that tree: approvals are the person's, written outside it.

## Rules: remote, role, read-only

Reads (`GET`) are open to every logged-in user, local or remote, any role (ui-spec 7.0 remote table).

Send is refused in this order; the first reason is the one shown (ui-spec 7.0 "Disabled reasons"):

Before anyone clicks, the screen asks the shared `GET /api/permissions?ops=submit_question` (T-009b, backed
by T-011's check and T-018's `SUBMIT_QUESTION` plus loopback) and shows its `reason` as written. The console
router computes no role, control, session or remote rule itself; it adds only its own rule, the read-only
store, through `GET /api/console/store`. Reason order on screen: the shell's read-only flag (`useReadOnly`,
`"Read-only: remote view"`), then the permission reason (`"Checking permissions…"` while loading,
`"Permission check unavailable"` on error or a missing op), then the store's. Reads go through the shell's
client (`useClient().get`); the screen re-reads when the event socket reconnects after a drop.

| Check | Where | Status on submit | Screen text |
|---|---|---|---|
| Request is not from the microscope PC | the shell's read-only flag; the access middleware on the POST | 403 `remote_view` | `"Read-only: remote view"` |
| Not logged in, screen locked | `/api/permissions`; the access middleware | 401 `login_required`, 423 `locked` | the permission reason |
| Role below operator (viewer), D16 | `/api/permissions`; `server_action_why(me, "submit_question")` in the route | 403 `role` | the permission reason, shown next to the form |
| A store that cannot take a request | `/api/console/store`; `store.writable` in the route | 409 `read_only_store` | `"Submitting to soft-matter-agents is not connected yet (read-only)"` |

- `AgentStore.writable` now says whether a question request can be written (card 010): both stores say
  yes, because a request goes into the console's own folder, never an agent's. The 409 rule stays for a
  store that cannot take one.

- D16: the POST route calls `server_action_why` (T-018 `SUBMIT_QUESTION` plus loopback) on the server.
  Disabling the button is only the display of the permission answer. Device control (the control token)
  is not needed: submitting moves nothing. An open experiment session is not needed either (PLAN §6 item 12
  covers commands that move hardware).
- The web submit goes through the shell's `client.post`: only a 403 `remote_view` switches the app to
  read-only; every other refusal is shown next to the form and changes no global state.
- An accepted send goes to the audit log as `question_submitted` with `user_id`, `origin: "console"`, `target` and
  the new request id (PLAN §5 "The three logs"), never the words.
  Refusals are not logged by this route: the audit kinds have none for a refused question.

## Prompt context (X1)

The screen calls the shell's `useScreenContext(details)` (`src/app/screenContext`, T-010 `web/README.md`);
the prompt box (T-014) only reads it. Details: selected `qid`, `version`, selected card `kind`
(`goal`, `axis`, `plan`, `synthesis`, `refusal`, ...), selected `run_id` and its `agent`. Short ids only;
no card bodies and no images (D7).

## Links out

- Simulation run detail → the T-012 simulation area for progress, trajectory and download (gap 6).
- "Experiments in this repository" panel (samples and experiment sessions) → `sample` and `sessions` areas. Not served
  by AgentStore; stage B shows links only (gap 5).

## Gaps (requests)

1. ~~T-008~~: closed, `AgentStore.writable` (T-025).
2. ~~T-009~~: closed, `create_app(agent_store=...)` and `AgentStoreDep`.
3. ~~T-009 / T-018~~: closed, `Login`, `IsLocal`, `server_action_why` (T-009b).
4. ~~T-018~~: closed, `AuditKind.QUESTION_SUBMITTED` covers the console submit and prompt boxes. There is
   no kind for a refused question, so refusals are not logged here.
5. **T-019 / sample**: the "Experiments in this repository" list has no read API yet; stage B links out only.
6. ~~T-010 / T-012~~: closed. The link is `#/simulation/runs/<run_id>`; the shell passes `#/<area>/<rest>`
   through (no link helper) and T-012 stage 2 reads the suffix.
7. ~~T-014~~: resolved by the shell's `useScreenContext` (T-010); nothing waits on T-014.
8. **T-008 / T-025, store**: ui-spec 7.1 list columns that the summaries do not carry: `purpose`, `intent`,
   `observable.name` of the latest goal (`QuestionSummary`), and `approval.kind` of the log (`RunSummary`).
   Closed: T-025 sends `purpose`, `intent`, `observable_name`, `approval_kind`; the lists show them ("—"
   when a card has none).

Web types: the router's models and `PermissionOut` are not in the committed `web/src/api/schema.ts` yet, so
`features/console/api.ts` keeps hand copies until T-010 regenerates it after this router merges.
