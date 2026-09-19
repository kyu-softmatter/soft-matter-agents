# 009 — the part number is the one field nothing can find

status: closed · issued 2026-09-18 by manager-librarian · **reassigned 2026-09-19 to seat:librarian** · **closed 2026-09-19** (006677d)

> Issued for librarian-2, whose home was a worktree. Worktrees were reverted to
> one working copy on 2026-09-18 (`328176f`) and the person deleted them, so
> that seat has no session and no tree. The registry entry stays — deleting it
> would make a future commit under that identity an unknown committer — but the
> work comes back to the seat that is actually sitting. Two librarian seats in
> one working copy is the shape §6.2.1 lost three times; there is now one.

## GOAL

`Store.subjects()` builds the names an entry answers to from four handles:
`subject[].id`, the entry's own id, `symbol`, and `numbers[].name`. It does not
read `identifiers`. Measured at 25 entries on 2026-09-18:

```
kb_query(observable='MRD71670')   -> 0 hits
kb_query(observable='Kinetix 22') -> 0 hits
kb_query(observable='na')         -> 6 hits, every one subject device:nosepiece
```

So the string printed on the barrel, used as the title of the vendor sheet and
typed by an operator finds nothing, while the one query that does work returns
six objectives with NA 0.2 / 0.45 / 0.8 / 1.42 / 1.45 / 1.25 that no argument
can tell apart. The caller can still read `identifiers` off each returned row —
disambiguation on the way back already works. What is missing is **addressing on
the way in**.

This is the `na` collision you left open and declined to fix by inventing a
device id per lens. Declining was right: that would have been a registry entry
created so a subject would resolve. The handle each lens already has is
`identifiers.part_number`, and the ruling it was waiting on is now on disk.

## CONTRACT

`contracts/schemas/kb_entry.schema.json` gained `addressable_identifiers`
(manager-librarian, this commit). Read it there rather than from this file —
this is a message and messages go stale, which is the lesson you drew yourself
one hour ago.

Its shape: a closed `addressable` list, and the criterion that decides
membership — **does reconfiguring the instrument change this value?** A part
number survives a lens swap; a slot number is falsified by one, and nothing in
the store records that someone turned the nosepiece. The argument was already in
the KB: `nosepiece_objective_assignment` says position-to-lens is the one claim
on that device a single swap falsifies.

## TASK

1. `subjects()` gains a fifth handle: the **values** of `identifiers` whose key
   is in `addressable`. Read the list from the schema the way `PURPOSES` is read
   from `goal.schema.json` (line 361) — do not retype it into the server.
2. The default is **not-addressable**. A key absent from the list stays out, so
   `position_0` and `fitted_slot` remain unqueryable. Fail closed: a key
   invented next month must not silently become a query surface.
3. Case. `'Kinetix 22'` has a space and a capital; `'MRD71670'` is upper. Decide
   whether matching folds case, apply the same rule to all five handles or state
   why this one differs, and write the decision where the code is.
4. `kb_query`'s tool description says "entries for an observable and condition
   range". After this, `observable` also accepts a part number — as it already
   accepts a device id and an entry id, so the argument name was broader than
   its name before you touched it. Say what it accepts, in the description the
   caller actually reads. **008 is the reason this line is in the task.**

## CONSTRAINTS

- `mcp_server.py` is yours; `contracts/` is read-only from your seat. If the
  ruling is wrong or the list is missing a key, send it up — do not edit it.
- Determinism (§4.3.1): the sort is grade, then E3 rank, then `entry_id`. A new
  handle must not reorder anything. A query that returned N entries before must
  return those same N in the same order.
- Do not add a `part_number` argument to `kb_query`. The return shape would then
  depend on which argument was filled, which is the reason `kb_group` is a
  separate tool rather than a branch inside `kb_query`.
- Commit as `librarian@seat.invalid` in the shared working copy, naming paths.
  **Check 41 judges you, it does not report PENDING** — this seat is registered
  with `owns: ["librarian_agent"]`, so a commit that stays inside that directory
  is a PASS and one that leaves it is a FAIL you should act on. The line here
  said PENDING until 2026-09-19 and was wrong even for librarian-2, which was
  registered by `d247886` before this task was written: PENDING is what an
  *unregistered* committer gets. A seat that reads "my commits are PENDING
  anyway" stops reading the one signal that catches a real boundary crossing,
  which is worse than the stale fact itself.

## REPORT

The three probe queries above, re-run, with counts.

Then the thing that would actually catch a mistake here: **a value that makes
two entries answer to one name**, which is the defect `subject` was introduced to
remove and which this task widens the namespace for. I measured it before
issuing this rather than make you report a number I already had — at 25 entries,
22 values get added, **0** collide with an existing handle, and two are shared:
`'air'` by three objectives and `'oil'` by two. Those two are the class handles
the schema note predicted, so the ruling and the store agree today.

What I did not measure is the part you owe: **what the server does when one
arrives.** Nothing above is a guarantee — it is one reading of one store at one
version, and the next entry can break it. Say whether a collision should refuse,
return both, or be caught at index time, and make the store say which. A
property that holds by luck and is never checked is the kind of guarantee you
have twice now said rots.
