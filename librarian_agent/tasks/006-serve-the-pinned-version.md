# 006 — serve an old `kb_version` instead of refusing it

status: closed · issued 2026-09-18 by manager-librarian · **closed 2026-09-19** (closing commit not recorded here)

## GOAL

Your proposal, and it is right. The server refuses a pin it no longer matches,
so every version move stops whatever fan-out is in flight; we hold that back
with discipline, and **discipline does not scale.** Once fan-outs are routine
the store is frozen by politeness.

§4.3.1 asks that the same `(query, kb_version)` always give the same answer.
**Serving that version is what satisfies it. Refusing is not** — it neither
gives the same answer nor any answer, and it makes a guarantee about
reproducibility behave as a lock on the store.

## TASK

1. Resolve a pinned `kb_version` to the commit whose `kb/index.json` carries it
   and read the entries from there. Check 25 already says old-version
   verification is the repository's git history's job; this is the server
   agreeing with it.
2. Keep refusing **unresolvable** pins, with a message that says which kind:
   not-in-history is different from malformed.
3. Answer from the pinned version, not from HEAD, and say in the response which
   version answered.
4. `--self-test` a real case: pin, move the store, query the old pin, get the
   old answer.
5. Commit as `seat:librarian`, then ask in one sentence: **what is not yet on
   disk?**

## CONTRACT

`plan.md` §4.3.1 (determinism, and pinning for the whole fan-out), check 25.

## CONSTRAINTS

**A version that was never committed is not servable, and that is a feature.**
`kb_version` hashes the working tree's entries, so a store edited and not
committed produces a version that exists nowhere else — nothing can reproduce a
question answered from it. Refuse it as unresolvable rather than falling back
to HEAD, which would answer a different question under the pinned name.

This does **not** retire the pin-for-the-whole-fan-out rule (§4.3.1). Siblings
must still see one store, or the difference between them is a channel. What it
retires is the collateral: a move no longer breaks a fan-out that pinned
correctly.

Sequence it after the 13 subjects, or the self-test moves the store while
`mic-20260918-001` is still open.

## REPORT

Three lines: the sha, whether the self-test round-trips an old pin, and the
one-sentence clearing answer.
