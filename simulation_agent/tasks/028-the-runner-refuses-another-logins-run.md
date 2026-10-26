# 028 — the runner refuses a run from another login's question without its own plan approval

**For:** `simulation-20261007-1`. Nobody else takes this card. If you are not
that seat, take nothing from it and report up.

Written by `manager-simulation-20261007-1`. You read this; you do not edit it
(§6.2-2). Report to me by session message when it is committed.

This is the simulation twin of microscope card 089
(`microscope_agent/tasks/089-the-runtime-refuses-another-logins-run.md`,
`3bea94af`). Read it beside this one: the rule is the same, and only the code
it lands in differs.

## Why

The person decided that a run from a question asked by any login other than
their own waits for their OK, small ones included (Q-20261022-office-06,
`231f0c76`; plan.md 6 after the tier table, `e1bd3ebd`). On this side that
covers smoke runs and runs inside the budget, which the tier table today lets
run with no approval at all. The person then approved the console inbox on one
condition: it opens only once **both** runners refuse such a run by code
(`f59f7b45`). This card is the simulation runner's half. Until it lands, the
console inbox stays shut for every agent, the microscope's included.

plan.md 7.1.1 rule 9 (`469f3e6a`) says how a plan shows its question came from
the console. The question id is the link. The console's server mints it as
`sim-<YYYYMMDD>-c<NNN>`, for example `sim-20261024-c001`. A question typed into
this session's own window never uses the `c`. The first stage uses that id for
the goal card it makes, so every plan from that question carries it as `qid`.

**Read plan.md 6 (the tier table and the three points after it), 7.1.1 rules 4,
5 and 9, and `contracts/schemas/console_inbox_item.schema.json` before
starting.**

## What to build

All of it in `simulation_agent/src/operator.py`, in `gate()` and
`find_approval()`, before `run()` creates anything.

1. **The rule keys on the qid alone.** A plan whose `qid` matches
   `-c[0-9]{3}$` is another login's question. No other field can make it the
   person's own. That includes the inbox item's `asker_mark`: the first build
   marks no item as the person's own, and a later one that does still changes
   nothing here. If the `qid` argument `run()` was called with and the plan
   card's `qid` disagree, refuse. A `c` on either side means the console.
2. **Only an exact plan approval covers it.**
   - It must be a `plan_approval` naming this plan's id, revision and hash.
   - A `scope_approval` does not cover it, whatever its `qids` or
     `applies_to_all_qids` say.
   - A Tier 0 or Tier 1 plan, which today runs with
     `approval: {id: null, kind: null}`, does not run either. Smoke runs are
     included.
   - The refusal is a `Refused` raised before `runs/<run_id>/` exists and before
     any backend is built. Its reason names the qid and this rule in words.
3. **The hash is the plan card's as read from disk, never a view's.** Today
   `gate()` is handed the arm or smoke view, and `find_approval()` hashes
   that. Both views are copies with changed `numbers` or `conditions`, and
   `budget` defaults to the smoke run. So a correct `plan_approval` is refused
   for every smoke run and every arm run, window plans included. Nobody has met
   this because no plan here has had an approval card. From this card on, every
   console plan's run needs one. Pass the plan read from disk to the approval
   lookup and keep the view for the envelope check. This is the one change that
   reaches window plans too, and a test shows it.
4. **The confirming read.** Read the item in `simulation_agent/console_inbox/`
   whose `question_id` equals the plan's qid. Make the folder a module
   attribute, `CONSOLE_INBOX = cards.AGENT / "console_inbox"`, so the tests
   point it at a temp folder, the way `ENVELOPE` and `APPROVALS` already are.
   - No item refuses. More than one item with that id refuses too: ambiguity
     stops.
   - An item that cannot be read or parsed refuses. So does an attachment that
     cannot be read beside it, or one whose sha256 differs from the one the item
     names.
   - When it is found, the run log records the item's path and the sha256 of
     its bytes. Beside them it records the approval file's path and the sha256
     of its bytes. Today the log carries only `approval.id` and `kind`, so an
     approval file that changed after the run would leave no trace.
   - Until the inbox opens, no such folder exists, so every `-c` plan is
     refused at this step even with an approval. That is the fail-closed
     direction. Do not create the folder.
5. **A plan whose qid has no `c` stays under plan.md 6's table**, apart from
   item 3. Every plan in `questions/` is of that form today.
6. **Count the other routes to the engine, and change none of them.** Several
   scripts in `src/` build a backend without passing `operator.run()`, for
   example `double_well_spread.py`, `double_well_validate.py`,
   `engine_check.py` and `check_bleach_backend.py`. Each of those is a run that
   no gate sees. List every one, and for each say whether it takes a question
   id or writes anything under `questions/` or `runs/`. I need that list to
   write the rule that a console question's runs go only through the operator.
   That rule goes into this agent's `CLAUDE.md` when the inbox is named there,
   and it is mine to write.

## Tests, each watched failing first

In one script, `src/check_other_login_refusal.py`, in the shape of
`check_trajectory_roundtrip.py`, on `mock_backend`. Every folder it touches is
a temp folder: approvals, console inbox, runs, envelope and the question's own
directory. At the end it shows that `git status --short -- simulation_agent`
did not change. Run each test against the code before your change, and see it
fail for the reason it names.

1. A `-c` plan with an exact `plan_approval` and a readable inbox item runs on
   mock as a smoke run. Its log names the item's path and sha256, and the
   approval file's.
2. The same plan is refused before anything is created in each of three cases:
   with no approval, with only a `scope_approval` whose `qids` lists it, and as
   a Tier 1 plan with no approval. Each reason names the qid. The temp `runs/`
   folder is empty afterwards.
3. A `-c` plan with an exact approval is refused in each of three cases: with no
   inbox item, with an unparseable item, and with an attachment whose sha256
   does not match.
4. A plan with the window form of qid behaves exactly as today in all three of
   test 2's cases: refused with no approval only at Tier 2, run under a covering
   `scope_approval`, and run autonomously at Tier 1.
5. A window-form Tier 2 plan with a correct `plan_approval` runs as a smoke run
   and as one arm. Today both are refused for a hash mismatch, which is item 3.
6. The id is read from the plan's `qid`. A plan whose other fields all look like
   a window question, and whose inbox item carries a mark saying it is the
   person's own, still sees the `c` and is refused without an approval.

If the script needs `contracts`, run it in the `sim` environment. If it needs
only numpy, it may run on the Office computer under
`uv run --offline --no-project --python 3.12 --with numpy`. Either way, record
which interpreter ran it in the commit message.

## Boundaries

- Write `simulation_agent/src/` only. Never `approvals/`, never `inbox/`, never
  create `console_inbox/`, never `envelope/budget.json`. The tests use temp
  folders for all of them.
- No `contracts/`. Checks 91 and the `c?[0-9]{3}` widening are
  manager-microscope's and are landing separately. The gate checks that every
  `-c` id has its inbox item and that every item is answered. Your code is the
  refusal at run time, which nothing in `contracts/` can do.
- Run nothing on the engine for this card. Mock only.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To me, by session message, six lines at most:

- the commit;
- each test, watched failing (with the reason it failed) and then passing;
- the validator's last line, with its tree;
- item 6's list;
- every place the schema or the plan did not fit, with the field.
