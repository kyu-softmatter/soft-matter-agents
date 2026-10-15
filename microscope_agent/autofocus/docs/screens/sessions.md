# Screen contract: `sessions` (F7 experiment sessions)

- Task: T-106 stage A. Owner: AF 실행2. Status: draft, 2026-10-01.
- Plan: PLAN.md 2절 F7, 5절 "실험 세션과 기록 저장소", 6절 rule 12, 7절 D10, D11, D13.
- Backed by `dino_autofocus.records` (T-019, branch `exec2/T-019-experiment-sessions`, in review).
  Router mechanism: T-009 (`server/api/<area>.py` with a module-level `router`, mounted at `/api/<area>`).
  Shell: T-010. Common disabled reasons: `docs/ui-spec.md` 7.0.
- An *experiment session* is one measurement run at the microscope, not a Claude session.

## 1. What the server holds

One `RecordsStore` and one `AutoCommitter` on `app.state`, made at start-up:
`GitFolderStore(RecordsConfig(...))` on the microscope PC, `FolderStore` in mock mode and in tests.
Handlers never call git themselves. Every write goes through `ExperimentSession`, and its commits go to
the committer's worker thread (T-019 `committer.py`), so a slow or failing git never blocks a request.

## 2. Endpoints

All paths are under `/api/sessions`. **Who may act is not decided here.** Role, microscope control,
experiment-session and remote rules come from the one shared check: `GET /api/permissions?ops=a,b` returns
`{op: {allowed, reason}}` (T-009b over T-011 `check()`, the single permission table plus engine state). The
screen shows those reasons and the router asks the same check before a write; neither works the rules out
itself. Op names (fixed): `session_open`, `session_close`, `session_continue`, answered from the T-018 named permissions plus loopback. The "Who" column below is
what the permission table is expected to say. Only this area's own checks (one open session, the current
sample, a session's owner, closed sessions) stay in the router.

| Method, path | Who | Backed by (T-019) | Returns |
|---|---|---|---|
| `GET /` `?user=&sample=&status=open\|closed` | everyone, remote included | `store.list_sessions()`, filtered in the router | `[SessionSummary]`, oldest first |
| `GET /current` | everyone | `open_session(store)`, `open_session_started_at(store)` | `SessionSummary \| null`, plus `started_at` |
| `GET /{id}` `?log_tail=200` | everyone | `ExperimentSession.load(store, id)`: `.info`, `.log_lines()[-n:]`, `.manifest()`; record files listed from `layout.records` | `SessionDetail` |
| `POST /` `{sample_id?}` | local operator or admin | `ExperimentSession.open(store, user_id, <current sample>, user_name=, hardware_profile=, committer=)` | `SessionDetail`, 201 |
| `POST /{id}/close` `{note}` | local; the session's own user, or admin | `ExperimentSession.load(...).close(note)` | `SessionDetail` |
| `POST /{id}/continue` | local operator or admin | engine `sample_open(<that session's sample>)`, then `ExperimentSession.continue_from(store, id, user_id, ...)` | `SessionDetail` of the new session, 201 |

**One sample per experiment session** (manager rule, main 9052f48; T-027). The sample is chosen first, by
the engine's `sample_open` or `sample_new` while no session is open; nothing moves. `POST /` opens the
session for that current sample. An optional `sample_id` in the body must match it, otherwise the request
is refused. `continue` reopens the earlier session's sample: the server runs `sample_open` for it (allowed
because no session is open) and then opens the new session with `continues` set. While a session is open,
the engine refuses `sample_open` and `sample_new` for any other sample.

`sample_new` writes no event (T-027). When the first session for a sample opens, the **engine** writes
`sample_created` as the first event in that session's `records/sample_events.jsonl`, from the
`set_experiment_session` hook (G1). The session-open path in the router only calls that hook after
`ExperimentSession.open`; it never writes sample events itself.

`SessionSummary`: `session_id, user_id, user_name, sample_id, status, started_at, closed_at, continues,
reflected`.

`SessionDetail`: every `session.json` field as recorded, plus:
- `log_tail`: the last n log lines.
- `records`: one item per `records/*.jsonl` with its name and line count.
- `manifest`: file count, total bytes, and count per `where`, with the entry list.
- `reflected`: whether the librarian has taken the session in.

The code commit, the dirty flag and the hardware-profile sha256 are shown **as recorded in
`session.json`**. They are never recomputed.

Refusals use the ui-spec 7.0 strings:

| Case | Status | Body `detail` (FastAPI) | Decided by |
|---|---|---|---|
| Any shared rule (remote view under D13, viewer role, control, ...) | 403 | the shared check's `reason`, e.g. `"Read-only: remote view"`, `"Needs the operator role"` | `/api/permissions` (T-009b) |
| Another session is already open | 409 | `"<id> is open; close it first"` | router |
| Write to a closed session (`SessionClosedError`) | 409 | `"Session <id> is closed (read-only)"` | router |
| Closing someone else's session, not admin | 403 | `"Only <user> or an admin can close this session"` | router (shown after the attempt; the screen does not compute it) |
| Unknown id | 404 | `"No experiment session <id>"` | router |
| No current sample (nothing opened with `sample_open` / `sample_new`) | 409 | `"Open or create a sample first"` | router |
| Body `sample_id` differs from the current sample | 409 | `"The current sample is <current>; open <sample_id> first"` | router |
| Bad sample id (`ValueError`) | 422 | the error text | router |

