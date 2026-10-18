# Draft: the operator console moves to a top-level folder, in the same step as the `microscope_runtime/` split

Written 2026-10-17 by architecture-office-20261016-2 (the GUI mockup seat; `paths`:
`docs/drafts/` only). A draft awaiting its section holders, per `plan.md` 7's rule for this
folder: its content moves into the sections it names, by their holders, and the draft is then
deleted. Sections touched: 7 and 11-25 (architecture-20261007-1), 14 and 6 (architecture-20261003-1),
`contracts/seats.json` and the root `CLAUDE.md` (architecture-20261007-1); the validator and the
cards (manager-microscope). **What is decided and what is not.** The *timing* is decided -- the
person, 2026-10-17, section 0's fourth sentence: the console moves now, in the same step as the
`microscope_runtime/` split (section 3). The *folder name* and the *ownership* were answered the same
day in architecture-20261003-1's window, from options that seat put, and are recorded here **as
relayed** (section 8): `console/`, and option A with a new manager -- a fifth boundary `console` with
its own execution seat(s) and a dedicated `manager-console` holding `console/tasks/`. Section 5 keeps
the options as the record of what was put. What remains is the person's act of seating: the console
seats and the manager-console are opened and seated in the person's own windows.

## 0. The person's words

In this seat's window, 2026-10-17, in order:

- "지금 GUI는 어디에 종속되어있나?" -- where does the GUI belong now, what is it tied to?
- "GUI를 가장 상위폴더로 옮기는게 좋을까?" -- would moving the GUI to the top-level folder be better?
- "병합 뒤 별도 단계로 콘솔을 최상위 폴더로 옮기는 설계 초안을 docs/drafts/에 잡아줘. 소유권 선택지도
  같이." -- draft, in docs/drafts/, the design for moving the console to the top-level folder as a
  separate step after the merge; the ownership options with it.

The third sentence is what this draft answers. It was a request for a draft, not the decision to move.

The decision came the same day, after the draft was written and after section 8's relay, in this
seat's window:

- "콘솔도 지금 microscope_runtime 분리 작업과 같은 단계에서 자기 최상위 폴더로 옮긴다. 초안의 '병합 뒤'
  조건을 그렇게 고치고, 실시간 의사결정 세션에 그 말을 전해줘." -- the console, too, moves to its own
  top-level folder now, in the same step as the microscope_runtime split; correct the draft's
  "after the merge" condition accordingly, and pass those words to the real-time decision session.

