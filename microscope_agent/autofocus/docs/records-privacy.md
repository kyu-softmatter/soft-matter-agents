# Personal information in the records (before they pass to the public runs/, draft 2026-10-02)

The user's decision (2026-10-02, integration-sma.md §9): **every experiment record goes to soft-matter-agents'
`microscope_agent/runs/<run_id>/`.** That repository is public, so personal information such as emails and names is removed or replaced before
it is passed over. Administrator emails stay, as now, only outside git (the settings folder, environment variables). This document sets what stays and what
crosses, which id a person is replaced with, and the shape of the export step. Implementation:
`src/dino_autofocus/records/redact.py` (replacement and checking) and `records/export.py` (export, as decided in §6). Both use only the standard
library, and neither changes how records are written.
Sources: this repository at `1302694`, soft-matter-agents at `baf6f1e` (read only).

## 1. The records written now, and their personal information (inventory)

The user id is the account email (D9). "Person" below means an email or a value derived from one.

| File (location) | Personal information fields | Source |
|---|---|---|
| `session.json` (session folder) | `user_id` (email), `user_name` (real name), the email's local part inside `session_id`, `code.repo` (a path; on a development PC it can be `C:\Users\<name>`), `hardware_profile.path`, `continues` (previous session id), `close_note` (free text) | `records/session.py:69,74,79,90,132`, `records/codeversion.py:15,41` |
| Session id and folder name `<YYYYMMDD-HHMM>-<slug(email)>-<n>` | The email's local part. It spreads into `session_id` on every line, the data folder `data/<session_id>/`, the manifest's data paths, and commit messages | `records/session.py:90,270`, `records/layout.py:113`, `records/manifest.py:68-69` |
| `log/session.jsonl` | `user_id` on every line, the git error text in `commit failed` lines (can contain paths) | `records/session.py:260,280` |
| `records/<op>.jsonl` (operation records inside a session) | `user_id` on every line, `user_id` and `confirmed_by` of `operation_started`, engine event `data.by` (confirm, update, approve, reject), `confirmed_by` of the closing summary, `trigger` (the person who aborted) | `server/app.py:215`, `engine/runner.py:259,870,891,894,914,953,967` |
| `records/manual_steps.jsonl` | `user_id`, notes a person wrote | `records/session.py:206,260` |
| `records/sample_events.jsonl` | `user_id`, flag names and notes, `note` text. When folded, `history[].by` | `records/events.py:45,75,100,106` |
| `manifest.json` | The session id inside data paths, names of attachment files a person chose | `records/manifest.py:69,73` |
| The record store's git history (local) | Commit author = real name + email | `records/store.py:29-32,113` |
| Operation records outside sessions, `data/engine_records/<op>_<stamp>/`, and sample folders `samples/<id>/<op>_<stamp>/` | `user_id` and `result.confirmed_by` in `summary.json`, Event `user_id` in `log.jsonl`, `user_id` of the `started` event | `engine/records.py:99`, `engine/runner.py:246,1079,1454`, `engine/operations/sample_ops.py:335,337`, `server/__main__.py:311` |
| Hardware profile `microscope/hardware/` | `host` (PC name), `confirmed.<item>.by` | `engine/operations/hardware_scan.py:155,312`, `engine/gates.py:104-106` |
| The fake librarian, `librarian/reflected.jsonl` and `samples/<id>.json` | `user_id`, `history[].by` in the folded state | `records/librarian_mock.py:71`, `records/events.py:106` |
| Assistant records `assistant.jsonl` (`DINO_AF_ASSISTANT_RECORDS`) | `user_id`, question text, screen context, answer text | `assistant/records.py:52-65`, `assistant/runner.py:82,290` |
| Accounts `accounts.json` (settings folder) | Email, real name, password hash, email of the administrator who approved | `auth/accounts.py:68-76` |
| Audit log `audit.jsonl` (settings folder) | `user_id`, `account`, `name`, `holder`, `login_id`, copies of assistant question and answer text | `auth/audit.py:92-98`, `auth/accounts.py:212-345`, `auth/logins.py:128-241`, `auth/control.py:103-149`, `server/api/assistant.py:168-181` |
| App logs `logs/app-*.log` (settings folder) | Server messages (emails may be mixed in) | `auth/applog.py` |

IP addresses are written nowhere (used only for the loopback check and then discarded, `server/api/__init__.py:218`).

## 2. What stays and what crosses

- **Local only (does not cross)**: accounts, the audit log, app logs, assistant conversations (`assistant.jsonl`), the person mapping table
  (§3), and the record store's git history (author emails). The export step does not even read these files.
- **Crosses (after replacement)**: the session folder's JSON / JSONL (`session.json`, `manifest.json`, `log/session.jsonl`,
  `records/*.jsonl`). People become person ids, and the user part of session ids becomes a person id too.
- **Dropped**: `user_name`, `login_id`, `control_grant`, and any `host` that is not mapped. Attachments that are not JSON
  (`files/*`) are not copied; only a list of them is returned (the manifest keeps their sizes and hashes). Large data (`data/`) stays outside git as it does now,
  and on that side too frames are kept outside the repository.

