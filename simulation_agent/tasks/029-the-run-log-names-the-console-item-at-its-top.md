# 029 — the run log names the console item at its top level

**For:** `simulation-20261007-1`. Nobody else takes this card. If you are not
that seat, take nothing from it and report up.

Written by `manager-simulation-20261007-1`. You read this; you do not edit it
(§6.2-2). Report to me by session message when it is committed.

This follows card 028 (`d36d0ad6`, landed at `ae651ec0`).

## Why

Card 028 records the console inbox item a run read only inside the `gate`
event, as `console_item`. manager-microscope has since given that record a
place in the contract: `run_log.schema.json` now has a top-level, optional
`console_item` with `{path, sha256, item_id, question_id, attachments[{file,
sha256}]}`, closed at both levels (`0e151070`). That is exactly the dict
`read_console_item()` returns.

Check 91 now holds it:
- A run log whose plan (named by `plan_path`) has a `-c` qid must carry the
  top-level `console_item`, unless the log's `ended` is `refused`.
- Its `question_id` must be the plan's qid. Its `item_id` must name an inbox
  item asking that qid. Its `path` must be that item's path in the tree, and
  its `sha256` must be the item's bytes.
- A log of a window-form qid that carries `console_item` fails, however it
  ended.

Check 91 reads only the top level. So today every future sim run of a console
question would fail the gate. None exists yet, because the inbox is not open
and every `-c` run is refused before its log exists. This card closes that
before one does.

## What to build

In `simulation_agent/src/operator.py`, `run()`, where `log.json` is written.

1. **Write `console_item` at the top level of `log.json`** when `gate()`
   returned one, as the dict `read_console_item()` returned, unchanged. Leave
   the key out entirely when there is none: no `null` and no empty object. The
   schema is closed, so the key is either the full record or absent.
2. **Keep the copy in the `gate` event.** That event records what the gate
   read at the moment it read it. The top-level field is what check 91
   judges. Both carry the same dict.
3. **`path` is repo-relative with forward slashes**, as check 91 compares it
   with the item's own path in the tree. `_where()` already does this when the
   item sits under `cards.REPO`. Make sure it does on this computer: if
   `cards.AGENT` and `cards.REPO` resolve differently (drive-letter case, a
   symlink, or one of the two not `.resolve()`d), `relative_to` raises and
   `_where` silently returns an absolute path. If the real inbox path could
   come back absolute, fix the resolution so it cannot. Do not loosen the
   comparison.
4. **`approval.file` stays as it is** at the top-level `approval`. It already
   matches the schema from `4e61cf96`.

## Tests, each watched failing first

Extend `src/check_other_login_refusal.py`; do not start a new script. Same
rules as card 028: mock only, every folder a temp folder, and
`git status --short -- simulation_agent` unchanged at the end.

1. Test 1's console run: its `log.json` has a top-level `console_item` equal
   to the gate event's, and the run log validates against
   `contracts/schemas/run_log.schema.json`. Validating needs `jsonschema`. If
   the interpreter lacks it, add `--with jsonschema` to the `uv` line and say
   so in the commit message.
2. Tests 4 and 5's window runs: `log.json` has no `console_item` key at all.
3. `path` comes out repo-relative and slash-separated for an item under the
   real `simulation_agent/console_inbox/` location. Compute it with `_where()`
   on that path; do not create the folder.

Watch 1 and 3 fail against `ae651ec0`'s operator before the change. Test 2
passes there, since it is today's behaviour: break it on purpose once (write
`console_item: None` for window runs) and watch it fail.

## Boundaries

- Write `simulation_agent/src/` only. Never `approvals/`, never `inbox/`,
  never create `console_inbox/`.
- No `contracts/`. The schema and check 91 are manager-microscope's and have
  landed.
- Mock only. Run nothing on the engine.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To me, by session message, four lines at most:

- the commit;
- each test, watched failing (with its reason) and then passing;
- the validator's last line, with its tree;
- whether `_where` could ever have returned an absolute path for the real
  inbox, and what you changed if so.
