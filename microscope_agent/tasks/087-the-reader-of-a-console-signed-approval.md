# 087 — the reader of a console-signed approval, and the approval file in every run log

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. Do this card
first, before 084.** The console's approval writer is being built now (the
person, `b4f340ee`). Until this card lands, the operator would take a
console-written approval on the console's own checks alone. So the writer
writes only into a test root and never into `microscope_runtime/approvals/`,
and this card is what lets it write for real (plan.md 15.1 item 4 at
`0607b848`). It touches `operator.py`'s approval reader, which cards 084 to
086 do not. If you are not that seat, take nothing from this card and report
up.

## Why

The person decided, Q-20261022-office-09 (`55a635b6`), that a plan approval
may be signed in the console. The console's server writes it into the
approvals folder at the moment the person types the password. The file
carries a "signed through the console under this login" mark, and no AI
session may write there. plan.md 15.1 item 4 says what the runtime does with
such a file:

- **One place and one reader.** The file is in `microscope_runtime/approvals/`
  and is read by the operator's reader as it is today. For a file carrying
  the mark, the reader adds three checks:
  1. the login must be the person's own, as named in a file the person places
     by hand beside the safety policy, never taken from the console's
     settings;
  2. a test login binds nothing;
  3. the plan hash binds, as for any approval.
- **A trace of every approval.** An approval binds from disk the moment it is
  there, before anyone commits it. So the run log carries the path and
  sha256 of the approval file that authorised the run.
- **No fallback.** Nothing is ever read from the old
  `microscope_agent/approvals/`.

**Read 15.1 item 4 and 6.1 before starting.**

## What is in `contracts/`

- **`plan_approval.schema.json`** (`e2f5b08b`, by manager-console):
  `signed_through` is `{"via": "console", "login": <id>}`, present only on a
  console-written approval. The login is
  `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`, and no other key is allowed.
- **`console_login.schema.json`** (this card's commit) describes
  `microscope_runtime/envelope/console_login.json`:
  `{artifact: "console_login", schema_version, login, written_by,
  written_at}`, with no other key. The person writes it by hand. No real one
  exists yet.
- **`run_log.schema.json`**: `approval.file` is `{path, sha256}` plus
  `signed_through` when the approval carried one. It is forbidden when
  `approval.id` is null. It is optional in the schema, because older logs
  lack it; your tests make it required for every run from now on.
- **The guards** (this card's commit):
  - `microscope_runtime/.claude/settings.json` denies
    `Edit(/envelope/console_login.json)`, and check 90 requires it;
  - since `088fb2b0`, check 41 refuses any seat committing
    `envelope/safety.json`, `envelope/console_login.json` or `approvals/`.

## What to build

In `microscope_runtime/src/operator.py`:

1. **Keep the raw bytes.** `approvals_on_disk` reads each file once. Keep the
   sha256 of exactly the bytes it parsed beside `__path`, so the hash in the
   log is of what was judged, not of a second read.
2. **For an approval carrying `signed_through`:**
   - read `envelope/console_login.json` from the runtime's own folder and
     validate it against its schema;
   - the approval's `signed_through.login` must equal the file's `login`,
     byte for byte;
   - a missing file, an invalid file or any other login is a refusal naming
     which. A test login is simply another login, and nothing treats it
     specially;
   - then the plan hash binds exactly as it does today (check 7). An approval
     that fails any of these covers nothing, and the reason says why.

   An approval without `signed_through` is judged exactly as today.
3. **Every run with an approval writes `approval.file`**: the path, the
   sha256 from item 1, and `signed_through` copied when present. This covers
   every place `operator.py` writes `"approval"`, today three.
4. **No fallback.** If `microscope_runtime/approvals/` is absent, refuse as
   today. Never read `microscope_agent/approvals/`, and never read the
   console's settings.

## Tests, each watched failing first

1. A console-signed approval whose login matches `console_login.json`, with a
   matching plan hash, authorises the plan, and the log's `approval.file`
   carries the right path, sha256 and `signed_through`.
2. The same approval with a different login, with `console_login.json`
   missing, or with it invalid is refused, each with its reason, and no
   device call is made.
3. A matching login with a wrong plan hash is still refused.
4. A hand-placed approval (no `signed_through`) is judged as before, and its
   log carries `approval.file` without `signed_through`.
5. The sha256 in the log equals the sha256 of the file's bytes on disk at the
   time of the read. A test that rewrites the file after the read shows the
   log keeps the bytes that were judged.
6. Every run log a test writes validates against `run_log.schema.json`, and
   every one with a non-null approval id carries `approval.file`.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, and
  never `envelope/` or `approvals/`. Tests write their approvals and login
  files in a temp folder.
- The console's writing side is manager-console's. Don't edit `console/`.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most:

- the commit;
- each test, watched failing, then passing;
- the suite's counts;
- every place the schema did not fit, with the field.