## 3. person id

- One **short public id** per person: `^[a-z][a-z0-9-]{1,31}$`. That side already uses short names that people chose, in public, such as `approved_by: "kyuhwan"` and
  `who: "kyuhwan"` (`microscope_agent/approvals/*`,
  `contracts/examples/plan_approval.json`). The recommendation is that a person uses the same id as on that side's approval cards
  (so runs and approvals can be linked through the person). For a person who has not chosen one, a random `p-xxxx` is made once
  (an email hash is not used: it can be traced back through the lab's list of people).
- The mapping table `people.json` is kept in **the settings folder** (next to `accounts.json`, outside git):
  `{"persons": [{"person_id", "email", "name", "aliases"}], "hosts": {"<PC name>": "<label>"}}`.
  `aliases` are the nicknames used in notes. Only the export reads this file.
- **Replacement happens at export, not when writing.** Local records keep the account id unchanged, and the screens, the session list and the librarian
  use them as they do now. Changing the mapping table changes the next export onward (what has already been exported stays in the public repository's history).

## 4. Replacement rules (`records/redact.py`)

In every string (keys and values), in order: a mapped email → id (case-insensitive, including the full-width `＠`), a home folder
(`C:\Users\<name>`, `C:/Users/<name>`, `/mnt/c/Users/<name>`, `/home/<name>`) → `~`, names and aliases (whole words,
case-insensitive) → id, the user part of a session id → id, a mapped PC name → its label.

Then it checks, and **if even one remains, the whole session is refused** (`RedactionRefused`): an email-shaped string, a home folder path,
a mapped name or alias, a session id whose user part is not a person id, or a person field (`user_id`, `by`, `confirmed_by`,
`approved_by`, `account`, `holder`) whose value is neither a person id nor an actor (`assistant`, `system`, `engine`).
The refusal message says only the file, the location and the kind, never the value.

Limit: a name or alias in a note that is not in the mapping table is not found. That is why whether to pass free text over is question 2.

## 5. The export step (`records/export.py`, implemented 2026-10-02)

```
  closed session + people.json --redact_session--> replaced copy (in memory) --> runs/<run_id>/console.*
```

1. Only sessions that are `closed` and fully committed (the same condition as the librarian's). Only sessions whose `session.json` has `bench` **exactly `true`**
   are exported (R-03): `false` (mock, simulation) is refused, and so is an old session with no value. `bench` and `backend_kind` are
   recorded from the engine's backend information when the session is opened (T-106b). The run id follows that side's naming rule for `runs/` folders (lowercase, digits, `-`,
   64 characters or fewer), and the `console.*` documents carry no top-level `card`/`artifact` key (that side's validator would read them as cards).
2. If `redact_session(session folder, mapping table)` refuses, nothing is written, and the reason is left on screen and in the app log.
3. Names: that side's `contracts/validate.py:1613` accepts under `runs/<run_id>/` only flat names (`[A-Za-z0-9_.-]+`)
   and `raw/...`. So the files are flattened to `console.session.json`, `console.manifest.json`, `console.log.session.jsonl` and
   `console.records.<op>.jsonl` (`RedactedSession.flat_files`). `log.json` (the run_log schema) is a file that side's
   operator writes, so this step does not create it.
4. This repository does not write into that repository (PLAN §5). After integration the writer is that side's seat, and this step goes as far as a function that
   hands over the replaced copy. The link is left in the session's `sma_run_id`.
5. Sample folders, hardware profiles and operation records outside sessions are to be passable separately under the same rules, but for now they are out of scope
   (there are places where a value that is not a person sits in a person field, such as `light_off.by` in `scan.json`, and those have to be fixed first,
   `engine/operations/scan_4x.py:567`).

## 6. The user's decisions (2026-10-02, all the recommended options)

1. **person id**: a short name the person chose (the same one as on that side's approval cards, e.g. `kyuhwan`). For an account without one,
   `assign_person_ids` makes a random `p-xxxxxx` once and saves it in `people.json`, and never changes an id already given.
   Whether to use part of a real name as the id is decided per person (by editing `people.json`).
2. **Free text**: passed over after the check, accepting the limit that names not in the mapping table are not found.
3. **Assistant conversation text**: local only. Even if a session folder has `assistant.jsonl`, it is not read (`redact.LOCAL_ONLY`;
   only its name is left in the result's `kept_local`).
4. **Sessions and runs**: attached as `console.*` next to that side's run folder (where `log.json` is). `export_session` uses
   `sma_run_id` from `session.json` (or the `run_id` argument), and refuses if there is none. This repository does not write to that side, so it creates
   a local staging folder `<out_dir>/<run_id>/console.*` and `console.export.json` (sha256 per file), and that side copies them.
   Open sessions, sessions whose `bench` is not `true`, run ids that break the rule, and runs that already have files are refused, and a refusal writes nothing.

Remaining work: putting `bench` into `session.json` (T-106b; for now a session with no value is exported), when to attach `sma_run_id` to a session
(after integration, when that side's plan runs), and sample folders, hardware profiles and operation records outside sessions (§5 item 5).