Section 3 carries it. The words went to architecture-office-20261017-1 (section 15's writer) and
architecture-20261003-1 (section 14's holder) the same hour.

## 1. Where the console is, and what it depends on (facts, 2026-10-17)

Two things are called "the GUI" today and they are in different places.

**The console that exists as code** is dino-autofocus's, inside the imported subtree:

| Part | Path | What it is |
|---|---|---|
| Web app | `microscope_agent/autofocus/web/` | React 19, Vite, three, TypeScript; areas `console, hardware, sample, map, objective, live, simulation, results, patterns, tweezers, sessions, accounts` (`web/src/app/areas.ts`) |
| Server | `microscope_agent/autofocus/src/dino_autofocus/server/` | FastAPI; `api/console.py` reads questions, runs, inbox and approvals through the `agents/` data layer; `api/hardware.py`, `map.py`, `objective.py`, `sample.py`, `simulation.py`, `patterns.py`, `sessions.py`, `auth.py`, `assistant.py` |
| Data layer | `.../dino_autofocus/agents/` | `MockStore` (default) and `SmaFiles`, which "reads the soft-matter-agents files and never writes them"; `sma_run.py` follows a run's `events.jsonl`, frame tap and stop channel; `sma_live` for live view |
| Assistant | `.../dino_autofocus/assistant/` | the in-app model that only proposes; an action reaches the engine after a person confirms it |
| Screen contract | `microscope_agent/autofocus/docs/screens/console.md` | endpoints, the read-only-store rule (409), card contents passed through untouched |

What it depends on: dino's own `pyproject.toml`, `uv.lock` and `web/package.json`; its own auth and
audit middleware; and, from this repository, **data only** -- `questions/`, `approvals/`, `runs/`,
read as files -- plus the run interface 11-25 built: `events.jsonl`, the loopback stop channel, the
frame tap, the `run_started` keys that its tests pin (14, "How to work here", last bullet).

To the validator it is one imported subtree: `IMPORTED_SUBTREES = ("microscope_agent/autofocus/",)`,
`ALLOWED_PATHS` has `^microscope_agent/autofocus/.+$`, and `seat_boundary_of` puts every path under it
in the **microscope** boundary (`AGENT_OF_PATH`). The checks that read cards or agent source do not
read inside it (7, `autofocus/`).

**The console's design** -- the mockup this seat builds -- is not in the repository at all. It is a
claude.ai Design artifact on mock data. It is a design of a *whole-system* console: overview; a
question's ask, status, design, knowledge, results and list; the person's decisions (inbox, permits
and limits); the microscope (run, focus search, light path, live hardware, sample map, sample,
objective change, devices, manual sheet); the simulation; the bridge; results across questions; the
librarian as a library and as a service; and the meta-harness board. Most of those screens show
what no microscope seat owns.

## 2. Why move it

(a) **The console reads all four agents, and the boundary rule puts it inside one.** 6.2 rule 3: a
session writes only inside its own agent directory. With the console under `microscope_agent/`,
only a microscope seat may edit the simulation, bridge, librarian and harness screens, and the
simulation, bridge and librarian seats may not touch a screen about their own work. The place and
the rule disagree; the screen is not untidy, it is misplaced.

(b) **It is a read-only consumer, by rules already settled.** 11-25's four rules hold wherever it
sits: it writes nothing into this tree (a draft reaches `approvals/` only through the person), a
draft is an ordinary plan card, every command goes through the orchestrator, and a number it shows
carries its source. Nothing in the system depends on the console; the console depends on every
agent's outputs. In 7's dependency picture that is a **leaf above all four agents**, the mirror of
`contracts/`, which is a root below them. A leaf does not belong inside one of the nodes it reads.

(c) **The gate's shape.** Today the whole subtree is judged as an import: the checks that read agent
source skip it. New console code written here after the import inherits that skip -- a widening
nobody chose. A console-only card shape, which rule (2) forbids, would not be caught there. A
top-level `console/` is this repository's own code and is judged as such (7.2).

(d) **The instrument side is not the console.** The run interface -- events, stop channel, frame
tap, live view as a preparatory run -- is the orchestrator's and stays in `microscope_agent/`. The
console only consumes it. Splitting makes that contract explicit: today 14 says a change to the
`run_started` keys "updates the console and its tests in the same commit", which is a one-boundary
convenience that a two-boundary layout cannot keep; it becomes a pinned interface in `contracts/`
(section 4, step 3) and two commits that meet at it.

## 3. When: now, in the same step as the `microscope_runtime/` split (decided 2026-10-17)

**The person's decision** (section 0, fourth sentence): the console moves to its own top-level folder
**now**, in the same step as the `microscope_runtime/` split that section 15 is writing -- not after
the dino-autofocus merge's after-work, which is what this draft's first version proposed. The 2026-10-15
decision -- "현미경 에이전트 안", inside the microscope agent -- is thereby replaced for the console
by a new decision of the person's, recorded here with the words; the import commit stays the ruling
record for the code (10.2), and `git subtree` history stays reachable through rename detection
whichever folder the files sit in.

**What the first version gave as reasons to wait, kept as the costs the decision accepts:**

- 14's order is card 069 → card 076 → the next bench visit → the first focus-search plan, with the
  public target 2026-10-23, and the import's own after-work is cards 071-075 (071 done at `8f94789`,
  074 closed at `4c62924d`; read 072, 073 and 075 for where they stand). Moving the console while any
  of those is open moves that card's paths under it: **the moving card lists every open card whose
  paths it touches, and each is repointed in the move commit or says in its own text where its paths
  went.**
- A bench card that cites a path inside the console's part of `autofocus/` cites it by the old path
  until repointed; the move commit's message carries the old→new path list so a citation still
  resolves through it.

**How it sits in 15's sequence** (as relayed, section 8): 15 moves nothing from `autofocus/` itself,
and its step 2 pins the run interface in `contracts/` before its own move. The console's move is
**the same step** in the person's words, so it rides on 15's sequence after that pin: the pin, then
15's move of `src/` into `microscope_runtime/`, then the console's move as two commits (section 6
step 5). Section 6 is the order; its first step is the person's act of seating the new seats, since
the three decisions are made.

## 4. What moves, what stays, and the target layout

**The principle**: what *reads and shows* moves; what *measures, moves or lights* stays. The console
is the first kind by definition (11-25). The file-by-file list is the moving seat's to make on the
card, with this principle; the obvious members are:

| Moves to `console/` | Stays in `microscope_agent/` |
|---|---|
| `web/` whole (shell, areas, features, api client, tests, `package.json`, lockfile, Vite config) | `focus/`, `engine/`, `synth/`, `models/`, `backbone.py`, `bench_values.py`, `live.py` (the live focus score) -- re-placed into `src/` by cards where 14 already says so, else left as the imported remainder |
| `server/` (app, `api/*`, auth, ws, static, edge, schemas) | `configs/micromanager/*.cfg` (byte-pinned by the root `.gitattributes` line; they do not move) |
| `agents/` (the data layer: `MockStore`, `SmaFiles`, `sma_run`, `sma_live`) | `scripts/` that train or measure |
| `assistant/` (proposes only; the person confirms) | `tools/launcher/` **to look**: a Windows launcher for the app -- it goes where what it launches goes |
| `tests/server`, `tests/assistant`, `tests/auth`, `tests/e2e`, `tests/agents` | `records/` **to look**: "experiment sessions and the local records store" on the microscope PC -- a record of the instrument's sessions, not a screen |
| `docs/screens/`, `docs/ui-spec.md` and the console's runbooks | `docs/integration-sma.md`, `docs/integration-sma-workplan.md` -- dino's own record, frozen; stays where it was imported |

Target:

```
console/
  CLAUDE.md          role / what it does not do / permissions   (design seat's, like every agent's)
  README.md          what it is and what it becomes today       (design seat's)
  tasks/             downward instructions, if option A         (manager's)
  web/
  server/            the FastAPI application; its own pyproject or the root's pixi tables -- open (section 7)
  tests/
  docs/
  failures.jsonl     dead ends, per seat, as every seat has
```

**The dependency rule for 7**: `console/` imports `contracts/` (the schemas, to read cards) and
nothing from any agent's `src/`; it reads `<agent>/questions/`, `<agent>/approvals/`, `<agent>/runs/`
and `bridge/threads/` as data; no agent imports anything from `console/`. The run interface it
consumes is pinned in `contracts/` (step 3 below), so a change to the writer and a change to the
reader are two commits that meet at a fixture rather than one commit across two boundaries.

The count of agents does not change: **the console is not a fifth agent.** It designs nothing, runs
nothing and knows nothing; it shows. D11 and D12 keep "four agents" and add one more directory the
same way `bridge/` is one -- the bridge carries cards without owning knowledge, the console shows
cards without owning anything.

## 5. Ownership -- the options

The question the person had to answer before anything else: **who owns `console/`.** Four options,
and a recommendation -- kept as the record of what was put. **Answered 2026-10-17, as relayed from
architecture-20261003-1's window** (section 8): "새 담당 영역 + 새 매니저" (a new boundary plus a new
manager) -- option A in the bridge's shape, with a dedicated `manager-console`; and the folder name
"console/ (권장)" -- `console/`, the recommended one.

