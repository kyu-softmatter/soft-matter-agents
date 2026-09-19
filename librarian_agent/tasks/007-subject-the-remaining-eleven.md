# 007 — subject the other eleven, and split the objectives

status: closed · issued 2026-09-18 by manager-librarian · **closed 2026-09-19** (b3b0afb)

## GOAL

Task 005 said fourteen and you did fourteen, which was right — a task that says
a number should mean it. The other eleven reach a query through a number name or
a symbol, so they are not invisible, but **six of them answer to `na` and six to
`working_distance`**, which means a query for `na` returns all six objectives
and the caller separates them by reading claims. A handle that always returns
the same six is barely a handle.

006 removed the batching cost, so this can move whenever.

## TASK

1. Give the remaining eleven a `subject`. The objectives take
   `{"kind": "device", "id": "nosepiece"}` at least; if a position identifies a
   lens well enough to be a subject in its own right, say so with an
   `identifiers` id rather than inventing a device id — **do not create a
   registry entry to make a subject resolve.** That inversion is what makes a
   registry meaningless.
2. Where an entry is genuinely about a quantity rather than a device, use
   `{"kind": "quantity", ...}` and accept that it is the unchecked kind. Say
   which ones those are in the report.
3. Commit as `seat:librarian`, then ask in one sentence: **what is not yet on
   disk?**

## CONTRACT

`contracts/schemas/kb_entry.schema.json`, and 005's ruling that an entry exists
so a card can cite it.

## CONSTRAINTS

**Still unverified, and still say so.** No check resolves a subject against its
registry. You checked the fifteen ids by hand before writing them, and a
hand-check is the guarantee that rots — which is why it is the thing being said
out loud rather than the thing being relied on. The check is queued behind an
§8 declaration that has not come; until it does, every subject added is useful
and unverified, and the next batch is more surface for the same unverified
claim. That is a reason to be careful with ids, not a reason to stop.

## REPORT

Three lines: the sha, which entries took `quantity` and why, and the
one-sentence clearing answer.
