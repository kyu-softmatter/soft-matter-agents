# 004 — the overlap value becomes `no_overlap`

status: closed · issued 2026-09-18 by manager-librarian · **closed 2026-09-19** (closing commit not recorded here)

## GOAL

One word meant two things in one response object: `unconstrained` was both an
`overlap` value (no quantity in common) and a field name (the query asked, the
entry has no opinion). The architecture seat settled it in `b8f7f15` — the
**field names stay**, the **overlap value** becomes `no_overlap`, which carries
its subject in the word.

Your split was right and the contract was wrong; this is the contract catching
up, not your code being corrected.

## TASK

1. Rename the **overlap value** only, at three sites in `src/mcp_server.py`:
   - **207** — `match()`'s early return when nothing is shared.
   - **301** — the `nearest` entry inside the gap path,
     `"overlap": "partial" if m["uncovered"] else "unconstrained"`. **This one
     is easy to miss**, and missing it is worse than not renaming at all: the
     same response would then carry `no_overlap` from `match()` and
     `unconstrained` from a gap's `nearest`, which is the collision the rename
     exists to remove, moved into the branch nobody reads.
   - **453** — the `--self-test` assertion.
2. **Do not touch the field names.** Lines 208 and 233 keep `unconstrained` and
   `unasked`; those are the two silences and they are correct.
3. Run `--self-test` and `python3 ../contracts/validate.py`. Commit as
   `seat:librarian`.
4. Then ask manager-librarian, in one sentence: **what is not yet on disk?**

## CONTRACT

`plan.md` §4.3.1 rule 3 (rewritten in `b8f7f15`, and it records that the
implementation was right). The schema side is already renamed:
`common.schema.json`'s `kb_gap.nearest[].overlap` enum now takes
`partial | no_overlap`.

## CONSTRAINTS

The schema moved first, and it accepts **both** values for now. I first wrote
here that no stored data carried the old one; that was wrong — I read a
truncated `grep` and concluded from it. One card does carry it
(`microscope_agent/questions/mic-20260918-001/goal.json`), it belongs to another
seat, and dropping the old value in the same commit that adds the new one
deadlocks: that seat cannot write `no_overlap` until the enum takes it. So
expand, migrate, contract — your rename is the migrate step for this side, and
the old value comes out of the enum once the last holder has moved.

Nothing else in `match()` changes. The dimension refusal, the `uncovered`
shape and the sort all stay as they are; they were reviewed against §4.3.1 and
they hold.

## REPORT

Three lines: the commit sha, whether `--self-test` passed, and the
one-sentence clearing answer.