### Option A -- a fifth boundary, `console`, with its own seat(s)

- Validator: `AGENT_OF_PATH` gains `(^console/, "console")`; `DESIGN_OWNED` gains
  `console/(CLAUDE.md|README.md|.claude/|tasks/)`; `ALLOWED_PATHS` gains the folder; the fixtures of
  checks 35 and 41 gain the boundary. `seats.json`'s `boundaries` note gains the name.
- Seats: `console-<machine>-<YYYYMMDD>-<n>` execution rows, `owns: ["console"]`, minted only on the
  person's statement (`a_seat_is_minted_only_on_a_statement`). Who writes `console/tasks/`: either a
  `manager-console` (the bridge's shape -- every agent directory pairs with a manager) or an existing
  manager's `paths` widened by one entry (fewer seats; the manager-microscope already holds the
  subtree's cards). **That sub-choice is the person's too.**
- `console/CLAUDE.md` carries 11-25's four rules as that seat's standing orders, and
  `console/.claude/settings.json` denies every instrument tool, as `bridge/`'s does.
- For: it is the only option in which the boundary rule (one directory, one session, one gate), the
  dependency direction (a leaf above the agents) and the gate (judged as this repository's code) all
  point the same way. The agents' seats stay out of the console, which is right, because the console
  reads all of them; the question "who writes the simulation screen" has the answer the system
  already gives everywhere -- the console seat writes the screen, the simulation seat writes the
  cards the screen shows, and a disagreement about what a screen may show is a card-contract
  question, which is a manager's.
- Against: more seats to seat -- the person seats each session directly (6.2.2), so six becomes
  seven or eight. More coordination at the shared files (`plan.md`, `seats.json`).

### Option B -- `console/` in the design boundary (architecture's), like `docs/`

- Validator: `SHARED_PATHS` gains `console/`. No new seat; the two mockup seats already sit in
  architecture.
- For: fits the *mockup* phase exactly -- the design of the console is architecture's work and is
  being done there now. Nothing to mint.
- Against: architecture's standing order is "specify, do not implement", and the console is a React
  and FastAPI application with tests -- the first implementation code in the design boundary besides
  `contracts/`, and thousands of lines of it. A seat holding `plan.md` and the console's source at
  once is the shared-surface hazard this repository already has, widened. **Fits the design phase,
  not the build.**

### Option C -- `console/` as a manager-owned path, like `contracts/`

- Validator: classify `console/` as design and list it in a manager's `owns_in_contracts`-style
  field, or widen a manager's `paths`.
- For: managers already own implementation under `contracts/` (the validator, `seat_commit.py`), so
  code under a manager has precedent.
- Against: `contracts/` is shared code **everyone depends on**; the console is code **nobody depends
  on**. The dependency direction is the opposite, and the precedent does not carry. Four managers
  would each have a say in one folder, which is the division problem `dividing_a_boundary` records.

### Option D -- stay where it is (`microscope_agent/autofocus/`)

- For: nothing to do; no reversal of 2026-10-15; dino's test layout stays as imported; and until the
  bench work of 14 is through, this is the right answer *for now*, which is why section 3 says
  "after".
- Against: section 2 (a)-(c), permanently.

### Recommendation

**A**, in the bridge's shape, started as section 3 says, with the move made as two commits (section 6
step 5). A with an existing manager holding `console/tasks/` would have been the smaller form and lost
nothing of (a)-(d); the person chose the dedicated manager (section 8). B is right until the build
starts and wrong after; C and D are not recommended.

## 6. The move, in order, with owners (if A)

1. **The person**: the three decisions -- timing (section 3, in this seat's window), folder name and
   ownership (section 5, in architecture-20261003-1's window, relayed) -- are made. What is left is
   the person's act that no session can do for them: opening and seating the console execution
   seat(s) and the `manager-console`, each in its own window, before their first commit
   (14, "How to work here"; `a_seat_is_minted_only_on_a_statement`). [the person]
2. **The record first**: 7 (layout, the dependency rule, "not a fifth agent"), 11-25 (one more
   "where it now sits" paragraph), 14 (a step after the import's after-work), 6 if the boundary list
   is enumerated there, `contracts/seats.json` (rows, `boundaries` note), root `CLAUDE.md` one
   paragraph. [architecture, by section holder]
3. **The run interface pinned in `contracts/`**: the `run_started` keys, the stop channel's request
   and reply, the frame tap's request -- as a schema or an examples fixture that both the
   orchestrator's tests and the console's tests read. This replaces 14's "same commit" bullet and is
   needed *before* the split, because after it the two sides are in two boundaries. **Section 15's
   step 2 already asks manager-microscope for exactly this pin** (section 8), so this step is 15's
   and not a second one. [manager-microscope specifies; a microscope seat lands it]
4. **The validator and the fixtures**: `AGENT_OF_PATH`, `DESIGN_OWNED`, `ALLOWED_PATHS`, what remains
   in `IMPORTED_SUBTREES` after the split (the remainder, or nothing once 14's re-placements are
   done), fixtures for 35 and 41 that show the new boundary refuses and admits correctly.
   [manager-microscope]
5. **The move, as two commits.** A `git mv` by path list would be one commit whose deletions are in
   the microscope boundary and whose additions are in the console boundary, and **the gate refuses
   that whoever commits it**: check 35 fails any commit whose paths classify into two boundaries
   ("one commit writes into [...]; a session writes inside one agent", `validate.py` line 3222-3223,
   read here on 2026-10-17), and check 41 is a second refusal, not the only one. So a seat owning both
   boundaries -- this draft's first version proposed one, minted for the move alone -- does not get
   through; **manager-microscope-20261003-1 corrected that the same day**, and this step is its
   correction. Three ways, and its recommendation taken:
   - (a) **Two commits**: the additions under `console/` first, by the console seat; the deletions
     under `microscope_agent/autofocus/` second, by a microscope seat; each message carrying the full
     old→new path list. Rename detection across the two is lost, so `git log --follow` starts over at
     the first commit -- but every old path still resolves at the first commit's parent, and the path
     list in both messages is the join, so a citation by old path keeps working. Nothing in the gate
     changes. **Recommended.**
   - (b) A declared exception in check 35 for a pure-rename commit between two named boundaries,
     listed in a move manifest. It loosens the gate, so it lands only on the person's word (8.3 rule
     1), and it grows a permanent hole for one move.
   - (c) The import's route: build the move outside the working copy as a merge and fast-forward it in
     -- check 35 skips merges and check 41 judges them via `--cc`. It works and makes a move look like
     a merge, which misleads a later reader.
   The first commit carries dino's tests at their new paths, green, and nothing else; the second
   removes the old copies and nothing else. The console's seats are registered in `seats.json` by
   architecture before the first of the two. [the console seat, then a microscope seat, each on
   manager-microscope's card]
6. **After**: `console/CLAUDE.md` and `console/README.md` written (design seat's); the first
   `console/tasks/` card is the console's connection to this repository's store, which today refuses
   with 409 "not connected yet" -- the mockup's screens are what that card builds toward. [manager,
   then the console seat]

## 7. Open, for the section holders

- **How the console shows the librarian's store.** The store's service is isolated by `caller_id`
  and a console has no question, so it cannot query (root `CLAUDE.md`, "A manager seat cannot
  query the store"). Reading `kb/` files as data for *display* keeps nothing and lands nothing on a
  card -- the same line the root `CLAUDE.md` draws between measuring and querying ("what may be
  kept"). It needs one sentence in 4.3.1 or 11-25 saying display is neither, and what a shown number
  carries (its entry's grade in words and the version shown from). [4.3.1's holder]
- **Packaging.** A `console/pyproject.toml` of its own (dino's today) or the root's pixi tables;
  `web/` keeps npm either way. 7's root-file coupling (ALLOWED_PATHS first, then SHARED_PATHS, then
  7) applies if it is the root's. [architecture]
- **The remainder of `autofocus/`** after the split: an imported subtree still, or re-placed by
  cards and the `IMPORTED_SUBTREES` entry removed. [manager-microscope, 14]
- **Tool denials** for `console/.claude/settings.json`: the bridge's set is the starting point (no
  instrument tools, no hardware path); whether the console's server may be *started* from a console
  session, and what that process may reach, is the one new question. [manager]
- **Pages**: `docs/` is public and the console is not published; no link from `index.html`. [architecture]
- **Name**: `console/` is used in this draft; `operator_console/` is the mockup's own wording.
  Nothing else depends on the choice. [the person]

## 8. Relayed the same day, after this draft was written (2026-10-17)

Recorded as relayed, not said in this seat's window: architecture-20261003-1 reports that the person
decided, in architecture-office-20261017-1's window, to split the microscope execution layer and the
run-time watcher into a new `microscope_runtime/` **now** -- "실시간 의사결정 + 현미경 하드웨어 조작
까지" (real-time decision-making, through to microscope hardware control), then "방문을 기다리지 말고
지금 분리 작업을 시작하자" (do not wait for the visit; start the split now) -- and that
architecture-office-20261017-1 is writing it as `plan.md` section 15 with a file list that includes
`autofocus/`.

What this draft says to that, sent to that seat the same hour: section 4's split line already divides
`autofocus/` into what measures, moves or lights and what reads and shows. The first column is what a
`microscope_runtime/` is for and can go there with the split; the console is the second column and
section 2's case applies to `microscope_runtime/` exactly as it applies to `microscope_agent/`. So 15
is asked to name `autofocus/`'s runtime members explicitly rather than `autofocus/` whole, which leaves
the console's destination open without holding up the split, and to pin the run interface in
`contracts/` (section 6 step 3) before any split puts its writer and its reader in two boundaries.

**The two windows differ on timing only** -- "after the merge, as a separate step" here, "now" there --
and this draft does not choose between them. The difference is put to the person in this seat's
window; the answer, with the words, replaces section 3's condition or confirms it.

**architecture-office-20261017-1's answer, the same hour (relayed):** section 15 **does not place the
console**. `autofocus/` stays exactly where it is in that split, neither whole nor in part, so the
imported-subtree rule is untouched; 15 says so in its own paragraph and cites this draft by path. What
15 moves into `microscope_runtime/` is the runtime code from `microscope_agent/src` (operator,
orchestrator, `devices/`, live view, run lock, focus search and decider, the copied focus core, the
watcher and bench kit when built) with their tests, `runs/`, and -- by the person's own commit --
`envelope/safety.json` and `approvals/`. Nothing from `autofocus/`. So section 4's "stays" column stays
inside `autofocus/` for now, and `microscope_runtime/` is available as its final destination when this
draft's question is answered. The run-interface pin (section 6 step 3) is in 15's step 2, asked of
manager-microscope, **before** that move -- the writer moves and the reader stays, so the pin is in
place whichever answer the person gives. In that window the person's console answer was conditional
-- "이제 필요 없지 않나? 필요하면 같이 옮기자" (isn't it unnecessary now? if needed, move it together) --
and that seat is telling the person the console is needed and that its place is asked here.

**Answered by the person in this seat's window the same day** -- the words are section 0's fourth
sentence, and section 3 now carries them: the console moves now, with the split, to its own top-level
folder. The timing difference above is closed. 15 may keep its paragraph that it does not place the
console: the place is this draft's, and the step is 15's.

**The folder name and the ownership, answered the same day (relayed by architecture-20261003-1, from
options it put to the person in its window):** folder "console/ (권장)" -- `console/`; ownership
"새 담당 영역 + 새 매니저" -- a new boundary plus a new manager, which is section 5's option A in the
bridge's shape: a fifth boundary `console`, its own execution seat(s) `console-<machine>-<date>-<n>`,
and a dedicated `manager-console` holding `console/tasks/`. Recorded as relayed, to be corrected if the
person says otherwise. What follows from it is distributed as 7's rule for this folder says:
architecture-20261007-1 takes the registry rows and 11-25's paragraph, architecture-20261003-1 takes
7's tree and 14's order when 15 lands, manager-microscope takes the validator tables (section 5 A) and
the move card (section 6 step 5), and architecture-office-20261017-1 places the move in 15's
sequence. The person still opens and seats the new seats in their own windows.

**Corrected the same day, by manager-microscope-20261003-1, after reading the draft at `e0d09c02`:**
the one-move seat the first version proposed for the cross-boundary commit does not pass the gate --
check 35 refuses a two-boundary commit whoever the committer is, which this seat then read at
`validate.py` line 3222-3223 rather than taking on the message. Section 6 step 5 now says two commits,
additions first and deletions second, each carrying the old→new path list, as that seat recommended;
the split line it took as written; and its order on its side once 15 lands is the run-interface
fixture first, then the validator tables and the 35/41 history fixtures for both new folders
(`microscope_runtime/` and `console/`), then the move card. It starts none of it before 15 lands.

**The registry side, the same day (relayed by architecture-20261007-1):** the person has already opened
and seated both console sessions in their own windows, and the rows are written from those seatings --
`manager-console-office-20261017-1` (owns `design`; `paths` `README.md` and `contracts/` with excludes)
and `console-office-20261017-1` (owns `console`) -- with the commit going through the commit tool as
this was written; cite that commit, not this sentence. The manager's `console/` paths are left out of
its row until the validator maps `console/`, because check 48 refuses a `paths` entry the validator
cannot grant; they join in the commit after the mapping, as does the `boundaries` note. 11-25's
paragraph, the root `CLAUDE.md` line and the store-display sentence are written after 15 and the
mapping land, so that none of them describes a folder before it exists. So section 6 step 1 is done
as far as seating goes, and step 2's registry part is in hand; the draft stays until each piece is in.

## 9. What does not change

11-25's four rules; 2.1 and P0 (safety in deterministic code; the console's STOP is a signal that
can only stop); never two Micro-Manager cores; live view as a preparatory run under an approved list;
the count "four agents"; the console drafts plans the person approves and commands nothing itself.
Moving its code changes where it lives, not what it may do -- 14's own sentence about the import,
and it holds for this move as well.
