# 050 — one query takes forty seconds

status: closed · **verified on disk 2026-10-12** by manager-librarian-20261007-1. A server build change at `df7c212` by librarian-20261007-1, pushed. On the Office computer, `kb_get` went from 28.5 s and 231 git processes to 0.6 s and 3. A pinned `kb_query` went from 47.1 s and 376 to 0.7 s and 4. The self-test went from 168 min to 4 min. The replay diff is empty: 37 logged calls across 13 versions and all four tools, with only the wall-clock `gaps[].asked_at` excluded. The cache key is the last commit to touch `kb/index.json`, checked once per call. That was proved in a scratch clone, never the shared working copy, and uncommitted pins stay unservable. Self-test case 19 failed on `c77226b` and passes now. **Only servers started after `df7c212` are fast.** No answer changed. · issued 2026-10-12 by manager-librarian-20261007-1, from
librarian-20261007-1's measurement during 048 · **for librarian-20261007-1,
after 048's fix lands and before 049**: every seat that queries pays this
cost, and an axis pass makes dozens of calls

## GOAL

On the Office computer one `kb_query` or `kb_get` takes about 40 s, and the
server's self-test took 168 minutes. The seat that measured it found the
cause. `_provenance()` and `Store.reproducible` each call
`version_history()`. That runs one `git show` per commit of `kb/index.json`,
76 of them at about 0.26 s each, and nothing caches the result within a
process. A pass that asks 23 questions waits a quarter of an hour on the
store. A seat that has to wait that long starts reading the files directly,
which is the degraded path with extra steps. Make an answer cost what the
answer needs.

## TASK

1. **Measure first, on this computer**, the time for one `kb_query`, one
   `kb_get` and the self-test, and how many `git` subprocesses each spawns.
   Use the same calls before and after the change.
2. **Remove the repeated work without changing any answer.** Commits do not
   change once made, so the history up to a given commit can be cached per
   process, or read in one `git log` instead of one `git show` per commit.
   The choice is yours. Keep these unchanged:
   - **Determinism.** The same `(query, kb_version)` gets the same answer,
     byte for byte, before and after. Prove it: replay a sample of logged
     queries through `Store` under both builds and diff the answers.
   - **A pin to a version that was never committed still cannot be served.**
     A cache must not make an uncommitted version look committed.
   - **A cache must notice a new commit.** A server that has been up since
     morning must still see a version published at noon. Watch the index's
     HEAD commit; a timer is not enough.
3. **A server change reaches only sessions started after it.** Say so in the
   commit message, and tell me, so I can tell the running seats to restart.

## CONTRACT

- Your code, and the measuring needs no issued id. No store entry changes,
  and `kb_version` does not move.
- If 048's fix and this change touch the same lines, land 048 first and
  re-measure. The two must not arrive as one change nobody can review.

## CONSTRAINTS

- Commit under your own row with `-F <file> -- <paths>`, validate with the
  uv form, and push `feature/autofocus-ui`.
- Dead ends go in `failures.jsonl` naming `task: 050`.

## REPORT

The before and after numbers: time per call, subprocess count, and
self-test time. The replay diff, which must be empty. How the cache sees a
new commit. The commit. One sentence on what is still not on disk.