## 3. What the shell shows (T-010)

- **Status bar, experiment session cell**: `<session_id> · <sample_id>` from `GET /current`, or
  `"No experiment session"`. It refreshes on the session event (gap G2) and on navigation.
- **Disabled reason**: when no session is open, instrument commands show
  `"Open an experiment session first"`. The engine decides this (PLAN 6절 rule 12), not the screen.

## 4. The `sessions` area (`web/src/features/sessions/`, stage B)

| Panel | Content |
|---|---|
| List | Columns: id, user, sample, status, started, closed, continues, reflected. Filters: user, sample, status. Opening a row shows its detail |
| Detail | Fields of `session.json` (code commit, dirty, hardware hash as recorded); log tail; record files with line counts; manifest summary and entries; reflected or not |
| Actions | `"Open experiment session for <current sample>"` (no sample field: the sample is picked in the `sample` area), `"Close"` with a note, `"Continue with this sample"` on a closed session (F7.4, reopens that sample). They are disabled with the shared check's reason for their op first, then this area's: no current sample, a session already open, the session closed |

If `/api/permissions` cannot be read, every control is disabled with `"Permission check unavailable"`
(rule for all screens); the list and the detail stay available. While the check is loading, controls are
disabled with `"Checking permissions…"` (same text on every screen). An op missing from the answer counts as
`"Permission check unavailable"`.

UI text is in English. Remote viewers and viewers can read everything and change nothing.

## 5. Gaps (requests via AF 업무분배보조 to the manager)

| # | Gap | Proposal | Owner |
|---|---|---|---|
| G1 | The engine needs to know the open session (rule 12, re-trace rule, the one-sample rule) | The server calls `engine.set_experiment_session(session_id, sample_id, started_at)` after open, close and continue, and once at start-up from `GET /current` | T-011 (assigned) |
| G2 | There is no event when a session opens or closes, so the status bar would need polling | Add a `session_changed` event kind (`session_id`, `sample_id`, `status`) on `/ws/events` | T-011 (assigned) |
| G3 | T-019 does not stop a second open session | The router refuses with 409. A store-level check is optional | T-106 (router) |
| G4 | `ExperimentSession.open` reads the code version with two git calls on every open (about 1 s on a loaded PC) | Accept `code=` so the server reads it once at start-up | T-106 stage B, change to `records/` listed in its review |
| G5 | Listing record files and their line counts has no T-019 function | A small `ExperimentSession.record_files()` helper | T-106 stage B, change to `records/` listed in its review |
| G6 | `reflected` comes from the mock librarian's `librarian/reflected.jsonl`. The real librarian's ledger format is decided at integration | Show `reflected` as true, false or unknown (null when no ledger exists) | integration (PLAN 10절) |
| G7 | Which `hardware_profile.json` to hash at open (F2.1 file path) | `profile_path` from T-011's `snapshot()["hardware"]` block | T-011 (answered) |
| G8 | The logged-in user id and name | Use T-105's auth dependency. Until it merges, tests use a fake user | T-105 (answered) |
| G9 | Where the server reads the current sample | `snapshot()["sample"] = {sample_id, reserved, session_id}` (set by `sample_open` / `sample_new`, T-027). Sample state shown on screens comes from `engine/sample.py`'s named view over the generic `records.events.fold()`, read through the server; `records/` gets no sample-specific fields | T-011 / T-027 (answered) |

| G10 | `create_app(records=...)` keeps the store only on the engine's sample seat | The router reads `app.state.records` if set, else `engine.sample_seat.store`; 503 `no_records` when neither. Proposal: `create_app` sets `app.state.records` | T-009 |
| G11 | The router makes one `AutoCommitter` and reads the code version once per app on first use (`app.state.records_committer`, `app.state.records_code_version`); nothing flushes the committer at shutdown, and a session left open by a crash is not handed to the engine at start-up | `create_app`'s lifespan builds both, adopts `GET /current` into `app.state.sessions` and `set_experiment_session` at start-up, and calls `committer.flush()` / `stop()` on shutdown | T-009 |

## 6. Stage B tests (outline)

- **pytest** (`TestClient`, a `FolderStore` and a `GitFolderStore` under `tmp_path`): open, close, list
  filters, detail fields, continue (reopens the same sample), open with no current sample or a different
  sample gets 409, a second open gets 409, a write after close gets 409, remote POST gets
  403, viewer gets 403, and the handler returns while a slow fake committer is still blocked.
- **vitest**: list and detail render, and open, close and continue are disabled with the reason in
  read-only mode.
- Tests open no browser or desktop window and stop every server they start.
