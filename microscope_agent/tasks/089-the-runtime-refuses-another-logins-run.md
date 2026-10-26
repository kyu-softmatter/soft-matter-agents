# 089 — the runtime refuses a run from another login's question without its own plan approval

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. It comes after card 087 and card 086's items 2 to 4 and 6**, and before 086's item 1 with 084. The person asked for the mock connected first (`aeea9d60`), and this card cannot bite before the inbox opens, so it costs nothing to come later. It also touches `operator.authorise`, and the console inbox cannot open until it lands. If you are not that seat, take nothing from this card and report up.

## Why

The person decided that a run from a question asked by any login other than their own waits for their OK, small ones included (Q-20261022-office-06, `231f0c76`; plan.md 6 at `e1bd3ebd`). They then approved the console inbox, on one condition: it opens only once both runners refuse such a run by code (`f59f7b45`).

plan.md 7.1.1 rule 9 (`469f3e6a`) says how a plan shows its question came from the console. The question id is the link:

- the console's server mints it as `<agent>-<YYYYMMDD>-c<NNN>`, for example `mic-20261024-c001`;
- a window question never uses the `c`;
- the agent's first stage uses that id for the goal card it makes, so every plan from that question carries it as its `qid`.

**Read plan.md 6, 7.1.1 rules 4, 5 and 9, and 15.1 item 5 before starting.**

## What to build

In `microscope_runtime/src/operator.py`, in the gate that decides whether a plan may run:

1. **The rule keys on the qid alone.** A plan whose `qid` matches `-c[0-9]{3}$` is another login's question. No other field of the plan can make it the person's own, and nothing read from the console's settings can either.
2. **Only an exact plan approval covers it.**
   - It must be a `plan_approval` naming this plan's id, revision and hash, with card 087's checks when it carries `signed_through`.
   - A `scope_approval` does not cover it, whatever its range.
   - A Tier 0 or Tier 1 plan that would otherwise run without an approval does not run either.
   - The refusal comes before any command, and its reason names the qid and this rule.
3. **The confirming read.** Read the inbox item that asked it, in `microscope_agent/console_inbox/`, whose `question_id` equals the plan's qid (`contracts/schemas/console_inbox_item.schema.json`).
   - If the item, or an attachment its sha256 names, cannot be read, refuse.
   - If the item is found, record its path and the sha256 of its bytes in the run log, beside `approval.file` (card 087).
   - **Record it as `console_item`, in the shape `contracts/schemas/run_log.schema.json` gives** (added 2026-10-26 at `0e151070`): `path`, `sha256` of the raw bytes, `item_id`, `question_id`, and each attachment with the sha256 checked.
   - **And record `plan_path`, the plan file this run opened, repo-relative with forward slashes** (`Path.relative_to(repo).as_posix()`). The gate finds whose question a run ran through that path, because a run log carries no qid of its own. Today the runtime writes no `plan_path`, so a log carrying `console_item` would be judged a window run borrowing an item and fail, and a `-c` run with no item would pass unseen. A path with backslashes names no card, and the gate fails it.
   - Until the inbox opens, no such folder exists, so every `-c` plan is refused at this step even with an approval. That is the fail-closed direction, and the tests use a temp folder.
4. **A plan whose qid has no `c` stays under 6's table, unchanged.** Every existing plan is of that form. Run the whole suite to show nothing else moved.

## Tests, each watched failing first

1. A `-c` plan with an exact plan approval and a readable inbox item in the temp folder runs on mock, and its log names the item's path and sha256.
2. The same plan with no approval, with only a scope approval whose range covers it, or as a Tier 1 plan with no approval at all, is refused before any command, each with the reason, and the mock records no device call.
3. A `-c` plan with an exact approval and no inbox item, an unreadable item, or an attachment whose sha256 does not match, is refused.
4. A plan with the window form of qid behaves exactly as today under all three of test 2's cases.
5. The id is read from the plan's `qid`, not from any other field. A test that sets every other field to look like a window question still sees the `c` and refuses.
6. Every run log the runtime writes, `-c` or not, refused or not, carries `plan_path` with no backslash, and joined to the repository root it is the file the run opened. Run on Windows, so the backslash case is the real one.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, never `envelope/` or `approvals/`, never `microscope_agent/console_inbox/`: tests use temp folders.
- The simulation runner's twin is manager-simulation's. The gate checks that every `-c` id has its inbox item, and that every item is answered, are manager-microscope's, in `contracts/`.
- Commit and push through `contracts/tools/seat_commit.py`, naming each path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most:

- the commit;
- each test, watched failing, then passing;
- the suite's counts;
- every place the schema or the plan did not fit, with the field.
