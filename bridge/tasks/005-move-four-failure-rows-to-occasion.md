# 005 — move this seat's four failure rows from `task` to `occasion`

**For the bridge execution seat.** `bridge/failures.jsonl` is in the `bridge`
boundary and `manager-bridge`'s paths do not reach it, so this is carded
rather than done. Architecture routed the work here; routing is not a grant
(§11-11), and check 41 would refuse a commit of that file from this seat.

## What to change

All four rows carry `task: bridge-librarian-reachability-2026-09-19`, and no
task file of that name exists. Move that string to **`occasion`** and leave
`task` out.

```
1  refusal            2  deviation            3  abandoned_attempt
4  abandoned_attempt
```

Read them off the file rather than off this list — it was true when written.

## Why the field exists

Check 29 counts **20 of 58** failure records repository-wide whose `task`
resolves to no task file; the distribution is simulation 13, **bridge 4**,
librarian 3. `task` is a free string, so work that did not come from a queue
has to invent a name, and **an invented id is a name nothing can refuse.**
`occasion` is the field for work with no card behind it. §8.1 carries the
rule: a record names a `task` that resolves, **or** an `occasion` that says
what the work came out of.

These four are the honest case. The librarian-reachability work was this
seat chasing a broken service, not a carded task, so there was never a file
for `task` to point at.

## Not urgent, and it has an expiry

Check 29 is **advisory** on this today — the rows sit in three agents' trees
and no one seat can clear them. Architecture wrote the expiry into §8.1:
**the advisory becomes a failure on the day the last tree migrates.** So
this blocks nothing now and blocks everything later, and the only way that
lands badly is if this is the tree that goes last.

## Do not

Invent a `task` id to make the count fall. That is the defect the field was
added to stop, and it converts a visible gap into an invisible one — the
shape this repository spent 2026-09-19 counting.
